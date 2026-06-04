from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, knowledge, models
from app.api.routes import kb_management, folder_kb
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database
    from app.services import db_service
    db_service.init_db()
    print("[Startup] Knowledge metadata DB initialized.")

    # Startup: tag Memgraph nodes with kb_name if available
    try:
        from app.services.memgraph_service import tag_untagged_nodes
        count = tag_untagged_nodes()
        if count > 0:
            print(f"[Startup] Tagged {count} Memgraph nodes with kb_name.")
    except Exception as e:
        print(f"[Startup] Memgraph tagging skipped: {e}")

    yield


app = FastAPI(title="AI Platform API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(kb_management.router, prefix="/api/knowledge", tags=["kb-management"])
app.include_router(folder_kb.router, prefix="/api/knowledge/folder", tags=["folder-kb"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
