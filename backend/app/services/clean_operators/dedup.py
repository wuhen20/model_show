"""去重算子"""
from .base import BaseOperator, CleanContext


class DedupOperator(BaseOperator):
    node_type = "dedup"

    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        dedup_fields = config.get("fields", [])
        if not dedup_fields:
            ctx.log("未配置去重字段，跳过去重")
            return

        ctx.log(f"执行去重，判定字段：{', '.join(dedup_fields)}")
        seen = set()
        deduped = []
        rows = ctx.df.to_dict("records")
        for row in rows:
            key = tuple(str(row.get(f, "")) for f in dedup_fields)
            if key not in seen:
                seen.add(key)
                deduped.append(row)
        removed = len(rows) - len(deduped)
        ctx.removed_count += removed

        import pandas as pd
        ctx.df = pd.DataFrame(deduped, columns=ctx.columns)
        ctx.log(f"去重完成，移除 {removed} 条重复数据，剩余 {len(ctx.df)} 条")
