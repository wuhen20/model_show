"""数据源算子：读取表数据并初始化 DataFrame"""
import pandas as pd

from app.core.database import (
    get_connection,
    _execute,
    _select_all_from,
    _is_oracle,
)
from .base import BaseOperator, CleanContext


class SourceOperator(BaseOperator):
    node_type = "source"

    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        table_name = config.get("tableName")
        if not table_name:
            raise ValueError("数据源节点未配置表名")

        ctx.log(f"数据源表：{table_name}")
        ctx.log("正在读取表数据...")
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                _execute(cursor, _select_all_from(table_name))
                # Oracle rowfactory 将列名统一转小写，columns 也需对应
                if _is_oracle():
                    columns = [desc[0].lower() for desc in cursor.description]
                else:
                    columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
        finally:
            conn.close()

        ctx.columns = columns
        ctx.total_count = len(rows)
        ctx.log(f"读取完成，共 {ctx.total_count} 条数据")

        # rows 是 _CiDict 列表，转成普通 dict 列表避免大小写匹配问题
        ctx.df = pd.DataFrame([dict(r) for r in rows], columns=columns)
        # 构建列名大小写映射：小写 → 原始列名，用于将配置中的字段名映射到 DataFrame 的实际列名
        ctx.col_lower_map = {c.lower(): c for c in ctx.df.columns}
