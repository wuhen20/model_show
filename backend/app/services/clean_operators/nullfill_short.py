"""短期空值处理算子（横向1个字段缺失）：支持统一策略 + 滑动窗口均值补全"""
import numpy as np
import pandas as pd

from .base import BaseOperator, CleanContext
from .nullfill import NullfillOperator


def _detect_gaps(series):
    """检测连续缺失段，返回 [(start, end, length), ...]"""
    is_nan = series.isna().values
    gaps = []
    n = len(is_nan)
    i = 0
    while i < n:
        if is_nan[i]:
            start = i
            while i < n and is_nan[i]:
                i += 1
            length = i - start
            gaps.append((start, i, length))
        else:
            i += 1
    return gaps


def _is_missing(val, treat_zero_as_null):
    """判断值是否为缺失（NaN 或 0-当treatZeroAsNull）"""
    if pd.isna(val):
        return True
    if treat_zero_as_null:
        try:
            return float(val) == 0.0
        except (ValueError, TypeError):
            return False
    return False


def _fill_short_gap_horizontal(df, fields, columns, w, treat_zero_as_null, ctx):
    """横向滑动窗口均值补全：对每行，在同行相邻字段中取窗口内有效值均值。
    只补全单个字段缺失（前后字段均有值）的情况，即连续缺失长度=1的短期空值。
    当 treat_zero_as_null=True 时，0也视为缺失参与检测，但不被替换为NaN。

    df: DataFrame（原地修改）
    fields: 需要处理的字段列表
    columns: 全部列名有序列表
    w: 窗口大小（前后各取 w 个字段）
    ctx: CleanContext
    """
    # 按列在 columns 中的顺序排列 fields
    ordered = [(columns.index(f), f) for f in fields if f in columns]
    ordered.sort(key=lambda x: x[0])
    if not ordered:
        return 0

    n_fields = len(ordered)
    total_filled = 0

    for row in df.index:
        # 先检测该行中的连续缺失段
        missing_mask = []
        for _, col_name in ordered:
            missing_mask.append(_is_missing(df.at[row, col_name], treat_zero_as_null))

        # 检测连续缺失段（start, end, length）
        gaps = []
        i = 0
        while i < n_fields:
            if missing_mask[i]:
                start = i
                while i < n_fields and missing_mask[i]:
                    i += 1
                gaps.append((start, i, i - start))
            else:
                i += 1

        # 只处理长度为1的短期空值
        short_gaps = [g for g in gaps if g[2] == 1]

        for s, e, gap_len in short_gaps:
            # s == e - 1，只有一个缺失点
            current_idx = s
            col_pos, col_name = ordered[current_idx]

            # 收集窗口内的有效值（排除NaN和0-当treatZeroAsNull）
            win_vals = []
            # 前 w 个
            for k in range(current_idx - 1, max(current_idx - w - 1, -1), -1):
                _, neighbor = ordered[k]
                nval = df.at[row, neighbor]
                if not _is_missing(nval, treat_zero_as_null):
                    try:
                        win_vals.append(float(nval))
                    except (ValueError, TypeError):
                        pass
            # 后 w 个
            for k in range(current_idx + 1, min(current_idx + w + 1, len(ordered))):
                _, neighbor = ordered[k]
                nval = df.at[row, neighbor]
                if not _is_missing(nval, treat_zero_as_null):
                    try:
                        win_vals.append(float(nval))
                    except (ValueError, TypeError):
                        pass

            if win_vals:
                filled_val = round(sum(win_vals) / len(win_vals), 4)
                df.at[row, col_name] = filled_val
                total_filled += 1

    return total_filled


class NullfillShortOperator(BaseOperator):
    node_type = "nullfill_short"

    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        strategy = config.get("strategy", "sliding_window")

        # 统一策略：委托给 NullfillOperator 处理
        _UNIFIED_STRATEGIES = {
            "drop", "fill", "ffill", "bfill", "interpolate",
            "mean", "median", "hfill_forward", "hfill_backward", "hinterpolate",
        }
        if strategy in _UNIFIED_STRATEGIES:
            ctx.log(f"短期空值处理使用统一策略：{strategy}")
            NullfillOperator().execute(ctx, node, config)
            return

        # 独有策略：sliding_window（横向滑动窗口均值）
        fields_raw = config.get("fields", [])
        fields = [
            ctx.col_lower_map[f.lower()] for f in fields_raw
            if f.lower() in ctx.col_lower_map
        ]
        window_size = config.get("windowSize", 3)
        try:
            window_size = int(window_size)
        except (ValueError, TypeError):
            window_size = 3
        if window_size < 1:
            window_size = 1
        treat_zero_as_null = config.get("treatZeroAsNull", False)

        if not fields:
            ctx.log("未配置空值处理字段，跳过短期空值处理")
            return

        df = ctx.df

        # 转为数值类型
        for f in fields:
            df[f] = pd.to_numeric(df[f], errors="coerce")

        # 统计处理前缺失数（NaN + 0-当treatZeroAsNull）
        null_count_before = 0
        for f in fields:
            if treat_zero_as_null:
                null_count_before += int(df[f].isna().sum() + (df[f] == 0).sum())
            else:
                null_count_before += int(df[f].isna().sum())

        ctx.log(
            f"执行短期空值处理（横向滑动窗口均值），窗口大小：{window_size}，"
            f"判定条件：同行单个字段缺失（连续1个缺失点），"
            f"字段：{', '.join(fields)}，共 {null_count_before} 处缺失"
            + ("（含0视为空值）" if treat_zero_as_null else "")
        )

        total_filled = _fill_short_gap_horizontal(
            df, fields, ctx.columns, window_size, treat_zero_as_null, ctx
        )

        if total_filled > 0:
            ctx.log(f"短期空值处理完成，共补全 {total_filled} 处")
        else:
            ctx.log("短期空值处理完成，无短期缺失需补全（同行单个字段缺失）")
