"""SQLite ORM 模型定义。

M1 阶段实现核心三表：model_metadata / model_version / invocation_log。
M2 阶段追加 dataset / dataset_version。
后续里程碑按需追加 training_task / mcp_service 等。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Integer,
    String,
    Text,
    Float,
    ForeignKey,
    DateTime,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ModelMetadata(Base):
    """小模型元数据。

    启动时从 registry/model_registry.py 同步至此表，作为运行时单一事实源。
    """

    __tablename__ = "model_metadata"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    scene: Mapped[str] = mapped_column(String(8), nullable=False)
    io_type: Mapped[str] = mapped_column(String(16), nullable=False)
    backend_type: Mapped[str] = mapped_column(String(16), default="local")
    description: Mapped[Optional[str]] = mapped_column(Text)
    input_spec: Mapped[Optional[str]] = mapped_column(Text)  # JSON
    output_spec: Mapped[Optional[str]] = mapped_column(Text)  # JSON
    sub_scenes: Mapped[Optional[str]] = mapped_column(Text)  # JSON 数组
    current_version: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="planned")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ModelVersion(Base):
    __tablename__ = "model_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_code: Mapped[str] = mapped_column(String(16), ForeignKey("model_metadata.code"))
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_path: Mapped[Optional[str]] = mapped_column(Text)
    metrics: Mapped[Optional[str]] = mapped_column(Text)  # JSON
    training_task_id: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class InvocationLog(Base):
    __tablename__ = "invocation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_code: Mapped[str] = mapped_column(String(16), nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(String(64))
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[int] = mapped_column(Integer, default=1)
    error_msg: Mapped[Optional[str]] = mapped_column(Text)
    invoked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_log_invoked_at", "invoked_at"),
        Index("idx_log_model_code", "model_code"),
    )


class Dataset(Base):
    """训练数据集。

    一个场景 + 一个模型编码 = 一个数据集目录。
    文件存储在 backend/data/datasets/{scene}/{model_code}/。
    """

    __tablename__ = "dataset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    scene: Mapped[str] = mapped_column(String(8), nullable=False)
    model_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    format: Mapped[str] = mapped_column(String(16), nullable=False)          # csv/txt/jpg/png/mp4/zip
    dataset_type: Mapped[str] = mapped_column(String(16), default="general") # general / yolo_detection
    description: Mapped[Optional[str]] = mapped_column(Text)
    schema_json: Mapped[Optional[str]] = mapped_column(Text)                 # CSV 列定义 JSON
    # YOLO 专用字段
    classes_json: Mapped[Optional[str]] = mapped_column(Text)                # YOLO 类别名列表 JSON
    image_count: Mapped[int] = mapped_column(Integer, default=0)             # 图片数
    label_count: Mapped[int] = mapped_column(Integer, default=0)             # 标注框总数
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    current_version: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class DatasetVersion(Base):
    """数据集版本历史。"""

    __tablename__ = "dataset_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("dataset.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)         # v1, v2, ...
    file_path: Mapped[str] = mapped_column(Text, nullable=False)             # 相对路径
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
