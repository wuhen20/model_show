import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.models import router as models_router
from app.api.routes.chat import router as chat_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.predict import router as predict_router
from app.api.routes.datasets import router as datasets_router
from app.db.database import init_db
from app.registry.model_registry import sync_registry


os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.data_dir, exist_ok=True)
os.makedirs(settings.models_pool_dir, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动钩子：建表 + 同步模型注册表
    try:
        init_db()
        synced = sync_registry()
        print(f"[startup] SQLite 初始化完成，同步模型注册表 {synced} 条")
    except Exception as e:
        print(f"[startup] 初始化失败: {e}")
    yield


app = FastAPI(
    title="模型能力展示与体验工作台 API",
    version="2.0.0",
    lifespan=lifespan,
)

_origins = [o.strip() for o in settings.cors_origin.split(",") if o.strip()]
_use_credentials = not (len(_origins) == 1 and _origins[0] == "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=_use_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# M1 路由
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["首页"])
app.include_router(models_router, prefix="/api/models", tags=["小模型管理"])
app.include_router(predict_router, prefix="/api/predict", tags=["统一推理"])
app.include_router(datasets_router, prefix="/api/datasets", tags=["训练数据集"])
# 既有：LLM 解读对话
app.include_router(chat_router, prefix="/api", tags=["对话服务"])


@app.get("/api/health")
def health_check():
    return {"code": 0, "message": "ok"}


@app.get("/api/llm-models")
def list_llm_models():
    """对话用 LLM 列表（与小模型 /api/models 区分）。"""
    data = [
        {
            "id": m["id"],
            "name": m["name"],
            "type": m["type"],
            "description": m["description"],
        }
        for m in settings.models
    ]
    return {"code": 0, "data": data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.server_port, reload=True)
