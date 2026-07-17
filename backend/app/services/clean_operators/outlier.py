"""异常值处理算子"""
import numpy as np
import pandas as pd

from .base import BaseOperator, CleanContext


class OutlierOperator(BaseOperator):
    node_type = "outlier"

    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        outlier_fields_raw = config.get("fields", [])
        outlier_fields = [
            ctx.col_lower_map[f.lower()] for f in outlier_fields_raw
            if f.lower() in ctx.col_lower_map
        ]
        check_negative = config.get("checkNegative", True)
        abs_threshold = config.get("absThreshold")
        strategy = config.get("strategy", "setnull")

        if not outlier_fields:
            ctx.log("未配置异常值处理字段，跳过异常值处理")
            return

        df = ctx.df
        # 将字段转为数值类型以便检测
        for f in outlier_fields:
            df[f] = pd.to_numeric(df[f], errors="coerce")

        # 构建异常值掩码
        outlier_mask = pd.Series(False, index=df.index)
        condition_desc = []

        if check_negative:
            neg_mask = df[outlier_fields].lt(0).any(axis=1)
            neg_count = int(neg_mask.sum())
            outlier_mask = outlier_mask | neg_mask
            condition_desc.append(f"负值({neg_count}行)")

        threshold_val = None
        if abs_threshold is not None and abs_threshold != "":
            try:
                threshold_val = float(abs_threshold)
            except (ValueError, TypeError):
                threshold_val = None
            if threshold_val is not None and threshold_val >= 0:
                abs_mask = df[outlier_fields].abs().gt(threshold_val).any(axis=1)
                abs_count = int(abs_mask.sum())
                outlier_mask = outlier_mask | abs_mask
                condition_desc.append(f"绝对值>{threshold_val}({abs_count}行)")

        outlier_rows = int(outlier_mask.sum())
        ctx.log(
            f"执行异常值处理，检测条件：{'，'.join(condition_desc)}，"
            f"字段：{', '.join(outlier_fields)}，共 {outlier_rows} 行含异常值"
        )

        if strategy == "setnull" and outlier_rows > 0:
            # 仅将异常行中异常字段的值置为 NaN
            for f in outlier_fields:
                cell_mask = pd.Series(False, index=df.index)
                if check_negative:
                    cell_mask = cell_mask | (df[f] < 0)
                if threshold_val is not None and threshold_val >= 0:
                    cell_mask = cell_mask | (df[f].abs() > threshold_val)
                set_count = int(cell_mask.sum())
                if set_count > 0:
                    # 使用 .mask() 方法确保赋值生效（比 df.loc[...] = np.nan 更可靠）
                    df[f] = df[f].mask(cell_mask, np.nan)
                    # 验证赋值是否生效
                    first_idx = cell_mask.idxmax()
                    verify_val = df.at[first_idx, f]
                    ctx.log(
                        f"字段 {f} 置空 {set_count} 个异常值，"
                        f"验证：行{first_idx}的值={verify_val}，类型={type(verify_val).__name__}"
                    )

        ctx.log(f"异常值处理完成，共处理 {outlier_rows} 行含异常值的数据")
