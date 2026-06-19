"""
终端健康度评价系统 — FastAPI 路由
Isolation Forest + 多模块综合评分
"""
from pathlib import Path
from io import BytesIO, StringIO
import traceback
import pickle
import os

import numpy as np
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from app.demo_services import terminal_health_engine as engine
from app.core.config import settings

router = APIRouter()

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent.parent.parent  # backend/
_MODELS_DIR = _BACKEND_DIR / "models_pool" / "ZJ" / "terminal_health"
_EXPERIENCE_DIR = _BACKEND_DIR / "experience_data" / "ZJ" / "terminal_health"
_DEMO_CSV = _EXPERIENCE_DIR / "mock_terminal_data.csv"
_DEFAULT_MODEL = str(_MODELS_DIR / "best_model.pkl")

# 确保目录存在
_MODELS_DIR.mkdir(parents=True, exist_ok=True)
_EXPERIENCE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------
global_state = {
    "train_df": None,
    "trained_model": None,
    "model_info": None,
}


# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------
class TrainParams(BaseModel):
    use_optimization: bool = False
    optimize_n_calls: int = 20


class GridSearchParams(BaseModel):
    n_estimators_start: int = 100
    n_estimators_end: int = 500
    n_estimators_step: int = 100
    max_samples_start: float = 0.5
    max_samples_end: float = 1.0
    max_samples_step: float = 0.1
    max_features_start: float = 0.5
    max_features_end: float = 1.0
    max_features_step: float = 0.1
    module: str = "both"


class CVParams(BaseModel):
    n_folds: int = 5
    use_optimization: bool = False


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _to_native(val):
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, dict):
        return {k: _to_native(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_to_native(v) for v in val]
    return val


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@router.get("/ping")
def ping():
    return {"status": "ok", "message": "terminal health demo is alive"}


@router.get("/model_info")
def model_info():
    return {
        "model_name": "Isolation Forest + 多模块综合评分",
        "model_path": _DEFAULT_MODEL,
        "has_model": os.path.exists(_DEFAULT_MODEL),
        "modules": ["使用年限", "通讯模块", "终端特征", "下挂设备", "厂商质量"],
        "weights": {"score_years": 0.25, "score_comm": 0.10, "score_module3": 0.30, "score_module4": 0.15, "score_MFR": 0.20},
    }


@router.get("/demo_csv")
def serve_demo_csv():
    if _DEMO_CSV.exists():
        return FileResponse(str(_DEMO_CSV), media_type="text/csv", filename="mock_terminal_data.csv")
    raise HTTPException(status_code=404, detail="演示数据文件不存在")


@router.get("/data_info")
def data_info():
    df = global_state["train_df"]
    if df is None:
        return {"status": "no_data", "message": "尚未上传数据"}

    info = {
        "status": "ok",
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "preview": df.head(5).fillna(0).round(4).to_dict(orient="records"),
    }

    if "is_removed" in df.columns:
        info["removal_rate"] = round(df["is_removed"].mean(), 4)
        info["removal_count"] = int(df["is_removed"].sum())
    if "MFR" in df.columns:
        info["manufacturers"] = df["MFR"].unique().tolist()
        info["manufacturer_count"] = df["MFR"].nunique()

    return info


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    try:
        content = await file.read()
        for encoding in ["utf-8-sig", "utf-8", "gbk", "gb2312"]:
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return {"status": "error", "message": "无法识别文件编码"}

        df = pd.read_csv(StringIO(text))
        df = engine.preprocess_features(df)

        global_state["train_df"] = df
        global_state["trained_model"] = None
        global_state["model_info"] = None

        return {
            "status": "ok",
            "message": f"成功上传数据: {len(df)} 行, {len(df.columns)} 列",
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": df.columns.tolist(),
        }
    except Exception as e:
        return {"status": "error", "message": f"上传失败: {str(e)}"}


@router.post("/train")
async def train_model(params: TrainParams = TrainParams()):
    df = global_state["train_df"]
    if df is None:
        return {"status": "error", "message": "请先上传训练数据"}

    try:
        import matplotlib.pyplot as plt
        plt.ioff()

        result_df, best_models = engine.main(
            df.copy(),
            use_param_optimization=params.use_optimization,
            optimize_n_calls=params.optimize_n_calls,
        )

        # 保存模型
        model_path = str(_MODELS_DIR / "best_model.pkl")
        global_state["trained_model"] = model_path

        # 评分统计
        score_cols = [
            "score_years", "score_comm", "score_module3",
            "score_module4", "score_MFR", "total_score",
        ]
        score_stats = {}
        for col in score_cols:
            if col in result_df.columns:
                score_stats[col] = {
                    "mean": round(float(result_df[col].mean()), 2),
                    "std": round(float(result_df[col].std()), 2),
                    "min": round(float(result_df[col].min()), 2),
                    "max": round(float(result_df[col].max()), 2),
                    "median": round(float(result_df[col].median()), 2),
                }

        # 等级分布
        grade_dist = result_df["grade"].value_counts().to_dict() if "grade" in result_df.columns else {}

        # 厂商分析
        mfr_analysis = None
        if "MFR" in result_df.columns and "total_score" in result_df.columns:
            mfr_grouped = result_df.groupby("MFR")["total_score"].agg(["mean", "count", "std"]).round(2)
            mfr_analysis = mfr_grouped.sort_values("mean", ascending=False).reset_index().to_dict(orient="records")

        # 评分分布
        score_distribution = None
        if "total_score" in result_df.columns:
            hist, edges = np.histogram(result_df["total_score"], bins=20)
            score_distribution = {
                "counts": hist.tolist(),
                "edges": [round(e, 2) for e in edges.tolist()],
                "labels": [f"{round(edges[i], 1)}-{round(edges[i+1], 1)}" for i in range(len(hist))],
            }

        # 拆除 vs 运行分布
        removal_distribution = None
        if "is_removed" in result_df.columns and "total_score" in result_df.columns:
            removed_scores = result_df[result_df["is_removed"] == 1]["total_score"].tolist()
            normal_scores = result_df[result_df["is_removed"] == 0]["total_score"].tolist()
            removal_distribution = {
                "removed": [round(s, 2) for s in removed_scores[:200]],
                "normal": [round(s, 2) for s in normal_scores[:200]],
            }

        # 权重
        weights = {"score_years": 0.25, "score_comm": 0.10, "score_module3": 0.30, "score_module4": 0.15, "score_MFR": 0.20}

        global_state["model_info"] = {
            "score_stats": score_stats,
            "grade_dist": grade_dist,
            "mfr_analysis": mfr_analysis,
            "score_distribution": score_distribution,
            "removal_distribution": removal_distribution,
            "total_samples": len(result_df),
            "weights": weights,
        }

        return {
            "status": "ok",
            "message": "训练完成",
            "score_stats": score_stats,
            "grade_dist": grade_dist,
            "mfr_analysis": mfr_analysis,
            "score_distribution": score_distribution,
            "removal_distribution": removal_distribution,
            "total_samples": len(result_df),
            "weights": weights,
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"训练失败: {str(e)}"}


@router.post("/grid_search")
async def grid_search(params: GridSearchParams):
    df = global_state["train_df"]
    if df is None:
        return {"status": "error", "message": "请先上传训练数据"}

    try:
        modules_to_run = []
        if params.module in ("module3", "both"):
            modules_to_run.append({
                "key": "module3",
                "name": "模块3 - 终端自身特征检测",
                "features": [
                    "CPU_RATE", "CPU_RATE_AVG", "DISK_RATE", "DISK_RATE_AVG",
                    "TEMP_ERR_RATE", "ONLINE_DUR", "ONLINE_TIME", "SIG_STR",
                    "ONOFF_NUM", "ONOFF_30D_NUM", "OFFSET_TIME",
                ],
            })
        if params.module in ("module4", "both"):
            modules_to_run.append({
                "key": "module4",
                "name": "模块4 - 下挂设备特征检测",
                "features": [
                    "FLOW_STAT", "METER_NET_RATE", "CUST_NUM_FLAG",
                    "COLL_FAIL_RATE_7D", "METER_FAIL_RATE",
                    "POWEROFF_NUM_30D", "TASK_SUCC_RATE",
                ],
            })

        y_removed = df["is_removed"].values if "is_removed" in df.columns else None
        if y_removed is None or len(np.unique(y_removed)) < 2:
            return {"status": "error", "message": "数据中需要有 is_removed 列且包含至少两种类别"}

        all_module_results = []
        for mod in modules_to_run:
            feature_cols = mod["features"]
            missing = [f for f in feature_cols if f not in df.columns]
            if missing:
                all_module_results.append({
                    "module": mod["key"],
                    "module_name": mod["name"],
                    "status": "error",
                    "message": f"缺少特征列: {missing}",
                })
                continue

            X = df[feature_cols].copy().fillna(df[feature_cols].median())

            best_params, grid_results = engine.grid_search_isolation_forest(
                X, y_removed,
                n_estimators_start=params.n_estimators_start,
                n_estimators_end=params.n_estimators_end,
                n_estimators_step=params.n_estimators_step,
                max_samples_start=params.max_samples_start,
                max_samples_end=params.max_samples_end,
                max_samples_step=params.max_samples_step,
                max_features_start=params.max_features_start,
                max_features_end=params.max_features_end,
                max_features_step=params.max_features_step,
                random_state=42,
                verbose=False,
            )

            n_est_values = sorted(list(set(r["n_estimators"] for r in grid_results)))
            max_samp_values = sorted(list(set(r["max_samples"] for r in grid_results)))
            max_feat_values = sorted(list(set(r["max_features"] for r in grid_results)))

            heatmaps = {}
            for mf in max_feat_values:
                mf_results = [r for r in grid_results if r["max_features"] == mf]
                auc_matrix = []
                for ms in max_samp_values:
                    row = []
                    for ne in n_est_values:
                        match = [r for r in mf_results if r["n_estimators"] == ne and r["max_samples"] == ms]
                        auc_val = match[0]["auc"] if match else 0.0
                        row.append(round(auc_val, 4))
                    auc_matrix.append(row)
                heatmaps[round(mf, 4)] = {
                    "x_labels": n_est_values,
                    "y_labels": [round(v, 4) for v in max_samp_values],
                    "matrix": auc_matrix,
                }

            all_module_results.append({
                "status": "ok",
                "module": mod["key"],
                "module_name": mod["name"],
                "best_params": best_params,
                "best_auc": max(r["auc"] for r in grid_results),
                "grid_results": grid_results,
                "max_features_values": [round(v, 4) for v in max_feat_values],
                "heatmaps": heatmaps,
            })

        msg = "、".join([r["module_name"] for r in all_module_results if r["status"] == "ok"])

        # Grid Search 完成后自动训练模型
        import matplotlib.pyplot as plt
        plt.ioff()
        try:
            result_df, _ = engine.main(df.copy(), use_param_optimization=False)
            model_path = str(_MODELS_DIR / "best_model.pkl")
            global_state["trained_model"] = model_path
            auto_trained = True
        except Exception:
            auto_trained = False

        final_msg = f"Grid Search 完成: {msg}" if msg else "Grid Search 全部失败"
        if auto_trained:
            final_msg += "（已自动训练模型，可直接预测）"

        return {
            "status": "ok",
            "message": final_msg,
            "modules": all_module_results,
            "auto_trained": auto_trained,
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"Grid Search 失败: {str(e)}"}


@router.post("/cross_validate")
async def cross_validate(params: CVParams = CVParams()):
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import roc_auc_score
    import matplotlib.pyplot as plt
    plt.ioff()

    df = global_state["train_df"]
    if df is None:
        return {"status": "error", "message": "请先上传训练数据"}

    if "is_removed" not in df.columns:
        return {"status": "error", "message": "数据中需要有 is_removed 列"}

    y = df["is_removed"].values
    if len(np.unique(y)) < 2:
        return {"status": "error", "message": "is_removed 需要至少两种类别"}

    try:
        skf = StratifiedKFold(n_splits=params.n_folds, shuffle=True, random_state=42)
        fold_results = []
        all_test_predictions = np.zeros(len(df))

        for fold_idx, (train_idx, test_idx) in enumerate(skf.split(df, y), 1):
            df_train_fold = df.iloc[train_idx].reset_index(drop=True)
            df_test_fold = df.iloc[test_idx].reset_index(drop=True)

            result_train, _ = engine.main(
                df_train_fold.copy(),
                use_param_optimization=params.use_optimization,
                optimize_n_calls=15,
            )

            df_test_pred = engine.predict_with_best_model(
                df.iloc[test_idx].reset_index(drop=True).copy(),
                model_path="best_model.pkl",
            )

            y_test = df_test_pred["is_removed"].values
            scores = df_test_pred["total_score"].values

            if len(np.unique(y_test)) > 1:
                fold_auc = roc_auc_score(y_test, -scores)
            else:
                fold_auc = None

            removed_indices = np.where(y_test == 1)[0]
            rank_quantiles = []
            for i in removed_indices:
                rank = np.sum(scores <= scores[i]) / len(scores)
                rank_quantiles.append(round(float(rank), 4))

            fold_info = {
                "fold": fold_idx,
                "train_size": len(train_idx),
                "test_size": len(test_idx),
                "auc": round(float(fold_auc), 4) if fold_auc is not None else None,
                "avg_rank_quantile": round(float(np.mean(rank_quantiles)), 4) if rank_quantiles else None,
                "removed_count": int(len(removed_indices)),
                "mean_score": round(float(scores.mean()), 2),
                "std_score": round(float(scores.std()), 2),
            }
            fold_results.append(fold_info)
            all_test_predictions[test_idx] = scores

        auc_values = [f["auc"] for f in fold_results if f["auc"] is not None]
        mean_auc = round(float(np.mean(auc_values)), 4) if auc_values else None
        std_auc = round(float(np.std(auc_values)), 4) if auc_values else None

        if len(np.unique(y)) > 1:
            overall_auc = round(float(roc_auc_score(y, -all_test_predictions)), 4)
        else:
            overall_auc = None

        auc_chart = {
            "labels": [f"Fold {f['fold']}" for f in fold_results],
            "values": [f["auc"] if f["auc"] is not None else 0 for f in fold_results],
        }

        all_ranks = []
        for f in fold_results:
            if f["avg_rank_quantile"] is not None:
                all_ranks.append(f["avg_rank_quantile"])
        avg_rank_overall = round(float(np.mean(all_ranks)), 4) if all_ranks else None

        if mean_auc and mean_auc >= 0.8:
            evaluation = "优秀 (AUC >= 0.8)"
        elif mean_auc and mean_auc >= 0.7:
            evaluation = "良好 (0.7 <= AUC < 0.8)"
        elif mean_auc and mean_auc >= 0.6:
            evaluation = "一般 (0.6 <= AUC < 0.7)"
        else:
            evaluation = "待优化 (AUC < 0.6)"

        return {
            "status": "ok",
            "message": f"K-Fold 交叉验证完成 ({params.n_folds} 折)",
            "n_folds": params.n_folds,
            "fold_results": fold_results,
            "mean_auc": mean_auc,
            "std_auc": std_auc,
            "overall_auc": overall_auc,
            "avg_rank_quantile": avg_rank_overall,
            "evaluation": evaluation,
            "auc_chart": auc_chart,
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"交叉验证失败: {str(e)}"}


@router.post("/predict")
async def predict(file: UploadFile = File(...)):
    model_path = global_state.get("trained_model")
    if model_path is None or not os.path.exists(model_path):
        if os.path.exists(_DEFAULT_MODEL):
            model_path = _DEFAULT_MODEL
        else:
            return {"status": "error", "message": "请先训练模型或上传预训练模型"}

    try:
        content = await file.read()
        for encoding in ["utf-8-sig", "utf-8", "gbk", "gb2312"]:
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return {"status": "error", "message": "无法识别文件编码"}

        df = pd.read_csv(StringIO(text))
        result_df = engine.predict_with_best_model(df, model_path=model_path)

        display_cols = [
            "meter_id", "MFR", "total_score", "grade",
            "score_years", "score_comm", "score_module3",
            "score_module4", "score_MFR",
        ]
        display_cols = [c for c in display_cols if c in result_df.columns]

        results = result_df[display_cols].round(2).to_dict(orient="records") if display_cols else []

        grade_dist = result_df["grade"].value_counts().to_dict() if "grade" in result_df.columns else {}

        return {
            "status": "ok",
            "message": f"预测完成，共 {len(result_df)} 条数据",
            "results": results,
            "grade_dist": grade_dist,
            "total_samples": len(result_df),
            "columns": display_cols,
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"预测失败: {str(e)}"}