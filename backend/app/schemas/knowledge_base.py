"""Pydantic models for knowledge base management API."""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


class TagCreate(BaseModel):
    level: int
    name: str
    parent_tag_id: str | None = None
    children: list[TagCreate] = []


class TagUpdate(BaseModel):
    name: str | None = None
    level: int | None = None
    parent_tag_id: str | None = None


class TagResponse(BaseModel):
    id: str
    kb_id: str
    level: int
    name: str
    parent_tag_id: str | None = None
    children: list[TagResponse] = []


# ---------------------------------------------------------------------------
# Knowledge Bases
# ---------------------------------------------------------------------------


class KBCreate(BaseModel):
    name: str
    description: str = ""
    icon: str = "brain"
    color: str = "#00d4ff"
    chunk_size: int = 500
    chunk_overlap: int = 50
    chunking_strategy: str = "basic"  # "basic" or "parent_child"
    parent_chunk_size: int = 1500
    chunk_separator: str = "\n\n"
    tags: list[TagCreate] = []


class KBUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    chunking_strategy: str | None = None
    parent_chunk_size: int | None = None
    chunk_separator: str | None = None


class KBResponse(BaseModel):
    id: str
    name: str
    workspace: str
    description: str
    icon: str
    color: str
    chunk_size: int
    chunk_overlap: int
    chunking_strategy: str
    parent_chunk_size: int
    chunk_separator: str = "\n\n"
    doc_count: int = 0
    tags: list[TagResponse] = []
    created_at: str = ""
    updated_at: str = ""


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    id: str
    kb_id: str
    file_name: str
    file_path: str
    file_size: int = 0
    mime_type: str = ""
    status: str = "pending"
    chunk_count: int = 0
    vector_count: int = 0
    tags: list[TagResponse] = []
    created_at: str = ""
    updated_at: str = ""


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------


class ChunkResponse(BaseModel):
    id: str
    document_id: str
    kb_id: str
    content: str
    chunk_index: int
    chunk_type: str = "child"
    parent_chunk_id: str | None = None
    vector_id: str | None = None
    metadata_json: str = "{}"
