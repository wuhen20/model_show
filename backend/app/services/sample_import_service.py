"""样本批量导入共享服务：解压 ZIP 并导入图片样本。

供 original_sample / sample 两个路由复用，通过 insert_callback 注入各自的 DB insert 函数。

优化：采用"预计算唯一文件名 + 多线程并行上传 + 串行写 DB"四阶段流程，
显著提升大 ZIP（8GB+ / 8000+ 文件）场景下的导入速度。
"""
import os
import io
import shutil
import zipfile
import tempfile
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("app.sample_import")

# 图片后缀（与前端 typeCodeToExtensions['05'] 保持一致）
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}

# 内容类型映射（模块级常量，避免每次上传重建）
_CONTENT_TYPE_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
    ".tif": "image/tiff", ".tiff": "image/tiff",
}

# 并行上传线程数，可通过环境变量覆盖
_DEFAULT_WORKERS = 8


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
    set_name: str = "",
    type_code: str = "",
    insert_callback = None,
    zip_bytes: bytes | None = None,
    zip_path: str | None = None,
    use_minio: bool = False,
    write_txt_to_db: bool = False,
    update_set_labels_callback=None,
) -> dict:
    """解压 ZIP 压缩包并导入图片样本到目标目录/MinIO 和数据库。

    四阶段流程：
      0. 统一为 zip_path 模式（zip_bytes 物化到临时文件，避免多线程 BytesIO 内存爆炸）
      1. 预获取已有文件名集合 + 预扫描 txt 标注文件
      2. 预计算所有图片的唯一文件名（串行，保证 used_names 一致性）
      3. 多线程并行上传图片（每线程独立 ZipFile，避免 read() 竞争）
      4. 串行写入数据库（保证 sample_no 序列号递增，避免 _get_next_sequence 竞争）

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
    # ========== 阶段 0：统一为 zip_path 模式 ==========
    # zip_bytes 模式下，BytesIO 在多线程中会被每个线程拷贝，8GB ZIP × 8 线程会导致内存爆炸
    # 因此先物化到临时文件，统一走 zip_path 路径
    _tmp_zip_path = None
    if not zip_path and zip_bytes is not None:
        fd, _tmp_zip_path = tempfile.mkstemp(suffix=".zip", prefix="sample_import_")
        with os.fdopen(fd, "wb") as f:
            f.write(zip_bytes)
        zip_path = _tmp_zip_path
        zip_bytes = None  # 释放内存引用

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

    try:
        # ========== 阶段 1：预扫描 txt 标注文件 ==========
        with zipfile.ZipFile(zip_path) as zf:
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

        # ========== 阶段 2：预计算所有图片的唯一文件名（串行单次遍历） ==========
        # image_tasks 元素: (zip_filename, unique_name, ext, basename, img_basename)
        image_tasks = []
        with zipfile.ZipFile(zip_path) as zf:  # 仅用于遍历 infolist，不读图片数据
            for info in zf.infolist():
                if info.is_dir() or "__MACOSX" in info.filename:
                    continue
                basename = os.path.basename(info.filename)
                if not basename or basename.startswith("."):
                    continue
                ext = os.path.splitext(basename)[1].lower()

                if ext in IMAGE_EXTS:
                    # 生成唯一文件名（单线程修改 used_names，保证一致性）
                    if use_minio:
                        unique_name = _get_unique_filename_for_minio(basename, used_names)
                    else:
                        unique_name = _get_unique_filename(target_dir, basename, used_names)
                    used_names.add(unique_name)

                    # 记录重命名映射
                    if unique_name != basename:
                        rename_map[basename] = unique_name
                        logger.info(f"图片文件重命名: {basename} -> {unique_name}")

                    img_basename = os.path.splitext(basename)[0]
                    # 保存 info.filename（zip 内路径字符串），后续 worker 用 zf.read(filename) 读取
                    image_tasks.append((info.filename, unique_name, ext, basename, img_basename))
                elif ext != ".txt":
                    skipped_count += 1

        # ========== 阶段 3：多线程并行上传 ==========
        # 关键：zipfile.ZipFile.read() 非线程安全，每个 worker 线程通过 initializer 独立打开自己的 ZipFile
        # 从同一路径打开多个只读 ZipFile 对象是安全的
        upload_results = [None] * len(image_tasks)  # 按原始顺序存储，保证 DB 写入顺序
        workers = int(os.environ.get("SAMPLE_IMPORT_WORKERS", str(_DEFAULT_WORKERS)))
        workers = max(1, min(workers, len(image_tasks))) if image_tasks else 1

        if image_tasks:
            # 线程局部 ZipFile + 跟踪列表（用于关闭）
            _thread_local = threading.local()
            _worker_zipfiles = []
            _worker_zipfiles_lock = threading.Lock()

            def _init_worker():
                """线程池初始化器：每个 worker 线程打开自己的 ZipFile（只读，多实例安全）"""
                zf = zipfile.ZipFile(zip_path)
                _thread_local.zf = zf
                with _worker_zipfiles_lock:
                    _worker_zipfiles.append(zf)

            def _upload_one(idx, zip_filename, unique_name, ext):
                """单张图片上传任务

                闭包捕获 set_no / use_minio / target_dir / minio_upload_image（MinIO 模式）
                """
                zf = _thread_local.zf
                data = zf.read(zip_filename)  # 线程安全：每个线程独立 ZipFile 实例
                if use_minio:
                    ct = _CONTENT_TYPE_MAP.get(ext, "application/octet-stream")
                    file_path = minio_upload_image(set_no, unique_name, data, content_type=ct)
                else:
                    target_path = os.path.join(target_dir, unique_name)
                    with open(target_path, "wb") as f:
                        f.write(data)
                    file_path = target_path
                return {"file_path": file_path, "data_size": len(data)}

            try:
                with ThreadPoolExecutor(max_workers=workers, initializer=_init_worker) as executor:
                    future_to_idx = {
                        executor.submit(_upload_one, idx, task[0], task[1], task[2]): idx
                        for idx, task in enumerate(image_tasks)
                    }
                    for future in as_completed(future_to_idx):
                        idx = future_to_idx[future]
                        try:
                            upload_results[idx] = future.result()
                        except Exception as e:
                            basename = image_tasks[idx][3]
                            upload_results[idx] = {"error": f"{basename}: {e}"}
            finally:
                # 关闭所有 worker 线程打开的 ZipFile
                for zf in _worker_zipfiles:
                    try:
                        zf.close()
                    except Exception:
                        pass

        # ========== 阶段 4：串行写入数据库（保持原 insert_callback 调用方式） ==========
        # 串行原因：insert_callback 内部调用 _get_next_sequence 生成 sample_no，
        # 涉及 s_sequence_counter 表的读-改-写，并行会导致序列号竞争
        source_name = "高质量样本集" if write_txt_to_db else "原始样本集"
        total_images = len(image_tasks)
        last_log_time = time.time()
        for idx, task in enumerate(image_tasks):
            zip_filename, unique_name, ext, basename, img_basename = task
            result = upload_results[idx]
            if result is None:
                continue
            if "error" in result:
                errors.append(result["error"])
                continue

            # 判断该图片是否有同名txt标注文件
            label_flag = 1 if img_basename in txt_basenames else 0

            # 获取对应的 label_content（write_txt_to_db=True 时）
            label_content = ""
            if write_txt_to_db and img_basename in image_label_content_map:
                label_content = image_label_content_map[img_basename]

            try:
                insert_callback(set_no, unique_name, ext.lstrip("."), type_code,
                                result["file_path"], result["data_size"],
                                label_flag, label_content)
                image_count += 1
            except Exception as e:
                errors.append(f"{basename}: {e}")

            # 每 10 秒输出一次导入进度日志
            now = time.time()
            if now - last_log_time >= 10:
                logger.info(f"{source_name} {set_no}（{set_name}）导入进度：{image_count}/{total_images}")
                last_log_time = now

        # 循环结束后输出最终完成日志
        if total_images > 0:
            logger.info(f"{source_name} {set_no}（{set_name}）导入完成：{image_count}/{total_images}")

        # txt_count 统计：write_txt_to_db=True 时为已处理的标注文件数；False 时为 0（全部跳过）
        if write_txt_to_db:
            txt_count = len(image_label_content_map) + (1 if classes_txt_content is not None else 0)

    finally:
        # 清理临时文件（zip_bytes 物化的临时 ZIP）
        if _tmp_zip_path and os.path.exists(_tmp_zip_path):
            try:
                os.remove(_tmp_zip_path)
            except Exception:
                pass

    return {
        "image_count": image_count,
        "txt_count": txt_count,
        "skipped_count": skipped_count,
        "errors": errors,
    }
