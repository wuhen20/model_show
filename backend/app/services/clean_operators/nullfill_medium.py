"""中期空值处理算子（横向2-4个连续字段缺失）：支持统一策略 + 拉格朗日插值补全"""
import numpy as np
import pandas as pd
from scipy.interpolate import lagrange

from .base import BaseOperator, CleanContext
from .nullfill import NullfillOperator
from .nullfill_short import _is_missing


def _fill_medium_gap_horizontal(df, fields, columns, treat_zero_as_null, ctx):
    """横向拉格朗日插值补全：对每行，检测同行中2-4个连续字段的缺失，用拉格朗日插值补全。
    当 treat_zero_as_null=True 时，0也视为缺失参与检测，但不被替换为NaN。

    df: DataFrame（原地修改）
    fields: 需要处理的字段列表
    columns: 全部列名有序列表
    ctx: CleanContext
    """
    # 按列在 columns 中的顺序排列 fields
    ordered = [(columns.index(f), f) for f in fields if f in columns]
    ordered.sort(key=lambda x: x[0])
    if not ordered:
        return 0

    n_fields = len(ordered)
    margin = 6  # 参考点数量上限

    total_filled = 0
    for row in df.index:
        # 提取该行所有 fields 的值和缺失掩码
        row_vals = np.empty(n_fields, dtype=np.float64)
        missing_mask = np.zeros(n_fields, dtype=bool)
        for i, (_, col_name) in enumerate(ordered):
            val = df.at[row, col_name]
            if _is_missing(val, treat_zero_as_null):
                missing_mask[i] = True
                row_vals[i] = np.nan
            else:
                row_vals[i] = float(val)

        # 检测横向连续缺失段
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

        # 只处理 2-4 个连续缺失（中期）
        medium_gaps = [g for g in gaps if 2 <= g[2] <= 4]

        for s, e, gap_len in medium_gaps:
            # 收集 gap 外的有效参考点
            ref_indices = []
            ref_values = []
            for k in range(n_fields):
                if (k < s or k >= e) and not missing_mask[k]:
                    ref_indices.append(k)
                    ref_values.append(row_vals[k])

            if len(ref_indices) < 2:
                continue

            # 按距离 gap 中心排序，取最近的 margin 个
            gap_center = (s + e - 1) / 2.0
            paired = list(zip(ref_indices, ref_values))
            paired.sort(key=lambda x: abs(x[0] - gap_center))
            selected = sorted(paired[:margin], key=lambda x: x[0])

            x_valid = np.array([p[0] for p in selected], dtype=np.float64)
            y_valid = np.array([p[1] for p in selected])

            # 数值稳定性检查
            if not np.all(np.isfinite(y_valid)) or np.max(np.abs(y_valid)) > 1e308:
                filled = _linear_fallback_row(row_vals, missing_mask, s, e)
                for idx, val in filled:
                    df.at[row, ordered[idx][1]] = round(val, 4)
                    total_filled += 1
                continue

            try:
                with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
                    poly = lagrange(x_valid, y_valid)
                for idx in range(s, e):
                    val = float(poly(float(idx)))
                    if np.isfinite(val):
                        df.at[row, ordered[idx][1]] = round(val, 4)
                        total_filled += 1
            except (ValueError, np.linalg.LinAlgError):
                filled = _linear_fallback_row(row_vals, missing_mask, s, e)
                for idx, val in filled:
                    df.at[row, ordered[idx][1]] = round(val, 4)
                    total_filled += 1

    return total_filled


def _linear_fallback_row(row_vals, missing_mask, start, end):
    """线性插值回退：对横向一段缺失用两端有效值线性插值。
    返回 [(field_idx, filled_val), ...]"""
    left_val, left_idx = None, None
    for k in range(start - 1, -1, -1):
        if not missing_mask[k]:
            left_val, left_idx = row_vals[k], k
            break
    right_val, right_idx = None, None
    for k in range(end, len(row_vals)):
        if not missing_mask[k]:
            right_val, right_idx = row_vals[k], k
            break

    filled = []
    if left_val is not None and right_val is not None:
        span = right_idx - left_idx
        for idx in range(start, end):
            ratio = (idx - left_idx) / span
            val = left_val + ratio * (right_val - left_val)
            if np.isfinite(val):
                filled.append((idx, val))
    elif left_val is not None:
        for idx in range(start, end):
            filled.append((idx, left_val))
    elif right_val is not None:
        for idx in range(start, end):
            filled.append((idx, right_val))
    return filled


class NullfillMediumOperator(BaseOperator):
    node_type = "nullfill_medium"

    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        strategy = config.get("strategy", "lagrange")

        # 统一策略：委托给 NullfillOperator 处理
        _UNIFIED_STRATEGIES = {
            "drop", "fill", "ffill", "bfill", "interpolate",
            "mean", "median", "hfill_forward", "hfill_backward", "hinterpolate",
        }
        if strategy in _UNIFIED_STRATEGIES:
            ctx.log(f"中期空值处理使用统一策略：{strategy}")
            NullfillOperator().execute(ctx, node, config)
            return

        # 独有策略：lagrange（横向拉格朗日插值）
        fields_raw = config.get("fields", [])
        fields = [
            ctx.col_lower_map[f.lower()] for f in fields_raw
            if f.lower() in ctx.col_lower_map
        ]
        treat_zero_as_null = config.get("treatZeroAsNull", False)

        if not fields:
            ctx.log("未配置空值处理字段，跳过中期空值处理")
            return

        df = ctx.df

        # 转为数值类型
        for f in fields:
            df[f] = pd.to_numeric(df[f], errors="coerce")

        # 统计处理前缺失数
        null_count_before = 0
        for f in fields:
            if treat_zero_as_null:
                null_count_before += int(df[f].isna().sum() + (df[f] == 0).sum())
            else:
                null_count_before += int(df[f].isna().sum())

        ctx.log(
            f"执行中期空值处理（横向拉格朗日插值），"
            f"判定条件：同行2-4个连续字段缺失，"
            f"字段：{', '.join(fields)}，共 {null_count_before} 处缺失"
            + ("（含0视为空值）" if treat_zero_as_null else "")
        )

        total_filled = _fill_medium_gap_horizontal(
            df, fields, ctx.columns, treat_zero_as_null, ctx
        )

        if total_filled > 0:
            ctx.log(f"中期空值处理完成，共补全 {total_filled} 处")
        else:
            ctx.log("中期空值处理完成，无中期缺失需补全（同行2-4个连续字段）")
