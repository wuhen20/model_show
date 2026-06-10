"""
电表健康评价演示 — FastAPI 路由
"""
import os
import uuid
import threading
from pathlib import Path
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from app.demo_services import meter_health_engine as engine

router = APIRouter()

_BACKEND_DIR = Path(__file__).parent.parent.parent.parent  # backend/
_EXPERIENCE_DIR = _BACKEND_DIR / "experience_data"
_DEMO_CSV = _EXPERIENCE_DIR / "ZJ" / "meter_health" / "mock_meter_data.csv"

UPLOAD_DIR = os.path.join(_BACKEND_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/ping")
def ping():
    return {"status": "ok", "message": "meter health demo is alive"}


@router.get("/demo_csv")
def serve_demo_csv():
    """直接提供演示数据集下载"""
    if _DEMO_CSV.exists():
        return FileResponse(str(_DEMO_CSV), media_type="text/csv", filename="mock_meter_data.csv")
    raise HTTPException(status_code=404, detail="演示数据文件不存在")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传训练 CSV 文件"""
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")

    task_id = str(uuid.uuid4())
    filepath = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    content = await file.read()
    with open(filepath, 'wb') as f:
        f.write(content)

    try:
        df = pd.read_csv(filepath)
        removal_rate = None
        if 'is_removed' in df.columns:
            removal_rate = round(float(df['is_removed'].mean()) * 100, 2)

        engine.tasks[task_id] = {
            'task_id': task_id,
            'filename': file.filename,
            'filepath': filepath,
            'rows': len(df),
            'columns': len(df.columns),
            'column_names': df.columns.tolist(),
            'removal_rate': removal_rate,
            'status': 'uploaded',
            'progress': 0,
            'message': '文件上传成功',
            'result': None,
            'created_at': datetime.now().isoformat(),
            'upload_dir': UPLOAD_DIR,
        }

        return JSONResponse(content={
            'task_id': task_id,
            'filename': file.filename,
            'rows': len(df),
            'columns': len(df.columns),
            'removal_rate': removal_rate,
            'has_mfr': 'MFR' in df.columns,
            'has_is_removed': 'is_removed' in df.columns,
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无法解析 CSV 文件: {str(e)}")


@router.post("/train")
async def start_training(
    task_id: str = Form(...),
    use_grid_search: bool = Form(False),
    optimize: bool = Form(False),
    n_calls: int = Form(30),
    n_est_start: int = Form(100),
    n_est_end: int = Form(500),
    n_est_step: int = Form(100),
    max_samp_start: float = Form(0.5),
    max_samp_end: float = Form(1.0),
    max_samp_step: float = Form(0.1),
    max_feat_start: float = Form(0.5),
    max_feat_end: float = Form(1.0),
    max_feat_step: float = Form(0.1),
):
    """启动训练任务"""
    task = engine.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在，请先上传文件")

    if task['status'] == 'training':
        raise HTTPException(status_code=400, detail="训练已在进行中")

    task['status'] = 'training'
    task['progress'] = 0
    task['message'] = '正在启动训练线程...'
    task['optimize'] = optimize
    task['n_calls'] = n_calls
    task['use_grid_search'] = use_grid_search
    task['upload_dir'] = UPLOAD_DIR

    thread = threading.Thread(
        target=engine.run_training,
        args=(task_id, task['filepath'], optimize, n_calls, use_grid_search,
              n_est_start, n_est_end, n_est_step,
              max_samp_start, max_samp_end, max_samp_step,
              max_feat_start, max_feat_end, max_feat_step),
        daemon=True
    )
    thread.start()

    return JSONResponse(content={'status': 'started', 'task_id': task_id})


@router.get("/status/{task_id}")
async def get_status(task_id: str):
    """查询训练/预测进度"""
    task = engine.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return JSONResponse(content={
        'task_id': task_id,
        'status': task['status'],
        'progress': task['progress'],
        'message': task['message'],
    })


@router.get("/results/{task_id}")
async def get_results(task_id: str):
    """获取训练结果"""
    task = engine.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail=f"训练未完成，当前状态: {task['status']}")
    if not task.get('result'):
        raise HTTPException(status_code=400, detail="结果数据不存在")

    return JSONResponse(content=task['result'])


@router.get("/validation/{task_id}")
async def get_validation(task_id: str):
    """获取模型验证结果"""
    task = engine.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail=f"训练未完成，当前状态: {task['status']}")

    result = task.get('result', {})
    validation = result.get('validation', {})
    validation_charts = result.get('validation_charts', {})

    return JSONResponse(content={
        'validation': validation,
        'validation_charts': validation_charts,
    })


@router.post("/predict")
async def predict_new_data(
    file: UploadFile = File(...),
    task_id: str = Form(...),
):
    """使用已训练的模型对新数据进行预测"""
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")

    train_task = engine.tasks.get(task_id)
    if not train_task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    if train_task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="训练未完成，无法预测")

    model_path = train_task['result'].get('model_path')
    if not model_path or not os.path.exists(model_path):
        raise HTTPException(status_code=400, detail="模型文件不存在，请重新训练")

    predict_task_id = str(uuid.uuid4())
    filepath = os.path.join(UPLOAD_DIR, f"{predict_task_id}_{file.filename}")

    content = await file.read()
    with open(filepath, 'wb') as f:
        f.write(content)

    engine.tasks[predict_task_id] = {
        'task_id': predict_task_id,
        'filename': file.filename,
        'filepath': filepath,
        'status': 'predicting',
        'progress': 0,
        'message': '开始预测...',
        'result': None,
        'train_task_id': task_id,
        'created_at': datetime.now().isoformat(),
        'upload_dir': UPLOAD_DIR,
    }

    thread = threading.Thread(
        target=engine.run_prediction,
        args=(predict_task_id, filepath, model_path),
        daemon=True
    )
    thread.start()

    return JSONResponse(content={'predict_task_id': predict_task_id, 'status': 'started'})


@router.get("/predict-results/{task_id}")
async def get_predict_results(task_id: str):
    """获取预测结果"""
    task = engine.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail=f"预测未完成，当前状态: {task['status']}")
    if not task.get('result'):
        raise HTTPException(status_code=400, detail="结果数据不存在")

    return JSONResponse(content=task['result'])


@router.get("/download/{task_id}")
async def download_result(task_id: str, file_type: str = "result"):
    """下载评分结果 CSV 或模型文件"""
    task = engine.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="任务未完成")

    if file_type == "model":
        model_path = task.get('result', {}).get('model_path')
        if not model_path or not os.path.exists(model_path):
            raise HTTPException(status_code=404, detail="模型文件不存在")
        return FileResponse(model_path, filename=f"{task_id}_model.pkl",
                           media_type='application/octet-stream')

    result_path = task.get('result', {}).get('result_csv_path')
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="结果文件不存在")
    return FileResponse(result_path, filename=f"{task_id}_result.csv",
                       media_type='text/csv')


@router.get("/tasks")
async def list_tasks():
    """列出所有任务（调试用）"""
    task_list = []
    for tid, t in engine.tasks.items():
        task_list.append({
            'task_id': tid,
            'filename': t.get('filename', ''),
            'status': t['status'],
            'progress': t['progress'],
            'message': t['message'],
            'created_at': t.get('created_at', ''),
        })
    return JSONResponse(content={'tasks': task_list})