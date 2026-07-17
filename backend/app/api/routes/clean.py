"""样本数据清洗任务接口"""
import json
import logging
import os
import sys
import shutil
from datetime import datetime
from fastapi import APIRouter, Query, UploadFile, File
from pydantic import BaseModel

logger = logging.getLogger("app.clean")

from app.core.database import (
    generate_clean_task_no,
    generate_sample_no,
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
    query_clean_log,
    query_clean_results,
    query_sample_set_options,
    batch_insert_sample_info,
    insert_original_sample_info,
    get_connection,
    _execute,
    _select_all_from,
    query_pic_clean_type_dict,
    insert_clean_pic_record,
    query_clean_pic_records,
    delete_original_sample_info_by_path,
    get_original_sample_set_path,
    delete_clean_pic_records,
    query_original_sample_file_paths,
    query_original_sample_set_by_type,
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


def _execute_image_clean_task(task: dict, task_no: str):
    """执行图像样本清洗任务：使用 cleanvision 检测问题图片，移动到隔离目录"""
    nodes = task.get("nodes", [])
    if not nodes:
        return {"code": 1, "message": "任务未配置清洗节点"}

    # 1. 从节点获取原始样本集编号和清洗类型编码
    image_node = None
    for node in nodes:
        if node.get("node_type") == "image_clean":
            image_node = node
            break
    if not image_node:
        return {"code": 1, "message": "未找到图像清洗节点"}

    set_no = image_node.get("node_id", "")
    clean_types_str = image_node.get("node_config") or ""
    if not set_no:
        return {"code": 1, "message": "清洗节点未关联原始样本集"}
    if not clean_types_str:
        return {"code": 1, "message": "未配置清洗类型"}

    clean_type_codes = [c.strip() for c in clean_types_str.split(",") if c.strip()]
    if not clean_type_codes:
        return {"code": 1, "message": "未配置清洗类型"}

    update_clean_task_status(task_no, "02")
    log_id = None
    total_count = 0
    removed_count = 0

    try:
        init_log = f"开始执行图像清洗任务：{task.get('task_name', task_no)}"
        log_id = insert_clean_log(task_no, init_log)
        logger.info(init_log)

        # 2. 查询清洗类型字典，将编码映射到 cleanvision issue 类型
        append_clean_log(log_id, "正在加载清洗类型配置...")
        logger.info("正在加载清洗类型配置...")
        dict_rows = query_pic_clean_type_dict()
        code_to_issue = {}  # {清洗类型编码: {spare1, code_name}}
        for row in dict_rows:
            code_val = row.get("CODE_VALUE", "")
            spare1 = row.get("SPARE1", "")
            code_name = row.get("CODE_NAME", "")
            if code_val in clean_type_codes and spare1:
                code_to_issue[code_val] = {"spare1": spare1, "code_name": code_name}

        if not code_to_issue:
            raise ValueError("配置的清洗类型在字典中未找到对应记录")

        configured_issues = {info["spare1"] for info in code_to_issue.values()}
        type_names = ', '.join(info['code_name'] for info in code_to_issue.values())
        append_clean_log(log_id, f"配置的检测类型：{type_names}")
        logger.info(f"配置的检测类型：{type_names}")

        # 3. 查询原始样本文件路径
        append_clean_log(log_id, "正在查询样本文件路径...")
        logger.info("正在查询样本文件路径...")
        file_rows = query_original_sample_file_paths(set_no)
        file_paths = []
        # 构建 规范化绝对路径 → 数据库存储 file_path 的映射，用于移动后精确删除原始样本记录
        norm_path_to_stored = {}
        for row in file_rows:
            fp = row.get("file_path") if isinstance(row, dict) else row[0]
            if fp:
                file_paths.append(fp)
                norm_path_to_stored[os.path.normpath(os.path.abspath(fp))] = fp

        if not file_paths:
            raise ValueError("原始样本集下未找到样本文件")

        total_count = len(file_paths)
        append_clean_log(log_id, f"共 {total_count} 个样本文件")
        logger.info(f"共 {total_count} 个样本文件")

        # 4. 提取公共目录作为 data_path
        abs_paths = [os.path.abspath(fp) for fp in file_paths]
        try:
            data_path = os.path.commonpath(abs_paths)
        except ValueError:
            raise ValueError("样本文件路径跨盘符，无法确定公共目录")

        if not os.path.isdir(data_path):
            raise ValueError(f"计算得到的图片目录不存在：{data_path}")

        append_clean_log(log_id, f"图片目录：{data_path}")
        logger.info(f"图片目录：{data_path}")

        # 5. 使用 cleanvision 检测问题图片
        append_clean_log(log_id, "正在检测图片质量问题，请稍候...")
        logger.info("正在检测图片质量问题，请稍候...")
        from cleanvision import Imagelab

        imagelab = Imagelab(data_path=data_path)

        # issue_types 格式：{"exact_duplicates":{}, "blurry":{"threshold":0.45}, ...}，key 为 SPARE1 英文名
        issue_types = {spare1: {} for spare1 in configured_issues}
        # 模糊类型设置自定义阈值
        if "blurry" in issue_types:
            issue_types["blurry"] = {"threshold": 0.45}
        # 过亮类型设置自定义阈值
        if "light" in issue_types:
            issue_types["light"] = {"threshold": 0.47}
        # 异常大小类型设置自定义阈值
        if "odd_size" in issue_types:
            issue_types["odd_size"] = {"threshold": 0.84}
        append_clean_log(log_id, f"检测类型参数：{issue_types}")
        logger.info(f"检测类型参数：{issue_types}")

        # 禁用 tqdm 输出
        os.environ['TQDM_DISABLE'] = '1'
        original_stderr = sys.stderr
        try:
            sys.stderr = open(os.devnull, 'w')
            try:
                imagelab.find_issues(issue_types=issue_types, verbose=False, n_jobs=1)
            except Exception as e_issue:
                # 某些类型不兼容单独指定，降级为全量检测后过滤
                msg = f"指定类型检测失败({e_issue})，降级为全量检测..."
                append_clean_log(log_id, msg)
                logger.warning(msg)
                imagelab = Imagelab(data_path=data_path)
                imagelab.find_issues(verbose=False, n_jobs=1)
        finally:
            if sys.stderr:
                sys.stderr.close()
            sys.stderr = original_stderr
            if 'TQDM_DISABLE' in os.environ:
                del os.environ['TQDM_DISABLE']

        append_clean_log(log_id, "检测完成，正在整理结果...")
        logger.info("检测完成，正在整理结果...")

        # 6. 从 issues DataFrame 提取问题图片
        issues_df = imagelab.issues
        # 收集 {image_name: [清洗类型编码列表]}
        problem_images = {}

        for image_name, row in issues_df.iterrows():
            issues_for_image = []
            for code_val, info in code_to_issue.items():
                issue_col = f"is_{info['spare1']}_issue"
                if issue_col in issues_df.columns and row[issue_col]:
                    issues_for_image.append(code_val)

            if issues_for_image:
                problem_images[image_name] = issues_for_image

        # 6.1 对于重复类型（exact_duplicates / near_duplicates），每个重复组保留一张，不全删除
        # cleanvision 的重复分组存储在 imagelab.info[issue_key]["sets"]，是 list[list[str]] 结构
        duplicate_type_codes = {
            code_val: info["spare1"]
            for code_val, info in code_to_issue.items()
            if info["spare1"] in ("exact_duplicates", "near_duplicates")
        }
        kept_for_duplicate = 0
        if duplicate_type_codes:
            imagelab_info = getattr(imagelab, "info", {}) or {}
            for code_val, spare1 in duplicate_type_codes.items():
                issue_info = imagelab_info.get(spare1, {}) or {}
                sets = issue_info.get("sets", []) or []
                append_clean_log(log_id, f"重复类型 [{spare1}] 检测到 {len(sets)} 个重复组")
                logger.info(f"重复类型 [{spare1}] 检测到 {len(sets)} 个重复组")
                for group in sets:
                    if not group or len(group) < 2:
                        continue
                    # 保留组内第一张：从其问题列表中移除该重复类型编码
                    keep_image = group[0]
                    if keep_image in problem_images:
                        issue_list = problem_images[keep_image]
                        if code_val in issue_list:
                            issue_list.remove(code_val)
                            kept_for_duplicate += 1
                        # 若该图片已无任何问题类型，则从待移动集合中移除
                        if not issue_list:
                            del problem_images[keep_image]
            if kept_for_duplicate > 0:
                msg = f"重复图片处理：每组保留 1 张，共保留 {kept_for_duplicate} 张重复图片不移动"
                append_clean_log(log_id, msg)
                logger.info(msg)

        removed_count = len(problem_images)
        result_count = total_count - removed_count
        msg = f"发现 {removed_count} 张问题图片，剩余 {result_count} 张正常图片"
        append_clean_log(log_id, msg)
        logger.info(msg)

        # 7. 创建目标目录并移动问题图片
        from app.core.config import settings
        base_dir = getattr(settings, "sample_upload_dir", "")
        if not base_dir:
            base_dir = os.path.abspath("uploads")
        target_dir = os.path.join(base_dir, "clean_result", task_no)
        os.makedirs(target_dir, exist_ok=True)

        append_clean_log(log_id, f"正在移动问题图片到：{target_dir}")
        logger.info(f"正在移动问题图片到：{target_dir}")

        moved_count = 0
        deleted_info_count = 0
        for image_name, issue_codes in problem_images.items():
            # image_name 是相对于 data_path 的路径
            src_path = os.path.join(data_path, image_name)
            if not os.path.exists(src_path):
                # 尝试用绝对路径
                src_path = image_name

            if not os.path.exists(src_path):
                warn_msg = f"警告：文件不存在，跳过：{image_name}"
                append_clean_log(log_id, warn_msg)
                logger.warning(warn_msg)
                continue

            dst_path = os.path.join(target_dir, os.path.basename(image_name))

            # 处理同名文件冲突
            if os.path.exists(dst_path):
                name, ext = os.path.splitext(os.path.basename(image_name))
                dst_path = os.path.join(target_dir, f"{name}_{moved_count}{ext}")

            try:
                shutil.move(src_path, dst_path)
                moved_count += 1
                # 一张图片只插入一条记录，多个问题类型逗号分隔
                clean_type_str = ",".join(issue_codes)
                insert_clean_pic_record(task_no, clean_type_str, os.path.basename(image_name), dst_path)
                logger.debug(f"移动文件：{image_name} -> {dst_path}")
                # 删除 s_original_sample_info 中对应的原始样本记录
                stored_fp = norm_path_to_stored.get(os.path.normpath(os.path.abspath(src_path)))
                if stored_fp:
                    try:
                        deleted_info_count += delete_original_sample_info_by_path(stored_fp)
                    except Exception as e_del:
                        warn_msg = f"警告：删除原始样本记录失败：{image_name}，{e_del}"
                        append_clean_log(log_id, warn_msg)
                        logger.warning(warn_msg)
            except Exception as e_move:
                warn_msg = f"警告：移动文件失败：{image_name}，{e_move}"
                append_clean_log(log_id, warn_msg)
                logger.warning(warn_msg)

        msg = f"成功移动 {moved_count} 张问题图片，删除 {deleted_info_count} 条原始样本记录"
        append_clean_log(log_id, msg)
        logger.info(msg)

        # 8. 完成执行记录
        finish_clean_log(
            log_id,
            execute_status="03",
            total_count=total_count,
            removed_count=removed_count,
            result_count=result_count,
            log_content="图像清洗执行完成，问题图片已移至隔离目录",
        )
        update_clean_task_status(task_no, "03", last_execute_flag=1)
        logger.info(f"图像清洗任务 {task_no} 执行完成")

        return {
            "code": 0,
            "message": f"执行成功，共检测 {total_count} 张图片，移动 {removed_count} 张问题图片",
            "data": {"fileName": "", "filePath": target_dir, "resultCount": result_count},
        }

    except Exception as e:
        if log_id:
            try:
                finish_clean_log(
                    log_id,
                    execute_status="04",
                    total_count=total_count,
                    removed_count=removed_count,
                    result_count=total_count - removed_count,
                    log_content=f"执行失败：{str(e)}",
                )
            except Exception:
                pass
        update_clean_task_status(task_no, "04", last_execute_flag=2)
        logger.exception("图像清洗任务执行异常")
        return {"code": 1, "message": f"执行失败: {str(e)}"}


@router.post("/execute-clean-task")
def execute_clean_task_api(req: ExecuteCleanTaskRequest):
    """执行清洗任务：图片类型走专用流程；时序类型按画布连线顺序执行算子管道"""
    task_no = req.taskNo.strip()
    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}

    task = get_clean_task_raw(task_no)
    if not task:
        return {"code": 1, "message": "未找到任务"}

    # 图片类型清洗任务走专用流程
    sample_type = str(task.get("sample_type") or "")
    if sample_type == "05":
        return _execute_image_clean_task(task, task_no)

    # 时序类型：交给管道执行器，按画布连线顺序执行各算子
    from app.services.clean_operators.pipeline import execute_clean_pipeline
    return execute_clean_pipeline(task, task_no)


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


@router.get("/view-clean-result")
def view_clean_result_api(recordId: int = Query(..., description="记录ID")):
    """查看清洗结果 JSON 文件内容"""
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
        if not os.path.exists(file_path):
            return {"code": 1, "message": f"文件不存在：{file_path}"}

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {"code": 0, "data": data}
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
        if not os.path.exists(file_path):
            return {"code": 1, "message": f"文件不存在：{file_path}"}

        task_no = row.get("task_no", "unknown")
        from urllib.parse import quote

        if format == "excel":
            # 读取 JSON 并转换为 Excel
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

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
        else:
            # 直接下载 JSON 文件
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
        if not os.path.exists(filePath):
            return {"code": 1, "message": f"文件不存在：{filePath}"}

        filename = os.path.basename(filePath)
        from urllib.parse import quote
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
def query_clean_pics_api(taskNo: str = Query(..., description="清洗任务编号")):
    """查询图像清洗任务被清洗的图片记录（含清洗原因）"""
    try:
        rows = query_clean_pic_records(taskNo)
        pics = []
        for row in rows:
            pics.append({
                "recordId": row.get("record_id"),
                "taskNo": row.get("task_no", ""),
                "cleanType": row.get("clean_type", ""),
                "cleanTypeName": row.get("clean_type_name", "") or row.get("clean_type", ""),
                "fileName": row.get("file_name", ""),
                "filePath": row.get("file_path", ""),
            })
        return {"code": 0, "data": pics}
    except Exception as e:
        logger.exception("查询图像清洗图片记录异常")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/serve-image")
def serve_image_api(filePath: str = Query(..., description="图片文件路径")):
    """读取并返回图片文件，用于展示被清洗的图片"""
    file_path = os.path.normpath(filePath)
    if not os.path.isfile(file_path):
        return {"code": 1, "message": f"图片文件不存在: {file_path}"}
    ext = os.path.splitext(file_path)[1].lower()
    content_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
        ".tif": "image/tiff", ".tiff": "image/tiff",
    }
    media_type = content_types.get(ext, "application/octet-stream")
    from fastapi.responses import FileResponse
    return FileResponse(file_path, media_type=media_type)


class RollbackCleanPicsRequest(BaseModel):
    taskNo: str


@router.post("/rollback-clean-pics")
def rollback_clean_pics_api(req: RollbackCleanPicsRequest):
    """回滚图像清洗：将隔离目录中的图片移回原始样本集目录，并恢复 s_original_sample_info 记录"""
    task_no = req.taskNo.strip()
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
        if not set_path:
            return {"code": 1, "message": "原始样本集未配置 set_path，无法确定恢复目录"}
        os.makedirs(set_path, exist_ok=True)

        # 3. 查询被清洗图片记录，按隔离路径去重（同一图片可能有多个清洗类型记录）
        pic_rows = query_clean_pic_records(task_no)
        if not pic_rows:
            return {"code": 1, "message": "无可回滚的清洗图片记录"}

        # 按 file_path(隔离路径) 去重，保留 file_name
        unique_files = {}
        for row in pic_rows:
            iso_path = row.get("file_path", "")
            file_name = row.get("file_name", "")
            if iso_path and iso_path not in unique_files:
                unique_files[iso_path] = file_name

        # 4. 逐个将文件从隔离目录移回 set_path，并恢复原始样本记录
        restored_count = 0
        skipped_count = 0
        errors = []
        for iso_path, file_name in unique_files.items():
            iso_path = os.path.normpath(iso_path)
            if not os.path.isfile(iso_path):
                errors.append(f"{file_name}: 隔离文件不存在，跳过")
                skipped_count += 1
                continue

            restore_path = os.path.join(set_path, file_name)
            # 处理同名文件冲突：若 set_path 已存在同名文件，添加后缀
            if os.path.exists(restore_path):
                name, ext = os.path.splitext(file_name)
                idx = 1
                while os.path.exists(os.path.join(set_path, f"{name}_{idx}{ext}")):
                    idx += 1
                restore_path = os.path.join(set_path, f"{name}_{idx}{ext}")

            try:
                file_size = os.path.getsize(iso_path)
                shutil.move(iso_path, restore_path)
                # 恢复 s_original_sample_info 记录（自动生成 sample_no）
                suffix = os.path.splitext(file_name)[1].lstrip(".").lower()
                insert_original_sample_info(
                    set_no=set_no,
                    sample_name=os.path.basename(restore_path),
                    suffix=suffix,
                    type_code=type_code,
                    file_path=restore_path,
                    file_size=file_size,
                )
                restored_count += 1
            except Exception as e_restore:
                errors.append(f"{file_name}: 恢复失败 - {e_restore}")
                skipped_count += 1

        # 5. 删除清洗图片记录（无论文件是否成功恢复，记录都已处理）
        delete_clean_pic_records(task_no)

        # 6. 尝试清理空的隔离目录
        from app.core.config import settings
        base_dir = getattr(settings, "sample_upload_dir", "")
        if base_dir:
            target_dir = os.path.join(base_dir, "clean_result", task_no)
            if os.path.isdir(target_dir):
                try:
                    # 仅在目录为空时删除
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


@router.post("/import-to-sample")
def import_to_sample_api(req: ImportToSampleRequest):
    """将清洗结果入库到样本信息表"""
    try:
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

        # 3. 读取 JSON 文件获取数据行
        file_path = log_row["file_path"]
        if not os.path.exists(file_path):
            return {"code": 1, "message": f"文件不存在：{file_path}"}

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        columns = data.get("columns", [])
        rows = data.get("rows", [])
        if not rows:
            return {"code": 1, "message": "清洗结果无数据"}

        # 4. 确定类型编码：优先样本集的 type_code，其次任务的 sample_type
        type_code = set_row.get("type_code") or log_row.get("sample_type") or ""
        business_system = set_row.get("business_system") or ""
        file_name = log_row.get("file_name") or ""

        # 5. 将每行数据转为 JSON 字符串作为样本，批量插入
        import json as _json
        file_size_bytes = os.path.getsize(file_path)
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
        return {"code": 0, "message": "入库成功", "data": {"count": 1, "sampleNo": sample_no}}
    except Exception as e:
        logger.exception("清洗结果入库异常")
        return {"code": 1, "message": f"入库失败: {str(e)}"}
