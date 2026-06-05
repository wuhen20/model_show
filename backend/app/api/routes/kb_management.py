"""Knowledge Base Management API — CRUD for bases, tags, documents, and sync."""

from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException

from app.core.config import settings
from app.schemas.knowledge_base import (
    KBCreate, KBUpdate, KBResponse,
    TagCreate, TagUpdate, TagResponse,
    DocumentResponse, ChunkResponse,
)
from app.services import db_service

router = APIRouter()


def _kb_to_response(kb: dict) -> dict:
    """Convert a raw KB dict to the response format with tags and doc_count."""
    tags = db_service.get_tags_tree(kb["id"])
    doc_count = db_service.count_documents(kb["id"])
    return {
        "id": kb["id"],
        "name": kb["name"],
        "workspace": kb["workspace"],
        "description": kb.get("description", ""),
        "icon": kb.get("icon", "brain"),
        "color": kb.get("color", "#00d4ff"),
        "chunk_size": kb.get("chunk_size", 500),
        "chunk_overlap": kb.get("chunk_overlap", 50),
        "chunking_strategy": kb.get("chunking_strategy", "basic"),
        "parent_chunk_size": kb.get("parent_chunk_size", 1500),
        "doc_count": doc_count,
        "tags": tags,
        "created_at": kb.get("created_at", ""),
        "updated_at": kb.get("updated_at", ""),
    }


def _doc_to_response(doc: dict) -> dict:
    """Convert a raw document dict to response format."""
    tags = doc.get("tags", [])
    return {
        "id": doc["id"],
        "kb_id": doc["kb_id"],
        "file_name": doc["file_name"],
        "file_path": doc["file_path"],
        "file_size": doc.get("file_size", 0),
        "mime_type": doc.get("mime_type", ""),
        "status": doc.get("status", "pending"),
        "chunk_count": doc.get("chunk_count", 0),
        "vector_count": doc.get("vector_count", 0),
        "tags": tags,
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


# ---------------------------------------------------------------------------
# Knowledge Base CRUD
# ---------------------------------------------------------------------------


@router.post("/bases", response_model=dict)
async def create_knowledge_base(body: KBCreate):
    """Create a new knowledge base with optional tags."""
    kb = db_service.create_knowledge_base(body.model_dump())
    # Create tags if provided
    if body.tags:
        db_service.batch_create_tags(kb["id"], [t.model_dump() for t in body.tags])
    result = _kb_to_response(db_service.get_knowledge_base(kb["id"]))
    return {"code": 0, "data": result}


@router.get("/bases/{kb_id}", response_model=dict)
async def get_knowledge_base(kb_id: str):
    """Get knowledge base detail including tags."""
    kb = db_service.get_knowledge_base(kb_id)
    if not kb:
        return {"code": -1, "message": "知识库不存在"}
    return {"code": 0, "data": _kb_to_response(kb)}


@router.put("/bases/{kb_id}", response_model=dict)
async def update_knowledge_base(kb_id: str, body: KBUpdate):
    """Update knowledge base metadata."""
    kb = db_service.update_knowledge_base(kb_id, body.model_dump(exclude_none=True))
    if not kb:
        return {"code": -1, "message": "知识库不存在或无更新"}
    return {"code": 0, "data": _kb_to_response(kb)}


@router.delete("/bases/{kb_id}", response_model=dict)
async def delete_knowledge_base(kb_id: str):
    """Delete a knowledge base and all associated data."""
    ok = db_service.delete_knowledge_base(kb_id)
    if not ok:
        return {"code": -1, "message": "知识库不存在"}
    return {"code": 0, "data": {"deleted": kb_id}}


# ---------------------------------------------------------------------------
# Tags CRUD
# ---------------------------------------------------------------------------


@router.get("/bases/{kb_id}/tags", response_model=dict)
async def get_kb_tags(kb_id: str):
    """Get all tags for a knowledge base as a tree structure."""
    tags = db_service.get_tags_tree(kb_id)
    return {"code": 0, "data": tags}


@router.post("/bases/{kb_id}/tags", response_model=dict)
async def create_kb_tag(kb_id: str, body: TagCreate):
    """Add a new tag to a knowledge base."""
    tag = db_service.create_tag({
        "kb_id": kb_id,
        "level": body.level,
        "name": body.name,
        "parent_tag_id": body.parent_tag_id,
    })
    # Also create children if provided
    if body.children:
        db_service.batch_create_tags(kb_id, [
            {**c.model_dump(), "parent_tag_id": tag["id"]}
            for c in body.children
        ])
    tags = db_service.get_tags_tree(kb_id)
    return {"code": 0, "data": tags}


@router.put("/tags/{tag_id}", response_model=dict)
async def update_tag(tag_id: str, body: TagUpdate):
    """Update a tag."""
    tag = db_service.update_tag(tag_id, body.model_dump(exclude_none=True))
    if not tag:
        return {"code": -1, "message": "标签不存在"}
    return {"code": 0, "data": tag}


@router.delete("/tags/{tag_id}", response_model=dict)
async def delete_tag(tag_id: str):
    """Delete a tag and all its children."""
    ok = db_service.delete_tag(tag_id)
    if not ok:
        return {"code": -1, "message": "标签不存在"}
    return {"code": 0, "data": {"deleted": tag_id}}


# ---------------------------------------------------------------------------
# Document Upload & Management
# ---------------------------------------------------------------------------


@router.post("/bases/{kb_id}/documents/upload", response_model=dict)
async def upload_documents(
    kb_id: str,
    files: list[UploadFile] = File(...),
    tag_ids: str = Form("[]"),
    new_tags: str = Form("[]"),
    chunk_size: int | None = Form(None),
    chunk_overlap: int | None = Form(None),
):
    """Upload files to a knowledge base with mandatory tag selection.

    Args:
        files: One or more files to upload.
        tag_ids: JSON array of existing tag IDs, e.g. '["uuid1","uuid2"]'.
        new_tags: JSON array of new tag objects to create, e.g. '[{"level":2,"name":"新标签","parent_tag_id":"uuid1"}]'.
        chunk_size: Optional per-upload chunk size override.
        chunk_overlap: Optional per-upload chunk overlap override.
    """
    import json
    from app.services import storage_service

    kb = db_service.get_knowledge_base(kb_id)
    if not kb:
        return {"code": -1, "message": "知识库不存在"}

    # Parse tag IDs
    try:
        selected_tag_ids = json.loads(tag_ids)
    except json.JSONDecodeError:
        selected_tag_ids = []

    # Create new tags if provided
    try:
        new_tags_data = json.loads(new_tags)
    except json.JSONDecodeError:
        new_tags_data = []

    if new_tags_data:
        created_tags = db_service.batch_create_tags(kb_id, new_tags_data)
        for ct in created_tags:
            selected_tag_ids.append(ct["id"])

    # Validate: at least one tag must be selected
    if not selected_tag_ids:
        return {"code": -1, "message": "上传文件时必须选择至少一个标签"}

    uploaded = []
    for f in files:
        content = await f.read()
        file_path = storage_service.save_file(kb_id, f.filename, content)

        doc = db_service.create_document({
            "kb_id": kb_id,
            "file_name": f.filename,
            "file_path": file_path,
            "file_size": len(content),
            "mime_type": f.content_type or "",
            "status": "pending",
            "tag_ids": selected_tag_ids,
        })
        uploaded.append(_doc_to_response(doc))

    return {"code": 0, "data": {"uploaded": uploaded, "count": len(uploaded)}}


@router.get("/bases/{kb_id}/documents", response_model=dict)
async def list_documents(
    kb_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List documents in a knowledge base."""
    result = db_service.list_documents(kb_id, page=page, page_size=page_size)
    return {
        "code": 0,
        "data": {
            "items": [_doc_to_response(d) for d in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        },
    }


@router.get("/documents/{doc_id}", response_model=dict)
async def get_document(doc_id: str):
    """Get document detail including tags."""
    doc = db_service.get_document(doc_id)
    if not doc:
        return {"code": -1, "message": "文档不存在"}
    return {"code": 0, "data": _doc_to_response(doc)}


@router.delete("/documents/{doc_id}", response_model=dict)
async def delete_document(doc_id: str):
    """Delete a document and its chunks."""
    doc = db_service.get_document(doc_id)
    if not doc:
        return {"code": -1, "message": "文档不存在"}
    # Delete chunks first
    db_service.delete_chunks_by_document(doc_id)
    # Delete file from storage
    try:
        from app.services import storage_service
        storage_service.delete_file(doc["file_path"])
    except Exception:
        pass
    db_service.delete_document(doc_id)
    return {"code": 0, "data": {"deleted": doc_id}}


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------


@router.get("/documents/{doc_id}/chunks", response_model=dict)
async def get_document_chunks(doc_id: str):
    """List all chunks for a document."""
    chunks = db_service.list_chunks(doc_id)
    return {"code": 0, "data": chunks}


# ---------------------------------------------------------------------------
# LightRAG Sync
# ---------------------------------------------------------------------------


@router.post("/bases/{kb_id}/sync-lightrag", response_model=dict)
async def sync_to_lightrag(kb_id: str):
    """Incrementally sync completed documents to LightRAG for graph parsing."""
    if not settings.lightrag_enabled:
        return {"code": -1, "message": "LightRAG 服务未启用，无法同步"}
    from app.services import sync_service
    try:
        result = await sync_service.sync_to_lightrag(kb_id)
        return {"code": 0, "data": result}
    except Exception as e:
        return {"code": -1, "message": f"同步失败: {e}"}


@router.get("/bases/{kb_id}/sync-status", response_model=dict)
async def get_sync_status(kb_id: str):
    """Check LightRAG sync status for documents in this KB."""
    pending = db_service.get_pending_documents(kb_id)
    return {
        "code": 0,
        "data": {
            "pending_count": len(pending),
            "pending_documents": [
                {"id": d["id"], "file_name": d["file_name"]}
                for d in pending
            ],
        },
    }
