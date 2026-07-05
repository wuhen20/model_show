from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from app.core.database import query_code_dict, query_sample_set, query_sample_info, save_sample_set, sample_statistic, sample_trend, query_audio_text, update_sample_score, insert_sample_info, update_label_think, generate_task_no, query_data_collect_task, save_data_collect_task, save_data_collect_task_det, query_data_collect_task_det, update_data_collect_task_det, get_task_det_raw, update_task_status, insert_collect_log, append_collect_log, finish_collect_log, query_collect_log, query_all_scheduled_tasks, get_task_execute_type, update_task_execute_type, delete_data_collect_task, execute_source_sql, save_query_result_to_desktop, query_target_table_columns, query_col_map, save_col_map, write_to_target_table
import os
import io
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

    if not task_name:
        return {"code": 1, "message": "任务名称不能为空"}
    if execute_type not in ("01", "02"):
        return {"code": 1, "message": "执行方式无效，应为 01-手动 或 02-定时"}
    if execute_type == "02" and not cron_formula:
        return {"code": 1, "message": "执行方式为定时时，cron 表达式不能为空"}

    try:
        task_no = generate_task_no()
        save_data_collect_task(task_no, task_name, remark, execute_type, cron_formula)

        # 定时任务：保存成功后注册到调度器
        if execute_type == "02":
            from app.services.scheduler_service import add_scheduled_task
            add_scheduled_task(task_no, cron_formula)

        return {"code": 0, "message": "保存成功", "data": {"taskNo": task_no}}
    except Exception as e:
        logger.exception("接口异常")
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
        logger.exception("接口异常")
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
    source_db_name = payload.get("sourceDbName", "").strip()
    target_table = payload.get("targetTable", "").strip()
    collect_sql = payload.get("collectSql", "").strip()
    source_db_auth = payload.get("sourceDbAuth", "").strip()

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
    """执行数据采集任务的核心逻辑：连接源数据库执行SQL，通过字段映射写入目标表。

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


@router.post("/execute-collect-task")
def execute_collect_task_api(req: ExecuteCollectTaskRequest):
    """执行数据采集任务：连接源数据库执行SQL，通过字段映射写入目标表"""
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
