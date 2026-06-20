"""
推理：K-means 分簇 + LightGBM 成功率预测 + TopK 补召时段
（加载预训练模型，不做训练）
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd


N_POINTS_PER_DAY = 96
LGB_FEATURE_LAG_DAYS = 7


class ModelBundle:
    """加载 5 个预训练模型 + manifest，提供推理接口"""

    def __init__(self, model_dir: str | Path):
        self.model_dir = Path(model_dir)
        manifest_path = self.model_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"找不到 {manifest_path}")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        # K-means
        self.kmeans = joblib.load(self.model_dir / "kmeans.joblib")

        # 4 个 LightGBM
        self.lgb_models: dict[int, lgb.Booster] = {}
        for m in self.manifest["models"]:
            if m["type"] == "LightGBM":
                cid = int(m["applies_to_cluster"])
                self.lgb_models[cid] = lgb.Booster(model_file=str(self.model_dir / m["file"]))

        self.cluster_meta = {
            int(m["applies_to_cluster"]): m
            for m in self.manifest["models"] if m["type"] == "LightGBM"
        }

    def info(self) -> dict:
        return {
            "project":  self.manifest.get("project"),
            "version":  self.manifest.get("version"),
            "generated_at": self.manifest.get("generated_at"),
            "n_clusters": len(self.lgb_models),
            "models": [
                {k: m.get(k) for k in ("id", "name", "type", "framework", "size_bytes")}
                for m in self.manifest["models"]
            ],
        }

    # -------------------------------------------------- K-means
    def predict_cluster(self, curve_96: Sequence[float]) -> int:
        """输入 96 点曲线 → 返回簇 ID"""
        arr = np.asarray(curve_96, dtype=float)
        if arr.shape != (N_POINTS_PER_DAY,):
            raise ValueError(f"curve_96 必须是 96 维向量，收到 shape={arr.shape}")
        return int(self.kmeans.predict(arr.reshape(1, -1))[0])

    # -------------------------------------------------- LightGBM 单点
    def predict_success_rate(
        self,
        cluster_id: int,
        lags: Sequence[float],
        slot: int,
        dow: int,
    ) -> float:
        """
        输入：簇 id + 过去 7 天同 slot 的成功率 + slot + 星期几
        输出：预测的下一日同 slot 的采集成功率 [0,1]
        """
        if cluster_id not in self.lgb_models:
            raise ValueError(f"cluster_id={cluster_id} 不在 0..{len(self.lgb_models)-1}")
        lags = list(lags)
        if len(lags) != LGB_FEATURE_LAG_DAYS:
            raise ValueError(f"lags 必须是 {LGB_FEATURE_LAG_DAYS} 维，收到 {len(lags)} 维")
        if not (0 <= slot < N_POINTS_PER_DAY):
            raise ValueError(f"slot 必须在 [0, {N_POINTS_PER_DAY-1}]，收到 {slot}")
        if not (0 <= dow <= 6):
            raise ValueError(f"dow 必须在 [0, 6]，收到 {dow}")
        feat = lags + [int(slot), slot * 15 / 60, int(dow)]
        booster = self.lgb_models[cluster_id]
        yhat = float(booster.predict(np.array([feat]))[0])
        return max(0.0, min(1.0, yhat))

    # -------------------------------------------------- LightGBM 整日
    def predict_24h_curve(
        self,
        cluster_id: int,
        slot_lags: Sequence[Sequence[float]],
        dow: int,
    ) -> list[dict]:
        """
        输入：簇 id + 96 个 slot 各自的 lag1..7 + 星期几
        输出：[{slot, hour, predicted_success}, ...]，长度 96
        """
        if len(slot_lags) != N_POINTS_PER_DAY:
            raise ValueError(f"slot_lags 必须是 96 × 7 矩阵")
        out = []
        for slot in range(N_POINTS_PER_DAY):
            lags = slot_lags[slot]
            yhat = self.predict_success_rate(cluster_id, lags, slot, dow)
            out.append({"slot": slot, "hour": round(slot * 15 / 60, 2), "predicted_success": round(yhat, 4)})
        return out

    # -------------------------------------------------- TopK 补召时段
    def topk_recall_slots(
        self,
        curve: Sequence[dict],
        threshold: float = 0.80,
        topk: int = 6,
    ) -> dict:
        """
        从一条 24h 预测曲线中选 TopK 高分时段（满足 >= threshold）
        输入：predict_24h_curve 的输出（或同结构）
        输出：{recall_slots, recall_times, n_slots, min/max/mean_predicted}
        """
        df = pd.DataFrame(list(curve))
        eligible = df[df["predicted_success"] >= float(threshold)]
        top = eligible.nlargest(int(topk), "predicted_success").sort_values("slot")
        if top.empty:
            top = df.nlargest(int(topk), "predicted_success").sort_values("slot")
        slot_list = [int(s) for s in top["slot"].tolist()]
        time_list = [f"{int(s*15//60):02d}:{int(s*15%60):02d}" for s in slot_list]
        return {
            "recall_slots":  slot_list,
            "recall_times":  time_list,
            "n_slots":       len(slot_list),
            "threshold":     float(threshold),
            "min_predicted": float(top["predicted_success"].min()),
            "max_predicted": float(top["predicted_success"].max()),
            "mean_predicted": float(top["predicted_success"].mean()),
        }
