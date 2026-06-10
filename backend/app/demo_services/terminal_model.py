"""
终端异常研判 XGBoost 多标签分类 — 模型核心逻辑
从 terminal_server.py 提取，适配 FastAPI 架构
"""
import os
import time
import traceback
from io import BytesIO
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    hamming_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from app.core.config import settings

# ---------------------------------------------------------------------------
# 路径计算
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent.parent  # backend/
_MODELS_DIR = _BACKEND_DIR / settings.models_pool_dir  # models_pool/
_EXPERIENCE_DIR = _BACKEND_DIR / settings.experience_data_dir  # experience_data/

DEFAULT_MODEL_PATH = str(_MODELS_DIR / "ZJ" / "terminal" / "terminal_xgb_model.joblib")
TUNED_MODEL_PATH = str(_MODELS_DIR / "ZJ" / "terminal" / "terminal_xgb_model_tuned.joblib")
DEMO_CSV_PATH = str(_EXPERIENCE_DIR / "ZJ" / "terminal" / "terminal_demo_100.csv")
current_model_path = DEFAULT_MODEL_PATH

# 调优状态
_tune_status = {"running": False, "progress": 0, "message": ""}


def get_tune_status() -> dict:
    return dict(_tune_status)


def set_tune_status(running: bool, progress: int, message: str):
    global _tune_status
    _tune_status = {"running": running, "progress": progress, "message": message}


# ---------------------------------------------------------------------------
# 常量配置
# ---------------------------------------------------------------------------
LABEL_COLUMNS = [
    "RMT_CHN_FLAG", "FLOW_FLAG", "POWEROFF_FLAG", "CLOCK_FLAG",
    "TMNL_NET_FLAG", "VER_FLAG", "TASK_FLAG", "TMNLTASK_FLAG",
    "OLD_FLAG", "STORAGE_FLAG", "NO_COMM_FLAG", "ENV_FLAG", "CARRIER_FLAG",
]

LABEL_CN_MAP = {
    "RMT_CHN_FLAG": "远程信道异常",
    "FLOW_FLAG": "上下行流量异常",
    "POWEROFF_FLAG": "终端停电异常",
    "CLOCK_FLAG": "终端时钟异常",
    "TMNL_NET_FLAG": "台区组网异常",
    "VER_FLAG": "终端版本异常",
    "TASK_FLAG": "终端采集方案异常",
    "TMNLTASK_FLAG": "采集任务监控集异常",
    "OLD_FLAG": "设备老旧异常",
    "STORAGE_FLAG": "设备存储溢出",
    "NO_COMM_FLAG": "终端与主站无通信",
    "ENV_FLAG": "运行环境影响",
    "CARRIER_FLAG": "终端载波模块异常",
}

FEATURE_CN_MAP = {
    "SIG_STR": "信号强度",
    "ONOFF_NUM": "上下线次数",
    "FLOW_STAT": "上下行流量饱和度",
    "OFFSET_TIME": "时钟偏差",
    "METER_NET_RATE": "电表组网异常率",
    "CUST_NUM_FLAG": "下挂用户数是否超过阈值",
    "RUN_YEARS": "建档年限",
    "COLL_FAIL_RATE_7D": "最近7天采集成功率不合格占比",
    "ONLINE_DUR": "连续在线时长",
    "MSG_TIME": "消息时间",
    "TEMP_ERR_RATE": "设备温度异常点数占比",
    "METER_FAIL_RATE": "采集失败电表占比",
}

# 网格搜索参数组合
PARAM_GRID = [
    {"n_estimators": 120, "max_depth": 3, "learning_rate": 0.06, "subsample": 0.9, "colsample_bytree": 0.9, "reg_lambda": 1.0, "min_child_weight": 2},
    {"n_estimators": 240, "max_depth": 4, "learning_rate": 0.06, "subsample": 0.9, "colsample_bytree": 0.9, "reg_lambda": 1.0, "min_child_weight": 2},
    {"n_estimators": 300, "max_depth": 4, "learning_rate": 0.04, "subsample": 0.9, "colsample_bytree": 0.9, "reg_lambda": 1.0, "min_child_weight": 2},
    {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.08, "subsample": 0.85, "colsample_bytree": 0.85, "reg_lambda": 0.5, "min_child_weight": 1},
    {"n_estimators": 200, "max_depth": 6, "learning_rate": 0.04, "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 2.0, "min_child_weight": 3},
    {"n_estimators": 250, "max_depth": 5, "learning_rate": 0.05, "subsample": 0.9, "colsample_bytree": 0.9, "reg_lambda": 1.0, "min_child_weight": 2},
]

# ---------------------------------------------------------------------------
# 全局模型状态
# ---------------------------------------------------------------------------
models = {}
feature_columns = []
thresholds = {}
scale_pos_weights = {}
feature_importance_dict = {}


def reload_model(model_path: str = None):
    """加载或重载模型，更新全局变量"""
    global models, feature_columns, thresholds, scale_pos_weights, feature_importance_dict, current_model_path

    if model_path is None:
        model_path = DEFAULT_MODEL_PATH

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")

    print(f"[terminal] 加载模型: {model_path}", flush=True)
    artifact = joblib.load(model_path)
    models = artifact["models"]
    feature_columns = artifact["feature_columns"]
    thresholds = artifact.get("thresholds", {label: 0.5 for label in LABEL_COLUMNS})
    scale_pos_weights = artifact.get("scale_pos_weight", {label: 1.0 for label in LABEL_COLUMNS})
    current_model_path = model_path

    # 提取特征重要性
    feature_importance_dict = {}
    for label in LABEL_COLUMNS:
        if label in models:
            imp = models[label].feature_importances_.tolist()
            sorted_idx = sorted(range(len(imp)), key=lambda i: imp[i], reverse=True)
            feature_importance_dict[label] = {
                "features": [feature_columns[i] for i in sorted_idx],
                "importance": [round(imp[i], 6) for i in sorted_idx],
            }
        else:
            feature_importance_dict[label] = {"features": [], "importance": []}

    print(f"[terminal] 模型加载完成, 特征数={len(feature_columns)}, 标签数={len(LABEL_COLUMNS)}", flush=True)


# 初始加载
if os.path.exists(DEFAULT_MODEL_PATH):
    reload_model(DEFAULT_MODEL_PATH)
else:
    print(f"[terminal] 警告: 模型文件不存在 {DEFAULT_MODEL_PATH}", flush=True)


def get_model_info() -> dict:
    """返回模型元信息"""
    return {
        "model_path": current_model_path,
        "model_name": os.path.basename(current_model_path),
        "is_tuned": "tuned" in os.path.basename(current_model_path).lower(),
        "feature_columns": feature_columns,
        "label_columns": LABEL_COLUMNS,
        "label_cn_map": LABEL_CN_MAP,
        "feature_cn_map": FEATURE_CN_MAP,
        "thresholds": thresholds,
        "scale_pos_weight": scale_pos_weights,
        "feature_importance": feature_importance_dict,
        "demo_csv_path": DEMO_CSV_PATH,
    }


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------
def _to_native(val):
    """递归转换 numpy 类型为 Python 原生类型"""
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


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict:
    """计算多标签分类的全量指标"""
    metrics = {
        "subset_accuracy": float(accuracy_score(y_true, y_pred)),
        "micro_f1": float(f1_score(y_true, y_pred, average="micro", zero_division=0)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "micro_precision": float(precision_score(y_true, y_pred, average="micro", zero_division=0)),
        "micro_recall": float(recall_score(y_true, y_pred, average="micro", zero_division=0)),
        "hamming_loss": float(hamming_loss(y_true, y_pred)),
        "per_label": {},
    }
    for i, label in enumerate(LABEL_COLUMNS):
        result = {
            "f1": float(f1_score(y_true[:, i], y_pred[:, i], zero_division=0)),
            "precision": float(precision_score(y_true[:, i], y_pred[:, i], zero_division=0)),
            "recall": float(recall_score(y_true[:, i], y_pred[:, i], zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(y_true[:, i], y_pred[:, i])),
        }
        unique_vals = np.unique(y_true[:, i])
        if len(unique_vals) > 1:
            result["auc"] = float(roc_auc_score(y_true[:, i], y_prob[:, i]))
        else:
            result["auc"] = None
        metrics["per_label"][label] = result
    return metrics


def run_predictions(df: pd.DataFrame) -> dict:
    """对 DataFrame 执行预测，返回完整结果"""
    missing_features = [c for c in feature_columns if c not in df.columns]
    if missing_features:
        return {"error": f"CSV 缺少特征列: {missing_features}"}

    id_col = "TMNL_DEV_ID" if "TMNL_DEV_ID" in df.columns else None

    X = df[feature_columns].astype(float).values
    n_samples = len(X)

    y_prob_list = []
    y_pred_list = []
    for label in LABEL_COLUMNS:
        if label in models:
            prob = models[label].predict_proba(X)[:, 1]
            thr = thresholds.get(label, 0.5)
            pred = (prob >= thr).astype(int)
        else:
            prob = np.zeros(n_samples)
            pred = np.zeros(n_samples, dtype=int)
        y_prob_list.append(prob)
        y_pred_list.append(pred)

    y_prob = np.column_stack(y_prob_list)
    y_pred = np.column_stack(y_pred_list)

    predictions = []
    for i in range(n_samples):
        pred_labels = [LABEL_COLUMNS[j] for j in range(len(LABEL_COLUMNS)) if y_pred[i, j] == 1]
        pred_labels_cn = [LABEL_CN_MAP.get(l, l) for l in pred_labels]
        if pred_labels:
            hit_idx = [j for j in range(len(LABEL_COLUMNS)) if y_pred[i, j] == 1]
            best_idx = int(hit_idx[np.argmax(y_prob[i, hit_idx])])
            primary_label = LABEL_COLUMNS[best_idx]
            primary_label_cn = LABEL_CN_MAP.get(primary_label, primary_label)
        else:
            primary_label = ""
            primary_label_cn = ""

        row = {
            "index": int(i),
            "pred_label_count": int(y_pred[i].sum()),
            "pred_labels": pred_labels,
            "pred_labels_cn": pred_labels_cn,
            "primary_label": primary_label,
            "primary_label_cn": primary_label_cn,
        }
        if id_col:
            row["device_id"] = str(df.iloc[i][id_col])

        row["probs"] = {LABEL_COLUMNS[j]: round(float(y_prob[i, j]), 6) for j in range(len(LABEL_COLUMNS))}
        row["preds"] = {LABEL_COLUMNS[j]: int(y_pred[i, j]) for j in range(len(LABEL_COLUMNS))}

        row["features"] = {}
        for f in feature_columns:
            val = df.iloc[i][f]
            if pd.isna(val):
                row["features"][f] = None
            elif isinstance(val, (np.integer,)):
                row["features"][f] = int(val)
            elif isinstance(val, (np.floating,)):
                row["features"][f] = float(val)
            else:
                row["features"][f] = val

        predictions.append(row)

    result = {
        "n_samples": int(n_samples),
        "n_features": len(feature_columns),
        "n_labels": len(LABEL_COLUMNS),
        "feature_columns": feature_columns,
        "label_columns": LABEL_COLUMNS,
        "label_cn_map": LABEL_CN_MAP,
        "feature_cn_map": FEATURE_CN_MAP,
        "thresholds": {k: float(v) for k, v in thresholds.items()},
        "scale_pos_weight": {k: float(v) for k, v in scale_pos_weights.items()},
        "feature_importance": feature_importance_dict,
        "predictions": predictions,
    }

    has_labels = all(c in df.columns for c in LABEL_COLUMNS)
    if has_labels:
        y_true = df[LABEL_COLUMNS].astype(int).values
        metrics = compute_metrics(y_true, y_pred, y_prob)
        metrics["thresholds"] = {k: float(v) for k, v in thresholds.items()}
        result["metrics"] = _to_native(metrics)

        cooccur = np.zeros((len(LABEL_COLUMNS), len(LABEL_COLUMNS)), dtype=int)
        label_arr = y_true
        for i in range(len(label_arr)):
            for a in range(len(LABEL_COLUMNS)):
                if label_arr[i, a] == 0:
                    continue
                for b in range(len(LABEL_COLUMNS)):
                    if label_arr[i, b] == 1:
                        cooccur[a, b] += 1
        result["cooccurrence_matrix"] = cooccur.tolist()
        result["pos_counts"] = [int(y_true[:, j].sum()) for j in range(len(LABEL_COLUMNS))]

        result["summary"] = {
            "total_samples": int(n_samples),
            "anomaly_samples": int((y_true.sum(axis=1) > 0).sum()),
            "normal_samples": int((y_true.sum(axis=1) == 0).sum()),
            "total_anomaly_flags": int(y_true.sum()),
            "pos_counts": {LABEL_CN_MAP.get(l, l): int(y_true[:, j].sum()) for j, l in enumerate(LABEL_COLUMNS)},
        }
    else:
        result["summary"] = {
            "total_samples": int(n_samples),
            "pred_anomaly_samples": int((y_pred.sum(axis=1) > 0).sum()),
            "pred_normal_samples": int((y_pred.sum(axis=1) == 0).sum()),
            "total_pred_anomaly_flags": int(y_pred.sum()),
            "pred_pos_counts": {LABEL_CN_MAP.get(l, l): int(y_pred[:, j].sum()) for j, l in enumerate(LABEL_COLUMNS)},
        }

    return result


# ---------------------------------------------------------------------------
# 超参数网格搜索
# ---------------------------------------------------------------------------
def _compute_scale_pos_weight(y: np.ndarray) -> float:
    pos = int((y == 1).sum())
    neg = int((y == 0).sum())
    if pos == 0:
        return 1.0
    return neg / pos


def _search_best_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    best_threshold = 0.5
    best_f1 = -1.0
    for t in np.arange(0.1, 0.91, 0.05):
        y_pred = (y_prob >= t).astype(int)
        score = f1_score(y_true, y_pred, zero_division=0)
        if score > best_f1:
            best_f1 = score
            best_threshold = float(round(t, 2))
    return best_threshold


def gridsearch_tune(file_content: bytes, filename: str) -> dict:
    """接收 CSV 文件内容，执行超参数网格搜索调优"""
    global _tune_status, models, thresholds, scale_pos_weights, feature_importance_dict

    if _tune_status["running"]:
        return {"error": "已有调优任务正在执行，请等待完成"}

    if not filename:
        return {"error": "未选择文件"}

    try:
        df = None
        for enc in ["utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"]:
            try:
                df = pd.read_csv(BytesIO(file_content), encoding=enc)
                if len(df) > 0:
                    break
            except Exception:
                continue

        if df is None or len(df) == 0:
            return {"error": "无法解析 CSV 文件或文件为空"}

        missing_labels = [c for c in LABEL_COLUMNS if c not in df.columns]
        if missing_labels:
            return {"error": f"CSV 缺少标签列: {missing_labels}，超参数调优需要带标签的数据"}

        missing_features = [c for c in feature_columns if c not in df.columns]
        if missing_features:
            return {"error": f"CSV 缺少特征列: {missing_features}"}

        n_total = len(df)
        print(f"[terminal] 超参数调优开始: {filename}, {n_total} 条样本", flush=True)
        set_tune_status(True, 0, "准备数据...")
        t_start = time.time()

        X_full = df[feature_columns].astype(float).values
        y_full = df[LABEL_COLUMNS].astype(int).values
        stratify = (y_full.sum(axis=1) > 0).astype(int)

        if n_total >= 10:
            train_idx, val_idx = train_test_split(
                np.arange(n_total), test_size=0.2, random_state=42,
                stratify=stratify,
            )
        else:
            n_val = max(1, int(n_total * 0.2))
            train_idx = np.arange(n_total - n_val)
            val_idx = np.arange(n_total - n_val, n_total)

        X_train, y_train = X_full[train_idx], y_full[train_idx]
        X_val, y_val = X_full[val_idx], y_full[val_idx]
        n_train, n_val = len(train_idx), len(val_idx)

        # 原始模型基准
        set_tune_status(True, 5, "计算原始模型基准...")
        result_orig = run_predictions(df)
        orig_full_metrics = result_orig.get("metrics", {})
        orig_full_summary = result_orig.get("summary", {})

        y_val_prob_orig = np.zeros((n_val, len(LABEL_COLUMNS)))
        y_val_pred_orig = np.zeros((n_val, len(LABEL_COLUMNS)), dtype=int)
        for j, label in enumerate(LABEL_COLUMNS):
            if label in models:
                prob = models[label].predict_proba(X_val)[:, 1]
                thr = thresholds.get(label, 0.5)
                y_val_prob_orig[:, j] = prob
                y_val_pred_orig[:, j] = (prob >= thr).astype(int)
        orig_macro_f1 = float(f1_score(y_val, y_val_pred_orig, average="macro", zero_division=0))

        # 网格搜索
        grid_results = []
        best_macro_f1 = -1.0
        best_params = None
        best_models = None
        best_thresholds = None
        best_scale_weights = None

        n_combos = len(PARAM_GRID)
        for combo_idx, params in enumerate(PARAM_GRID):
            progress_pct = int((combo_idx / n_combos) * 90)
            set_tune_status(True, progress_pct,
                f"网格搜索 {combo_idx+1}/{n_combos}: n_est={params['n_estimators']}, depth={params['max_depth']}, lr={params['learning_rate']}")

            combo_models = {}
            combo_thresholds = {}
            combo_scale_weights = {}
            combo_val_prob = np.zeros((n_val, len(LABEL_COLUMNS)))
            combo_val_pred = np.zeros((n_val, len(LABEL_COLUMNS)), dtype=int)

            for j, label in enumerate(LABEL_COLUMNS):
                y_train_j = y_train[:, j]
                spw = _compute_scale_pos_weight(y_train_j)
                combo_scale_weights[label] = spw

                model = XGBClassifier(
                    n_estimators=params["n_estimators"], max_depth=params["max_depth"],
                    learning_rate=params["learning_rate"], subsample=params["subsample"],
                    colsample_bytree=params["colsample_bytree"], reg_lambda=params["reg_lambda"],
                    min_child_weight=params["min_child_weight"], scale_pos_weight=spw,
                    objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                    random_state=42, n_jobs=1,
                )
                model.fit(X_train, y_train_j)

                prob = model.predict_proba(X_val)[:, 1]
                thr = _search_best_threshold(y_train_j, model.predict_proba(X_train)[:, 1]) if n_train > 5 else 0.5
                combo_thresholds[label] = thr
                combo_models[label] = model
                combo_val_prob[:, j] = prob
                combo_val_pred[:, j] = (prob >= thr).astype(int)

            per_label_f1 = {}
            valid_f1s = []
            for j, label in enumerate(LABEL_COLUMNS):
                f1_val = float(f1_score(y_val[:, j], combo_val_pred[:, j], zero_division=0))
                per_label_f1[label] = f1_val
                if y_val[:, j].sum() > 0:
                    valid_f1s.append(f1_val)
            macro_f1 = float(np.mean(valid_f1s)) if valid_f1s else 0.0
            micro_f1 = float(f1_score(y_val, combo_val_pred, average="micro", zero_division=0))

            combo_result = {
                "combo_index": combo_idx + 1,
                "params": {k: v for k, v in params.items()},
                "val_macro_f1": round(macro_f1, 6),
                "val_micro_f1": round(micro_f1, 6),
                "per_label_f1": {k: round(v, 6) for k, v in per_label_f1.items()},
            }
            grid_results.append(combo_result)

            if macro_f1 > best_macro_f1:
                best_macro_f1 = macro_f1
                best_params = {k: v for k, v in params.items()}
                best_models = combo_models
                best_thresholds = combo_thresholds
                best_scale_weights = combo_scale_weights

        # 用最佳参数在全量数据上重新训练
        set_tune_status(True, 92, "用最佳参数在全量数据上重新训练...")

        final_models = {}
        final_thresholds = {}
        final_scale_weights = {}

        for j, label in enumerate(LABEL_COLUMNS):
            y_full_j = y_full[:, j]
            spw = _compute_scale_pos_weight(y_full_j)
            final_scale_weights[label] = spw

            model = XGBClassifier(
                n_estimators=best_params["n_estimators"], max_depth=best_params["max_depth"],
                learning_rate=best_params["learning_rate"], subsample=best_params["subsample"],
                colsample_bytree=best_params["colsample_bytree"], reg_lambda=best_params["reg_lambda"],
                min_child_weight=best_params["min_child_weight"], scale_pos_weight=spw,
                objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                random_state=42, n_jobs=1,
            )
            model.fit(X_full, y_full_j)
            prob = model.predict_proba(X_full)[:, 1]
            thr = _search_best_threshold(y_full_j, prob)
            final_thresholds[label] = thr
            final_models[label] = model

        # 保存新模型
        set_tune_status(True, 97, "保存新模型...")
        artifact = {
            "models": final_models,
            "feature_columns": feature_columns,
            "label_columns": LABEL_COLUMNS,
            "thresholds": final_thresholds,
            "scale_pos_weight": final_scale_weights,
        }
        joblib.dump(artifact, TUNED_MODEL_PATH)

        # 重载新模型
        set_tune_status(True, 99, "重载新模型并重新预测...")
        reload_model(TUNED_MODEL_PATH)

        # 用新模型重新预测全量数据
        result = run_predictions(df)
        if "error" in result:
            return {"error": result["error"]}

        new_macro_f1 = result.get("metrics", {}).get("macro_f1", 0)
        improvement = round(new_macro_f1 - orig_macro_f1, 6)
        t_elapsed = round(time.time() - t_start, 1)

        result["grid_search"] = {
            "grid_results": grid_results,
            "best_params": best_params,
            "best_combo_index": grid_results.index(
                next(g for g in grid_results if g["val_macro_f1"] == round(best_macro_f1, 6))
            ) + 1 if grid_results else 0,
            "best_val_macro_f1": round(best_macro_f1, 6),
            "original_macro_f1": round(orig_macro_f1, 6),
            "tuned_macro_f1": round(new_macro_f1, 6),
            "improvement": improvement,
            "tuned_model_path": TUNED_MODEL_PATH,
            "time_elapsed_seconds": t_elapsed,
            "n_combos": n_combos,
            "n_train": n_train,
            "n_val": n_val,
            "original_full_metrics": {
                "micro_f1": orig_full_metrics.get("micro_f1"),
                "macro_f1": orig_full_metrics.get("macro_f1"),
                "subset_accuracy": orig_full_metrics.get("subset_accuracy"),
                "hamming_loss": orig_full_metrics.get("hamming_loss"),
                "micro_precision": orig_full_metrics.get("micro_precision"),
                "micro_recall": orig_full_metrics.get("micro_recall"),
            },
            "original_full_summary": orig_full_summary,
        }

        result = _to_native(result)
        set_tune_status(False, 100, "调优完成")
        print(f"[terminal] 调优完成! 耗时 {t_elapsed}s, Macro F1={new_macro_f1:.4f}", flush=True)
        return result

    except Exception as e:
        set_tune_status(False, 0, f"失败: {str(e)}")
        print(f"[terminal] 调优失败: {e}", flush=True)
        traceback.print_exc()
        return {"error": f"超参数调优失败: {str(e)}"}


def reset_model_to_original() -> dict:
    """重置模型为原始版本"""
    try:
        if not os.path.exists(DEFAULT_MODEL_PATH):
            return {"error": "原始模型文件不存在"}
        reload_model(DEFAULT_MODEL_PATH)
        return {
            "status": "ok", "message": "模型已重置为原始版本",
            "model_path": current_model_path,
            "model_name": os.path.basename(current_model_path),
        }
    except Exception as e:
        return {"error": f"重置失败: {str(e)}"}