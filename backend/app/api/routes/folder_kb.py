"""Folder-based Knowledge Base API — scan filesystem folders as knowledge bases."""

from fastapi import APIRouter, Query, HTTPException

from app.services import folder_kb_service
from app.schemas.folder_kb import ImportFolderKBRequest

router = APIRouter()


# ---------------------------------------------------------------------------
# Trend data — monthly file update counts across all KBs
# ---------------------------------------------------------------------------

@router.get("/trend", response_model=dict)
async def get_folder_kb_trend():
    """Monthly file update trend across all folder-based knowledge bases.

    Returns months list, per-KB series data, and summary stats.
    """
    data = folder_kb_service.scan_kb_trend_data()
    return {"code": 0, "data": data}


# ---------------------------------------------------------------------------
# Asset stats — per-KB file count, size, and extension breakdown
# ---------------------------------------------------------------------------

@router.get("/asset-stats", response_model=dict)
async def get_folder_kb_asset_stats():
    """Knowledge asset statistics across all folder-based knowledge bases.

    Returns total counts, per-KB file count/size/extension breakdown,
    and an overall extension summary.
    """
    data = folder_kb_service.scan_kb_asset_stats()
    return {"code": 0, "data": data}


# ---------------------------------------------------------------------------
# Cross-KB file list (replaces old /api/knowledge/list for folder-based KBs)
# ---------------------------------------------------------------------------
# Knowledge source distribution (5 major categories from filesystem)
# ---------------------------------------------------------------------------

@router.get("/source-distribution", response_model=dict)
async def get_folder_kb_source_distribution():
    """Knowledge source distribution grouped into 5 major categories.

    Categories: 标准规范体系, 作业指导体系, 培训考试体系, 管理制度体系, 技术文档体系
    """
    data = folder_kb_service.scan_kb_source_distribution()
    return {"code": 0, "data": data}


# ---------------------------------------------------------------------------

@router.get("/list", response_model=dict)
async def list_all_kb_files(
    tab: str = Query(default="latest"),
    keyword: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    """List knowledge items across all folder-based knowledge bases.

    Supports tab-based filtering:
      - latest:  most recently modified
      - popular: highest score (standard docs rank higher)
      - valuable: only high-value standard documents (score >= 5)
      - pending:  recently added files (modified in last 7 days)
    """
    try:
        result = folder_kb_service.scan_all_kb_files(
            tab=tab,
            keyword=keyword,
            category_id=category_id,
            page=page,
            page_size=page_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": result}


# ---------------------------------------------------------------------------
# List all folder-based knowledge bases
# ---------------------------------------------------------------------------

@router.get("/bases", response_model=dict)
async def list_folder_bases():
    """List all folder-based knowledge bases.

    Returns each KB's name, document count, tag tree, and path.
    """
    bases = folder_kb_service.scan_knowledge_bases()
    return {
        "code": 0,
        "data": {
            "bases": bases,
            "total": len(bases),
        },
    }


# ---------------------------------------------------------------------------
# Files in a folder KB
# ---------------------------------------------------------------------------

@router.get("/bases/{kb_name:path}/files", response_model=dict)
async def list_folder_kb_files(
    kb_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    keyword: str | None = Query(default=None),
):
    """List files in a folder-based knowledge base with pagination."""
    try:
        result = folder_kb_service.scan_kb_files(kb_name, page, page_size, keyword)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": result}


# ---------------------------------------------------------------------------
# Tags for a folder KB
# ---------------------------------------------------------------------------

@router.get("/bases/{kb_name:path}/tags", response_model=dict)
async def list_folder_kb_tags(kb_name: str):
    """Get the tag tree for a folder-based knowledge base."""
    try:
        tags = folder_kb_service.scan_kb_tags(kb_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": tags}


# ---------------------------------------------------------------------------
# Synthetic graph for a folder KB
# ---------------------------------------------------------------------------

@router.get("/bases/{kb_name:path}/graph", response_model=dict)
async def get_folder_kb_graph(kb_name: str):
    """Build a synthetic knowledge graph from the folder + tag structure."""
    try:
        graph = folder_kb_service.build_folder_graph(kb_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": graph}


# ---------------------------------------------------------------------------
# Import a folder KB into the DB-backed system
# ---------------------------------------------------------------------------

@router.post("/bases/{kb_name:path}/import", response_model=dict)
async def import_folder_kb(kb_name: str, body: ImportFolderKBRequest):
    """Import a folder-based knowledge base into the DB system.

    Creates a DB knowledge_base record with tags mirroring the folder
    structure, and document records for all files. After import the
    user can sync to LightRAG via the standard flow.
    """
    from app.services import db_service, storage_service

    try:
        folder_kb_service._validate_kb_name(kb_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Verify the folder KB exists and has files
    files_data = folder_kb_service.scan_kb_files(kb_name, page=1, page_size=9999)
    if files_data["total"] == 0:
        return {"code": -1, "message": "该文件夹知识库中没有可导入的文件"}

    tags_tree = folder_kb_service.scan_kb_tags(kb_name)

    # 1. Create the KB in DB
    kb = db_service.create_knowledge_base({
        "name": body.kb_name or kb_name,
        "description": body.description,
        "icon": body.icon,
        "color": body.color,
        "chunk_size": body.chunk_size,
        "chunk_overlap": body.chunk_overlap,
    })

    # 2. Create tags mirroring the folder structure
    def _folder_tags_to_create(tree: list[dict], parent_tag_id: str | None = None) -> list[dict]:
        """Convert folder tag tree to TagCreate-compatible dicts."""
        result = []
        for node in tree:
            tag_data = {
                "name": node["name"],
                "level": node["level"],
                "parent_tag_id": parent_tag_id,
            }
            if node.get("children"):
                tag_data["children"] = _folder_tags_to_create(node["children"])
            result.append(tag_data)
        return result

    tag_create_list = _folder_tags_to_create(tags_tree)
    if tag_create_list:
        db_service.batch_create_tags(kb["id"], tag_create_list)

    # 3. Create document records for each file
    # Build a mapping: relative_dir → [tag_names] to find tag IDs
    all_tags = db_service.list_tags(kb["id"])
    tag_name_to_id: dict[str, str] = {}
    for t in all_tags:
        tag_name_to_id[t["name"]] = t["id"]

    imported_docs = 0
    for file_item in files_data["items"]:
        # Read the file content
        content = folder_kb_service.read_folder_file(kb_name, file_item["relative_path"])
        if content is None:
            continue

        # Save to upload storage
        file_path = storage_service.save_file(kb["id"], file_item["file_name"], content)

        # Resolve tag IDs from tag names
        file_tag_ids = []
        for tag_name in file_item["tags"]:
            if tag_name in tag_name_to_id:
                file_tag_ids.append(tag_name_to_id[tag_name])

        db_service.create_document({
            "kb_id": kb["id"],
            "file_name": file_item["file_name"],
            "file_path": file_path,
            "file_size": file_item["file_size"],
            "mime_type": "",
            "status": "pending",
            "tag_ids": file_tag_ids,
        })
        imported_docs += 1

    return {
        "code": 0,
        "data": {
            "kb_id": kb["id"],
            "imported_docs": imported_docs,
            "imported_tags": len(all_tags),
        },
    }
