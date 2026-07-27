from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from app.core.database import (
    query_code_dict,
    generate_task_no,
    generate_sample_set_no,
    generate_sample_no,
    save_query_result_to_desktop,
)
from app.core.db_sample import (
    query_sample_set, query_sample_info, save_sample_set, update_sample_set,
    update_sample_set_labels, get_annotation_by_sample_no, query_audio_text,
    update_sample_score, insert_sample_info, update_label_think,
    apply_sample_set_version_change, get_sample_set_path,
    query_original_sample_set_by_type, insert_original_sample_info_for_collect,
    batch_insert_sample_info,
)
from app.core.db_collect import (
    sample_statistic, sample_trend,
    query_data_collect_task, save_data_collect_task, save_data_collect_task_det,
    query_data_collect_task_det, update_data_collect_task_det, get_task_det_raw,
    update_task_status, insert_collect_log, append_collect_log, finish_collect_log,
    query_collect_log, query_all_scheduled_tasks, get_task_execute_type,
    update_task_execute_type, delete_data_collect_task, execute_source_sql,
    query_target_table_columns, query_col_map, save_col_map, write_to_target_table,
)
from app.services.sample_minio_service import is_minio_enabled, is_minio_path, upload_image as minio_upload_image, download_image as minio_download_image, build_set_path as minio_build_set_path, build_object_id as minio_build_object_id, list_object_names as minio_list_object_names
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


@router.get("/get-classes")
def get_classes_api(setNo: str = Query(..., description="样本集编号")):
    """读取样本集的 sample_labels 字段，返回标签列表（每行一个标签）"""
    try:
        row = get_sample_set_path(setNo)
        if not row:
            return {"code": 0, "data": []}
        # get_sample_set_path 返回字典: {set_path, set_name, sample_labels}
        sample_labels = row.get("sample_labels") or ""
        # 保持原内容，按行分割，去除行尾换行符（与原 classes.txt 处理一致）
        classes = [line for line in sample_labels.splitlines() if line.strip()]
        return {"code": 0, "data": classes}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"读取标签失败: {str(e)}"}


@router.get("/get-samples-by-labels")
def get_samples_by_labels_api(
    setNo: str = Query(..., description="样本集编号"),
    labels: str = Query("", description="标签列表，逗号分隔"),
):
    """根据标签筛选样本：从 DB 读取 sample_labels 构建 class_id→class_name 映射，
    再遍历样本的 label_content 检查是否包含选中标签的 class_id"""
    try:
        if not labels:
            return {"code": 0, "data": []}

        selected_labels = set(lab.strip() for lab in labels.split(",") if lab.strip())
        if not selected_labels:
            return {"code": 0, "data": []}

        # 读取样本集的 sample_labels 构建 class_id -> class_name 映射
        set_row = get_sample_set_path(setNo)
        if not set_row:
            return {"code": 0, "data": []}
        sample_labels = set_row.get("sample_labels") or ""
        class_map = {}
        for idx, line in enumerate(sample_labels.splitlines()):
            name = line.strip()
            if name:
                class_map[idx] = name

        # 找出选中标签对应的 class_id 集合
        selected_ids = {cid for cid, cname in class_map.items() if cname in selected_labels}

        # 遍历样本，检查 label_content 中是否包含选中标签的 class_id
        rows = query_sample_info(setNo)
        data = []
        for row in rows:
            label_content = row.get("label_content") or ""
            if not label_content:
                continue
            matched = False
            for line in label_content.splitlines():
                parts = line.strip().split()
                if parts:
                    try:
                        cid = int(parts[0])
                        if cid in selected_ids:
                            matched = True
                            break
                    except ValueError:
                        continue
            if matched:
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
        return {"code": 1, "message": f"标签筛选失败: {str(e)}"}


class SaveSampleSetRequest(BaseModel):
    setName: str
    description: str = ""
    businessSystem: str = ""
    sampleTypeCode: str
    sampleTypeName: str
    sampleFieldCode: str = ""
    sampleFieldName: str = ""
    sampleLabels: str = ""  # 图像类型(05)的标注标签，每行一个，对应 classes.txt 内容


class UpdateSampleSetRequest(BaseModel):
    """更新样本集请求（不允许修改 set_name 和 type_code）"""
    setNo: str
    description: str = ""
    businessSystem: str = ""
    sampleFieldCode: str = ""
    sampleFieldName: str = ""
    sampleLabels: str = ""


class UpdateSampleScoreRequest(BaseModel):
    sampleNo: str
    sampleName: str
    scoreCode: str  # 01-优质/02-良好/03-一般/04-较差


@router.post("/save-sample-set")
def save_sample_set_api(req: SaveSampleSetRequest):
    try:
        from app.core.config import settings
        set_no = generate_sample_set_no()
        # 根据存储类型生成 set_path
        if is_minio_enabled():
            # MinIO 模式：以 setNo 作为对象 key 前缀（桶下"路径"）
            set_path = minio_build_set_path(set_no)
        else:
            # 本地模式：生成以样本集名称命名的文件夹
            set_path = os.path.join(settings.sample_upload_dir, req.setName)
            os.makedirs(set_path, exist_ok=True)
        # 只保留 SQL 需要的字段，避免 Oracle 报错多余的参数
        data = {
            'setCode': set_no,
            'setName': req.setName,
            'description': req.description,
            'businessSystem': req.businessSystem,
            'sampleTypeCode': req.sampleTypeCode,
            'sampleFieldCode': req.sampleFieldCode,
            'setPath': set_path,
            'sampleLabels': req.sampleLabels,
        }
        rowcount = save_sample_set(data)
        return {"code": 0, "message": "保存成功", "data": {"rowcount": rowcount, "setNo": set_no}}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"保存失败: {str(e)}"}


@router.post("/update-sample-set")
def update_sample_set_api(req: UpdateSampleSetRequest):
    """更新样本集（不允许修改 set_name 和 type_code，不更新 version）"""
    try:
        if not req.setNo:
            return {"code": 1, "message": "样本集编号不能为空"}
        data = {
            'setNo': req.setNo,
            'description': req.description,
            'businessSystem': req.businessSystem,
            'sampleFieldCode': req.sampleFieldCode,
            'sampleLabels': req.sampleLabels,
        }
        rowcount = update_sample_set(data)
        if rowcount == 0:
            return {"code": 1, "message": "未找到对应样本集"}
        return {"code": 0, "message": "更新成功"}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"更新失败: {str(e)}"}


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
    # MinIO 路径：从 MinIO 下载后返回
    if is_minio_path(filePath):
        try:
            content = minio_download_image(filePath)
        except Exception as e:
            logger.exception("MinIO 下载失败")
            return {"code": 1, "message": f"图片文件不存在: {filePath}, 错误: {e}"}
        ext = os.path.splitext(filePath)[1].lower()
        content_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
            ".tif": "image/tiff", ".tiff": "image/tiff",
            ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
            ".flac": "audio/flac", ".aac": "audio/aac", ".wma": "audio/x-ms-wma",
            ".m4a": "audio/mp4",
        }
        media_type = content_types.get(ext, "application/octet-stream")
        return StreamingResponse(io.BytesIO(content), media_type=media_type)

    # 本地路径
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
def get_annotations(sampleNo: str = Query(..., description="样本编号")):
    """获取 YOLO 标注信息：通过 sampleNo 从 DB 读取 sample_labels（classes.txt 内容）
    和 label_content（图片同名 txt 内容）"""
    # 从 DB 查询样本的 label_content 和样本集的 sample_labels
    row = get_annotation_by_sample_no(sampleNo)
    if not row:
        return {"code": 0, "data": {"hasAnnotations": False}}

    label_content = row.get("label_content") or ""
    sample_labels = row.get("sample_labels") or ""

    # 解析 sample_labels 为 class_names 列表（保持原行内容，去除空白行）
    class_names = [line.strip() for line in sample_labels.splitlines() if line.strip()]

    # 解析 label_content，每行格式: class_id center_x center_y width height
    boxes = []
    for line in label_content.splitlines():
        parts = line.strip().split()
        if len(parts) >= 5:
            try:
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
            except (ValueError, IndexError):
                continue

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
    """下载样本集：查询样本集下所有样本文件，打成 zip 压缩包返回

    - 本地模式：直接读取磁盘文件
    - MinIO 模式：从 MinIO 下载图片二进制
    - 标注 txt（图片同名 txt）和 classes.txt：从 DB 读取 label_content / sample_labels 重建
    """
    from urllib.parse import quote

    try:
        samples = query_sample_info(setNo)
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询样本失败: {str(e)}"}

    if not samples:
        return {"code": 1, "message": "该样本集下无样本数据"}

    # 读取样本集的 sample_labels（classes.txt 内容），用于打包到 zip
    set_row = get_sample_set_path(setNo)
    sample_labels_content = (set_row or {}).get("sample_labels") or ""

    mem_zip = io.BytesIO()
    added_names = set()
    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}

    with zipfile.ZipFile(mem_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for row in samples:
            file_path = row.get("file_path") or row.get("filePath")
            if not file_path:
                continue

            # 获取图片二进制内容
            image_bytes = None
            if is_minio_path(file_path):
                try:
                    image_bytes = minio_download_image(file_path)
                except Exception as e:
                    logger.warning(f"MinIO 下载失败: {file_path}, error: {e}")
                    continue
            else:
                file_path = os.path.normpath(file_path)
                if not os.path.isfile(file_path):
                    continue
                with open(file_path, "rb") as f:
                    image_bytes = f.read()

            # zip 内使用原始文件名，避免同名覆盖
            arc_name = os.path.basename(file_path)
            if arc_name in added_names:
                base, ext = os.path.splitext(arc_name)
                idx = 1
                while f"{base}_{idx}{ext}" in added_names:
                    idx += 1
                arc_name = f"{base}_{idx}{ext}"
            added_names.add(arc_name)
            zf.writestr(arc_name, image_bytes)

            # 图片类型：从 DB 读取 label_content 重建同名 .txt 标注文件
            ext = os.path.splitext(file_path)[1].lower()
            if ext in image_exts:
                label_content = row.get("label_content") or ""
                if label_content:
                    base_name = os.path.splitext(arc_name)[0]
                    lbl_name = base_name + ".txt"
                    if lbl_name in added_names:
                        base_name2, _ = os.path.splitext(lbl_name)
                        idx = 1
                        while f"{base_name2}_{idx}.txt" in added_names:
                            idx += 1
                        lbl_name = f"{base_name2}_{idx}.txt"
                    added_names.add(lbl_name)
                    # 保持 label_content 的原内容不变
                    zf.writestr(lbl_name, label_content)

        # 写入 classes.txt（如果 sample_labels 非空）
        if sample_labels_content:
            cls_name = "classes.txt"
            if cls_name in added_names:
                idx = 1
                while f"classes_{idx}.txt" in added_names:
                    idx += 1
                cls_name = f"classes_{idx}.txt"
            added_names.add(cls_name)
            # 保持 sample_labels 的原内容不变
            zf.writestr(cls_name, sample_labels_content)

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
    将图片 + YOLO 标注（DB label_content）转换为 conversations + images 结构
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

    def build_class_map(sample_labels: str):
        """从 sample_labels 字符串构建 YOLO 类别映射 {id: name}"""
        class_map = {}
        for idx, line in enumerate(sample_labels.splitlines()):
            name = line.strip()
            if name:
                class_map[idx] = name
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

    # 加载样本集的 sample_labels（classes.txt 内容）
    set_row = get_sample_set_path(setNo)
    sample_labels_content = (set_row or {}).get("sample_labels") or ""
    class_map = build_class_map(sample_labels_content)

    sharegpt_data = []
    skip_no_txt = 0
    skip_empty_anno = 0
    skip_bad_img = 0
    processed = 0

    # 按 samples 顺序处理，每条样本对应一张图片 + label_content 标注
    for row in samples:
        file_path = row.get("file_path") or row.get("filePath")
        if not file_path:
            continue

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in IMAGE_SUFFIXES:
            continue

        # 读取 label_content（图片同名 txt 内容）
        label_content = row.get("label_content") or ""
        if not label_content:
            skip_no_txt += 1
            continue

        # 读取图片尺寸
        try:
            if is_minio_path(file_path):
                img_bytes = minio_download_image(file_path)
                with Image.open(io.BytesIO(img_bytes)) as img:
                    img_w, img_h = img.width, img.height
            else:
                file_path_norm = os.path.normpath(file_path)
                if not os.path.isfile(file_path_norm):
                    continue
                with Image.open(file_path_norm) as img:
                    img_w, img_h = img.width, img.height
        except Exception as e:
            img_filename = os.path.basename(file_path)
            logger.warning(f"读取图片尺寸失败: {img_filename}, 错误: {e}")
            skip_bad_img += 1
            continue

        # 解析 YOLO 标注
        annotations = []
        for line in label_content.splitlines():
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
    """上传样本文件

    - 图片类型(05)：
        - 本地模式：图片保存到 sample_upload_dir/setName/，写入 s_sample_info
          图片同名 .txt 标注内容写入 s_sample_info.label_content（不保存到磁盘）
          classes.txt 内容更新 s_sample_set.sample_labels（不保存到磁盘）
        - MinIO 模式：图片上传到 MinIO，对象 ID 写入 s_sample_info.file_path
          .txt 标注内容同样写入 DB，不上传到 MinIO
    - 其他类型：维持原逻辑（本地保存 + DB 写入）
    """
    from app.core.config import settings
    from app.services.sample_import_service import _get_unique_filename, _get_unique_filename_for_minio

    use_minio = is_minio_enabled()
    # 本地模式需要目标目录，MinIO 模式不需要
    target_dir = None
    if not use_minio:
        target_dir = os.path.join(settings.sample_upload_dir, setName)
        os.makedirs(target_dir, exist_ok=True)

    success_count = 0
    errors = []
    # 初始化 used_names：MinIO 模式下预填入桶内已有对象名，避免覆盖
    if use_minio:
        used_names = minio_list_object_names(setNo)
    else:
        used_names = set()

    # 图片类型：预扫描本次上传的文件名，构建"图片名 → 同名txt内容"映射
    # 同时识别 classes.txt 内容
    image_label_map = {}  # {图片basename(无扩展名): txt内容}
    classes_txt_content = None  # classes.txt 原始内容
    if typeCode == '05':
        all_files = list(files)
        # 先读取所有 .txt 文件内容
        for f in all_files:
            if not f.filename:
                continue
            ext = os.path.splitext(f.filename)[1].lower()
            if ext == '.txt':
                try:
                    await f.seek(0)
                    content = await f.read()
                    try:
                        txt_text = content.decode("utf-8")
                    except UnicodeDecodeError:
                        txt_text = content.decode("gbk", errors="replace")
                    basename = os.path.splitext(f.filename)[0]
                    if basename.lower() == "classes":
                        # classes.txt 内容保持原样
                        classes_txt_content = txt_text
                    else:
                        image_label_map[basename] = txt_text
                except Exception as e:
                    errors.append(f"{f.filename}: 读取失败 - {str(e)}")
        # 重置文件指针位置，便于后续遍历
        for f in all_files:
            try:
                await f.seek(0)
            except Exception:
                pass
        files = all_files

    # 如有 classes.txt 上传，先更新样本集的 sample_labels
    if typeCode == '05' and classes_txt_content is not None:
        try:
            update_sample_set_labels(setNo, classes_txt_content)
        except Exception as e:
            errors.append(f"classes.txt: 更新样本集标签失败 - {str(e)}")

    for file in files:
        if not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower()

        # 图片类型：.txt 文件不再保存到磁盘/MinIO，已在上面的预扫描中处理
        if typeCode == '05' and ext == '.txt':
            continue

        # 生成唯一文件名（MinIO 模式下也需避免对象 key 冲突）
        if use_minio:
            # MinIO 模式下不需要 target_dir，仅检查 used_names
            unique_name = _get_unique_filename_for_minio(file.filename, used_names)
        else:
            unique_name = _get_unique_filename(target_dir, file.filename, used_names)
        used_names.add(unique_name)

        try:
            content = await file.read()

            # 图片类型：检测是否有同名txt标注文件
            label_flag = 0
            label_content = ""
            if typeCode == '05':
                img_basename = os.path.splitext(file.filename)[0]
                if img_basename in image_label_map:
                    label_flag = 1
                    # 保持 txt 原内容不变
                    label_content = image_label_map[img_basename]

            # 保存文件并得到 file_path
            if use_minio:
                # MinIO 模式：上传到 MinIO
                content_type_map = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                    ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
                    ".tif": "image/tiff", ".tiff": "image/tiff",
                }
                ct = content_type_map.get(ext, "application/octet-stream")
                file_path = minio_upload_image(setNo, unique_name, content, content_type=ct)
            else:
                # 本地模式：保存到磁盘
                file_path = os.path.join(target_dir, unique_name)
                with open(file_path, "wb") as f:
                    f.write(content)

            # 写入数据库
            insert_sample_info(
                set_no=setNo,
                sample_name=unique_name,
                suffix=ext,
                type_code=typeCode,
                file_path=file_path,
                file_size=len(content),
                label_flag=label_flag,
                label_content=label_content,
            )
            success_count += 1
        except Exception as e:
            errors.append(f"{file.filename}: 保存失败 - {str(e)}")

    msg = f"成功上传 {success_count} 个文件"
    if errors:
        msg += f"，失败 {len(errors)} 个: {'; '.join(errors[:5])}"

    # 图片类型：自动记录版本变更（仅当有成功新增的样本时）
    if typeCode == '05' and success_count > 0:
        try:
            ver = apply_sample_set_version_change(
                set_no=setNo,
                set_name=setName,
                added_count=success_count,
            )
            msg += f"，版本 {ver['pre_version']} → {ver['next_version']}"
        except Exception as e:
            logger.exception("版本变更记录写入失败")
            msg += f"（版本变更记录写入失败: {e}）"

    return {"code": 0, "message": msg}


@router.post("/upload-samples-batch")
async def upload_samples_batch(
    setNo: str = Form(...),
    setName: str = Form(...),
    typeCode: str = Form(...),
    file: UploadFile = File(...),
    majorVersionChange: str = Form("false"),
    versionRemark: str = Form(""),
):
    """批量导入：上传单个 ZIP，解压图片导入样本集

    - 图片保存到本地或上传到 MinIO
    - 同名 .txt 标注内容写入 s_sample_info.label_content（不保存到磁盘/MinIO）
    - classes.txt 内容更新 s_sample_set.sample_labels（不保存到磁盘/MinIO）
    - 支持手动大版本变更：majorVersionChange=true 时无论增量多少大版本号 +1、小版本号归 0
    - 大文件采用流式写入临时文件再解压，避免一次性读入内存
    """
    from app.core.config import settings
    from app.services.sample_import_service import extract_zip_and_import

    if typeCode != "05":
        return {"code": 1, "message": "批量导入仅支持图片类型（05）样本集"}

    # 解析手动大版本变更标识
    manual_major = (majorVersionChange or "").strip().lower() in ("true", "1", "on", "yes")
    # 变更说明长度校验
    version_remark = (versionRemark or "").strip()
    if len(version_remark) > 150:
        return {"code": 1, "message": "变更说明不能超过 150 个字"}

    use_minio = is_minio_enabled()
    # 流式写入临时文件，避免大 ZIP 一次性读入内存触发 400
    tmp_path = None
    try:
        import tempfile
        tmp_dir = settings.upload_tmp_dir or tempfile.gettempdir()
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, f"batch_import_{setNo}_{id(file)}.zip")
        with open(tmp_path, "wb") as tmp_f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB 分块
                if not chunk:
                    break
                tmp_f.write(chunk)

        if not zipfile.is_zipfile(tmp_path):
            return {"code": 1, "message": "上传文件不是有效的 ZIP 文件"}

        target_dir = None if use_minio else os.path.join(settings.sample_upload_dir, setName)
        result = extract_zip_and_import(
            target_dir=target_dir,
            set_no=setNo,
            set_name=setName,
            type_code=typeCode,
            insert_callback=insert_sample_info,
            zip_path=tmp_path,
            use_minio=use_minio,
            write_txt_to_db=True,
            update_set_labels_callback=update_sample_set_labels,
        )
        msg = (f"成功导入 {result['image_count']} 张图片，"
               f"写入数据库 {result['txt_count']} 个标注文件，"
               f"跳过 {result['skipped_count']} 个文件")
        if result["errors"]:
            msg += f"，失败 {len(result['errors'])} 个: {'; '.join(result['errors'][:5])}"

        # 记录版本变更（仅当有成功新增的图片时）
        if result["image_count"] > 0:
            try:
                ver = apply_sample_set_version_change(
                    set_no=setNo,
                    set_name=setName,
                    added_count=result["image_count"],
                    manual_major=manual_major,
                    manual_remark=version_remark,
                )
                msg += f"，版本 {ver['pre_version']} → {ver['next_version']}"
            except Exception as e:
                logger.exception("版本变更记录写入失败")
                msg += f"（版本变更记录写入失败: {e}）"

        return {"code": 0, "message": msg}
    except Exception as e:
        logger.exception("批量导入异常")
        return {"code": 1, "message": f"批量导入失败: {str(e)}"}
    finally:
        # 清理临时文件
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


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
        from app.core.database import get_connection, _execute
        conn = get_connection()
        with conn.cursor() as cursor:
            _execute(cursor, "SELECT task_name FROM s_data_collect_task WHERE task_no = %s", (task_no,))
            row = cursor.fetchone()
            if row:
                task_name = row.get("task_name") if isinstance(row, dict) else row[0]
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
    - 本地存储：文件保存到关联原始样本集的 set_path 目录
    - MinIO 存储：文件上传到 MinIO，file_path 写入 minio://bucket/setNo/filename
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

    # 判断存储模式
    use_minio = is_minio_enabled()

    # 查询任务名称
    task_name = ""
    try:
        from app.core.database import get_connection, _execute
        conn = get_connection()
        with conn.cursor() as cursor:
            _execute(cursor, "SELECT task_name FROM s_data_collect_task WHERE task_no = %s", (task_no,))
            row = cursor.fetchone()
            if row:
                task_name = row.get("task_name") if isinstance(row, dict) else row[0]
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

        # 准备保存目录 / MinIO 路径
        from app.core.config import settings
        set_path = det.get("set_path") or ""
        save_dir = ""
        if use_minio:
            # MinIO 模式：不需要本地目录，使用 sample_set_no 作为对象前缀
            if not sample_set_no:
                return {"code": 1, "message": "MinIO 模式下原始样本集编号不能为空"}
            minio_list = minio_list_object_names(sample_set_no)
            used_filenames = set(minio_list)  # 预填入 MinIO 已有对象名，避免覆盖
            append_collect_log(log_id, f"存储模式：MinIO，对象前缀：{sample_set_no}/")
        else:
            # 本地模式：优先使用关联原始样本集的 set_path 根目录
            if set_path:
                save_dir = set_path
            else:
                # 兜底：旧数据无 set_path 时回退原逻辑
                save_dir = os.path.join(settings.sample_upload_dir, "data_collect", task_no)
                append_collect_log(log_id, f"警告：原始样本集未配置 set_path，回退到 {save_dir}")
            os.makedirs(save_dir, exist_ok=True)
            used_filenames = set()

        if not use_minio:
            append_collect_log(log_id, f"文件保存目录：{save_dir}")
        mode_names = {"01": "存储路径", "02": "ceph", "03": "oss"}
        append_collect_log(log_id, f"图像获取方式：{mode_names.get(file_get_mode, file_get_mode)}")

        # 遍历每行数据，获取图像文件
        success_count = 0
        fail_count = 0

        from app.core.database import generate_sample_no
        from app.core.db_sample import insert_original_sample_info_for_collect

        for i, row in enumerate(rows):
            try:
                file_id_value = row[file_id_idx] if file_id_idx < len(row) else None
                if not file_id_value:
                    append_collect_log(log_id, f"第 {i + 1} 行：图像获取字段值为空，跳过")
                    fail_count += 1
                    continue

                file_id_value = str(file_id_value)

                # 获取展示用名称（file_name 字段值，仅用于数据库记录和前端展示）
                display_name = ""
                if file_name_idx is not None and file_name_idx < len(row) and row[file_name_idx]:
                    display_name = str(row[file_name_idx])

                # 文件保存名：直接使用对象 key 的 basename
                disk_filename = os.path.basename(file_id_value)
                base_name, ext = os.path.splitext(disk_filename)

                # 如果文件名无后缀，用 sample_name（display_name）的后缀补充
                if not ext and display_name:
                    _, name_ext = os.path.splitext(display_name)
                    if name_ext:
                        ext = name_ext
                        disk_filename = disk_filename + ext
                        base_name, _ = os.path.splitext(disk_filename)

                # 处理文件名冲突：自动加序号
                final_disk_name = disk_filename
                seq = 1
                while final_disk_name in used_filenames:
                    final_disk_name = f"{base_name}_{seq}{ext}"
                    seq += 1
                used_filenames.add(final_disk_name)

                # 根据获取方式下载文件，统一拿到 bytes 和 size
                image_bytes = None
                file_size_bytes = 0
                if file_get_mode == "01":
                    # 存储路径：file_id_value 就是文件路径
                    src_path = file_id_value
                    if not os.path.exists(src_path):
                        append_collect_log(log_id, f"第 {i + 1} 行：源文件不存在：{src_path}，跳过")
                        fail_count += 1
                        continue
                    with open(src_path, "rb") as f:
                        image_bytes = f.read()
                    file_size_bytes = len(image_bytes)
                elif file_get_mode == "02":
                    # ceph：file_id_value 是对象 key，先下载到临时文件再读取 bytes
                    import tempfile
                    tmp_dir = settings.upload_tmp_dir or tempfile.gettempdir()
                    os.makedirs(tmp_dir, exist_ok=True)
                    tmp_path = os.path.join(tmp_dir, f"collect_{task_no}_{i}")
                    try:
                        from app.services.ceph_service import download_from_ceph
                        file_size_bytes = download_from_ceph(bucket_name, file_id_value, tmp_path)
                        with open(tmp_path, "rb") as f:
                            image_bytes = f.read()
                    finally:
                        if os.path.isfile(tmp_path):
                            try:
                                os.remove(tmp_path)
                            except Exception:
                                pass
                elif file_get_mode == "03":
                    raise NotImplementedError("oss 获取方式暂未实现")
                else:
                    raise ValueError(f"不支持的获取方式：{file_get_mode}")

                # 保存文件：本地 or MinIO
                if use_minio:
                    content_type_map = {
                        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                        ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
                        ".tif": "image/tiff", ".tiff": "image/tiff",
                    }
                    ct = content_type_map.get(ext.lower(), "application/octet-stream")
                    file_path = minio_upload_image(sample_set_no, final_disk_name, image_bytes, content_type=ct)
                else:
                    local_path = os.path.join(save_dir, final_disk_name)
                    with open(local_path, "wb") as f:
                        f.write(image_bytes)
                    file_path = local_path

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
                    "file_path": file_path,
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
