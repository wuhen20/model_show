"""清洗管道执行入口：按画布连线顺序执行算子。"""
import json
import logging
import os
from datetime import datetime

import pandas as pd

from app.core.database import (
    update_clean_task_status,
    insert_clean_log,
    append_clean_log,
    finish_clean_log,
)
from . import OPERATOR_REGISTRY
from .base import CleanContext

logger = logging.getLogger("app.clean")


def _reorder_nodes_by_prev(nodes: list) -> list:
    """根据 prev_node_id 重建画布连线顺序。

    - 起点：prev_node_id 为 None 或空字符串的节点
    - 后续：prev_node_id 等于前一节点 node_id 的节点
    - 孤立节点（未连入主链）按原顺序追加在末尾
    """
    if not nodes:
        return []

    # 找起点
    start = next((n for n in nodes if not n.get("prev_node_id")), None)
    if start is None:
        # 退化情况：所有节点都有 prev_node_id（可能存在环或脏数据），按原顺序返回
        return list(nodes)

    ordered = [start]
    visited = {start["node_id"]}
    current_id = start["node_id"]
    # 沿链查找：找 prev_node_id == current_id 的节点
    while True:
        next_node = next(
            (n for n in nodes
             if n.get("prev_node_id") == current_id and n["node_id"] not in visited),
            None,
        )
        if next_node is None:
            break
        ordered.append(next_node)
        visited.add(next_node["node_id"])
        current_id = next_node["node_id"]

    # 处理孤立节点（未连入主链的节点）——按原顺序追加，避免遗漏
    for n in nodes:
        if n["node_id"] not in visited:
            ordered.append(n)
    return ordered


def _save_clean_result(ctx: CleanContext, task: dict, task_no: str, log_id: int) -> dict:
    """生成清洗结果 JSON 文件并保存到本地，返回包含文件信息的字典。"""
    ctx.log("正在生成清洗结果 JSON 文件...")

    df = ctx.df
    result_count = len(df)

    # 构造 JSON 数据：将 DataFrame 转为记录列表，处理 NaN 和 Timestamp
    records = []
    for _, row in df.iterrows():
        record = {}
        for col in df.columns:
            val = row[col]
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
        "totalCount": ctx.total_count,
        "removedCount": ctx.removed_count,
        "resultCount": result_count,
        "columns": list(df.columns),
        "rows": records,
    }

    # 保存目录：SAMPLE_UPLOAD_DIR 下的 clean_result 文件夹
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

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2, default=str)

    ctx.log(f"清洗结果已保存到：{file_path}")

    finish_clean_log(
        log_id,
        execute_status="03",
        total_count=ctx.total_count,
        removed_count=ctx.removed_count,
        result_count=result_count,
        log_content="执行完成，清洗结果已保存为 JSON 文件",
        file_name=file_name,
        file_path=file_path,
    )
    return {"fileName": file_name, "filePath": file_path, "resultCount": result_count}


def execute_clean_pipeline(task: dict, task_no: str) -> dict:
    """按画布连线顺序执行时序类型清洗任务。"""
    raw_nodes = task.get("nodes", [])
    if not raw_nodes:
        return {"code": 1, "message": "任务未配置流程节点"}

    # 按画布连线顺序重建节点顺序
    nodes = _reorder_nodes_by_prev(raw_nodes)

    # 校验起点必须是 source
    if not nodes or nodes[0].get("node_type") != "source":
        return {"code": 1, "message": "流程起点必须是数据源节点"}

    update_clean_task_status(task_no, "02")

    log_id = None
    try:
        init_log = f"开始执行清理任务：{task.get('task_name', task_no)}"
        log_id = insert_clean_log(task_no, init_log)

        ctx = CleanContext(
            task=task,
            task_no=task_no,
            log_id=log_id,
            nodes=nodes,
            append_log=append_clean_log,
        )

        # 按顺序执行各算子
        for node in nodes:
            node_type = node.get("node_type", "")
            operator_cls = OPERATOR_REGISTRY.get(node_type)
            if operator_cls is None:
                ctx.log(f"未知节点类型 {node_type}，跳过")
                continue
            config_str = node.get("node_config") or "{}"
            try:
                config = json.loads(config_str)
            except (json.JSONDecodeError, TypeError):
                config = {}
            operator = operator_cls()
            operator.execute(ctx, node, config)

        if ctx.df is None:
            raise ValueError("数据源节点未成功初始化数据")

        # 生成结果 JSON 文件
        result_info = _save_clean_result(ctx, task, task_no, log_id)

        update_clean_task_status(task_no, "03", last_execute_flag=1)
        return {"code": 0, "message": "执行成功，清洗结果已保存", "data": result_info}

    except Exception as e:
        # 失败时追加错误日志并更新执行记录
        if log_id:
            try:
                finish_clean_log(
                    log_id,
                    execute_status="04",
                    total_count=ctx.total_count if 'ctx' in locals() else 0,
                    removed_count=ctx.removed_count if 'ctx' in locals() else 0,
                    result_count=(len(ctx.df) if 'ctx' in locals() and ctx.df is not None else 0),
                    log_content=f"执行失败：{str(e)}",
                )
            except Exception:
                pass
        update_clean_task_status(task_no, "04", last_execute_flag=2)
        logger.exception("时序清洗任务执行异常")
        return {"code": 1, "message": f"执行失败: {str(e)}"}
