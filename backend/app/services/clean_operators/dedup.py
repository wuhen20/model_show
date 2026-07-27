"""去重算子"""
from .base import BaseOperator, CleanContext


class DedupOperator(BaseOperator):
    node_type = "dedup"

    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        dedup_fields_raw = config.get("fields", [])
        if not dedup_fields_raw:
            ctx.log("未配置去重字段，跳过去重")
            return

        # 将配置字段名映射到 DataFrame 实际列名（忽略大小写，对齐其他算子）
        # Oracle rowfactory 会将列名统一转小写，若不映射会导致 row.get 取不到值，
        # 所有行的 key 退化为空字符串，误判为全量重复只保留一条
        dedup_fields = [
            ctx.col_lower_map[f.lower()] for f in dedup_fields_raw
            if f.lower() in ctx.col_lower_map
        ]
        if not dedup_fields:
            ctx.log(f"警告：配置的去重字段 {dedup_fields_raw} 在数据中均不存在，跳过去重")
            return
        # 部分字段不存在时给出明确警告，避免静默按错误 key 去重
        if len(dedup_fields) < len(dedup_fields_raw):
            missing = [f for f in dedup_fields_raw if f.lower() not in ctx.col_lower_map]
            ctx.log(f"警告：以下去重字段在数据中不存在，已忽略：{', '.join(missing)}")

        ctx.log(f"执行去重，判定字段：{', '.join(dedup_fields)}")
        seen = set()
        deduped = []
        rows = ctx.df.to_dict("records")
        for row in rows:
            # 联合 key：各字段值转字符串后拼接为元组
            key = tuple(str(row.get(f, "")) for f in dedup_fields)
            if key not in seen:
                seen.add(key)
                deduped.append(row)
        removed = len(rows) - len(deduped)
        ctx.removed_count += removed

        import pandas as pd
        ctx.df = pd.DataFrame(deduped, columns=ctx.columns)
        ctx.log(f"去重完成，移除 {removed} 条重复数据，剩余 {len(ctx.df)} 条")
