import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes.models import router as models_router
from app.api.routes.chat import router as chat_router
from app.api.routes.knowledge import router as knowledge_router

os.makedirs(settings.upload_dir, exist_ok=True)

app = FastAPI(title="模型能力展示与体验工作台 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(models_router, prefix="/api/models", tags=["模型管理"])
app.include_router(chat_router, prefix="/api", tags=["对话服务"])
app.include_router(knowledge_router, prefix="/api/knowledge", tags=["知识管理"])

@app.get("/api/health")
def health_check():
    return {"code": 0, "message": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.server_port, reload=True)