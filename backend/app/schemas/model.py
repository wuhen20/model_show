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


# ── 数据集相关 Schema ──────────────────────────────────────────────────────────────

class DatasetBrief(BaseModel):
    id: int
    name: str
    scene: str
    model_code: Optional[str] = None
    format: str
    dataset_type: str = "general"
    description: Optional[str] = None
    classes: Optional[list[str]] = None
    image_count: int = 0
    label_count: int = 0
    sample_count: int = 0
    file_count: int = 0
    size_bytes: int = 0
    current_version: Optional[str] = None
    version_count: int = 0
    created_at: Optional[datetime] = None


class DatasetVersionBrief(BaseModel):
    id: int
    version: str
    file_count: int
    sample_count: int
    size_bytes: int
    created_at: Optional[datetime] = None


class DatasetDetail(DatasetBrief):
    schema_json: Optional[str] = None
    updated_at: Optional[datetime] = None
    versions: list[DatasetVersionBrief] = []


class YoloObject(BaseModel):
    class_id: int
    class_name: str
    cx: float                                          # 归一化中心 x
    cy: float                                          # 归一化中心 y
    w: float                                           # 归一化宽度
    h: float                                           # 归一化高度


class YoloPreviewItem(BaseModel):
    image_url: str
    image_file: str
    objects: list[YoloObject] = []
