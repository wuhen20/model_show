"""长期空值处理算子（横向>4个连续字段缺失）：支持统一策略 + KNN 补全"""
import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer

from .base import BaseOperator, CleanContext
from .nullfill import NullfillOperator
from .nullfill_short import _is_missing


def _detect_horizontal_long_gaps(df, fields, columns, treat_zero_as_null, max_nan_ratio, min_gap=5):
    """检测每行中横向连续缺失 >= min_gap 个字段且占比 < max_nan_ratio 的位置。
    当 treat_zero_as_null=True 时，0也视为缺失。
    返回 set of (row_index, field_name) 需要被 KNN 填充的位置。"""
    ordered = [(columns.index(f), f) for f in fields if f in columns]
    ordered.sort(key=lambda x: x[0])
    if not ordered:
        return set()

    n_fields = len(ordered)
    long_gap_positions = set()

    for row in df.index:
        # 检测缺失掩码
        missing_mask = []
        for _, col_name in ordered:
            missing_mask.append(_is_missing(df.at[row, col_name], treat_zero_as_null))

        # 检测连续缺失段
        i = 0
        while i < n_fields:
            if missing_mask[i]:
                start = i
                while i < n_fields and missing_mask[i]:
                    i += 1
                length = i - start
                # 检查连续缺失数 >= min_gap 且占比 < max_nan_ratio
                ratio = length / n_fields
                if length >= min_gap and ratio < max_nan_ratio:
                    for idx in range(start, i):
                        long_gap_positions.add((row, ordered[idx][1]))
            else:
                i += 1

    return long_gap_positions


class NullfillLongOperator(BaseOperator):
    node_type = "nullfill_long"

    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        strategy = config.get("strategy", "knn")

        # 统一策略：委托给 NullfillOperator 处理
        _UNIFIED_STRATEGIES = {
            "drop", "fill", "ffill", "bfill", "interpolate",
            "mean", "median", "hfill_forward", "hfill_backward", "hinterpolate",
        }
        if strategy in _UNIFIED_STRATEGIES:
            ctx.log(f"长期空值处理使用统一策略：{strategy}")
            NullfillOperator().execute(ctx, node, config)
            return

        # 独有策略：knn（横向缺失检测 + KNN 补全）
        fields_raw = config.get("fields", [])
        fields = [
            ctx.col_lower_map[f.lower()] for f in fields_raw
            if f.lower() in ctx.col_lower_map
        ]
        knn_k = config.get("knnK", 5)
        try:
            knn_k = int(knn_k)
        except (ValueError, TypeError):
            knn_k = 5
        if knn_k < 1:
            knn_k = 1
        max_nan_ratio = config.get("maxNanRatio", 0.5)
        try:
            max_nan_ratio = float(max_nan_ratio)
        except (ValueError, TypeError):
            max_nan_ratio = 0.5
        treat_zero_as_null = config.get("treatZeroAsNull", False)

        if not fields:
            ctx.log("未配置空值处理字段，跳过长期空值处理")
            return

        df = ctx.df

        # 转为数值类型
        for f in fields:
            df[f] = pd.to_numeric(df[f], errors="coerce")

        # 检测横向长期缺失（同行连续>4个字段缺失且占比<阈值）
        long_gap_positions = _detect_horizontal_long_gaps(
            df, fields, ctx.columns, treat_zero_as_null, max_nan_ratio, min_gap=5
        )

        if not long_gap_positions:
            ctx.log(f"无长期缺失（连续 >4 点且占比 <{max_nan_ratio:.0%}），跳过 KNN 补全")
            return

        # 统计处理前缺失数
        null_count_before = 0
        for f in fields:
            if treat_zero_as_null:
                null_count_before += int(df[f].isna().sum() + (df[f] == 0).sum())
            else:
                null_count_before += int(df[f].isna().sum())

        ctx.log(
            f"执行长期空值处理（KNN补全），K={knn_k}，"
            f"判定条件：连续 >4 点且占比 <{max_nan_ratio:.0%}，"
            f"检测到 {len(long_gap_positions)} 处长期缺失位置"
            + ("（含0视为空值）" if treat_zero_as_null else "")
        )

        # 构建 KNN 特征矩阵：用 DataFrame 中所有数值列作为特征
        numeric_cols = [
            c for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c])
        ]
        if len(numeric_cols) < 2:
            ctx.log("数值列不足，无法进行 KNN 补全")
            return

        feature_matrix = df[numeric_cols].values.astype(np.float64)

        # 当 treatZeroAsNull=True 时，0 也视为缺失，需在特征矩阵中替换为 NaN
        if treat_zero_as_null:
            feature_matrix[feature_matrix == 0] = np.nan

        # 过滤掉缺失过多的行（>60% NaN）
        train_nan_ratio = np.isnan(feature_matrix).sum(axis=1) / feature_matrix.shape[1]
        valid_train_mask = train_nan_ratio < 0.6
        if valid_train_mask.sum() < 2:
            ctx.log("有效样本不足，跳过 KNN 补全")
            return

        total_filled = 0
        try:
            k = min(knn_k, int(valid_train_mask.sum()))
            imputer = KNNImputer(n_neighbors=k, weights="distance")
            imputed = imputer.fit_transform(feature_matrix)

            # 只填充横向长期缺失位置
            col_idx_map = {c: i for i, c in enumerate(numeric_cols)}
            for row, col_name in long_gap_positions:
                if col_name in col_idx_map:
                    ci = col_idx_map[col_name]
                    orig_val = df.at[row, col_name]
                    imputed_val = imputed[df.index.get_loc(row), ci]
                    # 原值是NaN或0(当treatZeroAsNull)，且补全值有效
                    should_fill = pd.isna(orig_val) or (
                        treat_zero_as_null and orig_val == 0
                    )
                    if should_fill and not np.isnan(imputed_val) and np.isfinite(imputed_val):
                        df.at[row, col_name] = round(imputed_val, 4)
                        total_filled += 1
        except Exception as ex:
            ctx.log(f"KNN 补全失败：{str(ex)}")

        if total_filled > 0:
            ctx.log(f"长期空值处理完成，共补全 {total_filled} 处")
        else:
            ctx.log("长期空值处理完成，KNN 未填充任何值")
