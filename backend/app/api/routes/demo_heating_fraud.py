"""
电采暖高价低接研判 — FastAPI 路由
LightGBM + SHAP + 16维规则评分体系
"""
from pathlib import Path
from io import StringIO
import os
import traceback
import threading

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

from app.demo_services import heating_fraud_engine as engine

router = APIRouter()

_BACKEND_DIR = Path(__file__).parent.parent.parent.parent
_EXPERIENCE_DIR = _BACKEND_DIR / "experience_data" / "YD" / "heating_fraud"
_TRAIN_CSV = _EXPERIENCE_DIR / "train_features.csv"
_PREDICT_CSV = _EXPERIENCE_DIR / "predict_features.csv"

# 全局状态
_train_data = {"df": None, "path": None}
_predict_data = {"df": None, "path": None}
_train_status = {
    "running": False,
    "progress": 0,
    "message": "",
    "result": None,
    "error": None,
}
_train_lock = threading.Lock()


@router.get("/ping")
def ping():
    return {"status": "ok", "message": "heating fraud demo is alive"}


@router.get("/model_info")
def model_info():
    return engine.get_model_info()


@router.get("/demo_csv")
def serve_demo_csv():
    """下载训练体验数据"""
    if _TRAIN_CSV.exists():
        return FileResponse(str(_TRAIN_CSV), media_type="text/csv", filename="train_features.csv")
    raise HTTPException(status_code=404, detail="训练体验数据文件不存在")


@router.get("/predict_csv")
def serve_predict_csv():
    """下载预测体验数据"""
    if _PREDICT_CSV.exists():
        return FileResponse(str(_PREDICT_CSV), media_type="text/csv", filename="predict_features.csv")
    raise HTTPException(status_code=404, detail="预测体验数据文件不存在")


@router.get("/feature_importance")
def feature_importance():
    fi = engine.get_feature_importance()
    return {"status": "ok", "data": fi}


@router.get("/evaluate")
def evaluate():
    return engine.get_evaluation()


@router.get("/rule_spec")
def rule_spec():
    """返回16维规则评分体系说明表"""
    return {"status": "ok", "data": engine.get_rule_spec()}


@router.post("/upload_train")
async def upload_train(file: UploadFile = File(...)):
    try:
        content = await file.read()
        for enc in ["utf-8-sig", "utf-8", "gbk", "gb2312"]:
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        df = pd.read_csv(StringIO(text))
        _train_data["df"] = df
        # 保存到临时文件
        temp_path = str(_BACKEND_DIR / "data" / "heating_fraud_train_upload.csv")
        df.to_csv(temp_path, index=False, encoding="utf-8-sig")
        _train_data["path"] = temp_path
        # 检查是否有 label 列
        has_label = "label" in df.columns
        label_dist = df["label"].value_counts().to_dict() if has_label else {}
        return {
            "status": "ok",
            "rows": len(df),
            "features": len([c for c in df.columns if c not in ("meter_id", "label")]),
            "has_label": has_label,
            "label_distribution": [{"name": str(k), "value": int(v)} for k, v in label_dist.items()],
            "message": "训练数据上传成功",
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@router.post("/train")
async def train(n_trials: int = Form(100)):
    global _train_status
    with _train_lock:
        if _train_status["running"]:
            return {"status": "error", "message": "训练已在进行中"}

        # 确定训练数据路径
        csv_path = _train_data.get("path")
        if not csv_path or not os.path.exists(csv_path):
            csv_path = engine.get_train_csv_path()
        if not os.path.exists(csv_path):
            return {"status": "error", "message": "训练数据不存在，请先上传或使用内置数据"}

        _train_status = {
            "running": True,
            "progress": 0,
            "message": f"准备开始训练 (Optuna {n_trials} 轮)...",
            "result": None,
            "error": None,
        }

    def progress_callback(current, total, best_score):
        with _train_lock:
            _train_status["progress"] = int(current / total * 100) if total > 0 else 0
            _train_status["message"] = f"Optuna搜索中: {current}/{total} 轮, 当前最优 {engine.OPTUNA_OBJECTIVE}={best_score:.4f}"

    def run_train():
        global _train_status
        try:
            with _train_lock:
                _train_status["message"] = "正在加载数据与预处理..."
            result = engine.train(csv_path, n_trials=n_trials, progress_callback=progress_callback)
            with _train_lock:
                _train_status["running"] = False
                _train_status["progress"] = 100
                _train_status["message"] = "训练完成"
                _train_status["result"] = result
        except Exception as e:
            traceback.print_exc()
            with _train_lock:
                _train_status["running"] = False
                _train_status["error"] = str(e)
                _train_status["message"] = f"训练失败: {e}"

    threading.Thread(target=run_train, daemon=True).start()
    return {"status": "ok", "message": f"训练已启动 (Optuna {n_trials} 轮)"}


@router.get("/train_status")
def train_status():
    with _train_lock:
        resp = {
            "running": _train_status["running"],
            "progress": _train_status["progress"],
            "message": _train_status["message"],
        }
        if _train_status["result"] is not None:
            resp["result"] = _train_status["result"]
        if _train_status["error"] is not None:
            resp["error"] = _train_status["error"]
        return resp


@router.post("/upload_predict")
async def upload_predict(file: UploadFile = File(...)):
    try:
        content = await file.read()
        for enc in ["utf-8-sig", "utf-8", "gbk", "gb2312"]:
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        df = pd.read_csv(StringIO(text))
        _predict_data["df"] = df
        temp_path = str(_BACKEND_DIR / "data" / "heating_fraud_predict_upload.csv")
        df.to_csv(temp_path, index=False, encoding="utf-8-sig")
        _predict_data["path"] = temp_path
        has_meter_id = "meter_id" in df.columns
        return {
            "status": "ok",
            "rows": len(df),
            "features": len([c for c in df.columns if c not in ("meter_id", "label")]),
            "has_meter_id": has_meter_id,
            "message": "预测数据上传成功",
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@router.post("/predict")
async def predict():
    csv_path = _predict_data.get("path")
    if not csv_path or not os.path.exists(csv_path):
        csv_path = engine.get_predict_csv_path()
    if not os.path.exists(csv_path):
        return {"status": "error", "message": "预测数据不存在，请先上传或使用内置数据"}
    try:
        result = engine.predict(csv_path)
        return result
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@router.get("/download_result")
def download_result():
    """下载预测结果CSV"""
    result_csv = str(_BACKEND_DIR / "data" / "uploads" / "heating_fraud_predict_result.csv")
    if os.path.exists(result_csv):
        return FileResponse(result_csv, media_type="text/csv", filename="heating_fraud_predict_result.csv")
    raise HTTPException(status_code=404, detail="预测结果文件不存在，请先运行预测")
