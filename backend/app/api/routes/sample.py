from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from app.core.database import query_code_dict, query_sample_set, query_sample_info, save_sample_set, sample_statistic, sample_trend, query_audio_text, update_sample_score, insert_sample_info, update_label_think, generate_task_no, query_data_collect_task, save_data_collect_task, save_data_collect_task_det, query_data_collect_task_det, update_data_collect_task_det
import os
import io
import zipfile

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
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/sample-statistic")
def sample_statistic_api():
    """样本中心统计数据"""
    try:
        data = sample_statistic()
        return {"code": 0, "data": data}
    except Exception as e:
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
        return {"code": 1, "message": f"查询失败: {str(e)}"}


class SaveSampleSetRequest(BaseModel):
    setCode: str
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
        rowcount = save_sample_set(req.model_dump())
        return {"code": 0, "message": "保存成功", "data": {"rowcount": rowcount}}
    except Exception as e:
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
        return {"code": 1, "message": f"查询转写文字失败: {str(e)}"}


@router.get("/download-sample-set")
def download_sample_set(setNo: str = Query(..., description="样本集编号"), fileName: str = Query(..., description="下载文件名")):
    """下载样本集：查询样本集下所有样本文件，打成 zip 压缩包返回"""
    from urllib.parse import quote

    try:
        samples = query_sample_info(setNo)
    except Exception as e:
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
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.post("/save-collect-task")
def save_collect_task_api(payload: dict):
    """新增数据采集任务，任务编号自动生成"""
    task_name = payload.get("taskName", "").strip()
    remark = payload.get("remark", "").strip()
    if not task_name:
        return {"code": 1, "message": "任务名称不能为空"}
    try:
        task_no = generate_task_no()
        save_data_collect_task(task_no, task_name, remark)
        return {"code": 0, "message": "保存成功", "data": {"taskNo": task_no}}
    except Exception as e:
        return {"code": 1, "message": f"保存失败: {str(e)}"}


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
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.post("/save-collect-task-det")
def save_collect_task_det_api(payload: dict):
    """保存数据采集任务明细（新增或更新）"""
    task_no = payload.get("taskNo", "").strip()
    source_db_type = payload.get("sourceDbType", "").strip()
    source_db_host = payload.get("sourceDbHost", "").strip()
    source_db_port = payload.get("sourceDbPort", "").strip()
    source_db_usr = payload.get("sourceDbUsr", "").strip()
    source_db_pwd = payload.get("sourceDbPwd", "").strip()
    target_table = payload.get("targetTable", "").strip()
    collect_sql = payload.get("collectSql", "").strip()

    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}
    if not source_db_type or not source_db_host or not source_db_usr or not collect_sql or not target_table:
        return {"code": 1, "message": "数据库类型、地址、用户名、SQL、目标表不能为空"}

    data = {
        "taskNo": task_no,
        "sourceDbType": source_db_type,
        "sourceDbHost": source_db_host,
        "sourceDbPort": source_db_port,
        "sourceDbUsr": source_db_usr,
        "sourceDbPwd": source_db_pwd,
        "targetTable": target_table,
        "collectSql": collect_sql,
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
        return {"code": 1, "message": f"保存失败: {str(e)}"}
