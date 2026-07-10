"""Ceph 对象存储服务（通过 S3 兼容 API 访问）"""
import logging
import os
import re

logger = logging.getLogger("app.ceph_service")

# Content-Type 到文件扩展名的映射
_CONTENT_TYPE_EXT_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
    "image/svg+xml": ".svg",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "text/plain": ".txt",
    "application/json": ".json",
}


def _get_s3_client():
    import boto3
    from app.core.config import settings

    if not settings.ceph_endpoint:
        raise ValueError("Ceph 未配置：请在 .env 中设置 CEPH_ENDPOINT、CEPH_ACCESS_KEY、CEPH_SECRET_KEY")

    return boto3.client(
        's3',
        endpoint_url=settings.ceph_endpoint,
        aws_access_key_id=settings.ceph_access_key,
        aws_secret_access_key=settings.ceph_secret_key,
        verify=settings.ceph_secure,
    )


def download_from_ceph(bucket_name: str, object_key: str, local_path: str) -> int:
    """从 Ceph 下载文件到本地，返回文件大小（字节）"""
    s3 = _get_s3_client()
    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    file_size = response['ContentLength']
    with open(local_path, 'wb') as f:
        for chunk in response['Body'].iter_chunks(8192):
            f.write(chunk)
    logger.info(f"Ceph 下载完成：bucket={bucket_name}, key={object_key}, size={file_size}")
    return file_size


def get_ceph_object_ext(bucket_name: str, object_key: str) -> str | None:
    """获取 Ceph 对象对应的文件扩展名（含点号，如 .jpg）

    优先从 Content-Disposition 提取原始文件名的后缀，
    否则根据 Content-Type 推断，都无法确定时返回 None。
    """
    try:
        s3 = _get_s3_client()
        response = s3.head_object(Bucket=bucket_name, Key=object_key)

        # 优先从 Content-Disposition 提取原始文件名
        content_disposition = response.get("ContentDisposition", "")
        if content_disposition:
            match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\s]+)', content_disposition, re.IGNORECASE)
            if match:
                filename = match.group(1)
                _, ext = os.path.splitext(filename)
                if ext:
                    return ext

        # 根据 Content-Type 推断
        content_type = response.get("ContentType", "")
        if content_type:
            ext = _CONTENT_TYPE_EXT_MAP.get(content_type.split(";")[0].strip())
            if ext:
                return ext
    except Exception as e:
        logger.warning(f"获取 Ceph 对象元数据失败：bucket={bucket_name}, key={object_key}, error={e}")

    return None
