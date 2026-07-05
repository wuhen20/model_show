"""样本数据清理任务接口"""
import io
import json
from datetime import datetime
from fastapi import APIRouter, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.database import (
    generate_clean_task_no,
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
    get_connection,
    _execute,
    _select_all_from,
)

router = APIRouter()


class SaveCleanTaskRequest(BaseModel):
    taskName: str
    remark: str = ""


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
    """查询清理任务列表"""
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
    """新增清理任务"""
    task_name = req.taskName.strip()
    if not task_name:
        return {"code": 1, "message": "任务名称不能为空"}
    try:
        task_no = generate_clean_task_no()
        save_data_clean_task(task_no, task_name, req.remark)
        return {"code": 0, "message": "保存成功", "data": {"taskNo": task_no}}
    except Exception as e:
        return {"code": 1, "message": f"保存失败: {str(e)}"}


@router.get("/query-clean-task-detail")
def query_clean_task_detail_api(taskNo: str = Query(..., description="任务编号")):
    """查询清理任务详情（含节点）"""
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


@router.post("/execute-clean-task")
def execute_clean_task_api(req: ExecuteCleanTaskRequest):
    """执行清理任务：按流程编排读取数据→去重→导出 Excel 下载"""
    task_no = req.taskNo.strip()
    if not task_no:
        return {"code": 1, "message": "任务编号不能为空"}

    task = get_clean_task_raw(task_no)
    if not task:
        return {"code": 1, "message": "未找到任务"}

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

        # 生成 Excel
        append_clean_log(log_id, "正在生成 Excel 文件...")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="清洗结果")
        output.seek(0)

        result_count = len(df)

        # 完成执行记录
        finish_clean_log(
            log_id,
            execute_status="03",
            total_count=total_count,
            removed_count=removed_count,
            result_count=result_count,
            log_content="执行完成，清洗结果已生成"
        )

        # 更新任务状态为已完成
        update_clean_task_status(task_no, "03", last_execute_flag=1)

        task_name = task.get("task_name", task_no)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{task_name}_清洗结果_{timestamp}.xlsx"
        from urllib.parse import quote
        encoded_filename = quote(filename)

        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )
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
    """查询清理任务的执行记录列表"""
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
