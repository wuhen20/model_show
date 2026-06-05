"""首页统计路由。M1 阶段：基础统计 + 调用趋势。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ModelMetadata, InvocationLog
from app.registry.model_registry import SCENE_CATALOG
from app.schemas.model import SceneSummary

router = APIRouter()


@router.get("/stats", response_model=dict)
def dashboard_stats(db: Session = Depends(get_db)):
    """6 张顶部统计卡数据。"""
    total_models = db.execute(select(func.count(ModelMetadata.code))).scalar() or 0
    running_models = (
        db.execute(
            select(func.count(ModelMetadata.code)).where(ModelMetadata.status == "running")
        ).scalar()
        or 0
    )
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())
    today_calls = (
        db.execute(
            select(func.count(InvocationLog.id)).where(InvocationLog.invoked_at >= today_start)
        ).scalar()
        or 0
    )
    avg_latency = (
        db.execute(
            select(func.avg(InvocationLog.latency_ms)).where(
                InvocationLog.invoked_at >= today_start
            )
        ).scalar()
        or 0
    )
    success_count = (
        db.execute(
            select(func.count(InvocationLog.id)).where(
                InvocationLog.invoked_at >= today_start,
                InvocationLog.success == 1,
            )
        ).scalar()
        or 0
    )
    success_rate = round(success_count / today_calls * 100, 2) if today_calls > 0 else 100.0

    return {
        "code": 0,
        "data": {
            "scene_count": len(SCENE_CATALOG),
            "model_count": int(total_models),
            "running_models": int(running_models),
            "training_tasks": 0,  # M3 接入
            "mcp_services": 0,  # M5 接入
            "today_calls": int(today_calls),
            "avg_latency_ms": round(float(avg_latency or 0), 2),
            "success_rate": success_rate,
        },
    }


@router.get("/scene-summary", response_model=dict)
def scene_summary(db: Session = Depends(get_db)):
    """6 大场景的模型数 + 在线率 + 今日调用。"""
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())
    total_per_scene = dict(
        db.execute(
            select(ModelMetadata.scene, func.count(ModelMetadata.code)).group_by(
                ModelMetadata.scene
            )
        ).all()
    )
    running_per_scene = dict(
        db.execute(
            select(ModelMetadata.scene, func.count(ModelMetadata.code))
            .where(ModelMetadata.status == "running")
            .group_by(ModelMetadata.scene)
        ).all()
    )
    # 今日各场景调用量（通过 model_code 前缀场景识别）
    calls = db.execute(
        select(InvocationLog.model_code, func.count(InvocationLog.id))
        .where(InvocationLog.invoked_at >= today_start)
        .group_by(InvocationLog.model_code)
    ).all()
    scene_calls: dict[str, int] = {}
    for code, c in calls:
        scene = (code or "").split("-")[0]
        scene_calls[scene] = scene_calls.get(scene, 0) + int(c)

    return {
        "code": 0,
        "data": [
            SceneSummary(
                **s,
                total=total,
                running=running,
                today_calls=int(scene_calls.get(s["code"], 0)),
                online_rate=round(running / total * 100, 1) if total > 0 else 0.0,
            ).model_dump()
            for s, total, running in [
                (
                    s,
                    int(total_per_scene.get(s["code"], 0)),
                    int(running_per_scene.get(s["code"], 0)),
                )
                for s in SCENE_CATALOG
            ]
        ],
    }


@router.get("/invoke-trend", response_model=dict)
def invoke_trend(
    range_hours: int = Query(24, alias="range", ge=1, le=168),
    granularity_min: int = Query(5, alias="granularity", ge=1, le=60),
    db: Session = Depends(get_db),
):
    """调用趋势（按时间桶聚合）。M1 阶段简化为 Python 端聚合。"""
    end = datetime.now()
    start = end - timedelta(hours=range_hours)
    rows = db.execute(
        select(InvocationLog.invoked_at).where(InvocationLog.invoked_at >= start)
    ).all()
    bucket_sec = granularity_min * 60
    buckets: dict[int, int] = {}
    for (ts,) in rows:
        if ts is None:
            continue
        epoch = int(ts.timestamp())
        key = epoch - (epoch % bucket_sec)
        buckets[key] = buckets.get(key, 0) + 1
    series = sorted(
        [
            {"time": datetime.fromtimestamp(k).strftime("%Y-%m-%d %H:%M"), "count": v}
            for k, v in buckets.items()
        ],
        key=lambda x: x["time"],
    )
    return {"code": 0, "data": series}


@router.get("/recent", response_model=dict)
def recent_activity():
    """最近训练 / MCP / 日志。M1 阶段返回占位。"""
    return {
        "code": 0,
        "data": {
            "training": [],
            "mcp": [],
            "logs": [],
        },
    }
