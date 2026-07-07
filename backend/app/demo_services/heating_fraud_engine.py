"""
电采暖高价低接研判引擎 — 从 heating_fraud/v2_plus_model 重构
LightGBM 二分类 + SHAP 可解释性 + 16维规则化评分体系

函数化入口：train() / predict() / get_model_info() / get_feature_importance() / get_evaluation()
"""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Callable, Optional

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 中文字体
plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# ===================== 配置（从 config.py 内联） =====================
_BACKEND_DIR = Path(__file__).parent.parent.parent  # backend/
_MODELS_DIR = _BACKEND_DIR / "models_pool" / "YD" / "heating_fraud"
_DEFAULT_MODEL_PATH = str(_MODELS_DIR / "fraud_detection_model.pkl")
_EXPERIENCE_DIR = _BACKEND_DIR / "experience_data" / "YD" / "heating_fraud"
_TRAIN_CSV = _EXPERIENCE_DIR / "train_features.csv"
_PREDICT_CSV = _EXPERIENCE_DIR / "predict_features.csv"
_OUTPUT_DIR = _BACKEND_DIR / "data" / "uploads"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- 算法参数 ---
RANDOM_STATE = 42
LGBM_CV_FOLDS = 5
LGBM_EARLY_STOPPING_ROUNDS = 100
LGBM_FEATURE_IMPORTANCE_THRESHOLD = 0.005
LGBM_CORRELATION_THRESHOLD = 0.95
LGBM_NAN_RATIO_THRESHOLD = 0.50
LGBM_VARIANCE_THRESHOLD = 1e-8
OPTUNA_TIMEOUT = 2000

# 先验对齐
REAL_PRIOR_SUS = 2 / 19
USE_PRIOR_ALIGN = True

# 阈值优化
THRESHOLD_OPT_BETA = 0.5
OPTUNA_OBJECTIVE = "auc"

# 风险分级
RISK_HIGH_THRESHOLD = 0.7
RISK_LOW_THRESHOLD = 0.3

# 排除列
EXCLUDE_COLS = {"meter_id", "label"}
LABEL_MAP = {"honest": 0, "sus": 1}

# 规则化评分
RULE_WEIGHTS = {
    "avg_power_temp_slope": 0.15,
    "duty_cycle_temp_slope": 0.10,
    "peak_valley_ratio_intraday": 0.10,
    "night_to_evening_avg_power_ratio": 0.10,
    "low_power_ratio": 0.05,
    "pf_mean": 0.10,
    "high_power_duty_cycle": 0.03,
    "max_consecutive_low_power_hours": 0.03,
    "peak_duty_cycle": 0.03,
    "power_pf_corr": 0.05,
    "pf_bimodal_coef": 0.03,
    "temp_response_absence": 0.05,
    "pf_range": 0.03,
    "pf_cv_low_power": -0.08,
    "is_pf_highly_stable": -0.08,
    "low_power_pf_inverse_ratio": -0.05,
}

RULE_THRESHOLDS = {
    "avg_power_temp_slope": -0.065,
    "duty_cycle_temp_slope": -0.010,
    "peak_valley_ratio_intraday": 5.0,
    "night_to_evening_avg_power_ratio": 2.0,
    "low_power_ratio": 0.70,
    "pf_mean": 0.94,
    "high_power_duty_cycle": 0.20,
    "max_consecutive_low_power_hours": 240,
    "peak_duty_cycle": 0.65,
    "power_pf_corr": -0.3,
    "pf_bimodal_coef": 0.5,
    "temp_response_absence": 0.15,
    "pf_range": 0.3,
    "pf_cv_low_power": 0.05,
    "is_pf_highly_stable": 0.5,
    "low_power_pf_inverse_ratio": 0.01,
}

# 规则评分体系说明表（供前端展示）
RULE_SPEC = [
    {"dimension": "avg_power_temp_slope", "threshold": "< -0.065", "direction": "<", "weight": 0.15, "category": "物理判据", "meaning": "功率-温度斜率过陡→异常温度敏感性"},
    {"dimension": "duty_cycle_temp_slope", "threshold": "≥ -0.010", "direction": "≥", "weight": 0.10, "category": "物理判据", "meaning": "占空比对温度不敏感→非定频启停"},
    {"dimension": "peak_valley_ratio_intraday", "threshold": "< 5.0", "direction": "<", "weight": 0.10, "category": "物理判据", "meaning": "日内峰谷差异小→持续运行"},
    {"dimension": "night_to_evening_avg_power_ratio", "threshold": "< 2.0", "direction": "<", "weight": 0.10, "category": "物理判据", "meaning": "凌晨/晚高峰功率比低→均匀负荷→工业"},
    {"dimension": "low_power_ratio", "threshold": "> 0.70", "direction": ">", "weight": 0.05, "category": "行为假设", "meaning": "低负荷占比高→大部分时间保温/停机"},
    {"dimension": "pf_mean", "threshold": "< 0.94", "direction": "<", "weight": 0.10, "category": "行为假设", "meaning": "功率因数低→非电阻性负载"},
    {"dimension": "high_power_duty_cycle", "threshold": "< 0.20", "direction": "<", "weight": 0.03, "category": "行为假设", "meaning": "高负荷占空比低→很少达到供暖功率"},
    {"dimension": "max_consecutive_low_power_hours", "threshold": "> 240", "direction": ">", "weight": 0.03, "category": "行为假设", "meaning": "连续低负荷长→长期无供暖需求"},
    {"dimension": "peak_duty_cycle", "threshold": "> 0.65", "direction": ">", "weight": 0.03, "category": "行为假设", "meaning": "高峰时段占空比高→非典型采暖模式"},
    {"dimension": "power_pf_corr", "threshold": "< -0.3", "direction": "<", "weight": 0.05, "category": "TP强化", "meaning": "功率-PF负相关→混入低PF负荷"},
    {"dimension": "pf_bimodal_coef", "threshold": "> 0.5", "direction": ">", "weight": 0.03, "category": "TP强化", "meaning": "PF双峰→两种负荷模式交替"},
    {"dimension": "temp_response_absence", "threshold": "< 0.15", "direction": "<", "weight": 0.05, "category": "TP强化", "meaning": "温度响应缺失→非采暖负荷"},
    {"dimension": "pf_range", "threshold": "> 0.3", "direction": ">", "weight": 0.03, "category": "TP强化", "meaning": "PF范围大→负荷类型多样"},
    {"dimension": "pf_cv_low_power", "threshold": "< 0.05", "direction": "<", "weight": -0.08, "category": "FP排除", "meaning": "低负荷PF稳定→待机损耗"},
    {"dimension": "is_pf_highly_stable", "threshold": "≥ 0.5", "direction": "≥", "weight": -0.08, "category": "FP排除", "meaning": "PF极稳定→空气能设备"},
    {"dimension": "low_power_pf_inverse_ratio", "threshold": "< 0.01", "direction": "<", "weight": -0.05, "category": "FP排除", "meaning": "组合判据：需同时满足low_power_ratio和pf_cv_low_power条件"},
]


# ===================== 工具函数 =====================

def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _compute_prior_align_weights(y, real_prior_sus=None, verbose=True):
    if real_prior_sus is None:
        real_prior_sus = REAL_PRIOR_SUS
    real_prior_honest = 1 - real_prior_sus
    y_arr = np.asarray(y).ravel()
    n_sus = int((y_arr == 1).sum())
    n_honest = int((y_arr == 0).sum())
    n_total = len(y_arr)
    if n_sus == 0 or n_honest == 0:
        return None
    p_train_sus = n_sus / n_total
    p_train_honest = n_honest / n_total
    eps = 1e-10
    w_sus = real_prior_sus / max(p_train_sus, eps)
    w_honest = real_prior_honest / max(p_train_honest, eps)
    sample_weight = np.where(y_arr == 1, w_sus, w_honest)
    if verbose:
        print(f"  [先验对齐] sus:{n_sus} honest:{n_honest} -> w_sus={w_sus:.4f}, w_honest={w_honest:.4f}")
    return sample_weight


def _resolve_spw_and_weights(y, verbose=True):
    y_arr = np.asarray(y).ravel()
    n_sus = int((y_arr == 1).sum())
    n_honest = int((y_arr == 0).sum())
    if USE_PRIOR_ALIGN:
        spw = None
        sample_weight = _compute_prior_align_weights(y_arr, verbose=verbose)
    else:
        spw = n_honest / n_sus if n_sus > 0 else 1.0
        sample_weight = None
    return spw, sample_weight


def assign_risk_level(prob, risk_thresholds=None):
    if risk_thresholds is None:
        risk_thresholds = {"high": RISK_HIGH_THRESHOLD, "low": RISK_LOW_THRESHOLD}
    if prob >= risk_thresholds["high"]:
        return "高风险"
    elif prob >= risk_thresholds["low"]:
        return "中风险"
    else:
        return "低风险"


def compute_rule_score(df_features):
    scores = []
    hit_items = []
    for _, row in df_features.iterrows():
        score = 0.0
        hits = []
        for dim in RULE_THRESHOLDS:
            val = row.get(dim, np.nan)
            if pd.isna(val) or np.isinf(val):
                continue
            thr = RULE_THRESHOLDS[dim]
            direction = RULE_SPEC[[r["dimension"] for r in RULE_SPEC].index(dim)]["direction"]
            hit = False
            if direction == "<" and val < thr:
                hit = True
            elif direction == ">" and val > thr:
                hit = True
            elif direction == "≥" and val >= thr:
                hit = True
            if hit:
                w = RULE_WEIGHTS[dim]
                score += w
                meaning = RULE_SPEC[[r["dimension"] for r in RULE_SPEC].index(dim)]["meaning"]
                hits.append(f"{meaning}({val:.4f})")
        scores.append(score)
        hit_items.append("; ".join(hits))
    df_features = df_features.copy()
    df_features["rule_score"] = scores
    df_features["rule_hits"] = hit_items
    return df_features


# ===================== 训练流程 =====================

def _load_features(csv_path=None):
    if csv_path is None:
        csv_path = str(_TRAIN_CSV)
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    df["meter_id"] = df["meter_id"].astype(str)
    df["target"] = df["label"].map(LABEL_MAP)
    return df


def _preprocess_features(df):
    feature_cols = [
        c for c in df.columns
        if c not in EXCLUDE_COLS and c != "target" and pd.api.types.is_numeric_dtype(df[c])
    ]
    X = df[feature_cols].copy()
    y = df["target"].values
    # 剔除NaN率过高的特征
    nan_ratio = X.isna().mean()
    high_nan_cols = nan_ratio[nan_ratio > LGBM_NAN_RATIO_THRESHOLD].index.tolist()
    if high_nan_cols:
        X = X.drop(columns=high_nan_cols)
    # 替换无穷值
    X = X.replace([np.inf, -np.inf], np.nan)
    # 剔除低方差
    var_vals = X.var()
    low_var_cols = var_vals[var_vals < LGBM_VARIANCE_THRESHOLD].index.tolist()
    if low_var_cols:
        X = X.drop(columns=low_var_cols)
    # 中位数填充
    medians = X.median()
    X = X.fillna(medians)
    return X, y, X.columns.tolist()


def _select_features(X, y, feature_cols):
    import lightgbm as lgb
    from sklearn.model_selection import StratifiedKFold

    spw, sample_weight = _resolve_spw_and_weights(y)
    init_model = lgb.LGBMClassifier(
        n_estimators=100, learning_rate=0.1, max_depth=5,
        num_leaves=31, scale_pos_weight=spw,
        random_state=RANDOM_STATE, verbosity=-1,
    )
    if sample_weight is not None:
        init_model.fit(X, y, sample_weight=sample_weight)
    else:
        init_model.fit(X, y)
    importances = pd.Series(init_model.feature_importances_, index=feature_cols)
    importances = importances / importances.sum()
    low_imp_cols = importances[importances < LGBM_FEATURE_IMPORTANCE_THRESHOLD].index.tolist()
    keep_cols = [c for c in feature_cols if c not in low_imp_cols]
    X_filtered = X[keep_cols]
    # 相关性去冗余
    corr_matrix = X_filtered.corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    drop_cols = []
    for col in upper.columns:
        high_corr = upper[col][upper[col] > LGBM_CORRELATION_THRESHOLD].index.tolist()
        for hc in high_corr:
            if importances.get(col, 0) < importances.get(hc, 0):
                if col not in drop_cols:
                    drop_cols.append(col)
            else:
                if hc not in drop_cols:
                    drop_cols.append(hc)
    keep_cols = [c for c in keep_cols if c not in drop_cols]
    X_filtered = X_filtered[keep_cols]
    fi_mean = importances.loc[keep_cols].sort_values(ascending=False)
    return X_filtered, keep_cols, fi_mean


def train(features_csv_path: str, n_trials: int = 100, progress_callback: Optional[Callable] = None) -> dict:
    """完整训练流程：数据加载→预处理→特征筛选→Optuna→5-fold CV→阈值优化→SHAP→规则评分→保存"""
    import lightgbm as lgb
    import optuna
    import shap
    from sklearn.model_selection import StratifiedKFold, train_test_split
    from sklearn.metrics import (
        roc_auc_score, average_precision_score, f1_score,
        precision_score, recall_score, accuracy_score,
        confusion_matrix, roc_curve, precision_recall_curve,
    )

    print(f"[heating_fraud] 开始训练: {features_csv_path}, n_trials={n_trials}")
    # Task 1: 数据加载
    df = _load_features(features_csv_path)
    X_raw, y, raw_feature_cols = _preprocess_features(df)
    # Task 2: 特征筛选
    X, selected_cols, fi_mean = _select_features(X_raw, y, raw_feature_cols)
    print(f"  筛选后特征数: {len(selected_cols)}")

    spw, sample_weight_full = _resolve_spw_and_weights(y)

    # Task 3: Optuna 超参搜索
    X_train_opt, X_val_opt, y_train_opt, y_val_opt = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    if sample_weight_full is not None:
        _, sample_weight_opt = _resolve_spw_and_weights(y_train_opt, verbose=False)
    else:
        sample_weight_opt = None

    def objective(trial):
        params = {
            "n_estimators": 500,
            "learning_rate": trial.suggest_categorical("learning_rate", [0.01, 0.05, 0.1]),
            "max_depth": trial.suggest_int("max_depth", 3, 9),
            "num_leaves": trial.suggest_categorical("num_leaves", [15, 31, 63]),
            "min_child_samples": trial.suggest_categorical("min_child_samples", [10, 20, 50]),
            "subsample": trial.suggest_categorical("subsample", [0.7, 0.8, 0.9, 1.0]),
            "colsample_bytree": trial.suggest_categorical("colsample_bytree", [0.7, 0.8, 0.9, 1.0]),
            "reg_alpha": trial.suggest_categorical("reg_alpha", [0, 0.1, 1.0]),
            "reg_lambda": trial.suggest_categorical("reg_lambda", [0, 0.1, 1.0]),
            "min_child_weight": trial.suggest_float("min_child_weight", 1e-3, 10, log=True),
            "max_bin": trial.suggest_int("max_bin", 128, 512),
            "path_smooth": trial.suggest_float("path_smooth", 0, 10),
            "extra_trees": trial.suggest_categorical("extra_trees", [True, False]),
            "random_state": RANDOM_STATE,
            "verbosity": -1,
        }
        if spw is not None:
            params["scale_pos_weight"] = spw
        model = lgb.LGBMClassifier(**params)
        fit_kwargs = {}
        if sample_weight_opt is not None:
            fit_kwargs["sample_weight"] = sample_weight_opt
        model.fit(
            X_train_opt, y_train_opt,
            eval_set=[(X_val_opt, y_val_opt)],
            callbacks=[lgb.early_stopping(LGBM_EARLY_STOPPING_ROUNDS, verbose=False)],
            **fit_kwargs,
        )
        y_pred_proba = model.predict_proba(X_val_opt)[:, 1]
        if OPTUNA_OBJECTIVE == "f1":
            y_pred_bin = (y_pred_proba >= 0.5).astype(int)
            return f1_score(y_val_opt, y_pred_bin)
        else:
            return roc_auc_score(y_val_opt, y_pred_proba)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))

    def _optuna_callback(study, trial):
        if progress_callback:
            progress_callback(trial.number + 1, n_trials, study.best_value if study.best_trial else 0.0)

    study.optimize(objective, n_trials=n_trials, timeout=OPTUNA_TIMEOUT, show_progress_bar=False, callbacks=[_optuna_callback])
    best_params = study.best_params
    print(f"  Optuna最优{OPTUNA_OBJECTIVE}: {study.best_value:.4f}")

    # 5-fold CV
    skf = StratifiedKFold(n_splits=LGBM_CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    fold_metrics = []
    fold_models = []
    oof_proba = np.zeros(len(y))

    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]
        if sample_weight_full is not None:
            _, fold_sample_weight = _resolve_spw_and_weights(y_tr, verbose=False)
        else:
            fold_sample_weight = None
        params = {**best_params, "n_estimators": 500, "random_state": RANDOM_STATE, "verbosity": -1}
        if spw is not None:
            params["scale_pos_weight"] = spw
        fold_model = lgb.LGBMClassifier(**params)
        fit_kwargs = {}
        if fold_sample_weight is not None:
            fit_kwargs["sample_weight"] = fold_sample_weight
        fold_model.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(LGBM_EARLY_STOPPING_ROUNDS, verbose=False)],
            **fit_kwargs,
        )
        y_pred_proba = fold_model.predict_proba(X_val)[:, 1]
        oof_proba[val_idx] = y_pred_proba
        y_pred = (y_pred_proba >= 0.5).astype(int)
        fold_metrics.append({
            "fold": fold_idx + 1,
            "auc": float(roc_auc_score(y_val, y_pred_proba)),
            "f1": float(f1_score(y_val, y_pred)),
            "precision": float(precision_score(y_val, y_pred)),
            "recall": float(recall_score(y_val, y_pred)),
            "accuracy": float(accuracy_score(y_val, y_pred)),
        })
        fold_models.append(fold_model)

    avg_metrics = {k: float(np.mean([m[k] for m in fold_metrics])) for k in ["auc", "f1", "precision", "recall", "accuracy"]}

    # 全量训练最终模型
    best_iterations = [m.best_iteration_ for m in fold_models if hasattr(m, "best_iteration_") and m.best_iteration_ is not None]
    avg_best_iter = int(np.mean(best_iterations)) if best_iterations else 500
    final_params = {**best_params, "n_estimators": avg_best_iter, "random_state": RANDOM_STATE, "verbosity": -1}
    if spw is not None:
        final_params["scale_pos_weight"] = spw
    final_model = lgb.LGBMClassifier(**final_params)
    if sample_weight_full is not None:
        final_model.fit(X, y, sample_weight=sample_weight_full)
    else:
        final_model.fit(X, y)
    y_proba = final_model.predict_proba(X)[:, 1]

    # 阈值优化
    beta = THRESHOLD_OPT_BETA
    precisions, recalls, thresholds_pr = precision_recall_curve(y, oof_proba)
    beta_sq = beta ** 2
    f_beta_scores = (1 + beta_sq) * precisions * recalls / (beta_sq * precisions + recalls + 1e-10)
    best_idx = np.argmax(f_beta_scores)
    threshold = float(thresholds_pr[best_idx]) if best_idx < len(thresholds_pr) else 0.5
    y_pred = (oof_proba >= threshold).astype(int)

    # 风险分级
    risk_levels = [assign_risk_level(p) for p in oof_proba]
    risk_dist = {
        "高风险": int(sum(1 for r in risk_levels if r == "高风险")),
        "中风险": int(sum(1 for r in risk_levels if r == "中风险")),
        "低风险": int(sum(1 for r in risk_levels if r == "低风险")),
    }

    # 图表生成
    charts = {}
    # ROC/PR 曲线
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fpr, tpr, _ = roc_curve(y, oof_proba)
    axes[0].plot(fpr, tpr, label=f"AUC={roc_auc_score(y, oof_proba):.4f}")
    axes[0].plot([0, 1], [0, 1], "--", color="gray")
    axes[0].set_title("ROC Curve")
    axes[0].legend()
    axes[1].plot(recalls, precisions, label=f"AP={average_precision_score(y, oof_proba):.4f}")
    axes[1].set_title("PR Curve")
    axes[1].legend()
    charts["roc_pr_curve"] = _fig_to_base64(fig)

    # 风险分布
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {"高风险": "#e74c3c", "中风险": "#f39c12", "低风险": "#27ae60"}
    order = ["高风险", "中风险", "低风险"]
    counts = [risk_dist[r] for r in order]
    bars = ax.bar(order, counts, color=[colors[r] for r in order], alpha=0.8)
    for bar, cnt in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5, str(cnt), ha="center", fontweight="bold")
    ax.set_title("风险等级分布")
    charts["risk_distribution"] = _fig_to_base64(fig)

    # 混淆矩阵
    cm = confusion_matrix(y, y_pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=16)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["honest", "sus"])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["honest", "sus"])
    ax.set_title("混淆矩阵")
    fig.colorbar(im)
    charts["confusion_matrix"] = _fig_to_base64(fig)

    # SHAP
    print("  计算SHAP值...")
    explainer = shap.TreeExplainer(final_model)
    shap_values = explainer.shap_values(X)
    if isinstance(shap_values, list):
        sv = shap_values[1]
    elif shap_values.ndim == 3:
        sv = shap_values[:, :, 1]
    else:
        sv = shap_values

    shap.summary_plot(sv, X, feature_names=selected_cols, show=False, max_display=20)
    fig = plt.gcf()
    fig.set_size_inches(10, 8)
    charts["shap_summary"] = _fig_to_base64(fig)

    fig, ax = plt.subplots(figsize=(10, 8))
    shap_abs_mean = np.abs(sv).mean(axis=0)
    sorted_idx = np.argsort(shap_abs_mean)[-20:]
    ax.barh(range(len(sorted_idx)), shap_abs_mean[sorted_idx], tick_label=np.array(selected_cols)[sorted_idx])
    ax.set_title("SHAP全局特征重要性 (Top-20)")
    charts["shap_bar"] = _fig_to_base64(fig)

    # 规则评分 vs 模型概率
    df_result_full = df.copy().reset_index(drop=True)
    df_result_full = compute_rule_score(df_result_full)
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(df_result_full["rule_score"], oof_proba, alpha=0.5, s=30, c="#3498db")
    ax.axhline(y=threshold, color="red", linestyle="--", alpha=0.5, label=f"阈值={threshold:.4f}")
    ax.set_xlabel("规则评分")
    ax.set_ylabel("模型欺诈概率 (OOF)")
    ax.set_title("规则评分 vs 模型概率")
    ax.legend()
    ax.grid(True, alpha=0.3)
    charts["rule_vs_model"] = _fig_to_base64(fig)

    # 保存模型
    model_path = str(_MODELS_DIR / "fraud_detection_model.pkl")
    model_pkg = {
        "model": final_model,
        "selected_cols": selected_cols,
        "threshold": threshold,
        "label_map": LABEL_MAP,
        "risk_thresholds": {"high": RISK_HIGH_THRESHOLD, "low": RISK_LOW_THRESHOLD},
    }
    joblib.dump(model_pkg, model_path)
    print(f"  模型已保存: {model_path}")

    # 特征重要性
    feature_importance_list = [
        {"feature": feat, "importance": float(imp)} for feat, imp in fi_mean.head(20).items()
    ]

    return {
        "status": "ok",
        "model_path": model_path,
        "threshold": threshold,
        "metrics": {
            "oof_auc": float(roc_auc_score(y, oof_proba)),
            "oof_ap": float(average_precision_score(y, oof_proba)),
            "oof_f1": float(f1_score(y, y_pred)),
            "oof_precision": float(precision_score(y, y_pred)),
            "oof_recall": float(recall_score(y, y_pred)),
            "oof_accuracy": float(accuracy_score(y, y_pred)),
            "cv_avg_metrics": avg_metrics,
            "fold_metrics": fold_metrics,
        },
        "feature_importance": feature_importance_list,
        "risk_distribution": risk_dist,
        "n_features_used": len(selected_cols),
        "optuna_best_value": float(study.best_value),
        "optuna_best_params": {k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for k, v in best_params.items()},
        "charts": charts,
    }


# ===================== 预测流程 =====================

def predict(features_csv_path: str, model_path: str = None) -> dict:
    """预测推理：加载模型→特征对齐→模型预测→风险分级→规则评分→SHAP"""
    import shap

    if model_path is None:
        model_path = _DEFAULT_MODEL_PATH
    if not os.path.exists(model_path):
        return {"status": "error", "message": f"模型文件不存在: {model_path}"}

    model_pkg = joblib.load(model_path)
    model = model_pkg["model"]
    selected_cols = model_pkg["selected_cols"]
    threshold = model_pkg["threshold"]
    risk_thresholds = model_pkg["risk_thresholds"]

    df = pd.read_csv(features_csv_path, encoding="utf-8-sig")
    df["meter_id"] = df["meter_id"].astype(str)
    features_df = df.copy()
    # 特征对齐
    missing_cols = [c for c in selected_cols if c not in features_df.columns]
    for c in missing_cols:
        features_df[c] = 0.0
    features_df = features_df.replace([np.inf, -np.inf], np.nan)
    medians = features_df[selected_cols].median()
    features_df[selected_cols] = features_df[selected_cols].fillna(medians)
    X = features_df[selected_cols]

    # 预测
    if hasattr(model, "predict_proba"):
        fraud_prob = model.predict_proba(X)[:, 1]
    else:
        raw_scores = model.predict(X)
        fraud_prob = _sigmoid(raw_scores)
    pred_label = np.where(fraud_prob >= threshold, "sus", "honest")
    risk_level = [assign_risk_level(p, risk_thresholds) for p in fraud_prob]

    # 规则评分
    df_result_full = features_df.copy().reset_index(drop=True)
    df_result_full = compute_rule_score(df_result_full)

    # SHAP
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    if isinstance(shap_values, list):
        sv = shap_values[1]
    elif shap_values.ndim == 3:
        sv = shap_values[:, :, 1]
    else:
        sv = shap_values

    top_evidences = []
    for i in range(len(sv)):
        row_shap = np.abs(sv[i])
        top3_idx = np.argsort(row_shap)[-3:][::-1]
        evs = []
        for j in top3_idx:
            val = sv[i, j]
            direction = "↑指向高价低接" if val > 0 else "↓指向真实电采暖"
            evs.append(f"{selected_cols[j]}({direction})")
        top_evidences.append(evs)

    predictions = []
    for i in range(len(df)):
        predictions.append({
            "meter_id": str(features_df["meter_id"].iloc[i]),
            "pred_label": str(pred_label[i]),
            "fraud_prob": float(fraud_prob[i]),
            "risk_level": risk_level[i],
            "rule_score": float(df_result_full["rule_score"].iloc[i]),
            "rule_hits": str(df_result_full["rule_hits"].iloc[i]),
            "top_evidence_1": top_evidences[i][0] if len(top_evidences[i]) > 0 else "",
            "top_evidence_2": top_evidences[i][1] if len(top_evidences[i]) > 1 else "",
            "top_evidence_3": top_evidences[i][2] if len(top_evidences[i]) > 2 else "",
        })

    risk_dist = {
        "高风险": int(sum(1 for r in risk_level if r == "高风险")),
        "中风险": int(sum(1 for r in risk_level if r == "中风险")),
        "低风险": int(sum(1 for r in risk_level if r == "低风险")),
    }

    # 图表
    charts = {}
    # 风险分布
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {"高风险": "#e74c3c", "中风险": "#f39c12", "低风险": "#27ae60"}
    order = ["高风险", "中风险", "低风险"]
    counts = [risk_dist[r] for r in order]
    bars = ax.bar(order, counts, color=[colors[r] for r in order], alpha=0.8)
    for bar, cnt in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5, str(cnt), ha="center", fontweight="bold")
    ax.set_title("预测风险等级分布")
    charts["risk_distribution"] = _fig_to_base64(fig)

    # 规则vs模型
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(df_result_full["rule_score"], fraud_prob, alpha=0.5, s=30, c="#3498db")
    ax.axhline(y=threshold, color="red", linestyle="--", alpha=0.5, label=f"阈值={threshold:.4f}")
    ax.set_xlabel("规则评分")
    ax.set_ylabel("模型欺诈概率")
    ax.set_title("规则评分 vs 模型概率 (预测)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    charts["rule_vs_model"] = _fig_to_base64(fig)

    # SHAP summary
    shap.summary_plot(sv, X, feature_names=selected_cols, show=False, max_display=20)
    fig = plt.gcf()
    fig.set_size_inches(10, 8)
    charts["shap_summary"] = _fig_to_base64(fig)

    # SHAP bar
    fig, ax = plt.subplots(figsize=(10, 8))
    shap_abs_mean = np.abs(sv).mean(axis=0)
    sorted_idx = np.argsort(shap_abs_mean)[-20:]
    ax.barh(range(len(sorted_idx)), shap_abs_mean[sorted_idx], tick_label=np.array(selected_cols)[sorted_idx])
    ax.set_title("SHAP全局特征重要性 (Top-20)")
    charts["shap_bar"] = _fig_to_base64(fig)

    # Top-10高风险电表特征分布
    top10_idx = np.argsort(fraud_prob)[-10:][::-1]
    all_evidences = []
    for i in top10_idx:
        for col in ["top_evidence_1", "top_evidence_2", "top_evidence_3"]:
            ev = predictions[i].get(col, "")
            if ev:
                feat_name = ev.split("(")[0].strip()
                all_evidences.append(feat_name)
    from collections import Counter
    feat_counts = Counter(all_evidences)
    fig, ax = plt.subplots(figsize=(10, 6))
    if feat_counts:
        top_feats = feat_counts.most_common(15)
        ax.barh(range(len(top_feats)), [c for _, c in top_feats[::-1]], tick_label=[f for f, _ in top_feats[::-1]])
    ax.set_xlabel("出现次数")
    ax.set_title("Top-10高风险电表的关键判据特征分布")
    charts["top_features_bar"] = _fig_to_base64(fig)

    # 保存结果CSV
    result_csv = str(_OUTPUT_DIR / "heating_fraud_predict_result.csv")
    df_out = pd.DataFrame(predictions)
    df_out.to_csv(result_csv, index=False, encoding="utf-8-sig")

    return {
        "status": "ok",
        "n_samples": len(predictions),
        "predictions": predictions,
        "risk_distribution": risk_dist,
        "charts": charts,
        "result_csv_path": result_csv,
    }


# ===================== 信息查询函数 =====================

def get_model_info() -> dict:
    has_model = os.path.exists(_DEFAULT_MODEL_PATH)
    n_features = 0
    threshold = 0.5
    if has_model:
        try:
            pkg = joblib.load(_DEFAULT_MODEL_PATH)
            n_features = len(pkg.get("selected_cols", []))
            threshold = float(pkg.get("threshold", 0.5))
        except Exception:
            pass
    return {
        "model_type": "LightGBM + SHAP + 16维规则评分",
        "n_features": n_features,
        "threshold": threshold,
        "has_trained_model": has_model,
        "default_model_available": has_model,
        "label_map": LABEL_MAP,
        "risk_thresholds": {"high": RISK_HIGH_THRESHOLD, "low": RISK_LOW_THRESHOLD},
        "config": {
            "cv_folds": LGBM_CV_FOLDS,
            "optuna_objective": OPTUNA_OBJECTIVE,
            "use_prior_align": USE_PRIOR_ALIGN,
            "threshold_opt_beta": THRESHOLD_OPT_BETA,
        },
    }


def get_feature_importance() -> list:
    """从默认模型获取特征重要性"""
    if not os.path.exists(_DEFAULT_MODEL_PATH):
        return []
    try:
        pkg = joblib.load(_DEFAULT_MODEL_PATH)
        model = pkg["model"]
        cols = pkg["selected_cols"]
        if hasattr(model, "feature_importances_"):
            imps = model.feature_importances_
            imps = imps / imps.sum()
            result = [
                {"feature": cols[i], "importance": float(imps[i])}
                for i in np.argsort(imps)[::-1][:20]
            ]
            return result
    except Exception:
        pass
    return []


def get_evaluation() -> dict:
    """获取默认模型的评估指标（从 model_evaluation.json 如果存在）"""
    eval_path = _EXPERIENCE_DIR / "model_evaluation.json"
    if not eval_path.exists():
        # 尝试从源项目复制
        src_eval = Path(r"f:\qoderproject\heating_fraud\v2_plus_model\outputs\model_evaluation.json")
        if src_eval.exists():
            import shutil
            shutil.copy(str(src_eval), str(eval_path))
    if eval_path.exists():
        with open(eval_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"status": "no_data", "message": "评估数据不存在，请先训练模型"}


def get_rule_spec() -> list:
    """返回16维规则评分体系说明表"""
    return RULE_SPEC


def get_train_csv_path() -> str:
    return str(_TRAIN_CSV)


def get_predict_csv_path() -> str:
    return str(_PREDICT_CSV)
