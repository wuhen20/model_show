from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from app.core.database import query_code_dict, generate_sample_set_no
from app.core.db_sample import (
    query_original_sample_set, query_original_sample_info,
    save_original_sample_set, update_original_sample_set, insert_original_sample_info,
    update_original_sample_score, update_original_label_think, query_audio_text,
    query_time_series_data_by_set_no, get_original_sample_set_path,
)
from app.services.sample_minio_service import (
    is_minio_enabled, is_minio_path,
    upload_image as minio_upload_image,
    download_image as minio_download_image,
    build_set_path as minio_build_set_path,
    list_object_names as minio_list_object_names,
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


class UpdateSampleSetRequest(BaseModel):
    """更新原始样本集请求（不允许修改 set_name 和 type_code）"""
    setNo: str
    description: str = ""
    businessSystem: str = ""
    sampleFieldCode: str = ""
    sampleFieldName: str = ""


@router.post("/save-sample-set")
def save_sample_set_api(req: SaveSampleSetRequest):
    try:
        from app.core.config import settings
        set_no = generate_sample_set_no()
        # 根据存储类型生成 set_path
        if is_minio_enabled():
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
        }
        rowcount = save_original_sample_set(data)
        return {"code": 0, "message": "保存成功", "data": {"rowcount": rowcount, "setNo": set_no}}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"保存失败: {str(e)}"}


@router.post("/update-sample-set")
def update_sample_set_api(req: UpdateSampleSetRequest):
    """更新原始样本集（不允许修改 set_name 和 type_code，不更新 version）"""
    try:
        if not req.setNo:
            return {"code": 1, "message": "样本集编号不能为空"}
        data = {
            'setNo': req.setNo,
            'description': req.description,
            'businessSystem': req.businessSystem,
            'sampleFieldCode': req.sampleFieldCode,
        }
        rowcount = update_original_sample_set(data)
        if rowcount == 0:
            return {"code": 1, "message": "未找到对应样本集"}
        return {"code": 0, "message": "更新成功"}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"更新失败: {str(e)}"}


@router.get("/get-samples")
def get_samples_api(setNo: str = Query(..., description="样本集编号")):
    try:
        rows = query_original_sample_info(setNo)
        data = [_row_to_camel(row) for row in rows]
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/get-classes")
def get_classes_api(setNo: str = Query(..., description="样本集编号")):
    """读取样本集目录下的 classes.txt，返回标签列表"""
    try:
        row = get_original_sample_set_path(setNo)
        if not row:
            return {"code": 0, "data": []}
        set_path = row.get("set_path")
        if not set_path:
            return {"code": 0, "data": []}
        classes_file = os.path.join(set_path, "classes.txt")
        if not os.path.isfile(classes_file):
            return {"code": 0, "data": []}
        classes = []
        with open(classes_file, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    classes.append(name)
        return {"code": 0, "data": classes}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"读取标签失败: {str(e)}"}


@router.get("/get-samples-by-labels")
def get_samples_by_labels_api(
    setNo: str = Query(..., description="样本集编号"),
    labels: str = Query("", description="标签列表，逗号分隔"),
):
    """根据标签筛选样本：读取样本集目录下的 classes.txt 和每张图片同名 .txt 标注，
    返回包含指定标签的样本列表"""
    try:
        if not labels:
            return {"code": 0, "data": []}

        selected_labels = set(lab.strip() for lab in labels.split(",") if lab.strip())
        if not selected_labels:
            return {"code": 0, "data": []}

        row = get_original_sample_set_path(setNo)
        if not row:
            return {"code": 0, "data": []}
        set_path = row.get("set_path")
        if not set_path:
            return {"code": 0, "data": []}

        # 读取 classes.txt 构建 class_id -> class_name 映射
        classes_file = os.path.join(set_path, "classes.txt")
        class_map = {}
        if os.path.isfile(classes_file):
            with open(classes_file, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    name = line.strip()
                    if name:
                        class_map[idx] = name

        # 找出选中标签对应的 class_id 集合
        selected_ids = {cid for cid, cname in class_map.items() if cname in selected_labels}

        # 遍历目录下所有 .txt 标注文件（排除 classes.txt），检查是否包含选中标签的 class_id
        matched_filenames = set()
        IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
        for fname in os.listdir(set_path):
            if fname.lower() == "classes.txt" or not fname.lower().endswith(".txt"):
                continue
            txt_path = os.path.join(set_path, fname)
            if not os.path.isfile(txt_path):
                continue
            base_name = os.path.splitext(fname)[0]
            has_image = any(os.path.isfile(os.path.join(set_path, base_name + ext)) for ext in IMAGE_EXTS)
            if not has_image:
                continue
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if parts:
                            try:
                                cid = int(parts[0])
                                if cid in selected_ids:
                                    for ext in IMAGE_EXTS:
                                        img_name = base_name + ext
                                        if os.path.isfile(os.path.join(set_path, img_name)):
                                            matched_filenames.add(img_name)
                                    break
                            except ValueError:
                                continue
            except Exception:
                continue

        if not matched_filenames:
            return {"code": 0, "data": []}

        # 从全部样本中筛选出匹配的样本
        rows = query_original_sample_info(setNo)
        data = []
        for r in rows:
            sample_name = r.get("sample_name", "")
            if sample_name in matched_filenames:
                data.append(_row_to_camel(r))
        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("接口异常")
        return {"code": 1, "message": f"标签筛选失败: {str(e)}"}


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
def get_annotations(sampleNo: str = Query(..., description="样本编号")):
    """获取 YOLO 标注信息：原始样本不涉及标注，直接返回无标注"""
    return {"code": 0, "data": {"hasAnnotations": False}}


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
    """下载原始样本集：查询样本集下所有样本文件，打成 zip 压缩包返回

    原始样本管理不涉及标注 txt / classes.txt，仅下载图片文件。
    - 本地模式：直接读取磁盘文件
    - MinIO 模式：从 MinIO 下载图片二进制
    """
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

            arc_name = os.path.basename(file_path)
            if arc_name in added_names:
                base, ext = os.path.splitext(arc_name)
                idx = 1
                while f"{base}_{idx}{ext}" in added_names:
                    idx += 1
                arc_name = f"{base}_{idx}{ext}"
            added_names.add(arc_name)
            zf.writestr(arc_name, image_bytes)

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
    """上传原始样本文件

    - 原始样本管理仅上传图片，不涉及 classes.txt 和标注 txt 文件
    - 本地模式：保存到 sample_upload_dir/setName/ 目录，写入 s_original_sample_info
    - MinIO 模式：上传到 MinIO，对象 ID 写入 s_original_sample_info.file_path
    """
    from app.core.config import settings
    from app.services.sample_import_service import _get_unique_filename, _get_unique_filename_for_minio

    use_minio = is_minio_enabled()
    target_dir = None
    if not use_minio:
        target_dir = os.path.join(settings.sample_upload_dir, setName)
        os.makedirs(target_dir, exist_ok=True)

    success_count = 0
    errors = []
    # MinIO 模式下预填入桶内已有对象名，避免覆盖
    if use_minio:
        used_names = minio_list_object_names(setNo)
    else:
        used_names = set()

    for file in files:
        if not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        # 原始样本仅上传图片，跳过 .txt 文件（如有）
        if ext == '.txt':
            continue

        # 生成唯一文件名（MinIO 模式仅检查 used_names，本地模式同时检查磁盘）
        if use_minio:
            unique_name = _get_unique_filename_for_minio(file.filename, used_names)
        else:
            unique_name = _get_unique_filename(target_dir, file.filename, used_names)
        used_names.add(unique_name)

        try:
            content = await file.read()
            # 保存文件并得到 file_path
            if use_minio:
                content_type_map = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                    ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
                    ".tif": "image/tiff", ".tiff": "image/tiff",
                }
                ct = content_type_map.get(ext, "application/octet-stream")
                file_path = minio_upload_image(setNo, unique_name, content, content_type=ct)
            else:
                file_path = os.path.join(target_dir, unique_name)
                with open(file_path, "wb") as f:
                    f.write(content)

            # 原始样本不涉及标注，label_flag 固定为 0
            insert_original_sample_info(
                set_no=setNo,
                sample_name=unique_name,
                suffix=ext,
                type_code=typeCode,
                file_path=file_path,
                file_size=len(content),
                label_flag=0,
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
    """批量导入：上传单个 ZIP，解压图片导入样本集

    - 原始样本管理仅上传图片，不涉及 classes.txt 和标注 txt 文件
    - 图片保存到本地或上传到 MinIO
    - .txt 标注文件直接跳过（write_txt_to_db=False）
    - 大文件采用流式写入临时文件再解压，避免一次性读入内存
    """
    from app.core.config import settings
    from app.services.sample_import_service import extract_zip_and_import

    if typeCode != "05":
        return {"code": 1, "message": "批量导入仅支持图片类型（05）样本集"}

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
            insert_callback=insert_original_sample_info,
            zip_path=tmp_path,
            use_minio=use_minio,
            write_txt_to_db=False,
            update_set_labels_callback=None,
        )
        msg = (f"成功导入 {result['image_count']} 张图片，"
               f"跳过 {result['skipped_count']} 个文件")
        if result["errors"]:
            msg += f"，失败 {len(result['errors'])} 个: {'; '.join(result['errors'][:5])}"
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
