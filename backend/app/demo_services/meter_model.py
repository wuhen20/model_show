"""
电表异常研判 CNN+LSTM 多标签分类 — 模型核心逻辑
从 meter_server.py 提取，适配 FastAPI 架构
"""
import os
import time
import traceback
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, f1_score,
    hamming_loss, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, TensorDataset

torch.backends.mkldnn.enabled = False
torch.set_num_threads(1)

from app.core.config import settings

# ---------------------------------------------------------------------------
# 路径计算
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent.parent  # backend/
_MODELS_DIR = _BACKEND_DIR / settings.models_pool_dir  # models_pool/
_EXPERIENCE_DIR = _BACKEND_DIR / settings.experience_data_dir  # experience_data/

DEFAULT_MODEL_PATH = str(_MODELS_DIR / "ZJ" / "meter" / "meter_cnn_lstm_model.pt")
TUNED_MODEL_PATH = str(_MODELS_DIR / "ZJ" / "meter" / "meter_cnn_lstm_model_tuned.pt")
DEMO_CSV_PATH = str(_EXPERIENCE_DIR / "ZJ" / "meter" / "meter_demo_120.csv")
current_model_path = DEFAULT_MODEL_PATH

# 调优状态
_tune_status = {"running": False, "progress": 0, "message": ""}


def get_tune_status() -> dict:
    return dict(_tune_status)


def set_tune_status(running: bool, progress: int, message: str):
    global _tune_status
    _tune_status = {"running": running, "progress": progress, "message": message}


# ---------------------------------------------------------------------------
# 模型定义
# ---------------------------------------------------------------------------
class MeterCNNLSTMMultiLabel(nn.Module):
    def __init__(
        self,
        seq_input_channels: int,
        static_input_dim: int,
        num_labels: int,
        conv_channels_1: int = 32,
        conv_channels_2: int = 64,
        lstm_hidden_size: int = 64,
        static_hidden_dim: int = 64,
        fusion_hidden_dim: int = 128,
        dropout: float = 0.25,
    ):
        super().__init__()
        self.seq_branch = nn.Sequential(
            nn.Conv1d(seq_input_channels, conv_channels_1, kernel_size=5, padding=2),
            nn.BatchNorm1d(conv_channels_1), nn.ReLU(),
            nn.Conv1d(conv_channels_1, conv_channels_2, kernel_size=3, padding=1),
            nn.BatchNorm1d(conv_channels_2), nn.ReLU(),
            nn.MaxPool1d(kernel_size=2), nn.Dropout(dropout),
        )
        self.lstm = nn.LSTM(
            input_size=conv_channels_2, hidden_size=lstm_hidden_size,
            num_layers=1, batch_first=True, bidirectional=True,
        )
        self.static_branch = nn.Sequential(
            nn.Linear(static_input_dim, static_hidden_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(static_hidden_dim, static_hidden_dim // 2), nn.ReLU(),
        )
        fusion_input_dim = lstm_hidden_size * 2 + static_hidden_dim // 2
        self.classifier = nn.Sequential(
            nn.Linear(fusion_input_dim, fusion_hidden_dim), nn.ReLU(),
            nn.Dropout(dropout), nn.Linear(fusion_hidden_dim, num_labels),
        )

    def forward(self, seq_x: torch.Tensor, static_x: torch.Tensor) -> torch.Tensor:
        x = seq_x.transpose(1, 2)
        x = self.seq_branch(x)
        x = x.transpose(1, 2)
        lstm_out, _ = self.lstm(x)
        seq_feat = lstm_out[:, -1, :]
        static_feat = self.static_branch(static_x)
        fused = torch.cat([seq_feat, static_feat], dim=1)
        return self.classifier(fused)


# ---------------------------------------------------------------------------
# 常量配置
# ---------------------------------------------------------------------------
SEQ_LEN = 24
DYNAMIC_CHANNELS = ["voltage", "current", "active_power", "power_factor"]
LABEL_COLUMNS = ["POWER_COLL_FLAG", "PARAM_FLAG", "CLOCK_FLAG", "AGING_FLAG", "ENV_FLAG"]
LABEL_CN_MAP = {
    "POWER_COLL_FLAG": "电表停电采集异常",
    "PARAM_FLAG": "采集参数异常（F10）",
    "CLOCK_FLAG": "电表时钟异常",
    "AGING_FLAG": "设备老旧异常",
    "ENV_FLAG": "运行环境影响",
}
STATIC_BASE_COLUMNS = ["OFFSET_TIME", "RUN_YEARS", "COLL_FAIL_U_7D", "TEMP_ERR_RATE", "COLL_COMPLETE_U", "DEPTH"]
STAT_SUFFIXES = ["mean", "std", "peak_ratio", "kurtosis", "skewness", "crest_factor", "impulse_factor", "margin_factor"]
STAT_PREFIXES = ["voltage", "current", "active_power"]

FEATURE_CN_MAP = {
    "OFFSET_TIME": "时钟偏差", "RUN_YEARS": "建档年限",
    "COLL_FAIL_U_7D": "近7日采集失败率", "TEMP_ERR_RATE": "温度异常率",
    "COLL_COMPLETE_U": "采集完整率", "DEPTH": "深度等级",
    "voltage_mean": "电压均值", "voltage_std": "电压标准差", "voltage_peak_ratio": "电压峰值比",
    "voltage_kurtosis": "电压峰度", "voltage_skewness": "电压偏度",
    "voltage_crest_factor": "电压波峰因子", "voltage_impulse_factor": "电压脉冲因子", "voltage_margin_factor": "电压裕度因子",
    "current_mean": "电流均值", "current_std": "电流标准差", "current_peak_ratio": "电流峰值比",
    "current_kurtosis": "电流峰度", "current_skewness": "电流偏度",
    "current_crest_factor": "电流波峰因子", "current_impulse_factor": "电流脉冲因子", "current_margin_factor": "电流裕度因子",
    "active_power_mean": "功率均值", "active_power_std": "功率标准差", "active_power_peak_ratio": "功率峰值比",
    "active_power_kurtosis": "功率峰度", "active_power_skewness": "功率偏度",
    "active_power_crest_factor": "功率波峰因子", "active_power_impulse_factor": "功率脉冲因子", "active_power_margin_factor": "功率裕度因子",
}

# 网格搜索参数
PARAM_GRID = [
    {"learning_rate": 0.001, "epochs": 10, "batch_size": 16},
    {"learning_rate": 0.0005, "epochs": 15, "batch_size": 16},
    {"learning_rate": 0.001, "epochs": 20, "batch_size": 32},
    {"learning_rate": 0.0001, "epochs": 20, "batch_size": 16},
]

# ---------------------------------------------------------------------------
# 全局模型状态
# ---------------------------------------------------------------------------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = None
model_config = None
dyn_scaler = None
static_scaler = None
thresholds = {}
label_columns = LABEL_COLUMNS


def reload_model(model_path: str = None):
    """加载或重载 CNN+LSTM 模型"""
    global model, model_config, dyn_scaler, static_scaler, thresholds, label_columns, current_model_path

    if model_path is None:
        model_path = DEFAULT_MODEL_PATH

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")

    print(f"[meter] 加载模型: {model_path}", flush=True)
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    model_config = checkpoint["model_config"]
    model = MeterCNNLSTMMultiLabel(**model_config).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    dyn_scaler = checkpoint["dynamic_scaler"]
    static_scaler = checkpoint["static_scaler"]
    thresholds = {label: float(checkpoint["thresholds"][i]) for i, label in enumerate(LABEL_COLUMNS)}
    label_columns = checkpoint.get("label_columns", LABEL_COLUMNS)
    current_model_path = model_path

    print(f"[meter] 模型加载完成, 动态通道={DYNAMIC_CHANNELS}, 标签数={len(label_columns)}", flush=True)
    print(f"[meter] 阈值: {thresholds}", flush=True)
    print(f"[meter] 使用设备: {device}", flush=True)


# 初始加载
if os.path.exists(DEFAULT_MODEL_PATH):
    reload_model(DEFAULT_MODEL_PATH)
else:
    print(f"[meter] 警告: 模型文件不存在 {DEFAULT_MODEL_PATH}", flush=True)


def get_model_info() -> dict:
    """返回模型元信息"""
    return {
        "model_path": current_model_path,
        "model_name": os.path.basename(current_model_path),
        "is_tuned": "tuned" in os.path.basename(current_model_path).lower(),
        "label_columns": LABEL_COLUMNS,
        "label_cn_map": LABEL_CN_MAP,
        "feature_cn_map": FEATURE_CN_MAP,
        "thresholds": thresholds,
        "dynamic_channels": DYNAMIC_CHANNELS,
        "static_base_columns": STATIC_BASE_COLUMNS,
        "model_type": "CNN+LSTM",
        "demo_csv_path": DEMO_CSV_PATH,
    }


# ---------------------------------------------------------------------------
# 特征计算
# ---------------------------------------------------------------------------
def compute_signal_stats(x: np.ndarray) -> dict:
    """对一维序列计算 8 个统计量"""
    x = np.asarray(x, dtype=np.float64)
    eps = 1e-6
    mean = float(np.mean(x))
    std = float(np.std(x))
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(np.square(x))) + eps)
    mean_abs = float(np.mean(np.abs(x)) + eps)
    mean_sqrt_abs = float(np.mean(np.sqrt(np.abs(x) + eps)) + eps)
    centered = x - mean
    m2 = np.mean(centered ** 2) + eps
    m3 = np.mean(centered ** 3)
    m4 = np.mean(centered ** 4)
    skewness = float(m3 / (m2 ** 1.5))
    kurtosis = float(m4 / (m2 ** 2))
    return {
        "mean": mean, "std": std,
        "peak_ratio": peak / (abs(mean) + eps),
        "kurtosis": kurtosis, "skewness": skewness,
        "crest_factor": peak / rms,
        "impulse_factor": peak / mean_abs,
        "margin_factor": peak / (mean_sqrt_abs ** 2),
    }


def preprocess(df: pd.DataFrame) -> tuple:
    """从 DataFrame 提取动态+静态特征，缩放后返回 tensor"""
    n = len(df)

    dyn_arr = np.zeros((n, SEQ_LEN, len(DYNAMIC_CHANNELS)), dtype=np.float32)
    for c_idx, channel in enumerate(DYNAMIC_CHANNELS):
        cols = [f"{channel}_t{idx:03d}" for idx in range(1, SEQ_LEN + 1)]
        missing = [c for c in cols if c not in df.columns]
        if missing:
            csv_cols = list(df.columns)
            raise ValueError(
                f"CSV 缺少动态特征列({channel}): {missing[:5]}...\n"
                f"请确认上传的是电表数据集。\n"
                f"当前CSV列名(前15个): {csv_cols[:15]}"
            )
        dyn_arr[:, :, c_idx] = df[cols].values.astype(np.float32)

    missing_static_base = [c for c in STATIC_BASE_COLUMNS if c not in df.columns]
    if missing_static_base:
        raise ValueError(f"CSV 缺少静态特征列: {missing_static_base}")
    stat_feats = df[STATIC_BASE_COLUMNS].values.astype(np.float32)

    for prefix in STAT_PREFIXES:
        ch_idx = DYNAMIC_CHANNELS.index(prefix)
        for suffix in STAT_SUFFIXES:
            col_name = f"{prefix}_{suffix}"
            if col_name in df.columns:
                feat_vals = df[col_name].values.astype(np.float32)
            else:
                feat_vals = np.array([
                    compute_signal_stats(dyn_arr[i, :, ch_idx])[suffix]
                    for i in range(n)
                ], dtype=np.float32)
            stat_feats = np.column_stack([stat_feats, feat_vals])

    dyn_scaled = (dyn_arr - np.array(dyn_scaler["mean"], dtype=np.float32)) / np.array(dyn_scaler["std"], dtype=np.float32)
    static_scaled = (stat_feats - np.array(static_scaler["mean"], dtype=np.float32)) / np.array(static_scaler["std"], dtype=np.float32)

    dyn_tensor = torch.tensor(dyn_scaled, dtype=torch.float32).to(device)
    static_tensor = torch.tensor(static_scaled, dtype=torch.float32).to(device)

    return dyn_tensor, static_tensor, stat_feats, dyn_arr


def _to_native_val(val):
    """转换单个值为 Python 原生类型"""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    if pd.isna(val):
        return None
    return val


def _to_native(obj):
    """递归转换 numpy 类型为 Python 原生类型"""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(v) for v in obj]
    return obj


def run_predictions(df: pd.DataFrame) -> dict:
    """批量预测"""
    n = len(df)
    try:
        dyn_tensor, static_tensor, stat_feats, dyn_arr = preprocess(df)
    except ValueError as e:
        return {"error": str(e)}

    with torch.no_grad():
        logits = model(dyn_tensor, static_tensor)
        y_prob = torch.sigmoid(logits).cpu().numpy()

    y_pred = np.zeros_like(y_prob, dtype=np.int32)
    for j, label in enumerate(LABEL_COLUMNS):
        thr = thresholds.get(label, 0.5)
        y_pred[:, j] = (y_prob[:, j] >= thr).astype(np.int32)

    id_col = "METER_ID" if "METER_ID" in df.columns else None

    predictions = []
    for i in range(n):
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
        for c in STATIC_BASE_COLUMNS:
            val = df.iloc[i][c]
            row["features"][c] = _to_native_val(val)
        for c in df.columns:
            if c not in STATIC_BASE_COLUMNS and c not in LABEL_COLUMNS and c != id_col:
                if not c.startswith(("voltage_t", "current_t", "active_power_t", "power_factor_t")):
                    if c in FEATURE_CN_MAP:
                        val = df.iloc[i][c]
                        row["features"][c] = _to_native_val(val)

        predictions.append(row)

    all_static_cols = STATIC_BASE_COLUMNS.copy()
    for prefix in STAT_PREFIXES:
        for suffix in STAT_SUFFIXES:
            all_static_cols.append(f"{prefix}_{suffix}")

    result = {
        "n_samples": int(n),
        "n_features": len(all_static_cols),
        "n_labels": len(LABEL_COLUMNS),
        "feature_columns": all_static_cols,
        "label_columns": LABEL_COLUMNS,
        "label_cn_map": LABEL_CN_MAP,
        "feature_cn_map": FEATURE_CN_MAP,
        "thresholds": {k: float(v) for k, v in thresholds.items()},
        "predictions": predictions,
    }

    has_labels = all(c in df.columns for c in LABEL_COLUMNS)
    if has_labels:
        y_true = df[LABEL_COLUMNS].astype(int).values
        result["metrics"] = _compute_metrics(y_true, y_pred, y_prob)
        result["metrics"]["thresholds"] = result["thresholds"]

        cooccur = np.zeros((len(LABEL_COLUMNS), len(LABEL_COLUMNS)), dtype=int)
        for i in range(n):
            for a in range(len(LABEL_COLUMNS)):
                if y_true[i, a] == 0:
                    continue
                for b in range(len(LABEL_COLUMNS)):
                    if y_true[i, b] == 1:
                        cooccur[a, b] += 1
        result["cooccurrence_matrix"] = cooccur.tolist()
        result["pos_counts"] = [int(y_true[:, j].sum()) for j in range(len(LABEL_COLUMNS))]

        result["summary"] = {
            "total_samples": int(n),
            "anomaly_samples": int((y_true.sum(axis=1) > 0).sum()),
            "normal_samples": int((y_true.sum(axis=1) == 0).sum()),
            "total_anomaly_flags": int(y_true.sum()),
            "pos_counts": {LABEL_CN_MAP.get(l, l): int(y_true[:, j].sum()) for j, l in enumerate(LABEL_COLUMNS)},
        }
    else:
        result["summary"] = {
            "total_samples": int(n),
            "pred_anomaly_samples": int((y_pred.sum(axis=1) > 0).sum()),
            "pred_normal_samples": int((y_pred.sum(axis=1) == 0).sum()),
            "total_pred_anomaly_flags": int(y_pred.sum()),
            "pred_pos_counts": {LABEL_CN_MAP.get(l, l): int(y_pred[:, j].sum()) for j, l in enumerate(LABEL_COLUMNS)},
        }

    return result


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict:
    """计算多标签分类指标"""
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


# ---------------------------------------------------------------------------
# 超参数网格搜索
# ---------------------------------------------------------------------------
def _search_best_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """搜索 F1 最优阈值"""
    best_thr, best_f1 = 0.5, -1.0
    for t in np.arange(0.1, 0.91, 0.05):
        pred = (y_prob >= t).astype(int)
        score = f1_score(y_true, pred, zero_division=0)
        if score > best_f1:
            best_f1, best_thr = score, float(round(t, 2))
    return best_thr


def fine_tune_model(model_to_train, train_loader, val_dyn, val_static, val_y, lr, epochs, dev):
    """微调 CNN+LSTM 模型"""
    import copy

    val_dyn_t = torch.tensor(val_dyn, dtype=torch.float32).to(dev)
    val_static_t = torch.tensor(val_static, dtype=torch.float32).to(dev)
    val_y_t = torch.tensor(val_y, dtype=torch.float32).to(dev)

    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model_to_train.parameters(), lr=lr)

    best_val_loss = float("inf")
    best_state = copy.deepcopy(model_to_train.state_dict())
    patience = max(3, epochs // 3)
    no_improve = 0

    for epoch in range(epochs):
        model_to_train.train()
        for batch_dyn, batch_static, batch_labels in train_loader:
            batch_dyn = batch_dyn.to(dev)
            batch_static = batch_static.to(dev)
            batch_labels = batch_labels.to(dev)
            optimizer.zero_grad()
            logits = model_to_train(batch_dyn, batch_static)
            loss = criterion(logits, batch_labels)
            loss.backward()
            optimizer.step()

        model_to_train.eval()
        with torch.no_grad():
            val_logits = model_to_train(val_dyn_t, val_static_t)
            val_loss = criterion(val_logits, val_y_t).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = copy.deepcopy(model_to_train.state_dict())
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break

    model_to_train.load_state_dict(best_state)
    model_to_train.eval()
    with torch.no_grad():
        val_logits = model_to_train(val_dyn_t, val_static_t)
        val_prob = torch.sigmoid(val_logits).cpu().numpy()

    best_thresholds = {}
    val_pred = np.zeros_like(val_prob, dtype=int)
    for j, label in enumerate(LABEL_COLUMNS):
        thr = _search_best_threshold(val_y[:, j], val_prob[:, j])
        best_thresholds[label] = thr
        val_pred[:, j] = (val_prob[:, j] >= thr).astype(int)

    macro_f1 = float(f1_score(val_y, val_pred, average="macro", zero_division=0))
    micro_f1 = float(f1_score(val_y, val_pred, average="micro", zero_division=0))

    return best_state, macro_f1, micro_f1, best_thresholds


def gridsearch_tune(file_content: bytes, filename: str) -> dict:
    """接收 CSV 文件内容，执行超参数网格搜索调优"""
    global _tune_status, model, thresholds, current_model_path

    if _tune_status["running"]:
        return {"error": "已有调优任务正在执行"}

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
            return {"error": "无法解析 CSV 或文件为空"}

        missing_labels = [c for c in LABEL_COLUMNS if c not in df.columns]
        if missing_labels:
            return {"error": f"CSV 缺少标签列: {missing_labels}"}

        n_total = len(df)
        print(f"[meter] 超参数调优开始: {filename}, {n_total} 条样本", flush=True)
        set_tune_status(True, 0, "准备数据...")
        t_start = time.time()

        set_tune_status(True, 2, "计算原始模型基准...")

        try:
            dyn_tensor, static_tensor, _, _ = preprocess(df)
        except ValueError as e:
            return {"error": str(e)}

        y_full = df[LABEL_COLUMNS].astype(int).values
        X_dyn = dyn_tensor.cpu().numpy()
        X_static = static_tensor.cpu().numpy()
        stratify = (y_full.sum(axis=1) > 0).astype(int)

        if n_total >= 8:
            train_idx, val_idx = train_test_split(
                np.arange(n_total), test_size=0.3, random_state=42,
                stratify=stratify if len(np.unique(stratify)) > 1 else None,
            )
        else:
            n_val = max(1, n_total // 2)
            train_idx = np.arange(n_total - n_val)
            val_idx = np.arange(n_total - n_val, n_total)

        X_train_dyn, X_val_dyn = X_dyn[train_idx], X_dyn[val_idx]
        X_train_static, X_val_static = X_static[train_idx], X_static[val_idx]
        y_train, y_val = y_full[train_idx], y_full[val_idx]
        n_train, n_val = len(train_idx), len(val_idx)

        result_orig_full = run_predictions(df)
        orig_full_metrics = result_orig_full.get("metrics", {})

        grid_results = []
        best_macro_f1 = -1.0
        best_params = None
        best_state_dict = None
        best_thresholds = None

        n_combos = len(PARAM_GRID)
        for combo_idx, params in enumerate(PARAM_GRID):
            progress_pct = int((combo_idx / n_combos) * 85)
            set_tune_status(True, progress_pct,
                f"网格搜索 {combo_idx+1}/{n_combos}: lr={params['learning_rate']}, epochs={params['epochs']}, batch={params['batch_size']}")

            checkpoint = torch.load(DEFAULT_MODEL_PATH, map_location=device, weights_only=False)
            search_model = MeterCNNLSTMMultiLabel(**checkpoint["model_config"]).to(device)
            search_model.load_state_dict(checkpoint["model_state_dict"])

            train_dataset = TensorDataset(
                torch.tensor(X_train_dyn, dtype=torch.float32),
                torch.tensor(X_train_static, dtype=torch.float32),
                torch.tensor(y_train, dtype=torch.float32),
            )
            train_loader = DataLoader(train_dataset, batch_size=params["batch_size"], shuffle=True)

            state_dict, macro_f1, micro_f1, combo_thresholds = fine_tune_model(
                search_model, train_loader, X_val_dyn, X_val_static, y_val,
                lr=params["learning_rate"], epochs=params["epochs"], dev=device,
            )

            combo_result = {
                "combo_index": combo_idx + 1,
                "params": {k: v for k, v in params.items()},
                "val_macro_f1": round(macro_f1, 6),
                "val_micro_f1": round(micro_f1, 6),
            }
            grid_results.append(combo_result)

            if macro_f1 > best_macro_f1:
                best_macro_f1 = macro_f1
                best_params = {k: v for k, v in params.items()}
                best_state_dict = state_dict
                best_thresholds = combo_thresholds

        set_tune_status(True, 90, "应用最佳模型...")

        checkpoint = torch.load(DEFAULT_MODEL_PATH, map_location=device, weights_only=False)
        final_model = MeterCNNLSTMMultiLabel(**checkpoint["model_config"]).to(device)
        final_model.load_state_dict(best_state_dict)
        final_model.eval()

        set_tune_status(True, 95, "保存新模型...")

        tuned_checkpoint = {
            "model_config": checkpoint["model_config"],
            "model_state_dict": final_model.state_dict(),
            "dynamic_scaler": checkpoint["dynamic_scaler"],
            "static_scaler": checkpoint["static_scaler"],
            "thresholds": [best_thresholds.get(l, 0.5) for l in LABEL_COLUMNS],
            "label_columns": LABEL_COLUMNS,
        }
        torch.save(tuned_checkpoint, TUNED_MODEL_PATH)

        set_tune_status(True, 98, "重载新模型并全量预测...")
        reload_model(TUNED_MODEL_PATH)

        result = run_predictions(df)
        if "error" in result:
            return {"error": result["error"]}

        new_macro_f1 = result.get("metrics", {}).get("macro_f1", 0)
        improvement = round(new_macro_f1 - orig_full_metrics.get("macro_f1", 0), 6)
        result["eval_note"] = f"模型在 70% 数据上微调，在全量 {n_total} 条数据上评估"
        t_elapsed = round(time.time() - t_start, 1)

        result["grid_search"] = {
            "grid_results": grid_results,
            "best_params": best_params,
            "best_combo_index": grid_results.index(
                next(g for g in grid_results if g["val_macro_f1"] == round(best_macro_f1, 6))
            ) + 1 if grid_results else 0,
            "best_val_macro_f1": round(best_macro_f1, 6),
            "original_macro_f1": round(orig_full_metrics.get("macro_f1", 0), 6),
            "original_full_metrics": {
                "micro_f1": orig_full_metrics.get("micro_f1"),
                "macro_f1": orig_full_metrics.get("macro_f1"),
                "subset_accuracy": orig_full_metrics.get("subset_accuracy"),
                "hamming_loss": orig_full_metrics.get("hamming_loss"),
                "micro_precision": orig_full_metrics.get("micro_precision"),
                "micro_recall": orig_full_metrics.get("micro_recall"),
            },
            "tuned_macro_f1": round(new_macro_f1, 6),
            "improvement": improvement,
            "tuned_model_path": TUNED_MODEL_PATH,
            "time_elapsed_seconds": t_elapsed,
            "n_combos": n_combos,
            "n_train": n_train,
            "n_val": n_val,
        }

        result = _to_native(result)
        set_tune_status(False, 100, "调优完成")
        print(f"[meter] 调优完成! 耗时 {t_elapsed}s, Macro F1={new_macro_f1:.4f}, 提升={improvement:+.4f}", flush=True)
        return result

    except Exception as e:
        set_tune_status(False, 0, f"失败: {str(e)}")
        print(f"[meter] 调优失败: {e}", flush=True)
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