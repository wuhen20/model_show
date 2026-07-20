"""样本批量导入共享服务：解压 ZIP 并导入图片样本。

供 original_sample / sample 两个路由复用，通过 insert_callback 注入各自的 DB insert 函数。
"""
import os
import io
import shutil
import zipfile
import tempfile
import logging

logger = logging.getLogger("app.sample_import")

# 图片后缀（与前端 typeCodeToExtensions['05'] 保持一致）
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def _get_unique_filename(target_dir: str, basename: str, used_names: set) -> str:
    """生成唯一文件名，如果重名则添加序号（_1, _2...）

    同时检查磁盘已存在文件和本次导入已使用文件名。
    例如：4.17 (4).jpg 已存在 → 4.17 (4)_1.jpg → 4.17 (4)_2.jpg ...

    Args:
        target_dir: 目标目录
        basename: 原始文件名
        used_names: 已使用的文件名集合

    Returns:
        唯一的文件名（不含路径）
    """
    # 检查磁盘文件和 used_names 是否都不存在该文件名
    def name_conflicts(name: str) -> bool:
        return name in used_names or os.path.exists(os.path.join(target_dir, name))

    if not name_conflicts(basename):
        return basename

    # 分离文件名和扩展名
    name, ext = os.path.splitext(basename)
    counter = 1

    # 尝试添加序号
    while True:
        new_name = f"{name}_{counter}{ext}"
        if not name_conflicts(new_name):
            return new_name
        counter += 1


def _get_unique_filename_for_minio(basename: str, used_names: set) -> str:
    """MinIO 模式下生成唯一文件名

    MinIO 模式下不需要检查磁盘，仅检查 used_names（应预先填入已存在的 MinIO 对象名）。
    """
    if basename not in used_names:
        return basename
    name, ext = os.path.splitext(basename)
    counter = 1
    while True:
        new_name = f"{name}_{counter}{ext}"
        if new_name not in used_names:
            return new_name
        counter += 1


def extract_zip_and_import(
    target_dir: str | None,
    set_no: str,
    type_code: str,
    insert_callback,
    zip_bytes: bytes | None = None,
    zip_path: str | None = None,
    use_minio: bool = False,
    write_txt_to_db: bool = False,
    update_set_labels_callback=None,
) -> dict:
    """解压 ZIP 压缩包并导入图片样本到目标目录/MinIO 和数据库。

    - 仅处理图片文件(及同名 .txt 标注/classes.txt)，其它文件跳过
    - 图片文件保存到 target_dir（本地模式）或上传到 MinIO（MinIO 模式），并调用 insert_callback 写入数据库
    - .txt 标注文件处理：
        - write_txt_to_db=True（高质量样本）：读取内容，通过 insert_callback 的 label_content 参数写入 DB，不保存到磁盘/MinIO
        - write_txt_to_db=False（原始样本）：直接跳过，不保存不写 DB
    - classes.txt 处理（仅 write_txt_to_db=True 时）：
        - 读取内容，调用 update_set_labels_callback(set_no, content) 更新样本集 sample_labels
    - 文件名冲突时自动添加序号（_1, _2...），同名图片的标注文件内容同步对应

    参数:
        target_dir: 目标目录路径（本地模式使用，MinIO 模式传 None）
        set_no: 样本集编号
        type_code: 样本类型编码
        insert_callback: 写入数据库的回调函数，签名:
            (set_no, sample_name, suffix, type_code, file_path, file_size_bytes, label_flag, label_content="") -> None
        zip_bytes: ZIP 文件的字节内容（小文件用，已废弃不推荐）
        zip_path: ZIP 文件的磁盘路径（推荐，避免大文件读入内存）
        use_minio: 是否使用 MinIO 模式
        write_txt_to_db: 是否将 .txt 标注内容写入 DB（True=高质量样本，False=原始样本）
        update_set_labels_callback: classes.txt 内容更新回调，签名: (set_no, sample_labels_content) -> None

    返回: {image_count, txt_count, skipped_count, errors}
    """
    if not use_minio and target_dir:
        os.makedirs(target_dir, exist_ok=True)

    # MinIO 上传相关：避免覆盖已有对象
    if use_minio:
        from app.services.sample_minio_service import list_object_names as minio_list_object_names, upload_image as minio_upload_image
        used_names = minio_list_object_names(set_no)
    else:
        used_names = set()

    image_count = 0
    txt_count = 0
    skipped_count = 0
    errors = []

    # 图片重命名映射：{原文件名: 新文件名}，用于同步重命名标注文件
    rename_map = {}

    # 图片 basename → 标注 txt 内容（write_txt_to_db=True 时使用）
    image_label_content_map = {}

    # 根据输入方式打开 ZIP
    if zip_path:
        zf_ctx = zipfile.ZipFile(zip_path)
    else:
        zf_ctx = zipfile.ZipFile(io.BytesIO(zip_bytes))

    with zf_ctx as zf:
        # 预扫描：收集 ZIP 中 .txt 标注文件的 basename（不含扩展名），用于判断图片是否有标注
        # 同时读取 txt 内容（write_txt_to_db=True 时）
        txt_basenames = set()
        classes_txt_content = None
        if write_txt_to_db:
            for info in zf.infolist():
                if info.is_dir() or "__MACOSX" in info.filename:
                    continue
                basename = os.path.basename(info.filename)
                if not basename or basename.startswith("."):
                    continue
                if os.path.splitext(basename)[1].lower() != ".txt":
                    continue
                txt_basenames.add(os.path.splitext(basename)[0])
                # 读取 txt 内容（保持原内容不变）
                try:
                    raw = zf.read(info)
                    try:
                        txt_text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        txt_text = raw.decode("gbk", errors="replace")
                    img_basename = os.path.splitext(basename)[0]
                    if img_basename.lower() == "classes":
                        classes_txt_content = txt_text
                    else:
                        image_label_content_map[img_basename] = txt_text
                except Exception as e:
                    errors.append(f"{basename}: 读取内容失败 - {e}")
        else:
            for info in zf.infolist():
                if info.is_dir() or "__MACOSX" in info.filename:
                    continue
                basename = os.path.basename(info.filename)
                if basename and not basename.startswith(".") and os.path.splitext(basename)[1].lower() == ".txt":
                    txt_basenames.add(os.path.splitext(basename)[0])

        # 更新样本集 sample_labels（如有 classes.txt 且提供了回调）
        if write_txt_to_db and classes_txt_content is not None and update_set_labels_callback:
            try:
                update_set_labels_callback(set_no, classes_txt_content)
            except Exception as e:
                errors.append(f"classes.txt: 更新样本集标签失败 - {e}")

        # 处理图片文件
        for info in zf.infolist():
            if info.is_dir():
                continue

            name = info.filename
            if "__MACOSX" in name:
                continue

            basename = os.path.basename(name)
            if not basename or basename.startswith("."):
                continue

            ext = os.path.splitext(basename)[1].lower()

            if ext in IMAGE_EXTS:
                # 生成唯一文件名
                if use_minio:
                    unique_name = _get_unique_filename_for_minio(basename, used_names)
                else:
                    unique_name = _get_unique_filename(target_dir, basename, used_names)
                used_names.add(unique_name)

                # 记录重命名映射
                if unique_name != basename:
                    rename_map[basename] = unique_name
                    logger.info(f"图片文件重命名: {basename} -> {unique_name}")

                # 读取图片数据
                try:
                    data = zf.read(info)
                except Exception as e:
                    errors.append(f"{basename}: 读取失败 - {e}")
                    continue

                # 保存图片文件
                try:
                    if use_minio:
                        # MinIO 模式
                        content_type_map = {
                            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                            ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
                            ".tif": "image/tiff", ".tiff": "image/tiff",
                        }
                        ct = content_type_map.get(ext, "application/octet-stream")
                        from app.services.sample_minio_service import upload_image as _minio_upload
                        file_path = _minio_upload(set_no, unique_name, data, content_type=ct)
                    else:
                        # 本地模式
                        target_path = os.path.join(target_dir, unique_name)
                        with open(target_path, "wb") as f:
                            f.write(data)
                        file_path = target_path

                    # 判断该图片是否有同名txt标注文件
                    img_basename = os.path.splitext(basename)[0]
                    label_flag = 1 if img_basename in txt_basenames else 0

                    # 获取对应的 label_content（write_txt_to_db=True 时）
                    label_content = ""
                    if write_txt_to_db and img_basename in image_label_content_map:
                        label_content = image_label_content_map[img_basename]

                    # 调用 insert_callback 写入数据库
                    insert_callback(set_no, unique_name, ext.lstrip("."), type_code, file_path, len(data), label_flag, label_content)
                    image_count += 1
                except Exception as e:
                    errors.append(f"{basename}: {e}")

        # txt_count 统计：write_txt_to_db=True 时为已处理的标注文件数；False 时为 0（全部跳过）
        if write_txt_to_db:
            txt_count = len(image_label_content_map) + (1 if classes_txt_content is not None else 0)

        # 统计非图片非 txt 的跳过数量
        for info in zf.infolist():
            if info.is_dir() or "__MACOSX" in info.filename:
                continue
            basename = os.path.basename(info.filename)
            if not basename or basename.startswith("."):
                continue
            ext = os.path.splitext(basename)[1].lower()
            if ext not in IMAGE_EXTS and ext != ".txt":
                skipped_count += 1

    return {
        "image_count": image_count,
        "txt_count": txt_count,
        "skipped_count": skipped_count,
        "errors": errors,
    }
