"""
拆除旧表作业识别 — FastAPI 路由
YOLO + BoT-SORT 跟踪 + 状态机
"""
import os
import uuid
import threading
import traceback
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.demo_services import meter_removal_engine as engine

router = APIRouter()

_BACKEND_DIR = Path(__file__).parent.parent.parent.parent
_EXPERIENCE_DIR = _BACKEND_DIR / "experience_data" / "XC" / "meter_remove"
_UPLOAD_DIR = _BACKEND_DIR / "data" / "uploads"

# 异步任务存储
_tasks: dict[str, dict] = {}


@router.get("/ping")
def ping():
    return {"status": "ok", "message": "meter removal demo is alive"}


@router.get("/model_info")
def model_info():
    model_exists = (_EXPERIENCE_DIR.parent.parent.parent / "models_pool" / "XC" / "meter_remove" / "best.pt").exists()
    return {
        "model_type": "YOLOv8 + BoT-SORT + State Machine",
        "model_path": "models_pool/XC/meter_remove/best.pt",
        "model_available": model_exists,
        "classes": [
            {"id": 0, "name": "meter", "cn": "电表"},
            {"id": 1, "name": "cover", "cn": "端子盖"},
            {"id": 2, "name": "terminal", "cn": "端子"},
            {"id": 3, "name": "glove", "cn": "手套"},
            {"id": 4, "name": "screwdriver", "cn": "螺丝刀"},
        ],
        "config": {
            "conf_thresh": engine.CONF_THRESH,
            "need_sec": engine.NEED_SEC,
            "buffer_frames": engine.BUFFER_FRAMES,
            "glove_verify_frames": engine.GLOVE_VERIFY_FRAMES,
        },
        "description": "基于YOLO目标检测+BoT-SORT跟踪，对电表拆除过程进行自动化识别与状态跟踪。检测电表、端子、螺丝刀、端子盖、手套五类目标，通过多阶段状态机判断端子槽拆除进度和电表最终拆除状态。",
    }


@router.get("/videos")
def list_videos():
    """列出内置测试视频"""
    videos = []
    if _EXPERIENCE_DIR.exists():
        for f in sorted(_EXPERIENCE_DIR.iterdir()):
            if f.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv"):
                videos.append(f.name)
    return {"videos": videos, "directory": str(_EXPERIENCE_DIR)}


@router.get("/video/{filename}")
def serve_video(filename: str):
    """流式返回内置测试视频"""
    filepath = _EXPERIENCE_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"视频文件不存在: {filename}")
    return FileResponse(str(filepath), media_type="video/mp4")


@router.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """上传视频并启动异步分析任务"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件")

    task_id = str(uuid.uuid4())[:8]
    os.makedirs(str(_UPLOAD_DIR), exist_ok=True)
    video_path = str(_UPLOAD_DIR / f"{task_id}_input.mp4")
    with open(video_path, "wb") as f:
        f.write(await file.read())

    output_dir = str(_UPLOAD_DIR / task_id)
    os.makedirs(output_dir, exist_ok=True)

    _tasks[task_id] = {"status": "running", "progress": 0, "current_frame": 0,
                       "total_frames": 0, "current_state": "starting", "result": None, "error": None}

    def run_analysis():
        def progress_cb(current, total, state):
            _tasks[task_id]["current_frame"] = current
            _tasks[task_id]["total_frames"] = total
            _tasks[task_id]["current_state"] = state
            if total > 0:
                _tasks[task_id]["progress"] = round(current / total * 100, 1)

        try:
            result = engine.analyze_video(video_path, output_dir, progress_callback=progress_cb)
            _tasks[task_id]["result"] = result
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["progress"] = 100
        except Exception as e:
            traceback.print_exc()
            _tasks[task_id]["status"] = "error"
            _tasks[task_id]["error"] = str(e)

    threading.Thread(target=run_analysis, daemon=True).start()
    return {"status": "ok", "task_id": task_id, "message": "分析任务已启动"}


@router.post("/analyze-builtin")
async def analyze_builtin(filename: str = ""):
    """选择内置视频进行分析"""
    filepath = _EXPERIENCE_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"内置视频不存在: {filename}")

    task_id = str(uuid.uuid4())[:8]
    output_dir = str(_UPLOAD_DIR / task_id)
    os.makedirs(output_dir, exist_ok=True)

    _tasks[task_id] = {"status": "running", "progress": 0, "current_frame": 0,
                       "total_frames": 0, "current_state": "starting", "result": None, "error": None}

    def run_analysis():
        def progress_cb(current, total, state):
            _tasks[task_id]["current_frame"] = current
            _tasks[task_id]["total_frames"] = total
            _tasks[task_id]["current_state"] = state
            if total > 0:
                _tasks[task_id]["progress"] = round(current / total * 100, 1)

        try:
            result = engine.analyze_video(str(filepath), output_dir, progress_callback=progress_cb)
            _tasks[task_id]["result"] = result
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["progress"] = 100
        except Exception as e:
            traceback.print_exc()
            _tasks[task_id]["status"] = "error"
            _tasks[task_id]["error"] = str(e)

    threading.Thread(target=run_analysis, daemon=True).start()
    return {"status": "ok", "task_id": task_id, "message": "分析任务已启动"}


@router.get("/status/{task_id}")
def get_status(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    t = _tasks[task_id]
    return {
        "task_id": task_id,
        "status": t["status"],
        "progress": t["progress"],
        "current_frame": t["current_frame"],
        "total_frames": t["total_frames"],
        "current_state": t["current_state"],
        "error": t["error"],
    }


@router.get("/results/{task_id}")
def get_results(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    t = _tasks[task_id]
    if t["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"任务尚未完成 (当前状态: {t['status']})")
    result = t["result"]
    return {
        "status": "ok",
        "task_id": task_id,
        "annotated_video_url": f"/api/demo/meter-removal/annotated-video/{task_id}",
        "report": result["report"],
        "key_frames": result["key_frames"],
        "total_frames": result["total_frames"],
        "fps": result["fps"],
        "duration_seconds": result["duration_seconds"],
    }


@router.get("/annotated-video/{task_id}")
def serve_annotated_video(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    t = _tasks[task_id]
    if t["status"] != "completed" or not t["result"]:
        raise HTTPException(status_code=400, detail="标注视频尚未生成")
    video_path = t["result"]["annotated_video_path"]
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="标注视频文件不存在")
    return FileResponse(video_path, media_type="video/mp4")
