"""LightRAG HTTP client — proxy requests to LightRAG server."""

import httpx
from app.core.config import settings


def _base_url() -> str:
    return settings.lightrag_base_url.rstrip("/")


async def get_documents_paginated(
    workspace: str | None = None,
    page: int = 1,
    page_size: int = 10,
    status_filter: str | None = None,
) -> dict:
    """Fetch paginated document list from LightRAG.

    Returns raw LightRAG response with documents + status_counts.
    """
    headers = {}
    if workspace:
        headers["LIGHTRAG-WORKSPACE"] = workspace

    # LightRAG requires page_size >= 10
    safe_page_size = max(page_size, 10)
    body: dict = {
        "page": page,
        "page_size": safe_page_size,
    }
    if status_filter:
        body["status_filter"] = status_filter

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.post(
            f"{_base_url()}/documents/paginated",
            json=body,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


async def get_pipeline_status(workspace: str | None = None) -> dict:
    """Get document processing pipeline status from LightRAG."""
    headers = {}
    if workspace:
        headers["LIGHTRAG-WORKSPACE"] = workspace

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            f"{_base_url()}/documents/pipeline_status",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


async def get_status_counts(workspace: str | None = None) -> dict[str, int]:
    """Get document status counts (pending/processing/processed/failed).

    Returns the inner ``status_counts`` dict, e.g.
    ``{"pending": 5, "processing": 2, "processed": 1, "failed": 0, "all": 8}``.
    """
    headers = {}
    if workspace:
        headers["LIGHTRAG-WORKSPACE"] = workspace

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            f"{_base_url()}/documents/status_counts",
            headers=headers,
        )
        resp.raise_for_status()
        raw = resp.json()
        # LightRAG wraps the counts inside a "status_counts" key
        return raw.get("status_counts", raw)


async def get_graph(
    label: str,
    workspace: str | None = None,
    max_depth: int = 3,
    max_nodes: int = 200,
) -> dict:
    """Fetch a subgraph from LightRAG's graph endpoint."""
    headers = {}
    if workspace:
        headers["LIGHTRAG-WORKSPACE"] = workspace

    params = {
        "label": label,
        "max_depth": max_depth,
        "max_nodes": max_nodes,
    }

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            f"{_base_url()}/graphs",
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


async def get_graph_labels(workspace: str | None = None) -> list[str]:
    """Fetch all graph labels from LightRAG."""
    headers = {}
    if workspace:
        headers["LIGHTRAG-WORKSPACE"] = workspace

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            f"{_base_url()}/graph/label/list",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


async def upload_document(
    file_content: bytes,
    file_name: str,
    workspace: str | None = None,
) -> dict:
    """Upload a document to LightRAG for graph parsing.

    Calls POST /documents/upload with multipart file upload
    and optional workspace header.
    """
    headers = {}
    if workspace:
        headers["LIGHTRAG-WORKSPACE"] = workspace

    async with httpx.AsyncClient(timeout=120) as client:
        files = {"file": (file_name, file_content)}
        resp = await client.post(
            f"{_base_url()}/documents/upload",
            files=files,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()
