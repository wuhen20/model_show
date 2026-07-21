"""台区四精预测 — FastAPI 路由

支持四个模型: load_forecast / load_rate / power_factor / unbalance
所有端点通过 model_key 查询参数区分模型。
"""
from pathlib import Path
from io import StringIO
import os
import traceback
import threading

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import FileResponse

from app.demo_services import tq_forecast_engine as engine

router = APIRouter()

_BACKEND_DIR = Path(__file__).parent.parent.parent.parent

# 每个模型的训练状态
_train_status = {}
_train_lock = threading.Lock()


def _get_status(model_key):
    if model_key not in _train_status:
        _train_status[model_key] = {
            "running": False, "progress": 0, "message": "", "result": None, "error": None,
        }
    return _train_status[model_key]


@router.get("/ping")
def ping():
    return {"status": "ok", "message": "TQ forecast demo is alive"}


@router.get("/model_info")
def model_info(model_key: str = Query(...)):
    if model_key not in engine.MODEL_CONFIGS:
        raise HTTPException(status_code=400, detail=f"未知模型: {model_key}")
    return engine.get_model_info(model_key)


@router.get("/demo_csv")
def serve_demo_csv(model_key: str = Query(...)):
    """下载预测体验数据（predict_sample.csv）"""
    path = engine.get_predict_csv_path(model_key)
    if path and os.path.exists(path):
        return FileResponse(path, media_type="text/csv", filename=f"{model_key}_predict_sample.csv")
    raise HTTPException(status_code=404, detail="体验数据文件不存在")


@router.get("/predict_csv")
def serve_predict_csv(model_key: str = Query(...)):
    path = engine.get_predict_csv_path(model_key)
    if path and os.path.exists(path):
        return FileResponse(path, media_type="text/csv", filename=f"{model_key}_predict_sample.csv")
    raise HTTPException(status_code=404, detail="预测体验数据文件不存在")


@router.get("/evaluate")
def evaluate(model_key: str = Query(...)):
    return engine.get_evaluation(model_key)


@router.get("/training_log")
def training_log(model_key: str = Query(...)):
    return engine.get_training_log(model_key)


@router.get("/figures")
def figures(model_key: str = Query(...)):
    return {"status": "ok", "data": engine.get_prediction_figures(model_key)}


@router.post("/upload_train")
async def upload_train(model_key: str = Query(...), file: UploadFile = File(...)):
    try:
        content = await file.read()
        for enc in ["utf-8-sig", "utf-8", "gbk", "gb2312"]:
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        df = pd.read_csv(StringIO(text))
        temp_path = str(_BACKEND_DIR / "data" / f"tq_{model_key}_train_upload.csv")
        df.to_csv(temp_path, index=False, encoding="utf-8-sig")
        return {"status": "ok", "rows": len(df), "message": "训练数据上传成功（将使用内置预处理数据训练）"}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@router.post("/train")
async def train(model_key: str = Query(...), n_trials: int = Form(10)):
    if model_key not in engine.MODEL_CONFIGS:
        raise HTTPException(status_code=400, detail=f"未知模型: {model_key}")
    status = _get_status(model_key)
    with _train_lock:
        if status["running"]:
            return {"status": "error", "message": "该模型训练已在进行中"}
        status.update(running=True, progress=0, message=f"准备开始训练 (Optuna {n_trials} 轮)...", result=None, error=None)

    def progress_callback(current, total, best_score):
        with _train_lock:
            status["progress"] = int(current / total * 100) if total > 0 else 0
            status["message"] = f"Optuna搜索: {current}/{total} 轮, 最优 val_loss={best_score:.6f}"

    def run_train():
        try:
            with _train_lock:
                status["message"] = "正在加载数据与预处理..."
            result = engine.train(model_key, n_trials=n_trials, progress_callback=progress_callback)
            with _train_lock:
                status["running"] = False
                status["progress"] = 100
                status["message"] = "训练完成"
                status["result"] = result
        except Exception as e:
            traceback.print_exc()
            with _train_lock:
                status["running"] = False
                status["error"] = str(e)
                status["message"] = f"训练失败: {e}"

    threading.Thread(target=run_train, daemon=True).start()
    return {"status": "ok", "message": f"训练已启动: {engine.MODEL_CONFIGS[model_key]['name']} (Optuna {n_trials} 轮)"}


@router.get("/train_status")
def train_status(model_key: str = Query(...)):
    status = _get_status(model_key)
    with _train_lock:
        resp = {"running": status["running"], "progress": status["progress"], "message": status["message"]}
        if status["result"] is not None:
            resp["result"] = status["result"]
        if status["error"] is not None:
            resp["error"] = status["error"]
        return resp


@router.post("/upload_predict")
async def upload_predict(model_key: str = Query(...), file: UploadFile = File(...)):
    try:
        content = await file.read()
        for enc in ["utf-8-sig", "utf-8", "gbk", "gb2312"]:
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        df = pd.read_csv(StringIO(text))
        temp_path = str(_BACKEND_DIR / "data" / f"tq_{model_key}_predict_upload.csv")
        df.to_csv(temp_path, index=False, encoding="utf-8-sig")
        return {"status": "ok", "rows": len(df), "message": "预测数据上传成功"}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@router.post("/predict")
async def predict(model_key: str = Query(...)):
    try:
        result = engine.predict(model_key)
        return result
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@router.get("/download_result")
def download_result(model_key: str = Query(...)):
    result_csv = engine.get_prediction_results_csv(model_key)
    if result_csv and os.path.exists(result_csv):
        return FileResponse(result_csv, media_type="text/csv", filename=f"{model_key}_predict_result.csv")
    raise HTTPException(status_code=404, detail="预测结果文件不存在，请先运行预测")
