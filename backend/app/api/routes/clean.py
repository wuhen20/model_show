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
    get_connection,
    _execute,
    _select_all_from,
    query_pic_clean_type_dict,
    insert_clean_pic_record,
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

        # 2. 查询清洗类型字典，将编码映射到 cleanvision issue 类型
        append_clean_log(log_id, "正在加载清洗类型配置...")
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
        append_clean_log(log_id, f"配置的检测类型：{', '.join(info['code_name'] for info in code_to_issue.values())}")

        # 3. 查询原始样本文件路径
        append_clean_log(log_id, "正在查询样本文件路径...")
        file_rows = query_original_sample_file_paths(set_no)
        file_paths = []
        for row in file_rows:
            fp = row.get("file_path") if isinstance(row, dict) else row[0]
            if fp:
                file_paths.append(fp)

        if not file_paths:
            raise ValueError("原始样本集下未找到样本文件")

        total_count = len(file_paths)
        append_clean_log(log_id, f"共 {total_count} 个样本文件")

        # 4. 提取公共目录作为 data_path
        abs_paths = [os.path.abspath(fp) for fp in file_paths]
        try:
            data_path = os.path.commonpath(abs_paths)
        except ValueError:
            raise ValueError("样本文件路径跨盘符，无法确定公共目录")

        if not os.path.isdir(data_path):
            raise ValueError(f"计算得到的图片目录不存在：{data_path}")

        append_clean_log(log_id, f"图片目录：{data_path}")

        # 5. 使用 cleanvision 检测问题图片
        append_clean_log(log_id, "正在检测图片质量问题，请稍候...")
        from cleanvision import Imagelab

        imagelab = Imagelab(data_path=data_path)

        # 禁用 tqdm 输出
        os.environ['TQDM_DISABLE'] = '1'
        original_stderr = sys.stderr
        try:
            sys.stderr = open(os.devnull, 'w')
            # 尝试只检测配置的类型
            issue_types = {spare1: {} for spare1 in configured_issues}
            try:
                imagelab.find_issues(issue_types=issue_types, verbose=False, n_jobs=2)
            except Exception as e_issue:
                # 某些类型不兼容单独指定，降级为全量检测后过滤
                append_clean_log(log_id, f"指定类型检测失败({e_issue})，降级为全量检测...")
                imagelab = Imagelab(data_path=data_path)
                imagelab.find_issues(verbose=False, n_jobs=2)
        finally:
            if sys.stderr:
                sys.stderr.close()
            sys.stderr = original_stderr
            if 'TQDM_DISABLE' in os.environ:
                del os.environ['TQDM_DISABLE']

        append_clean_log(log_id, "检测完成，正在整理结果...")

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

        removed_count = len(problem_images)
        result_count = total_count - removed_count
        append_clean_log(log_id, f"发现 {removed_count} 张问题图片，剩余 {result_count} 张正常图片")

        # 7. 创建目标目录并移动问题图片
        from app.core.config import settings
        base_dir = getattr(settings, "sample_upload_dir", "")
        if not base_dir:
            base_dir = os.path.abspath("uploads")
        target_dir = os.path.join(base_dir, "clean_result", task_no)
        os.makedirs(target_dir, exist_ok=True)

        append_clean_log(log_id, f"正在移动问题图片到：{target_dir}")

        moved_count = 0
        for image_name, issue_codes in problem_images.items():
            # image_name 是相对于 data_path 的路径
            src_path = os.path.join(data_path, image_name)
            if not os.path.exists(src_path):
                # 尝试用绝对路径
                src_path = image_name

            if not os.path.exists(src_path):
                append_clean_log(log_id, f"警告：文件不存在，跳过：{image_name}")
                continue

            dst_path = os.path.join(target_dir, os.path.basename(image_name))

            # 处理同名文件冲突
            if os.path.exists(dst_path):
                name, ext = os.path.splitext(os.path.basename(image_name))
                dst_path = os.path.join(target_dir, f"{name}_{moved_count}{ext}")

            try:
                shutil.move(src_path, dst_path)
                moved_count += 1
                # 对每种问题类型插入一条记录
                for code_val in issue_codes:
                    insert_clean_pic_record(task_no, code_val, os.path.basename(image_name), dst_path)
            except Exception as e_move:
                append_clean_log(log_id, f"警告：移动文件失败：{image_name}，{e_move}")

        append_clean_log(log_id, f"成功移动 {moved_count} 张问题图片")

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
    """执行清洗任务：按流程编排读取数据→去重→导出 Excel 下载"""
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

    nodes = task.get("nodes", [])
    if not nodes:
        return {"code": 1, "message": "任务未配置流程节点"}

    # 解析节点配置
    source_node = None
    dedup_node = None
    nullfill_node = None
    for node in nodes:
        config_str = node.get("node_config") or "{}"
        try:
            config = json.loads(config_str)
        except (json.JSONDecodeError, TypeError):
            config = {}
        node["_config"] = config
        if node["node_type"] == "source" and source_node is None:
            source_node = node
        elif node["node_type"] == "dedup" and dedup_node is None:
            dedup_node = node
        elif node["node_type"] == "nullfill" and nullfill_node is None:
            nullfill_node = node

    if not source_node:
        return {"code": 1, "message": "流程中缺少数据源节点"}

    table_name = source_node["_config"].get("tableName")
    if not table_name:
        return {"code": 1, "message": "数据源节点未配置表名"}

    update_clean_task_status(task_no, "02")

    log_id = None
    total_count = 0
    removed_count = 0
    result_count = 0

    try:
        # 创建执行记录，直接写入初始日志
        init_log = f"开始执行清理任务：{task.get('task_name', task_no)}\n数据源表：{table_name}"
        log_id = insert_clean_log(task_no, init_log)

        # 读取表数据
        append_clean_log(log_id, "正在读取表数据...")
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                _execute(cursor, _select_all_from(table_name))
                # Oracle rowfactory 将列名统一转小写，columns 也需对应
                from app.core.database import _is_oracle
                if _is_oracle():
                    columns = [desc[0].lower() for desc in cursor.description]
                else:
                    columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
        finally:
            conn.close()

        total_count = len(rows)
        append_clean_log(log_id, f"读取完成，共 {total_count} 条数据")

        # 执行去重
        if dedup_node:
            dedup_fields = dedup_node["_config"].get("fields", [])
            if dedup_fields:
                append_clean_log(log_id, f"执行去重，判定字段：{', '.join(dedup_fields)}")
                seen = set()
                deduped = []
                for row in rows:
                    key = tuple(str(row.get(f, "")) for f in dedup_fields)
                    if key not in seen:
                        seen.add(key)
                        deduped.append(row)
                removed_count = total_count - len(deduped)
                rows = deduped
                append_clean_log(log_id, f"去重完成，移除 {removed_count} 条重复数据，剩余 {len(rows)} 条")
            else:
                removed_count = 0
                append_clean_log(log_id, "未配置去重字段，跳过去重")
        else:
            removed_count = 0
            append_clean_log(log_id, "无去重节点，跳过去重")

        # 生成 DataFrame（空值处理需要在 DataFrame 上进行）
        append_clean_log(log_id, "正在构建数据帧...")
        import pandas as pd
        # rows 是 _CiDict 列表，转成普通 dict 列表避免大小写匹配问题
        df = pd.DataFrame([dict(r) for r in rows], columns=columns)
        # 构建列名大小写映射：小写 → 原始列名，用于将配置中的字段名映射到 DataFrame 的实际列名
        col_lower_map = {c.lower(): c for c in df.columns}

        # 执行空值处理
        if nullfill_node:
            nullfill_fields_raw = nullfill_node["_config"].get("fields", [])
            # 将配置字段名映射到 DataFrame 实际列名（忽略大小写）
            nullfill_fields = [col_lower_map[f.lower()] for f in nullfill_fields_raw if f.lower() in col_lower_map]
            strategy = nullfill_node["_config"].get("strategy", "drop")
            fill_value = nullfill_node["_config"].get("fillValue", "")
            strategy_names = {
                "drop": "删除空值行",
                "fill": f"填充固定值「{fill_value}」",
                "ffill": "前向填充",
                "bfill": "后向填充",
                "interpolate": "线性插值",
                "mean": "均值填充",
                "median": "中位数填充",
                "hfill_forward": "横向向前填充",
                "hfill_backward": "横向向后填充",
                "hinterpolate": "横向插值",
            }
            if nullfill_fields:
                # 统计处理前空值数
                null_count_before = int(df[nullfill_fields].isnull().sum().sum())
                append_clean_log(
                    log_id,
                    f"执行空值处理，方式：{strategy_names.get(strategy, strategy)}，字段：{', '.join(nullfill_fields)}，共 {null_count_before} 处空值"
                )

                if strategy == "drop":
                    before_rows = len(df)
                    df = df.dropna(subset=nullfill_fields)
                    removed_by_null = before_rows - len(df)
                    append_clean_log(log_id, f"空值处理完成，移除 {removed_by_null} 条含空值数据，剩余 {len(df)} 条")
                elif strategy == "fill":
                    df[nullfill_fields] = df[nullfill_fields].fillna(fill_value)
                    append_clean_log(log_id, f"空值处理完成，共填充 {null_count_before} 处空值")
                elif strategy == "ffill":
                    # 前向填充：支持字符串，无需数值转换
                    df[nullfill_fields] = df[nullfill_fields].ffill()
                    remaining_null = int(df[nullfill_fields].isnull().sum().sum())
                    filled_count = null_count_before - remaining_null
                    if remaining_null > 0:
                        append_clean_log(
                            log_id,
                            f"空值处理完成，填充 {filled_count} 处空值，剩余 {remaining_null} 处无法填充（首行无前置值）"
                        )
                    else:
                        append_clean_log(log_id, f"空值处理完成，填充 {filled_count} 处空值")
                elif strategy == "bfill":
                    # 后向填充：支持字符串，无需数值转换
                    df[nullfill_fields] = df[nullfill_fields].bfill()
                    remaining_null = int(df[nullfill_fields].isnull().sum().sum())
                    filled_count = null_count_before - remaining_null
                    if remaining_null > 0:
                        append_clean_log(
                            log_id,
                            f"空值处理完成，填充 {filled_count} 处空值，剩余 {remaining_null} 处无法填充（末行无后置值）"
                        )
                    else:
                        append_clean_log(log_id, f"空值处理完成，填充 {filled_count} 处空值")
                elif strategy == "hfill_forward":
                    # 横向向前填充：在选定的空值处理字段范围内，用同一行中前一个字段的值填充
                    nullfill_ordered = [f for f in nullfill_fields if f in columns]
                    for pos, f in enumerate(nullfill_ordered):
                        if pos > 0:
                            prev_col = nullfill_ordered[pos - 1]
                            mask = df[f].isnull() & df[prev_col].notnull()
                            df.loc[mask, f] = df.loc[mask, prev_col]
                    remaining_null = int(df[nullfill_fields].isnull().sum().sum())
                    filled_count = null_count_before - remaining_null
                    if remaining_null > 0:
                        append_clean_log(
                            log_id,
                            f"空值处理完成，填充 {filled_count} 处空值，剩余 {remaining_null} 处无法填充（前一字段也为空）"
                        )
                    else:
                        append_clean_log(log_id, f"空值处理完成，填充 {filled_count} 处空值")
                elif strategy == "hfill_backward":
                    # 横向向后填充：在选定的空值处理字段范围内，用同一行中后一个字段的值填充
                    nullfill_ordered = [f for f in nullfill_fields if f in columns]
                    for pos, f in enumerate(nullfill_ordered):
                        if pos < len(nullfill_ordered) - 1:
                            next_col = nullfill_ordered[pos + 1]
                            mask = df[f].isnull() & df[next_col].notnull()
                            df.loc[mask, f] = df.loc[mask, next_col]
                    remaining_null = int(df[nullfill_fields].isnull().sum().sum())
                    filled_count = null_count_before - remaining_null
                    if remaining_null > 0:
                        append_clean_log(
                            log_id,
                            f"空值处理完成，填充 {filled_count} 处空值，剩余 {remaining_null} 处无法填充（后一字段也为空）"
                        )
                    else:
                        append_clean_log(log_id, f"空值处理完成，填充 {filled_count} 处空值")
                elif strategy == "hinterpolate":
                    # 横向插值：在选定的空值处理字段范围内，用同一行中前后字段的值做线性插值
                    for f in nullfill_fields:
                        if f not in columns:
                            continue
                        df[f] = pd.to_numeric(df[f], errors="coerce")
                    # 建立空值处理字段在 columns 中的位置映射，用于确定插值方向
                    nullfill_indices = [(columns.index(f), f) for f in nullfill_fields if f in columns]
                    nullfill_indices.sort(key=lambda x: x[0])
                    for i in df.index:
                        for pos, (col_pos, col_name) in enumerate(nullfill_indices):
                            if pd.notna(df.at[i, col_name]):
                                continue
                            # 在 nullfill_fields 范围内向前找最近的有效数值
                            prev_val = None
                            prev_pos = None
                            for k in range(pos - 1, -1, -1):
                                val = df.at[i, nullfill_indices[k][1]]
                                if pd.notna(val):
                                    prev_val = float(val)
                                    prev_pos = nullfill_indices[k][0]
                                    break
                            # 在 nullfill_fields 范围内向后找最近的有效数值
                            next_val = None
                            next_pos = None
                            for k in range(pos + 1, len(nullfill_indices)):
                                val = df.at[i, nullfill_indices[k][1]]
                                if pd.notna(val):
                                    next_val = float(val)
                                    next_pos = nullfill_indices[k][0]
                                    break
                            # 按列位置做线性插值
                            if prev_val is not None and next_val is not None:
                                interpolated = prev_val + (next_val - prev_val) * (col_pos - prev_pos) / (next_pos - prev_pos)
                                df.at[i, col_name] = round(interpolated, 6)
                            elif prev_val is not None:
                                df.at[i, col_name] = prev_val
                            elif next_val is not None:
                                df.at[i, col_name] = next_val
                    remaining_null = int(df[nullfill_fields].isnull().sum().sum())
                    filled_count = null_count_before - remaining_null
                    if remaining_null > 0:
                        append_clean_log(
                            log_id,
                            f"空值处理完成，填充 {filled_count} 处空值，剩余 {remaining_null} 处无法填充（前后均无有效值）"
                        )
                    else:
                        append_clean_log(log_id, f"空值处理完成，填充 {filled_count} 处空值")
                else:
                    # 数值型策略：先尝试转为数值类型
                    for f in nullfill_fields:
                        df[f] = pd.to_numeric(df[f], errors="coerce")
                    # 重新统计转换后的空值数（可能有非数字字符串被转为 NaN）
                    null_count_after_convert = int(df[nullfill_fields].isnull().sum().sum())
                    if null_count_after_convert > null_count_before:
                        append_clean_log(
                            log_id,
                            f"注意：{null_count_after_convert - null_count_before} 处非数值数据被转为空值"
                        )

                    if strategy == "interpolate":
                        df[nullfill_fields] = df[nullfill_fields].interpolate()
                    elif strategy == "mean":
                        for f in nullfill_fields:
                            mean_val = df[f].mean()
                            df[f] = df[f].fillna(round(mean_val, 6) if pd.notna(mean_val) else 0)
                    elif strategy == "median":
                        for f in nullfill_fields:
                            median_val = df[f].median()
                            df[f] = df[f].fillna(round(median_val, 6) if pd.notna(median_val) else 0)

                    remaining_null = int(df[nullfill_fields].isnull().sum().sum())
                    filled_count = null_count_after_convert - remaining_null
                    if remaining_null > 0:
                        append_clean_log(
                            log_id,
                            f"空值处理完成，填充 {filled_count} 处空值，剩余 {remaining_null} 处无法填充（无有效值可参考）"
                        )
                    else:
                        append_clean_log(log_id, f"空值处理完成，填充 {filled_count} 处空值")
            else:
                append_clean_log(log_id, "未配置空值处理字段，跳过空值处理")
        else:
            append_clean_log(log_id, "无空值处理节点，跳过空值处理")

        # 生成 JSON 文件并保存到本地
        append_clean_log(log_id, "正在生成清洗结果 JSON 文件...")

        result_count = len(df)

        # 构造 JSON 数据
        # 将 DataFrame 转为记录列表，处理 NaN 和 Timestamp
        records = []
        for _, row in df.iterrows():
            record = {}
            for col in df.columns:
                val = row[col]
                # 处理 pandas NaN
                if pd.isna(val):
                    record[col] = None
                elif hasattr(val, "isoformat"):
                    record[col] = val.isoformat()
                else:
                    record[col] = val
            records.append(record)

        result_data = {
            "taskNo": task_no,
            "taskName": task.get("task_name", task_no),
            "executeTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "totalCount": total_count,
            "removedCount": removed_count,
            "resultCount": result_count,
            "columns": list(df.columns),
            "rows": records,
        }

        # 确定保存目录：SAMPLE_UPLOAD_DIR 下的 clean_result 文件夹
        from app.core.config import settings
        base_dir = getattr(settings, "sample_upload_dir", "")
        if not base_dir:
            base_dir = os.path.abspath("uploads")
        clean_result_dir = os.path.join(base_dir, "clean_result")
        os.makedirs(clean_result_dir, exist_ok=True)

        # 文件命名：清洗任务编号_时间戳.json
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{task_no}_{timestamp_str}.json"
        file_path = os.path.join(clean_result_dir, file_name)

        # 写入文件（UTF-8 编码，ensure_ascii=False 保留中文）
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2, default=str)

        append_clean_log(log_id, f"清洗结果已保存到：{file_path}")

        # 完成执行记录（带文件名和路径）
        finish_clean_log(
            log_id,
            execute_status="03",
            total_count=total_count,
            removed_count=removed_count,
            result_count=result_count,
            log_content="执行完成，清洗结果已保存为 JSON 文件",
            file_name=file_name,
            file_path=file_path,
        )

        # 更新任务状态为已完成
        update_clean_task_status(task_no, "03", last_execute_flag=1)

        return {"code": 0, "message": "执行成功，清洗结果已保存", "data": {"fileName": file_name, "filePath": file_path, "resultCount": result_count}}
    except Exception as e:
        # 失败时追加错误日志并更新执行记录
        if log_id:
            try:
                finish_clean_log(
                    log_id,
                    execute_status="04",
                    total_count=total_count,
                    removed_count=removed_count,
                    result_count=result_count,
                    log_content=f"执行失败：{str(e)}"
                )
            except Exception:
                pass
        # 任务状态设为 04-失败，确保用户可以重新执行
        update_clean_task_status(task_no, "04", last_execute_flag=2)
        return {"code": 1, "message": f"执行失败: {str(e)}"}


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
