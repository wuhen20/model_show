import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 配置日志：输出到终端，便于排查接口异常
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")

# ---------------------------------------------------------------------------
# 确保后端根目录在 sys.path 中，以便导入集成进来的时序功能包
# （routers / services / models / predict_api_chronos2，源自 data-analysis 系统）
# ---------------------------------------------------------------------------
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

# ===== 原系统（对话 / LLM 模型列表）=====
from app.api.routes.models import router as models_router
from app.api.routes.chat import router as chat_router

# ===== 小模型平台（dev-algomodel，统一收敛到 /api/sm 命名空间）=====
from app.api.routes.dashboard import router as sm_dashboard_router
from app.api.routes.sm_models import router as sm_models_router
from app.api.routes.predict import router as sm_predict_router

# ===== 多模态目标检测（multimodal-llm）=====
from app.api.routes.detection import router as detection_router

# ===== 样本中心（sxy-sample-center）=====
from app.api.routes.sample import router as sample_router
from app.api.routes.clean import router as clean_router
from app.api.routes.original_sample import router as original_sample_router
from app.api.routes.upload_chunk import router as upload_chunk_router

# ===== 知识管理（liuqi-knowledgebase）=====
from app.api.routes import knowledge as kb_knowledge
from app.api.routes import kb_management as kb_mgmt
from app.api.routes import folder_kb as kb_folder

# ===== 时序样本集 / 预测 / 分析（time-series-large-model，路由自带 /api/<模块> 前缀）=====
from routers import upload as ts_upload
from routers import process as ts_process
from routers import download as ts_download
from routers import merge as ts_merge
from routers import predict as ts_predict
from routers import analysis as ts_analysis



# ---------------------------------------------------------------------------
# 运行期目录
# ---------------------------------------------------------------------------
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.data_dir, exist_ok=True)
os.makedirs(settings.models_pool_dir, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """统一启动钩子：小模型平台建表 + 知识管理元数据库 + Memgraph 标签。"""
    # 小模型平台：建表 + 同步模型注册表
    try:
        from app.db.database import init_db as sm_init_db
        from app.registry.model_registry import sync_registry as sm_sync_registry
        sm_init_db()
        n = sm_sync_registry()
        print(f"[startup] 小模型平台 SQLite 初始化完成，同步模型注册表 {n} 条")
    except Exception as e:
        print(f"[startup] 小模型平台初始化失败: {e}")

    # 知识管理：初始化元数据库
    try:
        from app.services import db_service
        db_service.init_db()
        print("[startup] 知识管理元数据库初始化完成")
    except Exception as e:
        print(f"[startup] 知识管理初始化失败: {e}")

    # 知识管理：Memgraph 节点 kb_name 打标签（可选组件）
    if getattr(settings, "memgraph_enabled", False):
        try:
            from app.services.memgraph_service import tag_untagged_nodes
            c = tag_untagged_nodes()
            if c:
                print(f"[startup] Memgraph 已为 {c} 个节点补充 kb_name 标签")
        except Exception as e:
            print(f"[startup] Memgraph 标签处理跳过: {e}")
    else:
        print("[startup] Memgraph 未启用，跳过节点标签处理")

    # 数据采集：初始化定时调度器，加载所有 execute_type='02' 的定时任务
    try:
        from app.services.scheduler_service import init_scheduler
        init_scheduler()
    except Exception as e:
        print(f"[startup] 数据采集定时调度器初始化失败: {e}")

    yield

    # 关闭定时调度器
    try:
        from app.services.scheduler_service import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass


app = FastAPI(
    title="模型能力展示与体验工作台 · 融合平台 API",
    version="3.0.0",
    lifespan=lifespan,
)

# Starlette >= 0.38 的 MultiPartParser 默认 max_part_size=1MB，
# 超过此大小的文件上传会触发 400 Bad Request。
# 将 Request._get_form 和 MultiPartParser 的限制提升至 2GB，支持大 ZIP 批量导入。
from starlette.requests import Request, MultiPartParser
_MAX_UPLOAD = 2 * 1024 * 1024 * 1024  # 2GB
# 修改 Request._get_form 的 max_part_size 默认值
_get_form_defaults = Request._get_form.__kwdefaults__
if _get_form_defaults and "max_part_size" in _get_form_defaults:
    _get_form_defaults["max_part_size"] = _MAX_UPLOAD
# 同时修改 MultiPartParser.__init__ 的默认值
_mp_defaults = MultiPartParser.__init__.__kwdefaults__
if _mp_defaults and "max_part_size" in _mp_defaults:
    _mp_defaults["max_part_size"] = _MAX_UPLOAD

# 多个允许的源用逗号分隔；保持 "*" 时自动禁用 credentials（避免浏览器拒绝）。
_origins = [o.strip() for o in settings.cors_origin.split(",") if o.strip()]
_use_credentials = not (len(_origins) == 1 and _origins[0] == "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=_use_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 原系统 =====
app.include_router(models_router, prefix="/api/models", tags=["模型管理(LLM)"])
app.include_router(chat_router, prefix="/api", tags=["对话服务"])

# ===== 小模型平台 =====
app.include_router(sm_dashboard_router, prefix="/api/sm/dashboard", tags=["小模型-首页"])
app.include_router(sm_models_router, prefix="/api/sm/models", tags=["小模型-管理"])
app.include_router(sm_predict_router, prefix="/api/sm/predict", tags=["小模型-统一推理"])

# ===== 多模态目标检测 =====
app.include_router(detection_router, prefix="/api/detection", tags=["多模态目标检测"])

# ===== 样本中心 =====
app.include_router(sample_router, prefix="/api/sample", tags=["样本管理"])
app.include_router(clean_router, prefix="/api/clean", tags=["样本数据清理"])
app.include_router(original_sample_router, prefix="/api/original-sample", tags=["原始样本管理"])
app.include_router(upload_chunk_router, prefix="/api/upload-chunk", tags=["样本批量导入(分片上传)"])

# ===== 知识管理 =====
app.include_router(kb_knowledge.router, prefix="/api/knowledge", tags=["知识管理"])
app.include_router(kb_mgmt.router, prefix="/api/knowledge", tags=["知识库管理"])
app.include_router(kb_folder.router, prefix="/api/knowledge/folder", tags=["文件夹知识库"])

# ===== 时序功能（路由自带 /api/upload、/api/process 等前缀）=====

app.include_router(ts_upload.router, tags=["时序-数据上传"])
app.include_router(ts_process.router, tags=["时序-数据预处理"])
app.include_router(ts_download.router, tags=["时序-文件下载与管理"])
app.include_router(ts_merge.router, tags=["时序-样本整合"])
app.include_router(ts_predict.router, tags=["时序-数据预测"])
app.include_router(ts_analysis.router, tags=["时序-数据分析"])



@app.get("/api/health")
def health_check():
    return {"code": 0, "message": "ok"}


@app.get("/api/llm-models")
def list_llm_models():
    """对话用 LLM 列表（与小模型 /api/sm/models 区分）。"""
    data = [
        {"id": m["id"], "name": m["name"], "type": m["type"], "description": m["description"]}
        for m in settings.models
    ]
    return {"code": 0, "data": data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.server_port, reload=False)
