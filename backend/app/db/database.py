"""SQLite 数据库引擎与会话管理。

MVP 阶段采用 SQLAlchemy 2.0 同步 API + WAL 模式，单进程读写足够。
后续如需异步可平滑迁移至 aiosqlite。
"""
from __future__ import annotations

import os
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.db.models import Base


def _resolve_db_path() -> Path:
    data_dir = Path(getattr(settings, "data_dir", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "model_show.db"


DB_PATH = _resolve_db_path()
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine: Engine = create_engine(
    DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _):
    """启用 WAL 提升并发读性能，并打开外键约束。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    """建表（幂等）。"""
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """事务上下文管理器，自动 commit / rollback / close。"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI 依赖注入：每请求一个 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
