import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保后端根目录在 sys.path 中，以便导入集成进来的时序功能包
# （routers / services / models / predict_api_chronos2，源自 data-analysis 系统）
BACKEND_ROOT = Path(__file__).resolve().parent.parent  # .../model_show/backend
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# 时序预测模型（Chronos-2）权重体积较大（约 900MB），未复制进本仓库。
# 默认指向 data-analysis 中已验证可用的本地模型目录；可用环境变量覆盖：
#   CHRONOS2_MODEL_ROOT  扫描模型的根目录
#   CHRONOS2_MODEL_PATH  默认使用的模型目录
_DEFAULT_TS_MODEL_ROOT = r"E:/PythonCode/Data Platform/data-analysis/backend/predict_api_chronos2/Model"
os.environ.setdefault("CHRONOS2_MODEL_ROOT", _DEFAULT_TS_MODEL_ROOT)
os.environ.setdefault("CHRONOS2_MODEL_PATH", _DEFAULT_TS_MODEL_ROOT + "/chronos-2")

from app.core.config import settings
from app.api.routes.models import router as models_router
from app.api.routes.chat import router as chat_router

# 时序样本集/预测/分析功能路由（集成自 data-analysis 后端，各自带 /api/<模块> 前缀）
from routers import upload as ts_upload
from routers import process as ts_process
from routers import download as ts_download
from routers import merge as ts_merge
from routers import predict as ts_predict
from routers import analysis as ts_analysis

os.makedirs(settings.upload_dir, exist_ok=True)

app = FastAPI(title="模型能力展示与体验工作台 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 原有路由 =====
app.include_router(models_router, prefix="/api/models", tags=["模型管理"])
app.include_router(chat_router, prefix="/api", tags=["对话服务"])

# ===== 时序功能路由（路由自带 /api/upload、/api/process 等前缀）=====
app.include_router(ts_upload.router, tags=["时序-数据上传"])
app.include_router(ts_process.router, tags=["时序-数据预处理"])
app.include_router(ts_download.router, tags=["时序-文件下载与管理"])
app.include_router(ts_merge.router, tags=["时序-样本整合"])
app.include_router(ts_predict.router, tags=["时序-数据预测"])
app.include_router(ts_analysis.router, tags=["时序-数据分析"])


@app.get("/api/health")
def health_check():
    return {"code": 0, "message": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.server_port, reload=True)
