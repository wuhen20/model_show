from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from app.core.database import query_code_dict, query_sample_set, query_sample_info, save_sample_set, sample_statistic, sample_trend, query_audio_text, update_sample_score, insert_sample_info, update_label_think, generate_task_no, generate_sample_set_no, generate_sample_no, query_data_collect_task, save_data_collect_task, save_data_collect_task_det, query_data_collect_task_det, update_data_collect_task_det, get_task_det_raw, update_task_status, insert_collect_log, append_collect_log, finish_collect_log, query_collect_log, query_all_scheduled_tasks, get_task_execute_type, update_task_execute_type, delete_data_collect_task, execute_source_sql, save_query_result_to_desktop, query_target_table_columns, query_col_map, save_col_map, write_to_target_table, query_original_sample_set_by_type
import os
import io
import json
import logging
import zipfile
import traceback

logger = logging.getLogger("app.sample")

router = APIRouter()


@router.get("/code-dict")
def get_code_dict(sortNo: list[str] = Query(default=["SAMPLE_TYPE", "QUALITY_LEVEL", "SAMPLE_FIELD"])):
    rows = query_code_dict(sortNo)
    result: dict[str, list[dict]] = {}
    for row in rows:
        sort_no = row["SORT_NO"]
        if sort_no not in result:
            result[sort_no] = []
        result[sort_no].append({
            "codeValue": row["CODE_VALUE"],
            "codeName": row["CODE_NAME"],
        })
    return {"code": 0, "data": result}


@router.get("/query-sample-set")
def query_sample_set_api():
    try:
        rows = query_sample_set()
        # 将数据库字段名转为驼峰命名返回前端
        data = []
        for row in rows:
            item = {}
            for k, v in row.items():
                # 下划线转驼峰
                parts = k.split("_")
                camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
                # datetime 类型转字符串
                if hasattr(v, "isoformat"):
                    v = v.isoformat()
                item[camel] = v
            data.append(item)
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/sample-statistic")
def sample_statistic_api():
    """样本中心统计数据"""
    try:
        data = sample_statistic()
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"统计失败: {str(e)}"}


@router.get("/sample-trend")
def sample_trend_api():
    """样本增长趋势（近5个月）"""
    try:
        rows = sample_trend()
        months = [row["month"] for row in rows]
        counts = [row["count"] for row in rows]
        return {"code": 0, "data": {"months": months, "counts": counts}}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"获取趋势数据失败: {str(e)}"}


@router.get("/get-samples")
def get_samples_api(setNo: str = Query(..., description="样本集编号")):
    try:
        rows = query_sample_info(setNo)
        data = []
        for row in rows:
            item = {}
            for k, v in row.items():
                parts = k.split("_")
                camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
                if hasattr(v, "isoformat"):
                    v = v.isoformat()
                item[camel] = v
            data.append(item)
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


class SaveSampleSetRequest(BaseModel):
    setName: str
    description: str = ""
    businessSystem: str = ""
    sampleTypeCode: str
    sampleTypeName: str
    sampleFieldCode: str = ""
    sampleFieldName: str = ""


class UpdateSampleScoreRequest(BaseModel):
    sampleNo: str
    sampleName: str
    scoreCode: str  # 01-优质/02-良好/03-一般/04-较差


@router.post("/save-sample-set")
def save_sample_set_api(req: SaveSampleSetRequest):
    try:
        set_no = generate_sample_set_no()
        # 只保留 SQL 需要的字段，避免 Oracle 报错多余的参数
        data = {
            'setCode': set_no,
            'setName': req.setName,
            'description': req.description,
            'businessSystem': req.businessSystem,
            'sampleTypeCode': req.sampleTypeCode,
            'sampleFieldCode': req.sampleFieldCode,
        }
        rowcount = save_sample_set(data)
        return {"code": 0, "message": "保存成功", "data": {"rowcount": rowcount, "setNo": set_no}}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"保存失败: {str(e)}"}


@router.post("/update-sample-score")
def update_sample_score_api(req: UpdateSampleScoreRequest):
    """更新样本质量评分"""
    valid_codes = {'01', '02', '03', '04'}
    if req.scoreCode not in valid_codes:
        return {"code": 1, "message": "评分编码无效，应为01-优质/02-良好/03-一般/04-较差"}
    try:
        rowcount = update_sample_score(req.sampleNo, req.sampleName, req.scoreCode)
        if rowcount == 0:
            return {"code": 1, "message": "未找到对应样本"}
        return {"code": 0, "message": "评分成功"}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"评分失败: {str(e)}"}


@router.get("/serve-image")
def serve_image(filePath: str = Query(..., description="图片文件路径")):
    """读取并返回图片文件"""
    filePath = os.path.normpath(filePath)
    if not os.path.isfile(filePath):
        return {"code": 1, "message": f"图片文件不存在: {filePath}"}
    # 根据 extension 推断 content_type
    ext = os.path.splitext(filePath)[1].lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".aac": "audio/aac",
        ".wma": "audio/x-ms-wma",
        ".m4a": "audio/mp4",
    }
    media_type = content_types.get(ext, "application/octet-stream")
    return FileResponse(filePath, media_type=media_type)


@router.get("/get-annotations")
def get_annotations(filePath: str = Query(..., description="图片文件路径")):
    """获取 YOLO 标注信息：读取同目录下 class.txt 和同名 .txt 标注文件"""
    # 统一路径格式：将 / 转为 \，去除多余分隔符，确保 os.path 操作正确
    filePath = os.path.normpath(filePath)

    dir_path = os.path.dirname(filePath)
    base_name = os.path.splitext(os.path.basename(filePath))[0]
    ext = os.path.splitext(filePath)[1].lower()

    # 仅对图片类型检查标注
    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
    if ext not in image_exts:
        return {"code": 0, "data": {"hasAnnotations": False}}

    class_file = os.path.normpath(os.path.join(dir_path, "classes.txt"))
    label_file = os.path.normpath(os.path.join(dir_path, base_name + ".txt"))

    if not os.path.isfile(class_file) or not os.path.isfile(label_file):
        return {"code": 0, "data": {"hasAnnotations": False}}

    # 读取 classes.txt
    try:
        with open(class_file, "r", encoding="utf-8") as f:
            class_names = [line.strip() for line in f.readlines() if line.strip()]
    except Exception:
        class_names = []

    # 读取标注文件，每行格式: class_id center_x center_y width height
    boxes = []
    try:
        with open(label_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    class_id = int(parts[0])
                    cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    boxes.append({
                        "classId": class_id,
                        "className": class_names[class_id] if class_id < len(class_names) else str(class_id),
                        "cx": cx,
                        "cy": cy,
                        "w": w,
                        "h": h,
                    })
    except Exception:
        pass

    return {
        "code": 0,
        "data": {
            "hasAnnotations": len(boxes) > 0,
            "classNames": class_names,
            "boxes": boxes,
        },
    }


@router.get("/get-audio-text")
def get_audio_text(sampleNo: str = Query(..., description="样本编号"), sampleName: str = Query(..., description="样本名称")):
    """查询语音样本的转写文字"""
    try:
        audio_text = query_audio_text(sampleNo, sampleName)
        return {"code": 0, "data": {"audioText": audio_text}}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询转写文字失败: {str(e)}"}


@router.get("/download-sample-set")
def download_sample_set(setNo: str = Query(..., description="样本集编号"), fileName: str = Query(..., description="下载文件名")):
    """下载样本集：查询样本集下所有样本文件，打成 zip 压缩包返回"""
    from urllib.parse import quote

    try:
        samples = query_sample_info(setNo)
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询样本失败: {str(e)}"}

    if not samples:
        return {"code": 1, "message": "该样本集下无样本数据"}

    mem_zip = io.BytesIO()
    added_names = set()
    with zipfile.ZipFile(mem_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for row in samples:
            file_path = row.get("file_path") or row.get("filePath")
            if not file_path:
                continue
            file_path = os.path.normpath(file_path)
            if not os.path.isfile(file_path):
                continue

            # zip 内使用原始文件名，避免同名覆盖
            arc_name = os.path.basename(file_path)
            if arc_name in added_names:
                base, ext = os.path.splitext(arc_name)
                idx = 1
                while f"{base}_{idx}{ext}" in added_names:
                    idx += 1
                arc_name = f"{base}_{idx}{ext}"
            added_names.add(arc_name)
            zf.write(file_path, arc_name)

            # 图片类型：附带同目录的 YOLO 标注文件
            dir_path = os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            ext = os.path.splitext(file_path)[1].lower()
            image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
            if ext in image_exts:
                label_file = os.path.join(dir_path, base_name + ".txt")
                if os.path.isfile(label_file):
                    lbl_name = os.path.basename(label_file)
                    if lbl_name not in added_names:
                        added_names.add(lbl_name)
                        zf.write(label_file, lbl_name)
                classes_file = os.path.join(dir_path, "classes.txt")
                if not os.path.isfile(classes_file):
                    classes_file = os.path.join(dir_path, "class.txt")
                if os.path.isfile(classes_file):
                    cls_name = os.path.basename(classes_file)
                    if cls_name not in added_names:
                        added_names.add(cls_name)
                        zf.write(classes_file, cls_name)

    mem_zip.seek(0)
    # Content-Disposition 中文文件名需 URL 编码
    safe_name = (fileName + ".zip").replace(" ", "_")
    encoded_name = quote(safe_name)
    return StreamingResponse(
        mem_zip,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"}
    )


@router.get("/export-sample-set-json")
def export_sample_set_json(setNo: str = Query(..., description="样本集编号"),
                           fileName: str = Query(..., description="下载文件名")):
    """导出样本集为 ShareGPT 格式 JSON：参考 YOLO转sharegpt.py 脚本逻辑
    将图片 + 同名 YOLO 标注 txt 转换为 conversations + images 结构
    """
    from urllib.parse import quote
    from PIL import Image

    HUMAN_QUESTION = ("<image>\n请识别图片内装表接电的错接线类型，并标出位置，"
                      "其中错接线类型有如下几种'一孔多线','端子接线缺失', "
                      "'单相导线颜色不规范', '零线并接','零线串接','三相导线颜色不规范', "
                      "'电能表接线杂乱', '单相电能表零火反接', '三相电能表零火反接'")
    IMAGE_SUFFIXES = ('.jpg', '.jpeg', '.png', '.gif', '.bmp',
                      '.tiff', '.tif', '.webp', '.svg', '.ico',
                      '.raw', '.cr2', '.nef', '.arw', '.dng')

    def load_class_map(dir_path):
        """从 classes.txt / class.txt 读取 YOLO 类别映射 {id: name}"""
        class_map = {}
        for cls_name in ("classes.txt", "class.txt"):
            cls_file = os.path.join(dir_path, cls_name)
            if os.path.isfile(cls_file):
                with open(cls_file, "r", encoding="utf-8") as f:
                    for idx, line in enumerate(f):
                        name = line.strip()
                        if name:
                            class_map[idx] = name
                break
        return class_map

    def yolo_to_qwen3vl(yolo_line, img_w, img_h, class_map):
        try:
            parts = yolo_line.strip().split()
            cls_id = int(parts[0])
            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            x_center = cx * img_w
            y_center = cy * img_h
            box_w = w * img_w
            box_h = h * img_h
            x1 = x_center - box_w / 2
            y1 = y_center - box_h / 2
            x2 = x_center + box_w / 2
            y2 = y_center + box_h / 2
            q_x1 = max(0, min(1000, int(round(x1 / img_w * 1000))))
            q_y1 = max(0, min(1000, int(round(y1 / img_h * 1000))))
            q_x2 = max(0, min(1000, int(round(x2 / img_w * 1000))))
            q_y2 = max(0, min(1000, int(round(y2 / img_h * 1000))))
            label = class_map.get(cls_id, f"未知类别_{cls_id}")
            return {"bbox_2d": [q_x1, q_y1, q_x2, q_y2], "label": label}
        except Exception as e:
            logger.warning(f"解析YOLO标注失败: {yolo_line}, 错误: {e}")
            return None

    try:
        samples = query_sample_info(setNo)
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询样本失败: {str(e)}"}

    if not samples:
        return {"code": 1, "message": "该样本集下无样本数据"}

    sharegpt_data = []
    skip_no_txt = 0
    skip_empty_anno = 0
    skip_bad_img = 0
    processed = 0

    # 按 samples 顺序处理，每条样本对应一张图片 + 同名 txt 标注
    for row in samples:
        file_path = row.get("file_path") or row.get("filePath")
        if not file_path:
            continue
        file_path = os.path.normpath(file_path)
        if not os.path.isfile(file_path):
            continue

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in IMAGE_SUFFIXES:
            continue

        img_filename = os.path.basename(file_path)
        dir_path = os.path.dirname(file_path)
        base_name = os.path.splitext(img_filename)[0]
        txt_path = os.path.join(dir_path, base_name + ".txt")

        # 1. 无标注文件跳过
        if not os.path.isfile(txt_path):
            skip_no_txt += 1
            continue

        # 2. 读取图片尺寸
        try:
            with Image.open(file_path) as img:
                img_w, img_h = img.width, img.height
        except Exception as e:
            logger.warning(f"读取图片尺寸失败: {img_filename}, 错误: {e}")
            skip_bad_img += 1
            continue

        # 3. 加载类别映射
        class_map = load_class_map(dir_path)

        # 4. 解析 YOLO 标注
        annotations = []
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                bbox_info = yolo_to_qwen3vl(line, img_w, img_h, class_map)
                if bbox_info:
                    annotations.append(bbox_info)

        if not annotations:
            skip_empty_anno += 1
            continue

        gpt_value = json.dumps(annotations, ensure_ascii=False)
        sharegpt_item = {
            "conversations": [
                {"from": "human", "value": HUMAN_QUESTION},
                {"from": "gpt", "value": gpt_value}
            ],
            "images": file_path
        }
        sharegpt_data.append(sharegpt_item)
        processed += 1

    logger.info(f"JSON导出统计: 正常处理 {processed} 张，无标注跳过 {skip_no_txt} 张，"
                f"标注为空 {skip_empty_anno} 张，图片读取失败 {skip_bad_img} 张")

    json_content = json.dumps(sharegpt_data, ensure_ascii=False, indent=2)
    safe_name = (fileName + ".json").replace(" ", "_")
    encoded_name = quote(safe_name)
    return StreamingResponse(
        io.BytesIO(json_content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"}
    )


@router.post("/upload-samples")
async def upload_samples(
    setNo: str = Form(..., description="样本集编号"),
    setName: str = Form(..., description="样本集名称"),
    typeCode: str = Form(..., description="样本类型编码"),
    files: list[UploadFile] = File(..., description="上传的文件列表"),
):
    """上传样本文件：保存到 sample_upload_dir/setName/ 目录，并写入 s_sample_info 表"""
    from app.core.config import settings

    # 目标目录：配置路径 / 样本集名称
    target_dir = os.path.join(settings.sample_upload_dir, setName)
    os.makedirs(target_dir, exist_ok=True)

    success_count = 0
    errors = []

    for file in files:
        if not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        # 保存文件
        file_path = os.path.join(target_dir, file.filename)
        try:
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            # 图片类型的 .txt 标注文件只保存，不写样本信息表
            if typeCode == '05' and ext == '.txt':
                continue
            # 写入数据库
            insert_sample_info(
                set_no=setNo,
                sample_name=file.filename,
                suffix=ext,
                type_code=typeCode,
                file_path=file_path,
                file_size=len(content),
            )
            success_count += 1
        except Exception as e:
            errors.append(f"{file.filename}: 保存失败 - {str(e)}")

    msg = f"成功上传 {success_count} 个文件"
    if errors:
        msg += f"，失败 {len(errors)} 个: {'; '.join(errors[:5])}"
    return {"code": 0, "message": msg}


@router.post("/upload-samples-batch")
async def upload_samples_batch(
    setNo: str = Form(...),
    setName: str = Form(...),
    typeCode: str = Form(...),
    file: UploadFile = File(...),
):
    """批量导入：上传单个 ZIP，解压图片到 sample_upload_dir/setName/，写入 s_sample_info"""
    from app.core.config import settings
    from app.services.sample_import_service import extract_zip_and_import

    if typeCode != "05":
        return {"code": 1, "message": "批量导入仅支持图片类型（05）样本集"}

    content = await file.read()
    if not zipfile.is_zipfile(io.BytesIO(content)):
        return {"code": 1, "message": "上传文件不是有效的 ZIP 文件"}

    target_dir = os.path.join(settings.sample_upload_dir, setName)
    try:
        result = extract_zip_and_import(
            zip_bytes=content,
            target_dir=target_dir,
            set_no=setNo,
            type_code=typeCode,
            insert_callback=insert_sample_info,
        )
        msg = (f"成功导入 {result['image_count']} 张图片，"
               f"保存 {result['txt_count']} 个标注文件，"
               f"跳过 {result['skipped_count']} 个文件")
        if result["errors"]:
            msg += f"，失败 {len(result['errors'])} 个: {'; '.join(result['errors'][:5])}"
        return {"code": 0, "message": msg}
    except Exception as e:
        logger.exception("批量导入异常")
        return {"code": 1, "message": f"批量导入失败: {str(e)}"}


@router.post("/update-label-think")
async def update_label_think_api(payload: dict):
    """保存样本思维链"""
    sample_no = payload.get("sampleNo", "")
    sample_name = payload.get("sampleName", "")
    label_think = payload.get("labelThink", "")
    if not sample_no or not sample_name:
        return {"code": 1, "message": "sampleNo 和 sampleName 不能为空"}
    try:
        update_label_think(sample_no, sample_name, label_think)
        return {"code": 0, "message": "保存成功"}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"保存失败: {str(e)}"}


@router.get("/query-collect-task")
def query_collect_task_api():
    """查询数据采集任务列表"""
    try:
        rows = query_data_collect_task()
        data = []
        for row in rows:
            item = {}
            for k, v in row.items():
                parts = k.split("_")
                camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
                if hasattr(v, "isoformat"):
                    v = v.isoformat()
                item[camel] = v
            data.append(item)
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.post("/save-collect-task")
def save_collect_task_api(payload: dict):
    """新增数据采集任务，任务编号自动生成"""
    task_name = payload.get("taskName", "").strip()
    remark = payload.get("remark", "").strip()
    execute_type = payload.get("executeType", "01").strip() or "01"
    cron_formula = payload.get("cronFormula", "").strip()
    sample_type = payload.get("sampleType", "").strip()
    sample_set_no = payload.get("sampleSetNo", "").strip()

    if not task_name:
        return {"code": 1, "message": "任务名称不能为空"}
    if not sample_type:
        return {"code": 1, "message": "数据类型不能为空"}
    if not sample_set_no:
        return {"code": 1, "message": "原始样本集不能为空"}
    if execute_type not in ("01", "02"):
        return {"code": 1, "message": "执行方式无效，应为 01-手动 或 02-定时"}
    if execute_type == "02" and not cron_formula:
        return {"code": 1, "message": "执行方式为定时时，cron 表达式不能为空"}

    try:
        task_no = generate_task_no()
        save_data_collect_task(task_no, task_name, remark, execute_type, cron_formula, sample_type, sample_set_no)

        # 定时任务：保存成功后注册到调度器
        if execute_type == "02":
            from app.services.scheduler_service import add_scheduled_task
            add_scheduled_task(task_no, cron_formula)

        return {"code": 0, "message": "保存成功", "data": {"taskNo": task_no}}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"保存失败: {str(e)}"}


@router.get("/query-sample-set-by-type")
def query_sample_set_by_type_api(sampleType: str = Query(..., description="样本类型编码")):
    """按样本类型查询原始样本集（用于数据采集任务关联选择）"""
    try:
        rows = query_original_sample_set_by_type(sampleType)
        data = [
            {
                "setNo": row["set_no"],
                "setName": row["set_name"],
                "setDescription": row.get("set_description") or "",
                "businessSystem": row.get("business_system") or "",
            }
            for row in rows
        ]
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/query-collect-task-det")
def query_collect_task_det_api(taskNo: str = Query(..., description="任务编号")):
    """查询数据采集任务明细"""
    try:
        row = query_data_collect_task_det(taskNo)
        if not row:
            return {"code": 0, "data": None}
        item = {}
        for k, v in row.items():
            parts = k.split("_")
            camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            # blob 类型转字符串
            if k == "collect_sql" and v is not None:
                if isinstance(v, bytes):
                    v = v.decode("utf-8")
            item[camel] = v
        return {"code": 0, "data": item}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.post("/test-db-connection")
def test_db_connection_api(payload: dict):
    """测试数据库连接"""
    db_type_code = payload.get("dbType", "").strip()
    host = payload.get("host", "").strip()
    port = payload.get("port", "").strip()
    user = payload.get("user", "").strip()
    pwd = payload.get("pwd", "").strip()
    database = payload.get("database", "").strip()
    auth = payload.get("auth", "").strip() or "NONE"

    if not db_type_code or not host or not user:
        return {"code": 1, "message": "数据库类型、地址、用户名不能为空"}

    # 编码值转换为数据库类型名称
    db_type_map = {"01": "MYSQL", "02": "ORACLE", "03": "HIVE"}
    db_type = db_type_map.get(db_type_code)
    if not db_type:
        return {"code": 1, "message": f"不支持的数据库类型编码: {db_type_code}"}

    try:
        # 尝试连接数据库，执行简单查询验证连接
        from app.core.database import get_connection_by_config
        conn = get_connection_by_config(
            db_type=db_type,
            host=host,
            port=port,
            user=user,
            pwd=pwd,
            database=database,
            auth=auth,
        )
        # 连接成功，关闭连接
        conn.close()
        return {"code": 0, "message": "连接成功"}
    except Exception as e:
        logger.exception("数据库连接测试失败")
        return {"code": 1, "message": f"连接失败: {str(e)}"}


@router.post("/save-collect-task-det")
def save_collect_task_det_api(payload: dict):
    """保存数据采集任务明细（新增或更新）"""
    task_no = payload.get("taskNo", "").strip()
    source_db_type = payload.get("sourceDbType", "").strip()
    source_db_host = payload.get("sourceDbHost", "").strip()
    source_db_port = payload.get("sourceDbPort", "").strip()
    source_db_usr = payload.get("sourceDbUsr", "").strip()
    source_db_pwd = payload.get("sourceDbPwd", "").strip()
    source_db_name = payload.get("sourceDbName", "").strip()
    target_table = payload.get("targetTable", "").strip()
    collect_sql = payload.get("collectSql", "").strip()
    source_db_auth = payload.get("sourceDbAuth", "").strip()
    # 图像类型采集相关字段（可选，时序任务不传）
    file_get_mode = payload.get("fileGetMode", "").strip()
    bucket_name = payload.get("bucketName", "").strip()
    file_id = payload.get("fileId", "").strip()
    file_name = payload.get("fileName", "").strip()

    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}
    if not source_db_type or not source_db_host or not source_db_usr or not collect_sql:
        return {"code": 1, "message": "数据库类型、地址、用户名、SQL不能为空"}

    data = {
        "taskNo": task_no,
        "sourceDbType": source_db_type,
        "sourceDbHost": source_db_host,
        "sourceDbPort": source_db_port,
        "sourceDbUsr": source_db_usr,
        "sourceDbPwd": source_db_pwd,
        "sourceDbName": source_db_name,
        "targetTable": target_table,
        "collectSql": collect_sql,
        "sourceDbAuth": source_db_auth,
        "fileGetMode": file_get_mode or None,
        "bucketName": bucket_name or None,
        "fileId": file_id or None,
        "fileName": file_name or None,
    }

    try:
        # 查询是否已有明细
        existing = query_data_collect_task_det(task_no)
        if existing:
            # 已有明细，执行更新
            update_data_collect_task_det(data)
            return {"code": 0, "message": "更新成功"}
        else:
            # 无明细，执行新增
            save_data_collect_task_det(data)
            return {"code": 0, "message": "保存成功"}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"保存失败: {str(e)}"}


class ExecuteCollectTaskRequest(BaseModel):
    taskNo: str


def execute_collect_task_internal(task_no: str, trigger_source: str = "manual") -> dict:
    """执行数据采集任务的核心逻辑。

    - 时序类型：连接源数据库执行SQL，通过字段映射写入目标表
    - 图像类型：连接源数据库执行SQL，根据图像获取配置下载图片文件并登记到 s_original_sample_info

    可被 HTTP 接口和定时调度器共同调用。
    trigger_source: manual-手动触发，scheduler-定时调度触发（仅用于日志标识）
    """
    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}

    # 查询任务明细
    det = get_task_det_raw(task_no)
    if not det:
        return {"code": 1, "message": "未找到任务明细，请先配置采集信息"}

    collect_sql = det.get("collect_sql")
    if not collect_sql:
        return {"code": 1, "message": "采集SQL不能为空"}

    sample_type = det.get("sample_type") or ""

    # 图像类型采集：走图像采集流程
    if sample_type == "05":
        return _execute_image_collect_task(task_no, det, trigger_source)

    # 时序类型采集：走原有的字段映射写入目标表流程
    target_table = det.get("target_table")
    if not target_table:
        return {"code": 1, "message": "目标表未配置，请先配置目标表"}

    # 查询字段映射配置
    col_map = query_col_map(task_no)
    if not col_map:
        return {"code": 1, "message": "字段映射配置为空，请先配置字段映射"}

    # 查询任务名称
    task_name = ""
    try:
        from app.core.database import get_connection
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT task_name FROM s_data_collect_task WHERE task_no = %s", (task_no,))
            row = cursor.fetchone()
            if row:
                task_name = row["task_name"]
        conn.close()
    except Exception:
        pass

    # 更新任务状态为执行中
    update_task_status(task_no, "02")
    # 写入执行日志，初始内容：数据采集任务：XXXX开始执行（触发方式）
    trigger_label = "定时调度" if trigger_source == "scheduler" else "手动"
    init_log = f"数据采集任务：{task_name or task_no}开始执行（{trigger_label}触发）"
    log_id = insert_collect_log(task_no, init_log)

    try:
        # 追加日志：开始连接源数据库
        append_collect_log(log_id, "开始连接源数据库")

        # 连接源数据库执行SQL
        columns, rows = execute_source_sql(
            db_type=det["source_db_type"],
            host=det["source_db_host"],
            port=str(det.get("source_db_port") or ""),
            user=det["source_db_usr"],
            pwd=det.get("source_db_pwd") or "",
            database=det.get("source_db_name") or "",
            sql=collect_sql,
            auth=det.get("source_db_auth") or "",
        )

        # 追加日志：数据获取成功
        append_collect_log(log_id, f"数据获取成功，数据量:{len(rows)}")

        # 追加日志：开始写入目标表
        append_collect_log(log_id, f"开始写入目标表：{target_table}")

        # 根据字段映射将数据写入目标表
        write_count = write_to_target_table(target_table, col_map, columns, rows)

        # 追加日志：写入完成
        append_collect_log(log_id, f"数据写入完成，写入数据量:{write_count}")

        # 更新日志：成功
        finish_collect_log(log_id, success=True, log_content="任务执行完成")
        # 更新任务状态：已完成，last_execute_flag=1（成功）
        update_task_status(task_no, "03", last_execute_flag=1)

        return {
            "code": 0,
            "message": f"执行成功，共获取 {len(rows)} 条数据，写入目标表 {target_table} 共 {write_count} 条",
            "data": {"targetTable": target_table, "rowCount": len(rows), "writeCount": write_count},
        }
    except Exception as e:
        fail_info = str(e)
        # 先更新任务状态为失败，确保状态一定更新（即使日志写入失败也不会卡在执行中）
        try:
            update_task_status(task_no, "03", last_execute_flag=2)
        except Exception:
            pass
        # 再写日志（独立 try，避免日志写入失败影响状态）
        try:
            finish_collect_log(log_id, success=False, log_content=f"执行出错:{fail_info}")
        except Exception:
            pass
        return {"code": 1, "message": f"执行失败: {fail_info}"}


def _format_file_size(size_bytes: int) -> str:
    """格式化文件大小带单位"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f}MB"


def _execute_image_collect_task(task_no: str, det: dict, trigger_source: str = "manual") -> dict:
    """执行图像类型数据采集任务

    流程：连接源数据库执行SQL → 根据获取方式下载图像文件 → 登记到 s_original_sample_info
    """
    # 从任务明细获取图像配置
    file_get_mode = det.get("file_get_mode") or ""
    file_id_field = det.get("file_id") or ""  # 图像获取字段名
    file_name_field = det.get("file_name") or ""  # 图像名称字段名
    bucket_name = det.get("bucket_name") or ""
    # 关联的原始样本集编号
    sample_set_no = det.get("original_sample_set_no") or ""

    if not file_get_mode:
        return {"code": 1, "message": "图像获取方式未配置，请先配置图像获取配置"}
    if not file_id_field:
        return {"code": 1, "message": "图像获取字段未配置，请先配置图像获取配置"}
    if file_get_mode == "02" and not bucket_name:
        return {"code": 1, "message": "ceph 模式下桶名称不能为空"}

    # 查询任务名称
    task_name = ""
    try:
        from app.core.database import get_connection
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT task_name FROM s_data_collect_task WHERE task_no = %s", (task_no,))
            row = cursor.fetchone()
            if row:
                task_name = row["task_name"]
        conn.close()
    except Exception:
        pass

    # 更新任务状态为执行中
    update_task_status(task_no, "02")
    trigger_label = "定时调度" if trigger_source == "scheduler" else "手动"
    init_log = f"图像采集任务：{task_name or task_no}开始执行（{trigger_label}触发）"
    log_id = insert_collect_log(task_no, init_log)

    try:
        append_collect_log(log_id, "开始连接源数据库执行SQL")

        # 连接源数据库执行SQL
        columns, rows = execute_source_sql(
            db_type=det["source_db_type"],
            host=det["source_db_host"],
            port=str(det.get("source_db_port") or ""),
            user=det["source_db_usr"],
            pwd=det.get("source_db_pwd") or "",
            database=det.get("source_db_name") or "",
            sql=det.get("collect_sql"),
            auth=det.get("source_db_auth") or "",
        )

        append_collect_log(log_id, f"SQL执行成功，共获取 {len(rows)} 条数据")

        # 构建列名小写映射，用于大小写不敏感匹配
        columns_lower_map = {col.lower(): i for i, col in enumerate(columns)}
        file_id_idx = columns_lower_map.get(file_id_field.lower())
        if file_id_idx is None:
            raise ValueError(f"SQL结果中未找到图像获取字段：{file_id_field}，查询出的列：{columns}")

        file_name_idx = None
        if file_name_field:
            file_name_idx = columns_lower_map.get(file_name_field.lower())
            if file_name_idx is None:
                raise ValueError(f"SQL结果中未找到图像名称字段：{file_name_field}，查询出的列：{columns}")

        # 准备保存目录：优先使用关联原始样本集的 set_path 根目录
        from app.core.config import settings
        set_path = det.get("set_path") or ""
        if set_path:
            save_dir = set_path
        else:
            # 兜底：旧数据无 set_path 时回退原逻辑，并记日志告警
            save_dir = os.path.join(settings.sample_upload_dir, "data_collect", task_no)
            append_collect_log(log_id, f"警告：原始样本集未配置 set_path，回退到 {save_dir}")
        os.makedirs(save_dir, exist_ok=True)

        append_collect_log(log_id, f"文件保存目录：{save_dir}")
        mode_names = {"01": "存储路径", "02": "ceph", "03": "oss"}
        append_collect_log(log_id, f"图像获取方式：{mode_names.get(file_get_mode, file_get_mode)}")

        # 遍历每行数据，获取图像文件
        success_count = 0
        fail_count = 0
        used_filenames = set()  # 用于文件名冲突检测

        from app.core.database import generate_sample_no, insert_original_sample_info_for_collect

        for i, row in enumerate(rows):
            try:
                file_id_value = row[file_id_idx] if file_id_idx < len(row) else None
                if not file_id_value:
                    append_collect_log(log_id, f"第 {i + 1} 行：图像获取字段值为空，跳过")
                    fail_count += 1
                    continue

                file_id_value = str(file_id_value)

                # 文件保存名：直接使用对象 key 的 basename
                disk_filename = os.path.basename(file_id_value)

                # 如果文件名无后缀，尝试从 Ceph 元数据补充
                base_name, ext = os.path.splitext(disk_filename)
                if not ext and file_get_mode == "02":
                    from app.services.ceph_service import get_ceph_object_ext
                    ceph_ext = get_ceph_object_ext(bucket_name, file_id_value)
                    if ceph_ext:
                        disk_filename = disk_filename + ceph_ext
                        base_name, ext = os.path.splitext(disk_filename)

                # 处理文件名冲突：自动加序号
                final_disk_name = disk_filename
                seq = 1
                while final_disk_name in used_filenames:
                    final_disk_name = f"{base_name}_{seq}{ext}"
                    seq += 1
                used_filenames.add(final_disk_name)

                local_path = os.path.join(save_dir, final_disk_name)

                # 获取展示用名称（file_name 字段值，仅用于数据库记录和前端展示）
                display_name = ""
                if file_name_idx is not None and file_name_idx < len(row) and row[file_name_idx]:
                    display_name = str(row[file_name_idx])

                # 根据获取方式下载文件
                if file_get_mode == "01":
                    # 存储路径：file_id_value 就是文件路径
                    src_path = file_id_value
                    if not os.path.exists(src_path):
                        append_collect_log(log_id, f"第 {i + 1} 行：源文件不存在：{src_path}，跳过")
                        fail_count += 1
                        continue
                    import shutil
                    shutil.copy2(src_path, local_path)
                    file_size_bytes = os.path.getsize(local_path)
                elif file_get_mode == "02":
                    # ceph：file_id_value 是对象 key
                    from app.services.ceph_service import download_from_ceph
                    file_size_bytes = download_from_ceph(bucket_name, file_id_value, local_path)
                elif file_get_mode == "03":
                    raise NotImplementedError("oss 获取方式暂未实现")
                else:
                    raise ValueError(f"不支持的获取方式：{file_get_mode}")

                # 提取后缀名（不含点）
                _, file_ext = os.path.splitext(final_disk_name)
                suffix = file_ext.lstrip(".") if file_ext else ""

                # 格式化文件大小
                file_size_str = _format_file_size(file_size_bytes)

                # sample_name：优先用 file_name 字段值（展示用），否则用磁盘文件名
                sample_name = display_name or final_disk_name

                # 生成样本编号并插入原始样本信息表
                sample_no = generate_sample_no()
                insert_original_sample_info_for_collect({
                    "sample_no": sample_no,
                    "sample_name": sample_name,
                    "set_no": sample_set_no,
                    "type_code": "05",
                    "suffix": suffix,
                    "file_path": local_path,
                    "file_size": file_size_str,
                    "collect_task_no": task_no,
                })
                success_count += 1

            except Exception as e:
                fail_count += 1
                append_collect_log(log_id, f"第 {i + 1} 行处理失败：{str(e)}")

        append_collect_log(log_id, f"图像采集完成，一共 {len(rows)} 个，获取成功 {success_count} 个，失败 {fail_count} 个")

        finish_collect_log(log_id, success=True, log_content="图像采集任务执行完成")
        update_task_status(task_no, "03", last_execute_flag=1)

        return {
            "code": 0,
            "message": f"执行成功，共获取 {len(rows)} 条数据，成功采集 {success_count} 个图像文件",
            "data": {"rowCount": len(rows), "successCount": success_count, "failCount": fail_count},
        }
    except Exception as e:
        fail_info = str(e)
        try:
            update_task_status(task_no, "03", last_execute_flag=2)
        except Exception:
            pass
        try:
            finish_collect_log(log_id, success=False, log_content=f"执行出错:{fail_info}")
        except Exception:
            pass
        return {"code": 1, "message": f"执行失败: {fail_info}"}


@router.post("/execute-collect-task")
def execute_collect_task_api(req: ExecuteCollectTaskRequest):
    """执行数据采集任务：根据任务类型走不同流程（时序/图像）"""
    return execute_collect_task_internal(req.taskNo.strip(), trigger_source="manual")


@router.post("/stop-collect-task")
def stop_collect_task_api(req: ExecuteCollectTaskRequest):
    """停止数据采集任务"""
    task_no = req.taskNo.strip()
    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}
    try:
        update_task_status(task_no, "04")
        return {"code": 0, "message": "已停止"}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"停止失败: {str(e)}"}


@router.post("/delete-collect-task")
def delete_collect_task_api(req: ExecuteCollectTaskRequest):
    """删除数据采集任务及其全部关联数据（明细、字段映射、执行日志）。

    若任务为定时执行方式，同步从调度器移除。
    """
    task_no = req.taskNo.strip()
    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}

    # 删除前查询执行方式，用于决定是否移除调度
    task_info = get_task_execute_type(task_no)

    try:
        delete_data_collect_task(task_no)
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"删除失败: {str(e)}"}

    # 同步移除定时调度（无论原执行方式，统一调用 remove 静默处理不存在的情况）
    try:
        from app.services.scheduler_service import remove_scheduled_task
        remove_scheduled_task(task_no)
    except Exception:
        pass

    return {"code": 0, "message": "删除成功"}


class UpdateExecTypeRequest(BaseModel):
    taskNo: str
    executeType: str
    cronFormula: str = ""


@router.post("/update-collect-task-exec-type")
def update_collect_task_exec_type_api(req: UpdateExecTypeRequest):
    """更新任务执行方式（手动/定时）和 cron 表达式，并同步调度器。

    - 改为手动：从调度器移除
    - 改为定时：新增/更新调度任务
    - 定时改定时（cron 变化）：更新调度任务
    """
    task_no = req.taskNo.strip()
    execute_type = req.executeType.strip()
    cron_formula = req.cronFormula.strip()

    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}
    if execute_type not in ("01", "02"):
        return {"code": 1, "message": "执行方式无效，应为 01-手动 或 02-定时"}
    if execute_type == "02" and not cron_formula:
        return {"code": 1, "message": "执行方式为定时时，cron 表达式不能为空"}

    # 查询原执行方式，用于判断是否需要变更调度
    old_info = get_task_execute_type(task_no)
    old_type = old_info.get("execute_type") if old_info else None

    try:
        update_task_execute_type(task_no, execute_type, cron_formula)
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"保存失败: {str(e)}"}

    # 同步调度器
    try:
        from app.services.scheduler_service import add_scheduled_task, remove_scheduled_task
        if execute_type == "02":
            # 改为定时：新增/更新调度（add 内部 replace_existing=True 会覆盖旧任务）
            add_scheduled_task(task_no, cron_formula)
        else:
            # 改为手动：移除调度（原为定时才需要移除，remove 静默处理不存在情况）
            if old_type == "02":
                remove_scheduled_task(task_no)
    except Exception as e:
        # 调度同步失败不影响数据持久化，仅提示
        print(f"[update-exec-type] 调度器同步异常: {e}")

    return {"code": 0, "message": "保存成功"}


@router.get("/query-collect-task-exec-type")
def query_collect_task_exec_type_api(taskNo: str = Query(..., description="任务编号")):
    """查询任务当前的执行方式和 cron 表达式"""
    try:
        row = get_task_execute_type(taskNo)
        if not row:
            return {"code": 0, "data": None}
        execute_type = row.get("execute_type") or "01"
        cron_formula = row.get("cron_formula") or ""
        return {
            "code": 0,
            "data": {
                "executeType": execute_type,
                "executeTypeName": "定时" if execute_type == "02" else "手动",
                "cronFormula": cron_formula,
            },
        }
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/query-collect-log")
def query_collect_log_api(taskNo: str = Query(..., description="任务编号")):
    """查询数据采集任务执行记录"""
    try:
        rows = query_collect_log(taskNo)
        data = []
        for row in rows:
            item = {}
            for k, v in row.items():
                parts = k.split("_")
                camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
                if hasattr(v, "isoformat"):
                    v = v.isoformat()
                item[camel] = v
            data.append(item)
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


class QueryTableColumnsRequest(BaseModel):
    taskNo: str
    tableName: str


@router.post("/query-table-columns")
def query_table_columns_api(req: QueryTableColumnsRequest):
    """查询目标表的字段信息（从项目自身数据库查询）"""
    table_name = req.tableName.strip()
    if not table_name:
        return {"code": 1, "message": "表名不能为空"}

    try:
        from app.core.database import _is_oracle, _show_columns_sql, _execute, get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                _execute(cursor, _show_columns_sql(table_name))
                rows = cursor.fetchall()
                data = []
                for col in rows:
                    data.append({
                        "columnName": col.get("field", col.get("Field", "")),
                        "columnType": col.get("col_type", col.get("Type", "")),
                        "columnComment": col.get("col_comment", col.get("Comment", "")),
                    })
                return {"code": 0, "data": data}
        finally:
            conn.close()
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询表字段失败: {str(e)}"}


@router.get("/query-col-map")
def query_col_map_api(taskNo: str = Query(..., description="任务编号")):
    """查询字段映射配置"""
    try:
        rows = query_col_map(taskNo)
        data = []
        for row in rows:
            data.append({
                "sourceColumn": row["source_column"] or "",
                "targetColumn": row["target_colum"] or "",
            })
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询映射失败: {str(e)}"}


@router.post("/save-col-map")
def save_col_map_api(payload: dict):
    """保存字段映射配置"""
    task_no = payload.get("taskNo", "").strip()
    target_table = payload.get("targetTable", "").strip()
    mappings = payload.get("mappings", [])
    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}
    if not target_table:
        return {"code": 1, "message": "目标表名不能为空"}
    try:
        save_col_map(task_no, target_table, mappings)
        return {"code": 0, "message": "保存成功"}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"保存失败: {str(e)}"}
