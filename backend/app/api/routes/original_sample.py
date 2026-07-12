from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from app.core.database import (
    query_code_dict, query_original_sample_set, query_original_sample_info,
    save_original_sample_set, insert_original_sample_info,
    update_original_sample_score, update_original_label_think, query_audio_text,
    generate_sample_set_no, query_time_series_data_by_set_no,
)
import os
import io
import logging
import zipfile

logger = logging.getLogger("app.original_sample")

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


def _row_to_camel(row: dict) -> dict:
    """将数据库行（下划线命名）转为驼峰命名字典，datetime 转 isoformat 字符串"""
    item = {}
    for k, v in row.items():
        parts = k.split("_")
        camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        if k == "label_think" and v is not None:
            if isinstance(v, bytes):
                v = v.decode("utf-8")
        item[camel] = v
    return item


@router.get("/query-sample-set")
def query_sample_set_api():
    try:
        rows = query_original_sample_set()
        data = [_row_to_camel(row) for row in rows]
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


class SaveSampleSetRequest(BaseModel):
    setName: str
    description: str = ""
    businessSystem: str = ""
    sampleTypeCode: str
    sampleTypeName: str = ""
    sampleFieldCode: str = ""
    sampleFieldName: str = ""


@router.post("/save-sample-set")
def save_sample_set_api(req: SaveSampleSetRequest):
    try:
        from app.core.config import settings
        set_no = generate_sample_set_no()
        # 生成以样本集名称命名的文件夹，路径写入 set_path
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
        }
        rowcount = save_original_sample_set(data)
        return {"code": 0, "message": "保存成功", "data": {"rowcount": rowcount, "setNo": set_no}}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"保存失败: {str(e)}"}


@router.get("/get-samples")
def get_samples_api(setNo: str = Query(..., description="样本集编号")):
    try:
        rows = query_original_sample_info(setNo)
        data = [_row_to_camel(row) for row in rows]
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/query-time-series-data")
def query_time_series_data_api(
    setNo: str = Query(..., description="样本集编号"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(20, ge=1, le=200, description="每页条数"),
):
    """时序类型原始样本集：分页查询关联的采集任务目标表数据"""
    try:
        result = query_time_series_data_by_set_no(setNo, page, pageSize)
        # 转换行数据为驼峰
        rows = [_row_to_camel(row) for row in result["rows"]]
        # 列名也转驼峰
        columns = []
        for col in result["columns"]:
            parts = col.split("_")
            camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
            columns.append({"key": camel, "label": col})
        return {
            "code": 0,
            "data": {
                "targetTable": result["target_table"],
                "total": result["total"],
                "rows": rows,
                "columns": columns,
            }
        }
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/serve-image")
def serve_image(filePath: str = Query(..., description="图片文件路径")):
    """读取并返回图片文件"""
    filePath = os.path.normpath(filePath)
    if not os.path.isfile(filePath):
        return {"code": 1, "message": f"图片文件不存在: {filePath}"}
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
    return FileResponse(filePath, media_type=media_type)


@router.get("/get-annotations")
def get_annotations(filePath: str = Query(..., description="图片文件路径")):
    """获取 YOLO 标注信息：读取同目录下 class.txt 和同名 .txt 标注文件"""
    filePath = os.path.normpath(filePath)
    dir_path = os.path.dirname(filePath)
    base_name = os.path.splitext(os.path.basename(filePath))[0]
    ext = os.path.splitext(filePath)[1].lower()

    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
    if ext not in image_exts:
        return {"code": 0, "data": {"hasAnnotations": False}}

    class_file = os.path.normpath(os.path.join(dir_path, "classes.txt"))
    label_file = os.path.normpath(os.path.join(dir_path, base_name + ".txt"))

    if not os.path.isfile(class_file) or not os.path.isfile(label_file):
        return {"code": 0, "data": {"hasAnnotations": False}}

    try:
        with open(class_file, "r", encoding="utf-8") as f:
            class_names = [line.strip() for line in f.readlines() if line.strip()]
    except Exception:
        class_names = []

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
                        "cx": cx, "cy": cy, "w": w, "h": h,
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
def get_audio_text_api(sampleNo: str = Query(...), sampleName: str = Query(...)):
    """查询语音样本的转写文字（s_audio_text 表为共享表）"""
    try:
        audio_text = query_audio_text(sampleNo, sampleName)
        return {"code": 0, "data": {"audioText": audio_text}}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询转写文字失败: {str(e)}"}


@router.get("/download-sample-set")
def download_sample_set(setNo: str = Query(...), fileName: str = Query(...)):
    """下载原始样本集：查询样本集下所有样本文件，打成 zip 压缩包返回"""
    from urllib.parse import quote

    try:
        samples = query_original_sample_info(setNo)
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询样本失败: {str(e)}"}

    if not samples:
        return {"code": 1, "message": "该样本集下无样本数据"}

    mem_zip = io.BytesIO()
    added_names = set()
    with zipfile.ZipFile(mem_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for row in samples:
            file_path = row.get("file_path")
            if not file_path:
                continue
            file_path = os.path.normpath(file_path)
            if not os.path.isfile(file_path):
                continue

            arc_name = os.path.basename(file_path)
            if arc_name in added_names:
                base, ext = os.path.splitext(arc_name)
                idx = 1
                while f"{base}_{idx}{ext}" in added_names:
                    idx += 1
                arc_name = f"{base}_{idx}{ext}"
            added_names.add(arc_name)
            zf.write(file_path, arc_name)

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
    safe_name = (fileName + ".zip").replace(" ", "_")
    encoded_name = quote(safe_name)
    return StreamingResponse(
        mem_zip,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"}
    )


@router.post("/upload-samples")
async def upload_samples(
    setNo: str = Form(...),
    setName: str = Form(...),
    typeCode: str = Form(...),
    files: list[UploadFile] = File(...),
):
    """上传原始样本文件：保存到 sample_upload_dir/setName/ 目录，并写入 s_original_sample_info 表"""
    from app.core.config import settings

    target_dir = os.path.join(settings.sample_upload_dir, setName)
    os.makedirs(target_dir, exist_ok=True)

    success_count = 0
    errors = []

    for file in files:
        if not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        file_path = os.path.join(target_dir, file.filename)
        try:
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            insert_original_sample_info(
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
    """批量导入：上传单个 ZIP，解压图片到 sample_upload_dir/setName/，写入 s_original_sample_info"""
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
            insert_callback=insert_original_sample_info,
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


class UpdateSampleScoreRequest(BaseModel):
    sampleNo: str
    sampleName: str
    scoreCode: str


@router.post("/update-sample-score")
def update_sample_score_api(req: UpdateSampleScoreRequest):
    """更新样本质量评分"""
    valid_codes = {'01', '02', '03', '04'}
    if req.scoreCode not in valid_codes:
        return {"code": 1, "message": "评分编码无效，应为01-优质/02-良好/03-一般/04-较差"}
    try:
        rowcount = update_original_sample_score(req.sampleNo, req.sampleName, req.scoreCode)
        if rowcount == 0:
            return {"code": 1, "message": "未找到对应样本"}
        return {"code": 0, "message": "评分成功"}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"评分失败: {str(e)}"}


@router.post("/update-label-think")
async def update_label_think_api(payload: dict):
    """保存样本思维链"""
    sample_no = payload.get("sampleNo", "")
    sample_name = payload.get("sampleName", "")
    label_think = payload.get("labelThink", "")
    if not sample_no or not sample_name:
        return {"code": 1, "message": "sampleNo 和 sampleName 不能为空"}
    try:
        update_original_label_think(sample_no, sample_name, label_think)
        return {"code": 0, "message": "保存成功"}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"保存失败: {str(e)}"}
