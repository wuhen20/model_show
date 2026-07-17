"""日期格式标准化算子"""
import pandas as pd

from .base import BaseOperator, CleanContext

# 13 种常见日期格式，自动匹配（不含源格式，由后端统一识别）
_COMMON_FORMATS = [
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d",
    "%Y%m%d%H%M%S",
    "%Y%m%d",
    "%Y年%m月%d日 %H:%M:%S",
    "%Y年%m月%d日",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
    "%m-%d-%Y %H:%M:%S",
    "%m-%d-%Y",
]


class DateFormatOperator(BaseOperator):
    node_type = "dateformat"

    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        date_field_raw = config.get("field", "")
        # 目标格式仅支持 YYYY-MM-DD 和 YYYY-MM-DD HH:MM:SS
        target_format = config.get("targetFormat", "%Y-%m-%d")

        if not date_field_raw:
            ctx.log("日期格式标准化节点配置不完整，跳过")
            return

        # 字段名大小写映射
        date_field = ctx.col_lower_map.get(date_field_raw.lower(), date_field_raw)
        df = ctx.df
        if date_field not in df.columns:
            ctx.log(f"日期字段 {date_field_raw} 不存在于数据中，跳过日期格式标准化")
            return

        ctx.log(f"执行日期格式标准化，字段：{date_field}，目标格式：{target_format}")
        # 将字段转为字符串（处理 varchar 和非 varchar 类型）
        original_series = df[date_field].astype(str).where(df[date_field].notna(), None)

        parsed = pd.Series(pd.NaT, index=df.index)
        format_used = None
        non_null_mask = (
            original_series.notna()
            & (original_series.astype(str).str.lower() != "nan")
            & (original_series.astype(str) != "")
        )
        remaining_mask = non_null_mask.copy()

        # 依次尝试 13 种常见格式
        for fmt in _COMMON_FORMATS:
            if not remaining_mask.any():
                break
            try_result = pd.to_datetime(
                original_series[remaining_mask], format=fmt, errors="coerce"
            )
            matched = try_result.notna()
            if matched.any():
                parsed.loc[remaining_mask.index[remaining_mask][matched]] = try_result[matched]
                remaining_mask.loc[remaining_mask.index[remaining_mask][matched]] = False
                if format_used is None:
                    format_used = fmt
                else:
                    format_used = "多种格式"

        # 对仍无法解析的行，尝试 pandas 自动推断
        if remaining_mask.any():
            try_result = pd.to_datetime(
                original_series[remaining_mask], errors="coerce"
            )
            matched = try_result.notna()
            if matched.any():
                parsed.loc[remaining_mask.index[remaining_mask][matched]] = try_result[matched]
                remaining_mask.loc[remaining_mask.index[remaining_mask][matched]] = False
                format_used = format_used or "自动推断"

        failed_count = int(remaining_mask.sum())
        success_count = int(parsed.notna().sum())

        ctx.log(
            f"日期格式自动识别：匹配格式{'：' + format_used if format_used else '：未识别'}，"
            f"成功 {success_count} 行，失败 {failed_count} 行"
        )

        if failed_count > 0:
            ctx.log(f"注意：{failed_count} 行数据无法识别为日期，将保持原值")

        # 按目标格式重新输出为字符串（无法解析的保留原值）
        formatted = parsed.dt.strftime(target_format)
        result_series = formatted.where(parsed.notna(), original_series)
        df[date_field] = result_series

        ctx.log(f"日期格式标准化完成，成功转换 {success_count} 行")
