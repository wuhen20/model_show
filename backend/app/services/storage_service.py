"""File storage abstraction — local filesystem or MinIO."""

import os
import shutil

from app.core.config import settings


def _upload_dir() -> str:
    return os.path.abspath(settings.upload_dir)


def save_file(kb_id: str, file_name: str, content: bytes) -> str:
    """Save a file and return its relative path.

    For local storage: saves to uploads/{kb_id}/{file_name}.
    For MinIO: saves to the kb-{workspace} bucket.
    """
    if settings.storage_backend == "minio":
        return _save_to_minio(kb_id, file_name, content)
    return _save_local(kb_id, file_name, content)


def _save_local(kb_id: str, file_name: str, content: bytes) -> str:
    dir_path = os.path.join(_upload_dir(), kb_id)
    os.makedirs(dir_path, exist_ok=True)
    # Handle duplicate filenames by appending a short hash
    file_path = os.path.join(dir_path, file_name)
    if os.path.exists(file_path):
        import hashlib
        short_hash = hashlib.md5(content).hexdigest()[:6]
        name, ext = os.path.splitext(file_name)
        file_name = f"{name}_{short_hash}{ext}"
        file_path = os.path.join(dir_path, file_name)
    with open(file_path, "wb") as f:
        f.write(content)
    return f"uploads/{kb_id}/{file_name}"


def _save_to_minio(kb_id: str, file_name: str, content: bytes) -> str:
    """Save file to MinIO bucket."""
    try:
        from minio import Minio
        from io import BytesIO

        kb = _get_kb_workspace(kb_id)
        bucket_name = f"{settings.minio_bucket_prefix}{kb}"

        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)

        object_name = file_name
        data = BytesIO(content)
        client.put_object(
            bucket_name,
            object_name,
            data,
            length=len(content),
        )
        return f"minio://{bucket_name}/{object_name}"
    except Exception as e:
        print(f"[Storage] MinIO upload failed, falling back to local: {e}")
        return _save_local(kb_id, file_name, content)


def get_file(path: str) -> bytes:
    """Read file content from storage."""
    if path.startswith("minio://"):
        return _get_from_minio(path)
    # Local file
    abs_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", path
    )
    with open(abs_path, "rb") as f:
        return f.read()


def _get_from_minio(path: str) -> bytes:
    """Read file from MinIO."""
    from minio import Minio
    from io import BytesIO

    # Parse minio://bucket-name/object-name
    parts = path.replace("minio://", "").split("/", 1)
    bucket_name = parts[0]
    object_name = parts[1] if len(parts) > 1 else ""

    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )

    response = client.get_object(bucket_name, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_file(path: str) -> bool:
    """Delete a file from storage."""
    if path.startswith("minio://"):
        return _delete_from_minio(path)
    # Local file
    abs_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", path
    )
    if os.path.exists(abs_path):
        os.remove(abs_path)
        return True
    return False


def _delete_from_minio(path: str) -> bool:
    """Delete file from MinIO."""
    from minio import Minio

    parts = path.replace("minio://", "").split("/", 1)
    bucket_name = parts[0]
    object_name = parts[1] if len(parts) > 1 else ""

    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )

    client.remove_object(bucket_name, object_name)
    return True


def _get_kb_workspace(kb_id: str) -> str:
    """Look up workspace name for a KB ID."""
    from app.services import db_service
    kb = db_service.get_knowledge_base(kb_id)
    if kb:
        return kb["workspace"]
    return kb_id
