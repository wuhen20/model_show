"""样本文件 MinIO 对象存储服务。

sample_storage_type=02 时启用，替代本地磁盘存储：
- 新建样本集时以 setNo 作为对象 key 前缀（桶下"路径"）
- 上传图片时仅写入图片对象，对象 ID 以 `minio://{bucket}/{setNo}/{file_name}` 形式存入 s_sample_info.file_path
- 下载/预览时通过该 ID 从 MinIO 读取

注：MinIO 是扁平命名空间，所谓"桶下创建路径"即使用 setNo 作为对象 key 前缀，
MinIO 控制台会按前缀展示为文件夹结构，无需显式创建空目录对象。
"""
import logging
from io import BytesIO
from typing import Optional
from urllib.parse import urlparse

from app.core.config import settings

logger = logging.getLogger("app.sample_minio")

# MinIO 对象 ID 前缀，用于区分本地路径与 MinIO 路径
MINIO_ID_PREFIX = "minio://"


def is_minio_enabled() -> bool:
    """是否启用 MinIO 存储模式"""
    return settings.storage_type == "02"


def is_minio_path(path: str) -> bool:
    """判断给定路径是否为 MinIO 对象 ID"""
    return bool(path) and path.startswith(MINIO_ID_PREFIX)


_minio_client = None


def _get_client():
    """获取 MinIO 客户端（单例缓存，避免每次请求重建连接）

    access_key/secret_key 可以为空（无认证模式），不做非空校验。
    """
    global _minio_client
    if _minio_client is not None:
        return _minio_client

    from minio import Minio

    if not settings.minio_endpoint:
        raise ValueError("MinIO 未配置：请在 .env 中设置 MINIO_ENDPOINT")

    _minio_client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    return _minio_client


def ensure_bucket(bucket_name: Optional[str] = None) -> str:
    """确保桶存在，返回实际使用的桶名"""
    client = _get_client()
    bucket = bucket_name or settings.minio_bucket
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info(f"MinIO 创建桶: {bucket}")
    return bucket


def build_set_path(set_no: str, bucket_name: Optional[str] = None) -> str:
    """构建样本集在 MinIO 下的"路径"标识（写入 s_sample_set.set_path）

    格式: minio://{bucket}/{setNo}
    该值仅用于标识样本集的存储位置，不实际上传空对象。
    """
    bucket = bucket_name or settings.minio_bucket
    return f"{MINIO_ID_PREFIX}{bucket}/{set_no}"


def build_object_id(set_no: str, file_name: str, bucket_name: Optional[str] = None) -> str:
    """构建图片对象的完整 ID（写入 s_sample_info.file_path）

    格式: minio://{bucket}/{setNo}/{file_name}
    """
    bucket = bucket_name or settings.minio_bucket
    object_key = f"{set_no}/{file_name}"
    return f"{MINIO_ID_PREFIX}{bucket}/{object_key}"


def parse_object_id(object_id: str) -> tuple[str, str]:
    """解析 MinIO 对象 ID，返回 (bucket_name, object_key)

    输入: minio://samples/SET001/img.jpg
    返回: ("samples", "SET001/img.jpg")
    """
    if not is_minio_path(object_id):
        raise ValueError(f"非 MinIO 路径: {object_id}")
    parsed = urlparse(object_id)
    bucket = parsed.netloc
    # parsed.path 形如 "/SET001/img.jpg"，去掉前导斜杠
    object_key = parsed.path.lstrip("/")
    return bucket, object_key


def sanitize_sub_dir(sub_dir: str) -> str:
    """校验并规范化子目录字符串（本地/MinIO 通用）。

    规则：
    - 去除首尾空白、首尾斜杠
    - 反斜杠统一为正斜杠
    - 禁止路径穿越（任一级为 .. 或 .）、绝对路径（以 / 开头或含盘符 :）、空字节

    Returns:
        合法时返回规范化后的字符串（如 "7月/批次A"）；
        非法或为空返回 ""（等价于不指定子目录，落到样本集根目录）
    """
    if not sub_dir:
        return ""
    s = str(sub_dir).strip().replace("\\", "/").strip("/")
    if not s or "\x00" in s or ":" in s:
        return ""
    parts = [p for p in s.split("/") if p]
    if not parts or any(p in ("..", ".") for p in parts):
        return ""
    return "/".join(parts)


def build_object_prefix(set_no: str, sub_dir: str = "") -> str:
    """构建 MinIO 对象 key 前缀（不含文件名）。

    sub_dir 非空时返回 "setNo/subDir"，否则返回 "setNo"。
    sub_dir 会先经 sanitize_sub_dir 校验。
    """
    clean = sanitize_sub_dir(sub_dir)
    return f"{set_no}/{clean}" if clean else set_no


def upload_image(set_no: str, file_name: str, content: bytes, content_type: str = "application/octet-stream",
                 bucket_name: Optional[str] = None) -> str:
    """上传图片到 MinIO，返回对象 ID

    Args:
        set_no: 样本集编号，作为对象 key 前缀
        file_name: 文件名（含扩展名）
        content: 文件二进制内容
        content_type: MIME 类型
        bucket_name: 桶名，为空则使用配置默认值

    Returns:
        对象 ID（minio://bucket/setNo/file_name）
    """
    bucket = ensure_bucket(bucket_name)
    object_key = f"{set_no}/{file_name}"
    client = _get_client()
    client.put_object(
        bucket_name=bucket,
        object_name=object_key,
        data=BytesIO(content),
        length=len(content),
        content_type=content_type,
    )
    logger.info(f"MinIO 上传成功: bucket={bucket}, key={object_key}, size={len(content)}")
    return f"{MINIO_ID_PREFIX}{bucket}/{object_key}"


def download_image(object_id: str) -> bytes:
    """从 MinIO 下载图片，返回二进制内容"""
    bucket, object_key = parse_object_id(object_id)
    client = _get_client()
    response = client.get_object(bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def get_image_size(object_id: str) -> int:
    """获取 MinIO 对象大小（字节）"""
    bucket, object_key = parse_object_id(object_id)
    client = _get_client()
    stat = client.stat_object(bucket, object_key)
    return stat.size or 0


def delete_object(object_id: str) -> None:
    """删除 MinIO 对象（静默处理不存在的情况）"""
    try:
        bucket, object_key = parse_object_id(object_id)
        client = _get_client()
        client.remove_object(bucket, object_key)
    except Exception as e:
        logger.warning(f"MinIO 删除对象失败: {object_id}, error: {e}")


def list_object_names(set_no: str, sub_dir: str = "", bucket_name: Optional[str] = None) -> set:
    """列出 MinIO 中指定 set_no（可含 sub_dir）前缀下"当前层级"的对象文件名

    用于上传时检测文件名冲突。采用非递归列举，仅返回当前层级的文件名，
    这样不同子目录下的同名文件不会被判为冲突。

    Args:
        set_no: 样本集编号
        sub_dir: 子目录（可选，会经 sanitize_sub_dir 校验）
        bucket_name: 桶名，为空则使用配置默认值

    Returns:
        文件名集合（不含 "setNo/" 或 "setNo/subDir/" 前缀）。
        子目录对象（以 / 结尾）会被过滤，仅保留文件。
    """
    bucket = bucket_name or settings.minio_bucket
    client = _get_client()
    clean = sanitize_sub_dir(sub_dir)
    prefix = f"{set_no}/{clean}/" if clean else f"{set_no}/"
    names = set()
    try:
        for obj in client.list_objects(bucket, prefix=prefix, recursive=False):
            # object_name 形如 "SET001/7月1日/img.jpg"，去掉前缀得到文件名
            name = obj.object_name
            if name.startswith(prefix):
                name = name[len(prefix):]
            # 过滤子目录对象（以 / 结尾）和空名
            if name and not name.endswith("/"):
                names.add(name)
    except Exception as e:
        logger.warning(f"MinIO 列举对象失败: bucket={bucket}, prefix={prefix}, error={e}")
    return names
