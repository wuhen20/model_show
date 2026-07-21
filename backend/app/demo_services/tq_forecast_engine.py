"""四川四模型（负荷预测/负载率/功率因数/三相不平衡）后端引擎。

CNN+LSTM 时序预测模型，支持：
  - 模型训练（Optuna 超参搜索 + 早停）
  - 体验预测（加载预训练模型推理 + 对比图）
  - 模型评估（读取 result_summary.json + 训练曲线）
"""
import os
import sys
import json
import base64
import io
import traceback
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

try:
    import optuna
except Exception:
    optuna = None

# ── 路径 ──────────────────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_MODELS_POOL = _BACKEND_DIR / "models_pool"
_EXP_DIR = _BACKEND_DIR / "experience_data" / "TQ"

# ── 模型配置 ──────────────────────────────────────────
MODEL_CONFIGS = {
    "load_forecast": {
        "name": "台区负荷预测",
        "code": "TQ-01",
        "input_days": 7, "output_days": 1,
        "input_steps": 672, "output_steps": 96,
        "time_series_dim": 9, "points_per_day": 96,
        "channels": ["power", "pf", "voltage", "current"],
        "target_key": "power", "target_unit": "kW",
        "model_type": "two_stage",
        "districts": {5572596045: {"name": "马鞍村1社", "capacity": 50, "res_cust": 41, "pv_cust": 0, "dg_flag": 1}},
        "num_districts": 1, "district_ids": [5572596045],
        "embed_dim": 4, "static_scalar_dim": 7,
        "cnn_out_channels": 24, "cnn_kernel_sizes": [7, 5],
        "lstm_hidden": 64, "lstm_layers": 1, "lstm_dropout": 0.4,
        "fc_hidden": 192, "static_mlp_dim": 12,
        "fc_dropout": 0.2, "static_mlp_dropout": 0.3,
        "residual_cnn_channels": 12, "residual_lstm_hidden": 32,
        "residual_fc_hidden": 96, "residual_lstm_dropout": 0.3,
        "model_path": _MODELS_POOL / "TQ" / "TQ01" / "load_forecast_best_model.pt",
        "exp_dir": _EXP_DIR / "TQ01_load_forecast",
        "batch_size": 16, "learning_rate": 1e-3, "max_epochs": 150,
        "patience_early_stop": 25, "grad_clip_norm": 1.0,
    },
    "load_rate": {
        "name": "台区负载率预测", "code": "TQ-01",
        "input_days": 14, "output_days": 3,
        "input_steps": 1344, "output_steps": 288,
        "time_series_dim": 7, "points_per_day": 96,
        "channels": ["power", "pf"], "target_key": "load_rate", "target_unit": "",
        "model_type": "single",
        "districts": {
            5571387233: {"name": "幸福村4社", "capacity": 50, "res_cust": 3, "pv_cust": 0, "dg_flag": 0},
            5571448883: {"name": "幸福村1社", "capacity": 50, "res_cust": 15, "pv_cust": 0, "dg_flag": 0},
            5572596045: {"name": "马鞍村1社", "capacity": 50, "res_cust": 41, "pv_cust": 0, "dg_flag": 1},
            5572711008: {"name": "甘伍村3社", "capacity": 50, "res_cust": 6, "pv_cust": 0, "dg_flag": 1},
        },
        "num_districts": 4, "district_ids": sorted([5571387233, 5571448883, 5572596045, 5572711008]),
        "embed_dim": 4, "static_scalar_dim": 4,
        "cnn_out_channels": 64, "cnn_kernel_sizes": [7, 5],
        "lstm_hidden": 128, "lstm_layers": 2, "lstm_dropout": 0.2,
        "fc_hidden": 512, "static_mlp_dim": 32,
        "fc_dropout": 0.0, "static_mlp_dropout": 0.0,
        "model_path": _MODELS_POOL / "TQ" / "TQ01" / "load_rate_best_model.pt",
        "exp_dir": _EXP_DIR / "TQ01_load_rate",
        "batch_size": 32, "learning_rate": 1e-3, "max_epochs": 100,
        "patience_early_stop": 10, "grad_clip_norm": 1.0,
    },
    "power_factor": {
        "name": "台区功率因数预测", "code": "TQ-02",
        "input_days": 14, "output_days": 3,
        "input_steps": 1344, "output_steps": 288,
        "time_series_dim": 7, "points_per_day": 96,
        "channels": ["power", "pf"], "target_key": "pf", "target_unit": "",
        "model_type": "single",
        "districts": {
            5571387233: {"name": "幸福村4社", "capacity": 50, "res_cust": 3, "pv_cust": 0, "dg_flag": 0},
            5571448883: {"name": "幸福村1社", "capacity": 50, "res_cust": 15, "pv_cust": 0, "dg_flag": 0},
            5572596045: {"name": "马鞍村1社", "capacity": 50, "res_cust": 41, "pv_cust": 0, "dg_flag": 1},
            5572711008: {"name": "甘伍村3社", "capacity": 50, "res_cust": 6, "pv_cust": 0, "dg_flag": 1},
        },
        "num_districts": 4, "district_ids": sorted([5571387233, 5571448883, 5572596045, 5572711008]),
        "embed_dim": 4, "static_scalar_dim": 4,
        "cnn_out_channels": 64, "cnn_kernel_sizes": [7, 5],
        "lstm_hidden": 128, "lstm_layers": 2, "lstm_dropout": 0.2,
        "fc_hidden": 512, "static_mlp_dim": 32,
        "fc_dropout": 0.0, "static_mlp_dropout": 0.0,
        "model_path": _MODELS_POOL / "TQ" / "TQ02" / "pf_best_model.pt",
        "exp_dir": _EXP_DIR / "TQ02_pf",
        "batch_size": 32, "learning_rate": 1e-3, "max_epochs": 100,
        "patience_early_stop": 10, "grad_clip_norm": 1.0,
    },
    "unbalance": {
        "name": "台区三相不平衡预测", "code": "TQ-03",
        "input_days": 14, "output_days": 3,
        "input_steps": 1344, "output_steps": 288,
        "time_series_dim": 10, "points_per_day": 96,
        "channels": ["power", "pf", "Ia", "Ib", "Ic"], "target_key": "unbalance", "target_unit": "",
        "model_type": "single",
        "districts": {
            5571387233: {"name": "幸福村4社", "capacity": 50, "res_cust": 3, "pv_cust": 0, "dg_flag": 0},
            5571448883: {"name": "幸福村1社", "capacity": 50, "res_cust": 15, "pv_cust": 0, "dg_flag": 0},
            5572596045: {"name": "马鞍村1社", "capacity": 50, "res_cust": 41, "pv_cust": 0, "dg_flag": 1},
            5572711008: {"name": "甘伍村3社", "capacity": 50, "res_cust": 6, "pv_cust": 0, "dg_flag": 1},
        },
        "num_districts": 4, "district_ids": sorted([5571387233, 5571448883, 5572596045, 5572711008]),
        "embed_dim": 4, "static_scalar_dim": 4,
        "cnn_out_channels": 64, "cnn_kernel_sizes": [7, 5],
        "lstm_hidden": 128, "lstm_layers": 2, "lstm_dropout": 0.2,
        "fc_hidden": 512, "static_mlp_dim": 32,
        "fc_dropout": 0.0, "static_mlp_dropout": 0.0,
        "model_path": _MODELS_POOL / "TQ" / "TQ03" / "unbalance_best_model.pt",
        "exp_dir": _EXP_DIR / "TQ03_unbalance",
        "batch_size": 32, "learning_rate": 1e-3, "max_epochs": 100,
        "patience_early_stop": 10, "grad_clip_norm": 1.0,
    },
}

# ── 模型定义 ──────────────────────────────────────────
class CNNLSTM(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.district_embedding = nn.Embedding(cfg["num_districts"], cfg["embed_dim"])
        self.cnn = nn.Sequential(
            nn.Conv1d(cfg["time_series_dim"], cfg["cnn_out_channels"],
                      kernel_size=cfg["cnn_kernel_sizes"][0], padding=cfg["cnn_kernel_sizes"][0] // 2),
            nn.BatchNorm1d(cfg["cnn_out_channels"]), nn.ReLU(),
            nn.Conv1d(cfg["cnn_out_channels"], cfg["cnn_out_channels"],
                      kernel_size=cfg["cnn_kernel_sizes"][1], padding=cfg["cnn_kernel_sizes"][1] // 2),
            nn.BatchNorm1d(cfg["cnn_out_channels"]), nn.ReLU(),
            nn.MaxPool1d(kernel_size=2),
        )
        self.lstm = nn.LSTM(
            input_size=cfg["cnn_out_channels"], hidden_size=cfg["lstm_hidden"],
            num_layers=cfg["lstm_layers"], batch_first=True,
            dropout=cfg["lstm_dropout"] if cfg["lstm_layers"] > 1 else 0,
        )
        self.dropout = nn.Dropout(cfg["lstm_dropout"])
        sid = cfg["embed_dim"] + cfg["static_scalar_dim"]
        layers = [nn.Linear(sid, cfg["static_mlp_dim"]), nn.ReLU()]
        if cfg.get("static_mlp_dropout", 0) > 0:
            layers.append(nn.Dropout(cfg["static_mlp_dropout"]))
        self.static_mlp = nn.Sequential(*layers)
        fc_in = cfg["lstm_hidden"] + cfg["static_mlp_dim"]
        fc_layers = [nn.Linear(fc_in, cfg["fc_hidden"]), nn.ReLU()]
        if cfg.get("fc_dropout", 0) > 0:
            fc_layers.append(nn.Dropout(cfg["fc_dropout"]))
        fc_layers.append(nn.Linear(cfg["fc_hidden"], cfg["output_steps"]))
        self.fc = nn.Sequential(*fc_layers)

    def forward(self, x_time, x_static):
        idx = x_static[:, 0].long()
        emb = self.district_embedding(idx)
        s = torch.cat([emb, x_static[:, 1:]], dim=1)
        s = self.static_mlp(s)
        x = x_time.permute(0, 2, 1)
        x = self.cnn(x).permute(0, 2, 1)
        _, (h, _) = self.lstm(x)
        x = self.dropout(h[-1])
        return self.fc(torch.cat([x, s], dim=1))


class ResidualCorrector(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.district_embedding = nn.Embedding(cfg["num_districts"], cfg["embed_dim"])
        self.cnn = nn.Sequential(
            nn.Conv1d(cfg["time_series_dim"], cfg["residual_cnn_channels"],
                      kernel_size=cfg["cnn_kernel_sizes"][0], padding=cfg["cnn_kernel_sizes"][0] // 2),
            nn.BatchNorm1d(cfg["residual_cnn_channels"]), nn.ReLU(),
            nn.MaxPool1d(kernel_size=2),
        )
        self.lstm = nn.LSTM(cfg["residual_cnn_channels"], cfg["residual_lstm_hidden"], 1, batch_first=True)
        self.dropout = nn.Dropout(cfg["residual_lstm_dropout"])
        sid = cfg["embed_dim"] + cfg["static_scalar_dim"]
        self.static_mlp = nn.Sequential(nn.Linear(sid, 8), nn.ReLU())
        self.fc = nn.Sequential(
            nn.Linear(cfg["residual_lstm_hidden"] + 8, cfg["residual_fc_hidden"]),
            nn.ReLU(), nn.Dropout(0.15),
            nn.Linear(cfg["residual_fc_hidden"], cfg["output_steps"]),
        )

    def forward(self, x_time, x_static):
        idx = x_static[:, 0].long()
        emb = self.district_embedding(idx)
        s = self.static_mlp(torch.cat([emb, x_static[:, 1:]], dim=1))
        x = self.cnn(x_time.permute(0, 2, 1)).permute(0, 2, 1)
        _, (h, _) = self.lstm(x)
        x = self.dropout(h[-1])
        return self.fc(torch.cat([x, s], dim=1))


# ── 辅助函数 ──────────────────────────────────────────
def _fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _deserialize_normalizer(norm_json):
    params = json.loads(norm_json) if isinstance(norm_json, str) else norm_json
    out = {}
    for k, v in params.items():
        out[int(k)] = v
    return out


def _load_train_npz(model_key):
    cfg = MODEL_CONFIGS[model_key]
    path = cfg["exp_dir"] / "train_data.npz"
    if not path.exists():
        raise FileNotFoundError(f"训练数据不存在: {path}")
    d = np.load(path, allow_pickle=True)
    return {
        "X_time": d["X_time"], "X_static": d["X_static"], "Y": d["Y"],
        "entity_ids": d["entity_ids"],
        "normalizer_params": _deserialize_normalizer(str(d["normalizer_params"])),
    }


# ── 训练 ──────────────────────────────────────────────
def train(model_key, n_trials=10, progress_callback=None):
    cfg = MODEL_CONFIGS[model_key]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data = _load_train_npz(model_key)
    X_time, X_static, Y = data["X_time"], data["X_static"], data["Y"]
    n = len(X_time)
    idx = np.random.RandomState(42).permutation(n)
    n_train = int(n * 0.85)
    tr_idx, va_idx = idx[:n_train], idx[n_train:]
    tr_dl = DataLoader(TensorDataset(
        torch.tensor(X_time[tr_idx], dtype=torch.float32),
        torch.tensor(X_static[tr_idx], dtype=torch.float32),
        torch.tensor(Y[tr_idx], dtype=torch.float32)),
        batch_size=cfg["batch_size"], shuffle=True, drop_last=True)
    va_dl = DataLoader(TensorDataset(
        torch.tensor(X_time[va_idx], dtype=torch.float32),
        torch.tensor(X_static[va_idx], dtype=torch.float32),
        torch.tensor(Y[va_idx], dtype=torch.float32)),
        batch_size=cfg["batch_size"], shuffle=False)

    best_params = None
    optuna_log = []

    if optuna and n_trials > 0:
        def objective(trial):
            lr = trial.suggest_float("lr", 5e-4, 3e-3, log=True)
            bs = trial.suggest_categorical("batch_size", [8, 16, 32])
            hidden = trial.suggest_categorical("lstm_hidden", [32, 64, 128])
            drop = trial.suggest_float("dropout", 0.1, 0.4)
            m = CNNLSTM({**cfg, "lstm_hidden": hidden, "lstm_dropout": drop}).to(device)
            opt = torch.optim.Adam(m.parameters(), lr=lr)
            crit = nn.MSELoss()
            m.train()
            for _ in range(5):
                for xt, xs, yb in tr_dl:
                    xt, xs, yb = xt.to(device), xs.to(device), yb.to(device)
                    opt.zero_grad()
                    loss = crit(m(xt, xs), yb)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(m.parameters(), cfg["grad_clip_norm"])
                    opt.step()
            m.eval()
            vl = 0.0
            with torch.no_grad():
                for xt, xs, yb in va_dl:
                    vl += crit(m(xt.to(device), xs.to(device)), yb.to(device)).item() * len(yb)
            vl /= len(va_dl.dataset)
            optuna_log.append({"trial": trial.number, "val_loss": round(vl, 6), "params": {"lr": lr, "batch_size": bs, "lstm_hidden": hidden, "dropout": drop}})
            return vl

        study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=42))
        for i in range(n_trials):
            study.optimize(objective, n_trials=1, catch=(Exception,))
            if progress_callback:
                progress_callback(i + 1, n_trials, study.best_value if study.best_trials else float("inf"))
        best_params = study.best_params if study.best_trials else None

    train_cfg = {**cfg}
    if best_params:
        train_cfg["lstm_hidden"] = best_params["lstm_hidden"]
        train_cfg["lstm_dropout"] = best_params["dropout"]
        train_cfg["batch_size"] = best_params["batch_size"]
        lr = best_params["lr"]
    else:
        lr = cfg["learning_rate"]

    model = CNNLSTM(train_cfg).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=cfg["max_epochs"], eta_min=1e-6)
    criterion = nn.MSELoss()

    best_val = float("inf")
    best_state = None
    best_epoch = 0
    patience = 0
    log_rows = []
    epochs = min(cfg["max_epochs"], 30)

    for ep in range(epochs):
        model.train()
        tl = 0.0
        for xt, xs, yb in tr_dl:
            xt, xs, yb = xt.to(device), xs.to(device), yb.to(device)
            optimizer.zero_grad()
            loss = criterion(model(xt, xs), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg["grad_clip_norm"])
            optimizer.step()
            tl += loss.item() * len(yb)
        tl /= len(tr_dl.dataset)
        scheduler.step()

        model.eval()
        vl = 0.0
        with torch.no_grad():
            for xt, xs, yb in va_dl:
                vl += criterion(model(xt.to(device), xs.to(device)), yb.to(device)).item() * len(yb)
        vl /= len(va_dl.dataset)

        log_rows.append({"epoch": ep + 1, "train_loss": round(tl, 8), "val_loss": round(vl, 8), "lr": optimizer.param_groups[0]["lr"]})
        if vl < best_val:
            best_val = vl
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            best_epoch = ep + 1
            patience = 0
        else:
            patience += 1
        if patience >= cfg["patience_early_stop"]:
            break

    model.load_state_dict(best_state)
    save_path = str(cfg["model_path"])
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    torch.save({"model_state_dict": best_state, "normalizer_params": data["normalizer_params"], "best_val_loss": best_val}, save_path)

    # 训练曲线
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot([r["epoch"] for r in log_rows], [r["train_loss"] for r in log_rows], "b-", label="Train Loss")
    ax.plot([r["epoch"] for r in log_rows], [r["val_loss"] for r in log_rows], "r--", label="Val Loss")
    ax.set_xlabel("Epoch"); ax.set_ylabel("Loss"); ax.set_title(f"{cfg['name']} Training Curve"); ax.legend(); ax.grid(True, alpha=0.3)
    chart_b64 = _fig_to_base64(fig)

    return {
        "metrics": {"best_val_loss": round(float(best_val), 6), "best_epoch": best_epoch, "total_params": n_params, "epochs_trained": len(log_rows)},
        "training_log": log_rows,
        "charts": {"training_curve": chart_b64},
        "optuna_best_params": best_params or {},
        "optuna_log": optuna_log,
        "model_path": save_path,
    }


# ── 预测 ──────────────────────────────────────────────
def predict(model_key, csv_path=None):
    cfg = MODEL_CONFIGS[model_key]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_path = str(cfg["model_path"])
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    ckpt = torch.load(model_path, map_location=device, weights_only=False)
    norm_params = ckpt.get("normalizer_params", {})
    if isinstance(norm_params, str):
        norm_params = _deserialize_normalizer(norm_params)

    model = CNNLSTM(cfg).to(device)
    sd_key = "model1_state_dict" if "model1_state_dict" in ckpt else "model_state_dict"
    model.load_state_dict(ckpt[sd_key])
    model.eval()
    has_residual = "model2_state_dict" in ckpt and cfg["model_type"] == "two_stage"
    if has_residual:
        model2 = ResidualCorrector(cfg).to(device)
        model2.load_state_dict(ckpt["model2_state_dict"])
        model2.eval()

    # 使用 train_data.npz 中的数据做预测（含真实值对比）
    data = _load_train_npz(model_key)
    X_time, X_static, Y = data["X_time"], data["X_static"], data["Y"]
    entity_ids = data["entity_ids"]
    n = len(X_time)
    idx = np.random.RandomState(42).permutation(n)
    n_train = int(n * 0.85)
    test_idx = idx[n_train:]
    n_show = min(3, len(test_idx))

    target_key = cfg["target_key"]
    _day_labels = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
    time_labels = [_day_labels[t % 96] for t in range(cfg["output_steps"])]
    districts = cfg["districts"]

    all_pred, all_true = [], []
    for i in range(n_show):
        si = test_idx[i]
        xt = torch.tensor(X_time[si:si+1], dtype=torch.float32).to(device)
        xs = torch.tensor(X_static[si:si+1], dtype=torch.float32).to(device)
        with torch.no_grad():
            pred_norm = model(xt, xs).cpu().numpy()[0]
            if has_residual:
                pred_norm += model2(xt, xs).cpu().numpy()[0]
        eid = int(entity_ids[si])
        p = norm_params.get(eid, {}).get(target_key, {"min": 0, "max": 1})
        scale = p["max"] - p["min"]
        pred_real = pred_norm * scale + p["min"]
        true_real = Y[si] * scale + p["min"]
        all_pred.append(pred_real)
        all_true.append(true_real)

    # 对比图
    fig, axes = plt.subplots(n_show, 1, figsize=(14, 3.5 * n_show), squeeze=False)
    fig.suptitle(f"{cfg['name']} - Predict vs True", fontsize=14)
    for i in range(n_show):
        ax = axes[i, 0]
        t = np.arange(len(all_pred[i]))
        ax.plot(t, all_true[i], "b-", label="True", linewidth=1.2, alpha=0.85)
        ax.plot(t, all_pred[i], "r--", label="Predicted", linewidth=1.2, alpha=0.85)
        ax.set_ylabel(cfg["target_unit"] or "value")
        tick_pos = list(range(0, len(all_pred[i]), 12))
        ax.set_xticks(tick_pos)
        ax.set_xticklabels([time_labels[p] for p in tick_pos], fontsize=7)
        eid = int(entity_ids[test_idx[i]])
        ax.set_title(f"{districts.get(eid, {}).get('name', eid)} - Sample #{i}", fontsize=10, color="gray")
        if i == 0:
            ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, alpha=0.3)
    chart_b64 = _fig_to_base64(fig)

    # 指标
    pred_flat = np.concatenate(all_pred)
    true_flat = np.concatenate(all_true)
    mae = float(np.mean(np.abs(pred_flat - true_flat)))
    rmse = float(np.sqrt(np.mean((pred_flat - true_flat) ** 2)))
    mask = np.abs(true_flat) > 1e-6
    mape = float(np.mean(np.abs((pred_flat[mask] - true_flat[mask]) / true_flat[mask])) * 100) if mask.any() else 0.0
    cvrmse = float(rmse / max(np.mean(true_flat), 1e-6) * 100)

    # 保存结果 CSV
    result_rows = []
    for i in range(n_show):
        eid = int(entity_ids[test_idx[i]])
        name = districts.get(eid, {}).get("name", str(eid))
        for t in range(len(all_pred[i])):
            day = t // 96 + 1
            h = (t * 15 // 60) % 24
            m = t * 15 % 60
            result_rows.append({"district": name, "sample": i, "day": f"Day{day}", "time": f"{h:02d}:{m:02d}",
                                "predicted": round(float(all_pred[i][t]), 4), "true": round(float(all_true[i][t]), 4)})
    result_df = pd.DataFrame(result_rows)
    result_csv = str(cfg["exp_dir"] / "predict_result.csv")
    result_df.to_csv(result_csv, index=False, encoding="utf-8-sig")

    return {
        "predictions": result_rows[:20],
        "charts": {"predict_compare": chart_b64},
        "metrics": {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 2), "cvrmse": round(cvrmse, 2)},
        "result_csv_path": result_csv,
        "n_samples": n_show,
    }


# ── 信息查询 ──────────────────────────────────────────
def get_model_info(model_key):
    cfg = MODEL_CONFIGS[model_key]
    has_model = cfg["model_path"].exists()
    n_params = 0
    if has_model:
        try:
            ckpt = torch.load(str(cfg["model_path"]), map_location="cpu", weights_only=False)
            m = CNNLSTM(cfg)
            sd_key = "model1_state_dict" if "model1_state_dict" in ckpt else "model_state_dict"
            m.load_state_dict(ckpt[sd_key])
            n_params = sum(p.numel() for p in m.parameters())
            if "model2_state_dict" in ckpt and cfg["model_type"] == "two_stage":
                m2 = ResidualCorrector(cfg)
                m2.load_state_dict(ckpt["model2_state_dict"])
                n_params += sum(p.numel() for p in m2.parameters())
        except Exception:
            pass
    return {
        "model_key": model_key,
        "name": cfg["name"],
        "code": cfg["code"],
        "config": {
            "input_days": cfg["input_days"], "output_days": cfg["output_days"],
            "input_steps": cfg["input_steps"], "output_steps": cfg["output_steps"],
            "time_series_dim": cfg["time_series_dim"],
            "channels": cfg["channels"],
            "cnn_out_channels": cfg["cnn_out_channels"],
            "lstm_hidden": cfg["lstm_hidden"], "lstm_layers": cfg["lstm_layers"],
            "fc_hidden": cfg["fc_hidden"],
        },
        "params": n_params,
        "has_trained_model": has_model,
        "model_type": cfg["model_type"],
        "target_key": cfg["target_key"],
        "target_unit": cfg["target_unit"],
        "districts": [{"id": k, "name": v["name"], "capacity": v["capacity"]} for k, v in cfg["districts"].items()],
    }


def get_evaluation(model_key):
    cfg = MODEL_CONFIGS[model_key]
    json_path = cfg["exp_dir"] / "result_summary.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    # 尝试从 prediction_results.csv 生成基本统计
    csv_path = cfg["exp_dir"] / "prediction_results.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        pred_col = [c for c in df.columns if "predict" in c.lower()][0]
        true_col = [c for c in df.columns if "true" in c.lower()][0]
        p, t = df[pred_col].values, df[true_col].values
        mae = float(np.mean(np.abs(p - t)))
        rmse = float(np.sqrt(np.mean((p - t) ** 2)))
        mask = np.abs(t) > 1e-6
        mape = float(np.mean(np.abs((p[mask] - t[mask]) / t[mask])) * 100) if mask.any() else 0
        return {"overall": {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 2)},
                "n_samples": len(df)}
    return {"error": "评估数据不存在"}


def get_training_log(model_key):
    cfg = MODEL_CONFIGS[model_key]
    logs = {}
    for name in ("training_log_stage1.csv", "training_log_stage2.csv", "training_log.csv"):
        p = cfg["exp_dir"] / name
        if p.exists():
            df = pd.read_csv(p)
            logs[name.replace(".csv", "")] = df.to_dict("records")
    return logs if logs else {"error": "训练日志不存在"}


def get_train_csv_path(model_key):
    cfg = MODEL_CONFIGS[model_key]
    return str(cfg["exp_dir"] / "train_data.npz")


def get_predict_csv_path(model_key):
    cfg = MODEL_CONFIGS[model_key]
    return str(cfg["exp_dir"] / "predict_sample.csv")


def get_prediction_figures(model_key):
    """返回评估目录中的预测对比图(base64)。"""
    cfg = MODEL_CONFIGS[model_key]
    figs_dir = cfg["exp_dir"] / "figures"
    result = []
    if figs_dir.exists():
        for p in sorted(figs_dir.glob("*.png")):
            with open(p, "rb") as f:
                result.append({"name": p.stem, "base64": base64.b64encode(f.read()).decode("utf-8")})
    return result


def get_prediction_results_csv(model_key):
    """返回 prediction_results.csv 路径。"""
    cfg = MODEL_CONFIGS[model_key]
    p = cfg["exp_dir"] / "prediction_results.csv"
    return str(p) if p.exists() else None
