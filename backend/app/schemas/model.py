"""模型相关 Pydantic Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


class SceneInfo(BaseModel):
    code: str
    name: str
    description: str
    icon: str
    count: int


class SceneSummary(BaseModel):
    """场景概览（含统计字段）。"""
    code: str
    name: str
    description: str
    icon: str
    total: int = 0
    running: int = 0
    today_calls: int = 0
    online_rate: float = 0.0


class ModelBrief(BaseModel):
    code: str
    name: str
    scene: str
    io_type: str
    backend_type: str
    status: str
    current_version: Optional[str] = None


class ModelDetail(ModelBrief):
    description: Optional[str] = None
    input_spec: list[dict] = Field(default_factory=list)
    output_spec: list[dict] = Field(default_factory=list)
    sub_scenes: Optional[list[str]] = None
    updated_at: Optional[datetime] = None


class PredictRequest(BaseModel):
    input: Any = None
    sub_scene: Optional[str] = None


class PredictResponse(BaseModel):
    code: str
    output: dict
    latency_ms: int
    trace_id: Optional[str] = None
    mock: bool = False
