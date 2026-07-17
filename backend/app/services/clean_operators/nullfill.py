"""空值处理算子"""
import numpy as np
import pandas as pd

from .base import BaseOperator, CleanContext

_STRATEGY_NAMES = {
    "drop": "删除空值行",
    "fill": "填充固定值「{fill}」",
    "ffill": "前向填充",
    "bfill": "后向填充",
    "interpolate": "线性插值",
    "mean": "均值填充",
    "median": "中位数填充",
    "hfill_forward": "横向向前填充",
    "hfill_backward": "横向向后填充",
    "hinterpolate": "横向插值",
}


class NullfillOperator(BaseOperator):
    node_type = "nullfill"

    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        nullfill_fields_raw = config.get("fields", [])
        # 将配置字段名映射到 DataFrame 实际列名（忽略大小写）
        nullfill_fields = [
            ctx.col_lower_map[f.lower()] for f in nullfill_fields_raw
            if f.lower() in ctx.col_lower_map
        ]
        strategy = config.get("strategy", "drop")
        fill_value = config.get("fillValue", "")
        treat_zero_as_null = config.get("treatZeroAsNull", False)

        if not nullfill_fields:
            ctx.log("未配置空值处理字段，跳过空值处理")
            return

        df = ctx.df
        strategy_name = _STRATEGY_NAMES.get(strategy, strategy)
        if strategy == "fill":
            strategy_name = strategy_name.format(fill=fill_value)

        # 根据配置决定是否将数值列中值为 0 的视为空值
        if treat_zero_as_null:
            for f in nullfill_fields:
                if pd.api.types.is_numeric_dtype(df[f]):
                    zero_count = int((df[f] == 0).sum())
                    if zero_count > 0:
                        ctx.log(f"字段 {f} 中有 {zero_count} 个零值将被视为空值处理")
                        df[f] = df[f].replace(0, np.nan)

        # 统计处理前空值数
        null_count_before = int(df[nullfill_fields].isnull().sum().sum())
        ctx.log(
            f"执行空值处理，方式：{strategy_name}，字段：{', '.join(nullfill_fields)}，"
            f"共 {null_count_before} 处空值"
        )

        if strategy == "drop":
            self._drop(ctx, df, nullfill_fields)
        elif strategy == "fill":
            self._fill(df, nullfill_fields, fill_value, null_count_before, ctx)
        elif strategy == "ffill":
            self._ffill(df, nullfill_fields, null_count_before, ctx)
        elif strategy == "bfill":
            self._bfill(df, nullfill_fields, null_count_before, ctx)
        elif strategy == "hfill_forward":
            self._hfill_forward(df, nullfill_fields, null_count_before, ctx, ctx.columns)
        elif strategy == "hfill_backward":
            self._hfill_backward(df, nullfill_fields, null_count_before, ctx, ctx.columns)
        elif strategy == "hinterpolate":
            self._hinterpolate(df, nullfill_fields, null_count_before, ctx, ctx.columns)
        elif strategy in ("interpolate", "mean", "median"):
            self._numeric_strategy(df, nullfill_fields, strategy, null_count_before, ctx)
        else:
            ctx.log(f"未知空值处理策略：{strategy}，跳过")

    def _drop(self, ctx: CleanContext, df: pd.DataFrame, fields: list) -> None:
        before_rows = len(df)
        ctx.df = df.dropna(subset=fields)
        removed = before_rows - len(ctx.df)
        ctx.removed_count += removed
        ctx.log(f"空值处理完成，移除 {removed} 条含空值数据，剩余 {len(ctx.df)} 条")

    def _fill(self, df: pd.DataFrame, fields: list, fill_value: str,
              null_count_before: int, ctx: CleanContext) -> None:
        for f in fields:
            if pd.api.types.is_numeric_dtype(df[f].dropna()):
                try:
                    numeric_fill = float(fill_value)
                    if numeric_fill == int(numeric_fill):
                        numeric_fill = int(numeric_fill)
                    df[f] = df[f].fillna(numeric_fill)
                except (ValueError, TypeError):
                    df[f] = df[f].fillna(fill_value)
            else:
                df[f] = df[f].fillna(fill_value)
        ctx.log(f"空值处理完成，共填充 {null_count_before} 处空值")

    def _ffill(self, df: pd.DataFrame, fields: list, null_count_before: int,
               ctx: CleanContext) -> None:
        df[fields] = df[fields].ffill()
        remaining_null = int(df[fields].isnull().sum().sum())
        filled_count = null_count_before - remaining_null
        if remaining_null > 0:
            ctx.log(f"空值处理完成，填充 {filled_count} 处空值，"
                    f"剩余 {remaining_null} 处无法填充（首行无前置值）")
        else:
            ctx.log(f"空值处理完成，填充 {filled_count} 处空值")

    def _bfill(self, df: pd.DataFrame, fields: list, null_count_before: int,
               ctx: CleanContext) -> None:
        df[fields] = df[fields].bfill()
        remaining_null = int(df[fields].isnull().sum().sum())
        filled_count = null_count_before - remaining_null
        if remaining_null > 0:
            ctx.log(f"空值处理完成，填充 {filled_count} 处空值，"
                    f"剩余 {remaining_null} 处无法填充（末行无后置值）")
        else:
            ctx.log(f"空值处理完成，填充 {filled_count} 处空值")

    def _hfill_forward(self, df: pd.DataFrame, fields: list, null_count_before: int,
                       ctx: CleanContext, columns: list) -> None:
        ordered = [f for f in fields if f in columns]
        for pos, f in enumerate(ordered):
            if pos > 0:
                prev_col = ordered[pos - 1]
                mask = df[f].isnull() & df[prev_col].notnull()
                df.loc[mask, f] = df.loc[mask, prev_col]
        self._log_horizontal_result(df, fields, null_count_before, ctx,
                                    "前一字段也为空")

    def _hfill_backward(self, df: pd.DataFrame, fields: list, null_count_before: int,
                        ctx: CleanContext, columns: list) -> None:
        ordered = [f for f in fields if f in columns]
        for pos, f in enumerate(ordered):
            if pos < len(ordered) - 1:
                next_col = ordered[pos + 1]
                mask = df[f].isnull() & df[next_col].notnull()
                df.loc[mask, f] = df.loc[mask, next_col]
        self._log_horizontal_result(df, fields, null_count_before, ctx,
                                    "后一字段也为空")

    def _hinterpolate(self, df: pd.DataFrame, fields: list, null_count_before: int,
                      ctx: CleanContext, columns: list) -> None:
        for f in fields:
            if f not in columns:
                continue
            df[f] = pd.to_numeric(df[f], errors="coerce")
        # 建立空值处理字段在 columns 中的位置映射，用于确定插值方向
        indices = [(columns.index(f), f) for f in fields if f in columns]
        indices.sort(key=lambda x: x[0])
        for i in df.index:
            for pos, (col_pos, col_name) in enumerate(indices):
                if pd.notna(df.at[i, col_name]):
                    continue
                # 在 fields 范围内向前找最近的有效数值
                prev_val = None
                prev_pos = None
                for k in range(pos - 1, -1, -1):
                    val = df.at[i, indices[k][1]]
                    if pd.notna(val):
                        prev_val = float(val)
                        prev_pos = indices[k][0]
                        break
                # 在 fields 范围内向后找最近的有效数值
                next_val = None
                next_pos = None
                for k in range(pos + 1, len(indices)):
                    val = df.at[i, indices[k][1]]
                    if pd.notna(val):
                        next_val = float(val)
                        next_pos = indices[k][0]
                        break
                # 按列位置做线性插值
                if prev_val is not None and next_val is not None:
                    interpolated = prev_val + (next_val - prev_val) * \
                        (col_pos - prev_pos) / (next_pos - prev_pos)
                    df.at[i, col_name] = round(interpolated, 4)
                elif prev_val is not None:
                    df.at[i, col_name] = prev_val
                elif next_val is not None:
                    df.at[i, col_name] = next_val
        self._log_horizontal_result(df, fields, null_count_before, ctx,
                                    "前后均无有效值")

    def _log_horizontal_result(self, df: pd.DataFrame, fields: list,
                               null_count_before: int, ctx: CleanContext,
                               fail_reason: str) -> None:
        remaining_null = int(df[fields].isnull().sum().sum())
        filled_count = null_count_before - remaining_null
        if remaining_null > 0:
            ctx.log(f"空值处理完成，填充 {filled_count} 处空值，"
                    f"剩余 {remaining_null} 处无法填充（{fail_reason}）")
        else:
            ctx.log(f"空值处理完成，填充 {filled_count} 处空值")

    def _numeric_strategy(self, df: pd.DataFrame, fields: list, strategy: str,
                          null_count_before: int, ctx: CleanContext) -> None:
        # 数值型策略：先尝试转为数值类型
        for f in fields:
            df[f] = pd.to_numeric(df[f], errors="coerce")
        # 重新统计转换后的空值数（可能有非数字字符串被转为 NaN）
        null_count_after_convert = int(df[fields].isnull().sum().sum())
        if null_count_after_convert > null_count_before:
            ctx.log(f"注意：{null_count_after_convert - null_count_before} 处非数值数据被转为空值")

        if strategy == "interpolate":
            df[fields] = df[fields].interpolate()
            # 对插值结果保留4位小数
            for f in fields:
                df[f] = df[f].apply(lambda x: round(x, 4) if pd.notna(x) and isinstance(x, float) else x)
        elif strategy == "mean":
            for f in fields:
                mean_val = df[f].mean()
                df[f] = df[f].fillna(round(mean_val, 4) if pd.notna(mean_val) else 0)
        elif strategy == "median":
            for f in fields:
                median_val = df[f].median()
                df[f] = df[f].fillna(round(median_val, 4) if pd.notna(median_val) else 0)

        remaining_null = int(df[fields].isnull().sum().sum())
        filled_count = null_count_after_convert - remaining_null
        if remaining_null > 0:
            ctx.log(f"空值处理完成，填充 {filled_count} 处空值，"
                    f"剩余 {remaining_null} 处无法填充（无有效值可参考）")
        else:
            ctx.log(f"空值处理完成，填充 {filled_count} 处空值")
