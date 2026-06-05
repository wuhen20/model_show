"""小模型管理路由：列表 / 详情 / 场景目录。"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ModelMetadata
from app.registry.model_registry import SCENE_CATALOG, MODEL_REGISTRY
from app.schemas.model import ModelBrief, ModelDetail, SceneInfo

router = APIRouter()


def _row_to_brief(row: ModelMetadata) -> ModelBrief:
    return ModelBrief(
        code=row.code,
        name=row.name,
        scene=row.scene,
        io_type=row.io_type,
        backend_type=row.backend_type,
        status=row.status,
        current_version=row.current_version,
    )


def _row_to_detail(row: ModelMetadata) -> ModelDetail:
    return ModelDetail(
        code=row.code,
        name=row.name,
        scene=row.scene,
        io_type=row.io_type,
        backend_type=row.backend_type,
        status=row.status,
        current_version=row.current_version,
        description=row.description,
        input_spec=json.loads(row.input_spec) if row.input_spec else [],
        output_spec=json.loads(row.output_spec) if row.output_spec else [],
        sub_scenes=json.loads(row.sub_scenes) if row.sub_scenes else None,
        updated_at=row.updated_at,
    )


@router.get("/scenes", response_model=dict)
def list_scenes(db: Session = Depends(get_db)):
    """6 大场景及每个场景下的模型数（带在线数统计）。"""
    counts = dict(
        db.execute(
            select(ModelMetadata.scene, func.count(ModelMetadata.code)).group_by(
                ModelMetadata.scene
            )
        ).all()
    )
    running_counts = dict(
        db.execute(
            select(ModelMetadata.scene, func.count(ModelMetadata.code))
            .where(ModelMetadata.status == "running")
            .group_by(ModelMetadata.scene)
        ).all()
    )
    scenes = [
        {
            **s,
            "count": int(counts.get(s["code"], 0)),
            "running": int(running_counts.get(s["code"], 0)),
        }
        for s in SCENE_CATALOG
    ]
    return {"code": 0, "data": scenes}


@router.get("", response_model=dict)
def list_models(
    scene: Optional[str] = Query(None, description="按场景过滤：ZJ/XC/FH/TQ/YD/ZC"),
    status: Optional[str] = Query(None, description="按状态过滤：running/planned/offline/error"),
    db: Session = Depends(get_db),
):
    stmt = select(ModelMetadata)
    if scene:
        stmt = stmt.where(ModelMetadata.scene == scene)
    if status:
        stmt = stmt.where(ModelMetadata.status == status)
    rows = db.execute(stmt.order_by(ModelMetadata.code)).scalars().all()
    return {
        "code": 0,
        "total": len(rows),
        "data": [_row_to_brief(r).model_dump() for r in rows],
    }


@router.get("/{code}", response_model=dict)
def get_model(code: str, db: Session = Depends(get_db)):
    row = db.get(ModelMetadata, code)
    if row is None:
        raise HTTPException(status_code=404, detail=f"model {code} not found")
    return {"code": 0, "data": _row_to_detail(row).model_dump()}


@router.post("/{code}/online", response_model=dict)
def online_model(code: str, db: Session = Depends(get_db)):
    row = db.get(ModelMetadata, code)
    if row is None:
        raise HTTPException(status_code=404, detail=f"model {code} not found")
    row.status = "running"
    db.commit()
    return {"code": 0, "data": {"code": code, "status": "running"}}


@router.post("/{code}/offline", response_model=dict)
def offline_model(code: str, db: Session = Depends(get_db)):
    row = db.get(ModelMetadata, code)
    if row is None:
        raise HTTPException(status_code=404, detail=f"model {code} not found")
    row.status = "offline"
    db.commit()
    return {"code": 0, "data": {"code": code, "status": "offline"}}
