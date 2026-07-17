"""字符替换算子（node_type 保留为 str2num，与已存数据库兼容）"""
from .base import BaseOperator, CleanContext


class StrReplaceOperator(BaseOperator):
    node_type = "str2num"

    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        fields_raw = config.get("fields", [])
        replace_from = config.get("replaceFrom", "")
        replace_to = config.get("replaceTo", "")
        fields = [
            ctx.col_lower_map[f.lower()] for f in fields_raw
            if f.lower() in ctx.col_lower_map
        ]

        if not fields or not replace_from:
            ctx.log("字符替换节点配置不完整，跳过")
            return

        replace_to_display = replace_to if replace_to else "（空）"
        ctx.log(
            f"执行字符替换，字段：{', '.join(fields)}，"
            f"\"{replace_from}\" → \"{replace_to_display}\""
        )

        df = ctx.df
        total_replaced = 0
        for f in fields:
            series = df[f].astype(str).where(df[f].notna(), "")
            # 统计替换前包含 replace_from 的行数
            match_mask = series.str.contains(replace_from, regex=False, na=False)
            match_count = int(match_mask.sum())
            # 执行精确字符串替换（不使用正则，空 replace_to 表示删除）
            df[f] = series.str.replace(replace_from, replace_to, regex=False)
            total_replaced += match_count
            if match_count > 0:
                ctx.log(f"字段 {f} 中 {match_count} 行包含\"{replace_from}\"，已替换")
            else:
                ctx.log(f"字段 {f} 中未找到\"{replace_from}\"，无需替换")

        ctx.log(f"字符替换完成，共替换 {total_replaced} 处")
