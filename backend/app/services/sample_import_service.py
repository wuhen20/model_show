"""样本批量导入共享服务：解压 ZIP 并导入图片样本。

供 original_sample / sample 两个路由复用，通过 insert_callback 注入各自的 DB insert 函数。
"""
import os
import io
import zipfile
import logging

logger = logging.getLogger("app.sample_import")

# 图片后缀（与前端 typeCodeToExtensions['05'] 保持一致）
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def extract_zip_and_import(
    zip_bytes: bytes,
    target_dir: str,
    set_no: str,
    type_code: str,
    insert_callback,
) -> dict:
    """解压 ZIP 压缩包并导入图片样本到目标目录和数据库。

    - 仅处理图片文件(及同名 .txt 标注/classes.txt)，其它文件跳过
    - 图片文件保存到 target_dir 并调用 insert_callback 写入数据库
    - .txt 标注文件仅保存到 target_dir，不写数据库
    - 文件名取 basename（扁平化），重名直接覆盖（与单文件上传行为一致）

    insert_callback 签名: (set_no, sample_name, suffix, type_code, file_path, file_size_bytes) -> None

    返回: {image_count, txt_count, skipped_count, errors}
    """
    os.makedirs(target_dir, exist_ok=True)

    image_count = 0
    txt_count = 0
    skipped_count = 0
    errors = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            # 跳过目录项
            if info.is_dir():
                continue

            name = info.filename
            # 跳过 macOS 元数据目录
            if "__MACOSX" in name:
                continue

            basename = os.path.basename(name)
            if not basename:
                continue
            # 跳过隐藏文件
            if basename.startswith("."):
                continue

            ext = os.path.splitext(basename)[1].lower()
            target_path = os.path.join(target_dir, basename)

            try:
                if ext in IMAGE_EXTS:
                    # 图片：落盘 + 写库
                    data = zf.read(info)
                    with open(target_path, "wb") as f:
                        f.write(data)
                    insert_callback(set_no, basename, ext.lstrip("."), type_code, target_path, len(data))
                    image_count += 1
                elif ext == ".txt":
                    # 标注文件（classes.txt / 同名 txt）：仅落盘不写库
                    data = zf.read(info)
                    with open(target_path, "wb") as f:
                        f.write(data)
                    txt_count += 1
                else:
                    # 非图片非 txt：跳过
                    skipped_count += 1
            except Exception as e:
                errors.append(f"{basename}: {e}")

    return {
        "image_count": image_count,
        "txt_count": txt_count,
        "skipped_count": skipped_count,
        "errors": errors,
    }
