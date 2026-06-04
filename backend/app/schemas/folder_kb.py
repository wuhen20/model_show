"""Pydantic schemas for folder-based knowledge base endpoints."""

from pydantic import BaseModel


class FolderTagResponse(BaseModel):
    name: str
    level: int
    children: list["FolderTagResponse"] = []


class FolderDocumentResponse(BaseModel):
    id: str
    file_name: str
    relative_path: str
    file_size: int
    extension: str
    tags: list[str]
    modified_time: str


class FolderKBResponse(BaseModel):
    name: str
    doc_count: int
    top_tags: list[str] = []


class FolderKBListResponse(BaseModel):
    bases: list[FolderKBResponse]
    total: int


class ImportFolderKBRequest(BaseModel):
    """Request body for importing a folder KB into the DB-backed system."""
    kb_name: str
    description: str = ""
    icon: str = "folder"
    color: str = "#ffaa00"
    chunk_size: int = 500
    chunk_overlap: int = 50
