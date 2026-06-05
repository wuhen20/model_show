"""SQLite metadata storage for knowledge bases, tags, documents, and chunks."""

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

_DB_PATH: str = ""


def _get_db_path() -> str:
    global _DB_PATH
    if not _DB_PATH:
        _DB_PATH = os.path.abspath(settings.metadata_db_path)
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    return _DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    workspace       TEXT NOT NULL UNIQUE,
    description     TEXT DEFAULT '',
    icon            TEXT DEFAULT 'brain',
    color           TEXT DEFAULT '#00d4ff',
    chunk_size      INTEGER DEFAULT 500,
    chunk_overlap   INTEGER DEFAULT 50,
    chunking_strategy TEXT DEFAULT 'basic',
    parent_chunk_size INTEGER DEFAULT 1500,
    chunk_separator TEXT DEFAULT '\\n\\n',
    created_at      TEXT,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    id              TEXT PRIMARY KEY,
    kb_id           TEXT NOT NULL,
    level           INTEGER NOT NULL,
    name            TEXT NOT NULL,
    parent_tag_id   TEXT,
    created_at      TEXT,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,
    kb_id           TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_size       INTEGER DEFAULT 0,
    mime_type       TEXT DEFAULT '',
    status          TEXT DEFAULT 'pending',
    chunk_count     INTEGER DEFAULT 0,
    vector_count    INTEGER DEFAULT 0,
    lightrag_doc_id TEXT,
    error_message   TEXT,
    created_at      TEXT,
    updated_at      TEXT,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_tags (
    document_id     TEXT NOT NULL,
    tag_id          TEXT NOT NULL,
    PRIMARY KEY (document_id, tag_id),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chunks (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL,
    kb_id           TEXT NOT NULL,
    content         TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,
    chunk_type      TEXT DEFAULT 'child',
    parent_chunk_id TEXT,
    vector_id       TEXT,
    metadata_json   TEXT DEFAULT '{}',
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tags_kb ON tags(kb_id);
CREATE INDEX IF NOT EXISTS idx_documents_kb ON documents(kb_id);
CREATE INDEX IF NOT EXISTS idx_document_tags_doc ON document_tags(document_id);
CREATE INDEX IF NOT EXISTS idx_document_tags_tag ON document_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_kb ON chunks(kb_id);
CREATE INDEX IF NOT EXISTS idx_chunks_parent ON chunks(parent_chunk_id);
"""


def init_db():
    """Create tables and seed existing knowledge bases from settings."""
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()

        # Migrate: add chunk_separator column if missing (SQLite ALTER TABLE)
        try:
            conn.execute("ALTER TABLE knowledge_bases ADD COLUMN chunk_separator TEXT DEFAULT '\\n\\n'")
            conn.commit()
        except Exception:
            pass  # Column already exists

        # Seed existing knowledge bases from settings if table is empty
        count = conn.execute("SELECT COUNT(*) FROM knowledge_bases").fetchone()[0]
        if count == 0:
            now = _now()
            for kb in settings.knowledge_bases:
                conn.execute(
                    """INSERT OR IGNORE INTO knowledge_bases
                       (id, name, workspace, description, icon, color, chunk_size, chunk_overlap,
                        chunking_strategy, parent_chunk_size, chunk_separator, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        kb.get("id", _new_id()),
                        kb.get("name", ""),
                        kb.get("workspace", ""),
                        kb.get("description", ""),
                        kb.get("icon", "brain"),
                        kb.get("color", "#00d4ff"),
                        settings.default_chunk_size,
                        settings.default_chunk_overlap,
                        "basic",
                        settings.default_parent_chunk_size,
                        "\\n\\n",
                        now,
                        now,
                    ),
                )
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Knowledge Base CRUD
# ---------------------------------------------------------------------------


def list_knowledge_bases() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM knowledge_bases ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_knowledge_base(kb_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_knowledge_base_by_workspace(workspace: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM knowledge_bases WHERE workspace = ?", (workspace,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_knowledge_base(data: dict) -> dict:
    kb_id = data.get("id") or _new_id()
    now = _now()
    # Generate workspace slug from name
    workspace = data.get("workspace") or _slugify(data.get("name", ""))

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO knowledge_bases
               (id, name, workspace, description, icon, color, chunk_size, chunk_overlap,
                chunking_strategy, parent_chunk_size, chunk_separator, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                kb_id,
                data["name"],
                workspace,
                data.get("description", ""),
                data.get("icon", "brain"),
                data.get("color", "#00d4ff"),
                data.get("chunk_size", settings.default_chunk_size),
                data.get("chunk_overlap", settings.default_chunk_overlap),
                data.get("chunking_strategy", "basic"),
                data.get("parent_chunk_size", settings.default_parent_chunk_size),
                data.get("chunk_separator", "\\n\\n"),
                now,
                now,
            ),
        )
        conn.commit()
        kb = get_knowledge_base(kb_id)
        return kb
    finally:
        conn.close()


def update_knowledge_base(kb_id: str, data: dict) -> dict | None:
    allowed = {
        "name", "description", "icon", "color",
        "chunk_size", "chunk_overlap", "chunking_strategy", "parent_chunk_size",
        "chunk_separator",
    }
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not updates:
        return get_knowledge_base(kb_id)

    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [kb_id]

    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE knowledge_bases SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
        return get_knowledge_base(kb_id)
    finally:
        conn.close()


def delete_knowledge_base(kb_id: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _slugify(name: str) -> str:
    """Generate a workspace-safe slug from a name."""
    import re
    # Simple slugify: lowercase, replace spaces/special chars with underscore
    slug = re.sub(r"[^\w一-鿿]", "_", name.lower().strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        slug = _new_id()[:8]
    # Ensure uniqueness
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM knowledge_bases WHERE workspace = ?", (slug,)
        ).fetchone()
        if existing:
            slug = f"{slug}_{_new_id()[:4]}"
        return slug
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tags CRUD
# ---------------------------------------------------------------------------


def list_tags(kb_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tags WHERE kb_id = ? ORDER BY level, created_at",
            (kb_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_tags_tree(kb_id: str) -> list[dict]:
    """Return tags as a nested tree structure."""
    all_tags = list_tags(kb_id)
    return _build_tag_tree(all_tags)


def _build_tag_tree(tags: list[dict]) -> list[dict]:
    """Build a tree from a flat list of tags."""
    by_id = {t["id"]: {**t, "children": []} for t in tags}
    roots = []
    for t in tags:
        node = by_id[t["id"]]
        parent_id = t.get("parent_tag_id")
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def create_tag(data: dict) -> dict:
    tag_id = _new_id()
    now = _now()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO tags (id, kb_id, level, name, parent_tag_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                tag_id,
                data["kb_id"],
                data["level"],
                data["name"],
                data.get("parent_tag_id"),
                now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def update_tag(tag_id: str, data: dict) -> dict | None:
    allowed = {"name", "level", "parent_tag_id"}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not updates:
        return None

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [tag_id]

    conn = get_connection()
    try:
        conn.execute(f"UPDATE tags SET {set_clause} WHERE id = ?", values)
        conn.commit()
        row = conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_tag(tag_id: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def batch_create_tags(kb_id: str, tags_data: list[dict]) -> list[dict]:
    """Create multiple tags, possibly nested. Returns created tags."""
    created = []
    conn = get_connection()
    try:
        for tag_data in tags_data:
            tag_id = _new_id()
            now = _now()
            # Handle nested tags (children)
            children_data = tag_data.pop("children", [])
            conn.execute(
                """INSERT INTO tags (id, kb_id, level, name, parent_tag_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    tag_id,
                    kb_id,
                    tag_data.get("level", 1),
                    tag_data["name"],
                    tag_data.get("parent_tag_id"),
                    now,
                ),
            )
            created.append({"id": tag_id, **tag_data})

            # Create children
            for child in children_data:
                child_id = _new_id()
                conn.execute(
                    """INSERT INTO tags (id, kb_id, level, name, parent_tag_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        child_id,
                        kb_id,
                        child.get("level", tag_data.get("level", 1) + 1),
                        child["name"],
                        tag_id,  # parent is the tag we just created
                        now,
                    ),
                )
                created.append({"id": child_id, **child})

        conn.commit()
        return created
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Documents CRUD
# ---------------------------------------------------------------------------


def create_document(data: dict) -> dict:
    doc_id = data.get("id") or _new_id()
    now = _now()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO documents
               (id, kb_id, file_name, file_path, file_size, mime_type, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc_id,
                data["kb_id"],
                data["file_name"],
                data["file_path"],
                data.get("file_size", 0),
                data.get("mime_type", ""),
                data.get("status", "pending"),
                now,
                now,
            ),
        )
        # Insert document-tag associations
        for tag_id in data.get("tag_ids", []):
            conn.execute(
                "INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)",
                (doc_id, tag_id),
            )
        conn.commit()
        return get_document(doc_id) or {}
    finally:
        conn.close()


def get_document(doc_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row:
            return None
        doc = dict(row)
        # Get tags
        tag_rows = conn.execute(
            """SELECT t.* FROM tags t
               JOIN document_tags dt ON t.id = dt.tag_id
               WHERE dt.document_id = ?""",
            (doc_id,),
        ).fetchall()
        doc["tags"] = [dict(r) for r in tag_rows]
        return doc
    finally:
        conn.close()


def list_documents(kb_id: str, page: int = 1, page_size: int = 20) -> dict:
    conn = get_connection()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE kb_id = ?", (kb_id,)
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT * FROM documents WHERE kb_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (kb_id, page_size, offset),
        ).fetchall()

        items = []
        for r in rows:
            doc = dict(r)
            tag_rows = conn.execute(
                """SELECT t.* FROM tags t
                   JOIN document_tags dt ON t.id = dt.tag_id
                   WHERE dt.document_id = ?""",
                (doc["id"],),
            ).fetchall()
            doc["tags"] = [dict(t) for t in tag_rows]
            items.append(doc)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        conn.close()


def update_document(doc_id: str, data: dict) -> dict | None:
    allowed = {
        "file_name", "file_path", "file_size", "mime_type",
        "status", "chunk_count", "vector_count", "lightrag_doc_id", "error_message",
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return get_document(doc_id)

    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [doc_id]

    conn = get_connection()
    try:
        conn.execute(f"UPDATE documents SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return get_document(doc_id)
    finally:
        conn.close()


def delete_document(doc_id: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_pending_documents(kb_id: str) -> list[dict]:
    """Get completed documents that haven't been synced to LightRAG."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM documents
               WHERE kb_id = ? AND status = 'completed' AND lightrag_doc_id IS NULL""",
            (kb_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Chunks CRUD
# ---------------------------------------------------------------------------


def create_chunk(data: dict) -> dict:
    chunk_id = data.get("id") or _new_id()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO chunks (id, document_id, kb_id, content, chunk_index, chunk_type, parent_chunk_id, vector_id, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                chunk_id,
                data["document_id"],
                data["kb_id"],
                data["content"],
                data["chunk_index"],
                data.get("chunk_type", "child"),
                data.get("parent_chunk_id"),
                data.get("vector_id"),
                data.get("metadata_json", "{}"),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def batch_create_chunks(chunks_data: list[dict]) -> list[dict]:
    """Create multiple chunks in a single transaction."""
    created = []
    conn = get_connection()
    try:
        for cd in chunks_data:
            chunk_id = cd.get("id") or _new_id()
            conn.execute(
                """INSERT INTO chunks (id, document_id, kb_id, content, chunk_index, chunk_type, parent_chunk_id, vector_id, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    chunk_id,
                    cd["document_id"],
                    cd["kb_id"],
                    cd["content"],
                    cd["chunk_index"],
                    cd.get("chunk_type", "child"),
                    cd.get("parent_chunk_id"),
                    cd.get("vector_id"),
                    cd.get("metadata_json", "{}"),
                ),
            )
            created.append({"id": chunk_id, **cd})
        conn.commit()
        return created
    finally:
        conn.close()


def list_chunks(document_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
            (document_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_chunks_by_kb(kb_id: str, status: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        if status:
            rows = conn.execute(
                """SELECT c.* FROM chunks c
                   JOIN documents d ON c.document_id = d.id
                   WHERE c.kb_id = ? AND d.status = ?
                   ORDER BY c.document_id, c.chunk_index""",
                (kb_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE kb_id = ? ORDER BY document_id, chunk_index",
                (kb_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_chunks_by_document(document_id: str) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def count_documents(kb_id: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE kb_id = ?", (kb_id,)
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def count_chunks(kb_id: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE kb_id = ?", (kb_id,)
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()
