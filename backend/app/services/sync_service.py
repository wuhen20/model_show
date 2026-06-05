"""LightRAG incremental sync service."""

import asyncio
from typing import Any

from app.core.config import settings
from app.services import db_service, lightrag_service


async def sync_to_lightrag(kb_id: str) -> dict:
    """Sync completed documents that haven't been synced to LightRAG yet.

    Returns a dict with sync progress info.
    """
    if not settings.lightrag_enabled:
        return {
            "synced": 0,
            "failed": 0,
            "total": 0,
            "message": "LightRAG 服务未启用，无法同步",
        }

    kb = db_service.get_knowledge_base(kb_id)
    if not kb:
        raise ValueError(f"知识库 {kb_id} 不存在")

    workspace = kb["workspace"]
    pending_docs = db_service.get_pending_documents(kb_id)

    if not pending_docs:
        return {
            "synced": 0,
            "failed": 0,
            "total": 0,
            "message": "没有需要同步的文档",
        }

    synced = 0
    failed = 0
    errors = []

    from app.services import storage_service

    for doc in pending_docs:
        try:
            # Read file content from storage
            content = storage_service.get_file(doc["file_path"])
            file_name = doc["file_name"]

            # Upload to LightRAG
            result = await lightrag_service.upload_document(
                file_content=content,
                file_name=file_name,
                workspace=workspace,
            )

            # Update document record
            lightrag_doc_id = result.get("id", result.get("document_id", ""))
            db_service.update_document(doc["id"], {
                "lightrag_doc_id": lightrag_doc_id,
                "status": "synced",
            })
            synced += 1

        except Exception as e:
            failed += 1
            errors.append({"doc_id": doc["id"], "file_name": doc["file_name"], "error": str(e)})
            # Update document with error
            db_service.update_document(doc["id"], {
                "status": "failed",
                "error_message": str(e),
            })

    return {
        "synced": synced,
        "failed": failed,
        "total": len(pending_docs),
        "errors": errors,
        "message": f"成功同步 {synced} 个文档" + (f"，{failed} 个失败" if failed else ""),
    }
