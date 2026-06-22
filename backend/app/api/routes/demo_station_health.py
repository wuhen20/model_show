"""
主站异常研判 — FastAPI 路由
XGBoost + RF + 1D-CNN Stacking 集成
"""
from pathlib import Path
from io import BytesIO, StringIO
import os
import traceback
import threading

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse

from app.demo_services import station_health_engine as engine

router = APIRouter()

_BACKEND_DIR = Path(__file__).parent.parent.parent.parent
_EXPERIENCE_DIR = _BACKEND_DIR / "experience_data" / "ZJ" / "station_health"
_DEMO_CSV = _EXPERIENCE_DIR / "simulated_train_data.csv"
_TEST_CSV = _EXPERIENCE_DIR / "主站异常研判_1万条真实噪声样本.csv"

# 全局状态
_train_data = {"df": None, "path": None}


@router.get("/ping")
def ping():
    return {"status": "ok", "message": "station health demo is alive"}


@router.get("/model_info")
def model_info():
    has_trained = os.path.exists(os.path.join(engine._TRAINED_MODEL_DIR, "traction_detect_xgb_model.json"))
    return {
        "model_type": "XGBoost + RandomForest + 1D-CNN Stacking",
        "n_classes": engine.N_CLASSES,
        "target_names": engine.TARGET_NAMES,
        "has_trained_model": has_trained,
        "default_model_available": True,
    }


@router.get("/demo_csv")
def serve_demo_csv():
    if _DEMO_CSV.exists():
        return FileResponse(str(_DEMO_CSV), media_type="text/csv", filename="simulated_train_data.csv")
    raise HTTPException(status_code=404, detail="演示数据文件不存在")


@router.get("/test_csv")
def serve_test_csv():
    if _TEST_CSV.exists():
        return FileResponse(str(_TEST_CSV), media_type="text/csv", filename="test_data.csv")
    raise HTTPException(status_code=404, detail="测试数据文件不存在")


@router.get("/feature_importance")
def feature_importance():
    fi = engine.get_feature_importance()
    return {"status": "ok", "data": fi}


@router.get("/evaluate")
def evaluate():
    try:
        model_xgb, model_rf, model_cnn, cnn_scaler, meta_learner, label_encoder = engine.load_models()
        drop_features = engine.get_dropped_features()
        # 加载测试数据
        test_path = _TEST_CSV
        if not test_path.exists():
            test_path = _DEMO_CSV
        df = pd.read_csv(str(test_path))
        X = df.iloc[:, :-2]
        y = df.iloc[:, -2].squeeze()
        # 对齐特征
        existing_drop = [f for f in drop_features if f in X.columns]
        X_sel = X.drop(columns=existing_drop, errors="ignore")
        # 各模型预测
        xgb_proba = model_xgb.predict_proba(X_sel)
        rf_proba = model_rf.predict_proba(X_sel)
        X_scaled = cnn_scaler.transform(X_sel)
        X_cnn = np.expand_dims(X_scaled, axis=-1)
        cnn_proba = model_cnn.predict(X_cnn, verbose=0)
        y_pred_stack, _ = engine.stacking_predict(xgb_proba, rf_proba, cnn_proba, meta_learner)
        # 标签编码
        import numpy as np
        from sklearn.preprocessing import LabelEncoder
        le = LabelEncoder()
        y_enc = pd.Series(le.fit_transform(y.astype(str)), index=y.index)
        from sklearn.metrics import accuracy_score, f1_score
        def eval_one(name, proba, y_true):
            pred = np.argmax(proba, axis=1)
            return {"modelName": name, "accuracy": round(float(accuracy_score(y_true, pred)), 4), "f1": round(float(f1_score(y_true, pred, average='weighted')), 4)}
        return {
            "status": "ok",
            "evaluations": [
                eval_one("XGBoost", xgb_proba, y_enc),
                eval_one("RandomForest", rf_proba, y_enc),
                eval_one("1D-CNN", cnn_proba, y_enc),
                {"modelName": "Stacking集成", "accuracy": round(float(accuracy_score(y_enc, y_pred_stack)), 4), "f1": round(float(f1_score(y_enc, y_pred_stack, average='weighted')), 4)},
            ],
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@router.post("/predict")
async def predict(file: UploadFile = File(...), model_type: str = Query("default", description="default|trained")):
    use_trained = model_type == "trained"
    model_dir = engine.get_model_dir(use_trained)
    try:
        content = await file.read()
        for enc in ["utf-8-sig", "utf-8", "gbk", "gb2312"]:
            try: text = content.decode(enc); break
            except UnicodeDecodeError: continue
        df = pd.read_csv(StringIO(text))
        result = engine.predict(df, model_dir)
        result["model_type"] = model_type
        return result
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@router.post("/upload_train")
async def upload_train(file: UploadFile = File(...)):
    try:
        content = await file.read()
        for enc in ["utf-8-sig", "utf-8", "gbk", "gb2312"]:
            try: text = content.decode(enc); break
            except UnicodeDecodeError: continue
        df = pd.read_csv(StringIO(text))
        _train_data["df"] = df
        X = df.iloc[:, :-2]
        y = df.iloc[:, -2].squeeze()
        class_dist = y.value_counts().to_dict()
        return {
            "status": "ok",
            "rows": len(df),
            "features": len(X.columns),
            "class_distribution": [{"name": str(k), "value": int(v)} for k, v in class_dist.items()],
            "message": "数据上传成功",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/train")
async def train(n_trials: int = Form(10)):
    if _train_data["df"] is None:
        return {"status": "error", "message": "请先上传训练数据"}

    if engine.get_train_status()["running"]:
        return {"status": "error", "message": "训练已在进行中"}

    # 保存为临时文件
    temp_path = str(_BACKEND_DIR / "data" / "station_health_train.csv")
    _train_data["df"].to_csv(temp_path, index=False, encoding="utf-8-sig")

    def run_train():
        try:
            engine.train_model(temp_path, n_trials=n_trials)
        except Exception as e:
            traceback.print_exc()

    threading.Thread(target=run_train, daemon=True).start()
    return {"status": "ok", "message": f"训练已启动 (Optuna {n_trials}轮)"}


@router.get("/train_status")
def train_status():
    return engine.get_train_status()


@router.post("/reset_model")
def reset_model():
    return engine.reset_model()