"""样本数据清洗任务接口"""
import json
import logging
import os
import sys
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from fastapi import APIRouter, Query, UploadFile, File
from pydantic import BaseModel

logger = logging.getLogger("app.clean")

from app.core.database import (
    generate_clean_task_no,
    generate_sample_no,
    get_connection,
    _execute,
    _select_all_from,
)
from app.core.db_sample import (
    batch_insert_sample_info,
    insert_original_sample_info,
    batch_insert_original_sample_info,
    delete_original_sample_info_by_path,
    get_original_sample_set_path,
    query_original_sample_file_paths,
    query_original_sample_set_by_type,
    apply_sample_set_version_change,
    query_sample_set_options,
    query_original_samples,
)
from app.core.db_clean import (
    query_data_clean_tasks,
    save_data_clean_task,
    save_data_clean_task_nodes,
    query_data_clean_task_detail,
    delete_data_clean_task,
    query_database_tables,
    query_clean_table_columns,
    get_clean_task_raw,
    update_clean_task_status,
    insert_clean_log,
    append_clean_log,
    finish_clean_log,
    finish_clean_task_and_log,
    query_clean_log,
    query_clean_results,
    query_pic_clean_type_dict,
    insert_clean_pic_record,
    insert_clean_pic_records_batch,
    query_clean_pic_records,
    delete_clean_pic_records,
)
from app.services.sample_minio_service import (
    is_minio_path, download_image, upload_image, delete_object,
)

router = APIRouter()


class SaveCleanTaskRequest(BaseModel):
    taskName: str
    remark: str = ""
    sampleType: str = ""
    originalSampleSetNo: str = ""
    cleanTypes: str = ""


class SaveCleanTaskNodesRequest(BaseModel):
    taskNo: str
    nodes: list[dict]


class DeleteCleanTaskRequest(BaseModel):
    taskNo: str


class ExecuteCleanTaskRequest(BaseModel):
    taskNo: str


def _to_camel_dict(d: dict) -> dict:
    """snake_case → camelCase"""
    result = {}
    for k, v in d.items():
        parts = k.split("_")
        camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
        result[camel] = v
    return result


@router.get("/query-clean-tasks")
def query_clean_tasks_api():
    """查询清洗任务列表"""
    try:
        rows = query_data_clean_tasks()
        tasks = []
        for row in rows:
            task = _to_camel_dict(row)
            status_code = str(row.get("task_status") or "01")
            flag = row.get("last_execute_flag")
            task["taskStatusCode"] = status_code
            task["taskStatusName"] = {
                "01": "未执行", "02": "执行中", "03": "已完成", "04": "失败"
            }.get(status_code, "未执行")
            task["lastExecuteFlagCode"] = flag
            task["lastExecuteFlagName"] = {0: "未执行", 1: "成功", 2: "失败"}.get(flag, "未执行")
            tasks.append(task)
        return {"code": 0, "data": tasks}
    except Exception as e:
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.post("/save-clean-task")
def save_clean_task_api(req: SaveCleanTaskRequest):
    """新增清洗任务"""
    task_name = req.taskName.strip()
    if not task_name:
        return {"code": 1, "message": "任务名称不能为空"}
    try:
        task_no = generate_clean_task_no()
        save_data_clean_task(task_no, task_name, req.remark, req.sampleType)

        # 图片类型：同时保存节点配置到 s_data_clean_task_node
        if req.sampleType == "05" and req.originalSampleSetNo:
            # 查询原始样本集名称
            set_name = ""
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    _execute(cursor, "SELECT set_name FROM s_original_sample_set WHERE set_no = %s", (req.originalSampleSetNo,))
                    row = cursor.fetchone()
                    if row:
                        set_name = row.get("set_name") if isinstance(row, dict) else row[0]
            finally:
                conn.close()

            # 保存节点：node_id=原始样本集编号, node_name=原始样本集名称, node_config=清洗类型编码
            nodes_to_save = [{
                "nodeId": req.originalSampleSetNo,
                "nodeType": "image_clean",
                "nodeName": set_name or req.originalSampleSetNo,
                "nodeConfig": req.cleanTypes,
                "posX": 0,
                "posY": 0,
                "prevNodeId": None,
            }]
            save_data_clean_task_nodes(task_no, nodes_to_save)

        return {"code": 0, "message": "保存成功", "data": {"taskNo": task_no}}
    except Exception as e:
        return {"code": 1, "message": f"保存失败: {str(e)}"}


@router.get("/query-clean-task-detail")
def query_clean_task_detail_api(taskNo: str = Query(..., description="任务编号")):
    """查询清洗任务详情（含节点）"""
    try:
        task = query_data_clean_task_detail(taskNo)
        if not task:
            return {"code": 1, "message": "未找到任务"}
        # 主表字段转 camelCase
        result = _to_camel_dict(task)
        status_code = str(task.get("task_status") or "01")
        result["taskStatusCode"] = status_code
        result["taskStatusName"] = {
            "01": "未执行", "02": "执行中", "03": "已完成", "04": "失败"
        }.get(status_code, "未执行")
        # 节点列表转 camelCase + 解析 node_config
        nodes = []
        for node in task.get("nodes", []):
            n = _to_camel_dict(node)
            config_str = node.get("node_config") or ""
            # image_clean 节点的 node_config 是逗号分隔的编码字符串，不是 JSON
            if node.get("node_type") == "image_clean":
                n["nodeConfig"] = config_str
            else:
                try:
                    n["nodeConfig"] = json.loads(config_str) if config_str else {}
                except (json.JSONDecodeError, TypeError):
                    n["nodeConfig"] = {}
            nodes.append(n)
        result["nodes"] = nodes
        return {"code": 0, "data": result}
    except Exception as e:
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.post("/save-clean-task-nodes")
def save_clean_task_nodes_api(req: SaveCleanTaskNodesRequest):
    """保存清理任务流程节点"""
    task_no = req.taskNo.strip()
    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}
    try:
        # nodeConfig 序列化为 JSON 字符串存储
        nodes_to_save = []
        for node in req.nodes:
            config = node.get("nodeConfig", {})
            if isinstance(config, dict):
                config_str = json.dumps(config, ensure_ascii=False)
            else:
                config_str = str(config)
            nodes_to_save.append({
                "nodeId": node.get("nodeId", ""),
                "nodeType": node.get("nodeType", ""),
                "nodeName": node.get("nodeName", ""),
                "nodeConfig": config_str,
                "posX": node.get("posX", 0),
                "posY": node.get("posY", 0),
                "prevNodeId": node.get("prevNodeId", None),
            })
        save_data_clean_task_nodes(task_no, nodes_to_save)
        return {"code": 0, "message": "保存成功"}
    except Exception as e:
        return {"code": 1, "message": f"保存失败: {str(e)}"}


@router.post("/delete-clean-task")
def delete_clean_task_api(req: DeleteCleanTaskRequest):
    """删除清理任务"""
    task_no = req.taskNo.strip()
    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}
    try:
        delete_data_clean_task(task_no)
        return {"code": 0, "message": "删除成功"}
    except Exception as e:
        return {"code": 1, "message": f"删除失败: {str(e)}"}


@router.get("/query-database-tables")
def query_database_tables_api():
    """查询当前数据库所有表名"""
    try:
        tables = query_database_tables()
        return {"code": 0, "data": tables}
    except Exception as e:
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/query-clean-table-columns")
def query_clean_table_columns_api(tableName: str = Query(..., description="表名")):
    """查询指定表的字段列表"""
    try:
        columns = query_clean_table_columns(tableName)
        result = []
        for col in columns:
            result.append({
                "fieldName": col.get("field", col.get("Field", "")),
                "fieldType": col.get("col_type", col.get("Type", "")),
                "fieldKey": col.get("key_col", col.get("Key", "")),
                "fieldNull": "",
            })
        return {"code": 0, "data": result}
    except Exception as e:
        return {"code": 1, "message": f"查询失败: {str(e)}"}


def _execute_image_clean_task(task: dict, task_no: str, log_id: int):
    """执行图像样本清洗任务（自实现版本，兼容本地与 MinIO 存储）

    原 cleanvision 实现已备份至 app/services/_cleanvision_backup.py，
    新实现详见 app/services/image_clean_service.py。
    """
    nodes = task.get("nodes", [])
    if not nodes:
        # 更新日志为失败状态
        if log_id:
            finish_clean_task_and_log(task_no=task_no, task_status="04", last_execute_flag=2,
                                       record_id=log_id, execute_status="04",
                                       log_content="任务未配置清洗节点")
        return

    # 1. 从节点获取原始样本集编号和清洗类型编码
    image_node = None
    for node in nodes:
        if node.get("node_type") == "image_clean":
            image_node = node
            break
    if not image_node:
        if log_id:
            finish_clean_task_and_log(task_no=task_no, task_status="04", last_execute_flag=2,
                                       record_id=log_id, execute_status="04",
                                       log_content="未找到图像清洗节点")
        return

    set_no = image_node.get("node_id", "")
    clean_types_str = image_node.get("node_config") or ""
    if not set_no:
        if log_id:
            finish_clean_task_and_log(task_no=task_no, task_status="04", last_execute_flag=2,
                                       record_id=log_id, execute_status="04",
                                       log_content="清洗节点未关联原始样本集")
        return
    if not clean_types_str:
        if log_id:
            finish_clean_task_and_log(task_no=task_no, task_status="04", last_execute_flag=2,
                                       record_id=log_id, execute_status="04",
                                       log_content="未配置清洗类型")
        return

    clean_type_codes = [c.strip() for c in clean_types_str.split(",") if c.strip()]
    if not clean_type_codes:
        if log_id:
            finish_clean_task_and_log(task_no=task_no, task_status="04", last_execute_flag=2,
                                       record_id=log_id, execute_status="04",
                                       log_content="未配置清洗类型")
        return

    # 2. 委托给图像清洗服务执行
    from app.services.image_clean_service import execute_image_clean_task

    deps = {
        "update_clean_task_status": update_clean_task_status,
        "insert_clean_log": insert_clean_log,
        "append_clean_log": append_clean_log,
        "finish_clean_log": finish_clean_log,
        "finish_clean_task_and_log": finish_clean_task_and_log,
        "query_pic_clean_type_dict": query_pic_clean_type_dict,
        "query_original_samples": query_original_samples,
        "insert_clean_pic_record": insert_clean_pic_record,
        "insert_clean_pic_records_batch": insert_clean_pic_records_batch,
        "delete_original_sample_info_by_path": delete_original_sample_info_by_path,
    }
    execute_image_clean_task(task, task_no, set_no, clean_type_codes, deps, log_id)


def _execute_timeseries_clean_task(task: dict, task_no: str, log_id: int):
    """执行时序清洗任务（后台线程），包装 pipeline 的同步调用

    execute_clean_pipeline 内部已自行处理成功/失败的状态更新，
    此处 try/except 仅防止线程崩溃时无人收场。
    """
    from app.services.clean_operators.pipeline import execute_clean_pipeline
    try:
        result = execute_clean_pipeline(task, task_no, log_id)
        logger.info(f"时序清洗任务 {task_no} 后台执行完成: {result.get('message', '')}")
    except Exception as e:
        logger.exception(f"时序清洗任务 {task_no} 后台执行异常（pipeline 外部未捕获）")
        # 异常时更新日志状态
        if log_id:
            try:
                finish_clean_task_and_log(
                    task_no=task_no, task_status="04", last_execute_flag=2,
                    record_id=log_id, execute_status="04",
                    log_content=f"执行异常：{str(e)}"
                )
            except Exception:
                pass


@router.post("/execute-clean-task")
def execute_clean_task_api(req: ExecuteCleanTaskRequest):
    """执行清洗任务（异步：启动后台线程，立即返回，前端轮询任务状态）

    图片类型和时序类型均采用异步执行模式：
    - 启动前先将任务状态更新为"执行中"(02)
    - 创建"执行中"状态的日志记录，确保前端轮询时能立即看到当前执行记录
    - 后台线程执行清洗逻辑，使用已创建的 log_id
    - 接口立即返回，前端通过查询执行记录轮询进度
    """
    task_no = req.taskNo.strip()
    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}

    task = get_clean_task_raw(task_no)
    if not task:
        return {"code": 1, "message": "未找到任务"}

    # 防止重复执行：检查任务状态是否已处于执行中
    current_status = str(task.get("task_status") or "")
    if current_status == "02":
        return {"code": 1, "message": f"任务 {task_no} 正在执行中，请勿重复触发"}

    sample_type = str(task.get("sample_type") or "")

    # 先将任务状态更新为"执行中"，确保前端立即看到状态变化
    update_clean_task_status(task_no, "02")

    # 创建"执行中"状态的日志记录，确保前端轮询时能立即看到当前执行记录
    init_log = f"开始执行清洗任务：{task.get('task_name', task_no)}"
    log_id = insert_clean_log(task_no, init_log)

    import threading

    if sample_type == "05":
        # 图片类型清洗任务
        thread = threading.Thread(
            target=_execute_image_clean_task,
            args=(task, task_no, log_id),
            name=f"image_clean_{task_no}",
            daemon=True,
        )
        thread.start()
        logger.info(f"图像清洗任务 {task_no} 已启动后台线程 {thread.ident}")
    else:
        # 时序类型清洗任务
        thread = threading.Thread(
            target=_execute_timeseries_clean_task,
            args=(task, task_no, log_id),
            name=f"ts_clean_{task_no}",
            daemon=True,
        )
        thread.start()
        logger.info(f"时序清洗任务 {task_no} 已启动后台线程 {thread.ident}")

    return {
        "code": 0,
        "message": "任务已启动，请通过执行记录查看进度",
        "data": {
            "async": True,
            "taskNo": task_no,
            "fileName": "",
            "filePath": "",
            "resultCount": 0,
        },
    }


@router.get("/query-clean-log")
def query_clean_log_api(taskNo: str = Query(..., description="任务编号")):
    """查询清洗任务的执行记录列表"""
    try:
        rows = query_clean_log(taskNo)
        logs = []
        for row in rows:
            log = _to_camel_dict(row)
            status = str(row.get("execute_status") or "")
            log["executeStatusCode"] = status
            log["executeStatusName"] = {
                "02": "执行中", "03": "成功", "04": "失败"
            }.get(status, "未知")
            logs.append(log)
        return {"code": 0, "data": logs}
    except Exception as e:
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/query-clean-results")
def query_clean_results_api():
    """查询清洗结果列表（仅已完成 execute_status=03 的记录）"""
    try:
        rows = query_clean_results()
        results = []
        for row in rows:
            item = _to_camel_dict(row)
            results.append(item)
        return {"code": 0, "data": results}
    except Exception as e:
        logger.exception("查询清洗结果异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


# 清洗结果文件内存缓存：{record_id: {"mtime": float, "data": dict, "loaded_at": float}}
# 同一文件首次访问时全量解析，后续分页请求直接从缓存切片，避免重复IO和解析
_clean_result_cache: dict = {}
_CLEAN_CACHE_MAX = 10  # 最多缓存10个文件，防止内存占用过大
import time as _time


def _load_clean_result_with_cache(record_id: int, file_path: str) -> dict:
    """加载清洗结果JSON，带缓存校验的内存缓存。

    本地文件用 mtime 校验，MinIO 对象用 size 校验。
    未变更时直接返回缓存，变更后重新加载。
    """
    if is_minio_path(file_path):
        # MinIO 模式：用对象 size 作为缓存校验
        try:
            from app.services.sample_minio_service import get_image_size
            obj_size = get_image_size(file_path)
        except Exception:
            obj_size = -1

        cached = _clean_result_cache.get(record_id)
        if cached and cached.get("size") == obj_size:
            return cached["data"]

        from app.services.sample_minio_service import download_image
        content = download_image(file_path)
        data = json.loads(content.decode("utf-8"))

        # 缓存淘汰
        if len(_clean_result_cache) >= _CLEAN_CACHE_MAX:
            oldest_key = min(
                _clean_result_cache.keys(),
                key=lambda k: _clean_result_cache[k].get("loaded_at", 0),
            )
            _clean_result_cache.pop(oldest_key, None)

        _clean_result_cache[record_id] = {
            "size": obj_size,
            "data": data,
            "loaded_at": _time.time(),
        }
        return data
    else:
        # 本地模式：用 mtime 校验
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            mtime = 0

        cached = _clean_result_cache.get(record_id)
        if cached and cached.get("mtime") == mtime:
            return cached["data"]

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 缓存淘汰
        if len(_clean_result_cache) >= _CLEAN_CACHE_MAX:
            oldest_key = min(
                _clean_result_cache.keys(),
                key=lambda k: _clean_result_cache[k].get("loaded_at", 0),
            )
            _clean_result_cache.pop(oldest_key, None)

        _clean_result_cache[record_id] = {
            "mtime": mtime,
            "data": data,
            "loaded_at": _time.time(),
        }
        return data


@router.get("/view-clean-result")
def view_clean_result_api(
    recordId: int = Query(..., description="记录ID"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(20, ge=1, le=500, description="每页条数，最大500"),
):
    """查看清洗结果 JSON 文件内容（分页返回）。
    首次请求加载并缓存整个文件，后续分页请求从缓存切片返回。"""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT file_path, file_name FROM s_data_clean_log WHERE record_id = %s"
                _execute(cursor, sql, (recordId,))
                row = cursor.fetchone()
        finally:
            conn.close()

        if not row or not row.get("file_path"):
            return {"code": 1, "message": "清洗结果文件不存在"}

        file_path = row["file_path"]
        # MinIO 路径无需检查本地文件存在性，本地路径需要检查
        if not is_minio_path(file_path) and not os.path.exists(file_path):
            return {"code": 1, "message": f"文件不存在：{file_path}"}

        # 带缓存加载
        data = _load_clean_result_with_cache(recordId, file_path)

        all_rows = data.get("rows", []) or []
        total = len(all_rows)
        # 切片当前页
        start = (page - 1) * pageSize
        end = start + pageSize
        page_rows = all_rows[start:end]

        return {
            "code": 0,
            "data": {
                "taskNo": data.get("taskNo", ""),
                "taskName": data.get("taskName", ""),
                "executeTime": data.get("executeTime", ""),
                "totalCount": data.get("totalCount", 0),
                "removedCount": data.get("removedCount", 0),
                "resultCount": data.get("resultCount", total),
                "columns": data.get("columns", []),
                "rows": page_rows,
                "total": total,
                "page": page,
                "pageSize": pageSize,
            },
        }
    except Exception as e:
        logger.exception("查看清洗结果异常")
        return {"code": 1, "message": f"查看失败: {str(e)}"}


@router.get("/download-clean-result")
def download_clean_result_api(recordId: int = Query(..., description="记录ID"),
                               format: str = Query("json", description="下载格式：json / excel")):
    """下载清洗结果文件，支持 JSON 和 Excel 格式"""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT file_path, file_name, task_no FROM s_data_clean_log WHERE record_id = %s"
                _execute(cursor, sql, (recordId,))
                row = cursor.fetchone()
        finally:
            conn.close()

        if not row or not row.get("file_path"):
            return {"code": 1, "message": "清洗结果文件不存在"}

        file_path = row["file_path"]
        # MinIO 路径无需检查本地文件存在性，本地路径需要检查
        if not is_minio_path(file_path) and not os.path.exists(file_path):
            return {"code": 1, "message": f"文件不存在：{file_path}"}

        task_no = row.get("task_no", "unknown")
        from urllib.parse import quote

        # 加载 JSON 数据（自动适配本地/MinIO）
        data = _load_clean_result_with_cache(recordId, file_path)

        if format == "excel":
            # JSON 转 Excel
            import pandas as pd
            import io as _io
            columns = data.get("columns", [])
            rows = data.get("rows", [])
            df = pd.DataFrame(rows, columns=columns) if columns else pd.DataFrame(rows)

            output = _io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="清洗结果")
            output.seek(0)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{task_no}_清洗结果_{timestamp}.xlsx"
            encoded_filename = quote(filename)
            headers = {
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers=headers,
            )
        elif is_minio_path(file_path):
            # MinIO 模式：下载 JSON bytes 返回
            from app.services.sample_minio_service import download_image
            from fastapi.responses import StreamingResponse
            import io as _io
            content = download_image(file_path)
            filename = row.get("file_name") or f"{task_no}_清洗结果.json"
            encoded_filename = quote(filename)
            headers = {
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
            return StreamingResponse(
                _io.BytesIO(content),
                media_type="application/json",
                headers=headers,
            )
        else:
            # 本地模式：直接返回文件
            filename = row.get("file_name") or f"{task_no}_清洗结果.json"
            encoded_filename = quote(filename)
            headers = {
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
            from fastapi.responses import FileResponse
            return FileResponse(
                file_path,
                media_type="application/json",
                filename=filename,
                headers=headers,
            )
    except Exception as e:
        logger.exception("下载清洗结果异常")
        return {"code": 1, "message": f"下载失败: {str(e)}"}


@router.get("/view-clean-result-by-path")
def view_clean_result_by_path_api(filePath: str = Query(..., description="文件路径")):
    """通过文件路径查看清洗结果 JSON 内容"""
    try:
        if is_minio_path(filePath):
            # MinIO 模式：从对象存储下载并解析
            from app.services.sample_minio_service import download_image
            content = download_image(filePath)
            data = json.loads(content.decode("utf-8"))
        else:
            # 本地模式
            if not os.path.exists(filePath):
                return {"code": 1, "message": f"文件不存在：{filePath}"}
            with open(filePath, "r", encoding="utf-8") as f:
                data = json.load(f)

        return {"code": 0, "data": data}
    except Exception as e:
        logger.exception("查看清洗结果异常")
        return {"code": 1, "message": f"查看失败: {str(e)}"}


@router.get("/download-clean-result-by-path")
def download_clean_result_by_path_api(filePath: str = Query(..., description="文件路径")):
    """通过文件路径下载清洗结果 JSON 文件"""
    try:
        from urllib.parse import quote

        if is_minio_path(filePath):
            # MinIO 模式：从对象存储下载
            from app.services.sample_minio_service import download_image
            from fastapi.responses import StreamingResponse
            import io as _io
            content = download_image(filePath)
            # 从 MinIO 路径提取文件名
            filename = filePath.rstrip("/").split("/")[-1]
            encoded_filename = quote(filename)
            headers = {
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
            return StreamingResponse(
                _io.BytesIO(content),
                media_type="application/json",
                headers=headers,
            )
        else:
            # 本地模式
            if not os.path.exists(filePath):
                return {"code": 1, "message": f"文件不存在：{filePath}"}

            filename = os.path.basename(filePath)
            encoded_filename = quote(filename)
            headers = {
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
            from fastapi.responses import FileResponse
            return FileResponse(
                filePath,
                media_type="application/json",
                filename=filename,
                headers=headers,
            )
    except Exception as e:
        logger.exception("下载清洗结果异常")
        return {"code": 1, "message": f"下载失败: {str(e)}"}


@router.get("/sample-set-options")
def sample_set_options_api(typeCode: str = Query("", description="样本类型编码，为空则返回全部")):
    """获取样本集下拉选项，可按类型过滤"""
    try:
        rows = query_sample_set_options(typeCode)
        # 转为 camelCase 格式
        options = [_to_camel_dict(row) for row in rows]
        return {"code": 0, "data": options}
    except Exception as e:
        logger.exception("查询样本集选项异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/query-pic-clean-types")
def query_pic_clean_types_api():
    """查询图像清洗类型字典（含 cleanvision 编码 spare1）"""
    try:
        rows = query_pic_clean_type_dict()
        result = []
        for row in rows:
            result.append({
                "codeValue": row.get("CODE_VALUE", ""),
                "codeName": row.get("CODE_NAME", ""),
                "spare1": row.get("SPARE1", ""),
            })
        return {"code": 0, "data": result}
    except Exception as e:
        logger.exception("查询图像清洗类型字典异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/query-clean-pics")
def query_clean_pics_api(
    taskNo: str = Query(None, description="清洗任务编号"),
    cleanLogId: int = Query(None, description="清洗执行记录ID（优先级高于 taskNo）"),
):
    """查询图像清洗任务被清洗的图片记录（含清洗原因）

    优先按 cleanLogId 查询（精确匹配某次执行结果），否则按 taskNo 查询（兼容旧逻辑）。
    """
    try:
        rows = query_clean_pic_records(task_no=taskNo, clean_log_id=cleanLogId)
        pics = []
        for row in rows:
            pics.append({
                "recordId": row.get("record_id"),
                "taskNo": row.get("task_no", ""),
                "cleanType": row.get("clean_type", ""),
                "cleanTypeName": row.get("clean_type_name", "") or row.get("clean_type", ""),
                "fileName": row.get("file_name", ""),
                "filePath": row.get("file_path", ""),
                "cleanLogId": row.get("clean_log_id"),
                "repeatFileName": row.get("repeat_file_name", "") or "",
                "repeatFilePath": row.get("repeat_file_path", "") or "",
            })
        return {"code": 0, "data": pics}
    except Exception as e:
        logger.exception("查询图像清洗图片记录异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/serve-image")
def serve_image_api(filePath: str = Query(..., description="图片文件路径")):
    """读取并返回图片文件，用于展示被清洗的图片（支持本地路径和 MinIO 路径）"""
    from fastapi.responses import Response

    content_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
        ".tif": "image/tiff", ".tiff": "image/tiff",
    }

    # MinIO 路径
    if is_minio_path(filePath):
        try:
            image_bytes = download_image(filePath)
            if not image_bytes:
                return {"code": 1, "message": f"MinIO 图片不存在: {filePath}"}
            ext = os.path.splitext(filePath)[1].lower()
            media_type = content_types.get(ext, "application/octet-stream")
            return Response(content=image_bytes, media_type=media_type)
        except Exception as e:
            logger.exception(f"从 MinIO 读取图片失败: {filePath}")
            return {"code": 1, "message": f"读取图片失败: {str(e)}"}

    # 本地路径
    file_path = os.path.normpath(filePath)
    if not os.path.isfile(file_path):
        return {"code": 1, "message": f"图片文件不存在: {file_path}"}
    ext = os.path.splitext(file_path)[1].lower()
    media_type = content_types.get(ext, "application/octet-stream")
    from fastapi.responses import FileResponse
    return FileResponse(file_path, media_type=media_type)


class RollbackCleanPicsRequest(BaseModel):
    taskNo: str
    cleanLogId: int = None  # 精确回滚某次执行的结果（优先级高于 taskNo）


@router.post("/rollback-clean-pics")
def rollback_clean_pics_api(req: RollbackCleanPicsRequest):
    """回滚图像清洗：将隔离目录中的图片移回原始样本集目录，并恢复 s_original_sample_info 记录

    支持 cleanLogId 精确回滚某次执行结果，避免多次执行后回滚错误。
    """
    task_no = req.taskNo.strip()
    clean_log_id = req.cleanLogId
    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}

    try:
        # 1. 查询任务节点，获取原始样本集编号（set_no）
        task = get_clean_task_raw(task_no)
        if not task:
            return {"code": 1, "message": "未找到清洗任务"}

        set_no = ""
        for node in task.get("nodes", []):
            if node.get("node_type") == "image_clean":
                set_no = node.get("node_id", "")
                break
        if not set_no:
            return {"code": 1, "message": "清洗任务未关联原始样本集，无法回滚"}

        # 2. 查询原始样本集的 set_path 和 type_code
        set_row = get_original_sample_set_path(set_no)
        if not set_row:
            return {"code": 1, "message": "原始样本集不存在"}
        set_path = set_row.get("set_path", "") or ""
        type_code = set_row.get("type_code", "") or "05"

        # 3. 查询被清洗图片记录（优先用 cleanLogId 精确查询）
        pic_rows = query_clean_pic_records(task_no=task_no, clean_log_id=clean_log_id)
        if not pic_rows:
            return {"code": 1, "message": "无可回滚的清洗图片记录"}

        # 按 file_path(隔离路径) 去重，保留 file_name
        unique_files = {}
        for row in pic_rows:
            iso_path = row.get("file_path", "")
            file_name = row.get("file_name", "")
            if iso_path and iso_path not in unique_files:
                unique_files[iso_path] = file_name

        # 4. 并行处理 MinIO 下载+上传（本地模式 move 很快，串行即可），
        #    收集成功项后统一批量插入数据库
        restored_count = 0
        skipped_count = 0
        errors = []

        # 分离 MinIO 和本地两类任务
        minio_tasks = []   # [(iso_path, file_name)]
        local_tasks = []   # [(iso_path, file_name)]
        for iso_path, file_name in unique_files.items():
            if is_minio_path(iso_path):
                minio_tasks.append((iso_path, file_name))
            else:
                local_tasks.append((iso_path, file_name))

        # 成功恢复的记录，供批量插入
        restored_records = []

        # ---------- MinIO 模式：线程池并行下载+上传 ----------
        def _restore_minio(task):
            iso_path, file_name = task
            if not set_path:
                return ("skip", file_name, "原始样本集未配置 set_path")
            try:
                image_bytes = download_image(iso_path)
                if not image_bytes:
                    return ("skip", file_name, "隔离文件不存在")
                ext = os.path.splitext(file_name)[1].lower()
                ct_map = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                    ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
                }
                content_type = ct_map.get(ext, "application/octet-stream")
                new_path = upload_image(set_no, file_name, image_bytes, content_type=content_type)
                # 删除隔离对象
                try:
                    delete_object(iso_path)
                except Exception:
                    pass
                suffix = ext.lstrip(".").lower()
                file_size = len(image_bytes)
                return ("ok", {
                    "set_no": set_no,
                    "sample_name": file_name,
                    "suffix": suffix,
                    "type_code": type_code,
                    "file_path": new_path,
                    "file_size": file_size,
                }, None)
            except Exception as e_restore:
                return ("err", file_name, str(e_restore))

        if minio_tasks:
            max_workers = min(8, max(1, len(minio_tasks)))
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="rollback") as pool:
                futures = [pool.submit(_restore_minio, t) for t in minio_tasks]
                for fut in as_completed(futures):
                    status, payload, msg = fut.result()
                    if status == "ok":
                        restored_records.append(payload)
                    elif status == "skip":
                        skipped_count += 1
                        errors.append(f"{payload}: {msg}")
                    else:
                        skipped_count += 1
                        errors.append(f"{payload}: 恢复失败 - {msg}")

        # ---------- 本地模式：串行 move（同盘 rename 极快，无需并行） ----------
        for iso_path, file_name in local_tasks:
            if not set_path:
                errors.append(f"{file_name}: 原始样本集未配置 set_path，跳过")
                skipped_count += 1
                continue
            os.makedirs(set_path, exist_ok=True)
            iso_path_norm = os.path.normpath(iso_path)
            if not os.path.isfile(iso_path_norm):
                errors.append(f"{file_name}: 隔离文件不存在，跳过")
                skipped_count += 1
                continue

            restore_path = os.path.join(set_path, file_name)
            # 处理同名文件冲突
            if os.path.exists(restore_path):
                name, ext = os.path.splitext(file_name)
                idx = 1
                while os.path.exists(os.path.join(set_path, f"{name}_{idx}{ext}")):
                    idx += 1
                restore_path = os.path.join(set_path, f"{name}_{idx}{ext}")

            try:
                file_size = os.path.getsize(iso_path_norm)
                shutil.move(iso_path_norm, restore_path)
                suffix = os.path.splitext(file_name)[1].lstrip(".").lower()
                restored_records.append({
                    "set_no": set_no,
                    "sample_name": os.path.basename(restore_path),
                    "suffix": suffix,
                    "type_code": type_code,
                    "file_path": restore_path,
                    "file_size": file_size,
                })
            except Exception as e_restore:
                errors.append(f"{file_name}: 恢复失败 - {e_restore}")
                skipped_count += 1

        # ---------- 批量插入数据库记录 ----------
        if restored_records:
            try:
                batch_insert_original_sample_info(restored_records)
                restored_count = len(restored_records)
            except Exception as e_batch:
                logger.exception("批量插入恢复记录失败，回退到逐条插入")
                # 回退到逐条插入，保证健壮性
                for r in restored_records:
                    try:
                        insert_original_sample_info(
                            set_no=r["set_no"],
                            sample_name=r["sample_name"],
                            suffix=r["suffix"],
                            type_code=r["type_code"],
                            file_path=r["file_path"],
                            file_size=r["file_size"],
                        )
                        restored_count += 1
                    except Exception as e_one:
                        errors.append(f"{r.get('sample_name')}: 插入失败 - {e_one}")
                        skipped_count += 1

        # 5. 删除清洗图片记录
        delete_clean_pic_records(task_no=task_no, clean_log_id=clean_log_id)

        # 6. 尝试清理空的隔离目录（本地模式）
        from app.core.config import settings
        base_dir = getattr(settings, "sample_upload_dir", "")
        if base_dir:
            target_dir = os.path.join(base_dir, "clean_result", task_no)
            if os.path.isdir(target_dir):
                try:
                    if not os.listdir(target_dir):
                        os.rmdir(target_dir)
                except Exception:
                    pass

        msg = f"回滚完成，恢复 {restored_count} 张图片"
        if skipped_count:
            msg += f"，跳过 {skipped_count} 张"
        if errors:
            msg += f"，失败: {'; '.join(errors[:5])}"
        return {"code": 0, "message": msg, "data": {"restoredCount": restored_count, "skippedCount": skipped_count}}
    except Exception as e:
        logger.exception("回滚图像清洗异常")
        return {"code": 1, "message": f"回滚失败: {str(e)}"}


@router.get("/original-sample-set-options")
def original_sample_set_options_api(typeCode: str = Query("", description="样本类型编码，为空则返回全部")):
    """获取原始样本集下拉选项，可按类型过滤"""
    try:
        rows = query_original_sample_set_by_type(typeCode)
        options = []
        for row in rows:
            options.append({
                "setNo": row.get("set_no", ""),
                "setName": row.get("set_name", ""),
            })
        return {"code": 0, "data": options}
    except Exception as e:
        logger.exception("查询原始样本集选项异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


class ImportToSampleRequest(BaseModel):
    recordId: int
    setNo: str
    sampleName: str = ""
    majorVersionChange: bool = False
    versionRemark: str = ""


@router.post("/import-to-sample")
def import_to_sample_api(req: ImportToSampleRequest):
    """将清洗结果入库到样本信息表

    支持手动大版本变更：majorVersionChange=True 时大版本号 +1、小版本号归 0；
    否则小版本号 +1。versionRemark 为可选变更说明（最多 150 字）。
    """
    try:
        # 变更说明长度校验
        version_remark = (req.versionRemark or "").strip()
        if len(version_remark) > 150:
            return {"code": 1, "message": "变更说明不能超过 150 个字"}

        # 1. 获取清洗记录
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT l.file_path, l.file_name, l.task_no, t.sample_type, t.task_name
                    FROM s_data_clean_log l
                    LEFT JOIN s_data_clean_task t ON l.task_no = t.task_no
                    WHERE l.record_id = %s
                """
                _execute(cursor, sql, (req.recordId,))
                log_row = cursor.fetchone()
        finally:
            conn.close()

        if not log_row:
            return {"code": 1, "message": "清洗记录不存在"}
        if not log_row.get("file_path"):
            return {"code": 1, "message": "清洗结果文件路径为空"}

        # 2. 获取样本集信息
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT set_no, set_name, type_code, business_system FROM s_sample_set WHERE set_no = %s"
                _execute(cursor, sql, (req.setNo,))
                set_row = cursor.fetchone()
        finally:
            conn.close()

        if not set_row:
            return {"code": 1, "message": "所选样本集不存在"}

        # 3. 读取 JSON 文件获取数据行（支持本地和 MinIO 两种存储模式）
        file_path = log_row["file_path"]
        if is_minio_path(file_path):
            # MinIO 模式：下载对象内容
            from app.services.sample_minio_service import download_image as _minio_download
            try:
                content_bytes = _minio_download(file_path)
                if not content_bytes:
                    return {"code": 1, "message": f"文件不存在：{file_path}"}
            except Exception as e_dl:
                return {"code": 1, "message": f"文件不存在：{file_path}, 错误: {e_dl}"}
            data = json.loads(content_bytes.decode("utf-8"))
            file_size_bytes = len(content_bytes)
        else:
            # 本地模式
            if not os.path.exists(file_path):
                return {"code": 1, "message": f"文件不存在：{file_path}"}
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            file_size_bytes = os.path.getsize(file_path)

        columns = data.get("columns", [])
        rows = data.get("rows", [])
        if not rows:
            return {"code": 1, "message": "清洗结果无数据"}

        # 4. 确定类型编码：优先样本集的 type_code，其次任务的 sample_type
        type_code = set_row.get("type_code") or log_row.get("sample_type") or ""
        business_system = set_row.get("business_system") or ""
        file_name = log_row.get("file_name") or ""

        # 5. 将每行数据转为 JSON 字符串作为样本，批量插入
        # 格式化文件大小带单位
        if file_size_bytes < 1024:
            file_size = f"{file_size_bytes}B"
        elif file_size_bytes < 1024 * 1024:
            file_size = f"{file_size_bytes / 1024:.2f}KB"
        else:
            file_size = f"{file_size_bytes / (1024 * 1024):.2f}MB"
        suffix = "json"

        # 一个文件生成一条样本记录
        sample_no = generate_sample_no()
        # 使用用户输入的样本名称，若为空则使用文件名（去掉.json后缀）
        if req.sampleName.strip():
            sample_name = req.sampleName.strip()
        else:
            sample_name = file_name.replace(".json", "") if file_name.endswith(".json") else file_name

        # 结果数据数量
        result_count = len(rows)

        record = {
            "sample_no": sample_no,
            "sample_name": sample_name,
            "set_no": req.setNo,
            "type_code": type_code,
            "suffix": suffix,
            "business_system": business_system,
            "file_path": file_path,
            "file_size": file_size,
            "result_count": result_count,
        }

        batch_insert_sample_info([record])

        # 6. 记录版本变更（入库视为新增 1 条样本）
        #    时序清洗结果入库不使用 SAMPLE_MAJOR_VERSION_THRESHOLD 阈值：
        #    - 未勾选大版本变更：仅小版本号 +1
        #    - 勾选大版本变更：大版本号 +1、小版本号归 0
        ver_info = {"pre_version": "", "next_version": ""}
        try:
            ver = apply_sample_set_version_change(
                set_no=req.setNo,
                set_name=set_row.get("set_name") or "",
                added_count=1,
                manual_major=bool(req.majorVersionChange),
                manual_remark=version_remark,
                apply_threshold=False,
                sample_label="样本",
            )
            ver_info["pre_version"] = ver.get("pre_version", "")
            ver_info["next_version"] = ver.get("next_version", "")
        except Exception as ve:
            logger.exception("入库版本变更记录写入失败")
            # 版本变更失败不影响入库结果，仅记录异常

        msg = "入库成功"
        if ver_info["pre_version"] and ver_info["next_version"]:
            msg += f"，版本 {ver_info['pre_version']} → {ver_info['next_version']}"

        return {
            "code": 0,
            "message": msg,
            "data": {
                "count": 1,
                "sampleNo": sample_no,
                "preVersion": ver_info["pre_version"],
                "nextVersion": ver_info["next_version"],
            },
        }
    except Exception as e:
        logger.exception("清洗结果入库异常")
        return {"code": 1, "message": f"入库失败: {str(e)}"}
