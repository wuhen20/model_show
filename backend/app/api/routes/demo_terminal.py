"""
终端异常研判演示 — FastAPI 路由
"""
from pathlib import Path
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from app.demo_services import terminal_model as tm

router = APIRouter()

_BACKEND_DIR = Path(__file__).parent.parent.parent.parent  # backend/
_EXPERIENCE_DIR = _BACKEND_DIR / "experience_data"
_DEMO_CSV = _EXPERIENCE_DIR / "ZJ" / "terminal" / "terminal_demo_100.csv"


@router.get("/ping")
def ping():
    return {"status": "ok", "message": "terminal demo is alive"}


@router.get("/model_info")
def model_info():
    return tm.get_model_info()


@router.get("/demo_csv")
def serve_demo_csv():
    """直接提供演示数据集下载"""
    if _DEMO_CSV.exists():
        return FileResponse(str(_DEMO_CSV), media_type="text/csv", filename="terminal_demo_100.csv")
    raise HTTPException(status_code=404, detail="演示数据文件不存在")


@router.post("/predict")
async def predict(file: UploadFile = File(...)):
    """接收 CSV 文件，运行预测"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    try:
        content = await file.read()
        df = None
        for enc in ["utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"]:
            try:
                df = pd.read_csv(BytesIO(content), encoding=enc)
                if len(df) > 0:
                    break
            except Exception:
                continue

        if df is None or len(df) == 0:
            raise HTTPException(status_code=400, detail="无法解析 CSV 文件或文件为空")

        result = tm.run_predictions(df)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        result = tm._to_native(result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")


@router.get("/gridsearch_status")
def gridsearch_status():
    return tm.get_tune_status()


@router.post("/reset_model")
def reset_model():
    result = tm.reset_model_to_original()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/gridsearch_tune")
async def gridsearch_tune(file: UploadFile = File(...)):
    """接收 CSV，执行超参数网格搜索微调"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    try:
        content = await file.read()
        result = tm.gridsearch_tune(content, file.filename or "unknown.csv")
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调优失败: {str(e)}")