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
    - 文件名冲突时自动添加序号（_1, _2...），同名图片的标注文件同步重命名

    insert_callback 签名: (set_no, sample_name, suffix, type_code, file_path, file_size_bytes, label_flag) -> None

    返回: {image_count, txt_count, skipped_count, errors}
    """
    os.makedirs(target_dir, exist_ok=True)

    image_count = 0
    txt_count = 0
    skipped_count = 0
    errors = []

    # 已使用的文件名集合（用于避免重名）
    used_names = set()
    
    # 图片重命名映射：{原文件名: 新文件名}，用于同步重命名标注文件
    rename_map = {}

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # 预扫描：收集 ZIP 中 .txt 标注文件的 basename（不含扩展名），用于判断图片是否有标注
        txt_basenames = set()
        for info in zf.infolist():
            if info.is_dir() or "__MACOSX" in info.filename:
                continue
            basename = os.path.basename(info.filename)
            if basename and not basename.startswith(".") and os.path.splitext(basename)[1].lower() == ".txt":
                txt_basenames.add(os.path.splitext(basename)[0])

        # 第一轮：处理图片文件，建立重命名映射
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
                unique_name = _get_unique_filename(target_dir, basename, used_names)
                used_names.add(unique_name)
                
                # 记录重命名映射
                if unique_name != basename:
                    rename_map[basename] = unique_name
                    logger.info(f"图片文件重命名: {basename} -> {unique_name}")
                
                # 保存图片文件
                target_path = os.path.join(target_dir, unique_name)
                try:
                    data = zf.read(info)
                    with open(target_path, "wb") as f:
                        f.write(data)
                    # 判断该图片是否有同名txt标注文件
                    img_basename = os.path.splitext(basename)[0]
                    label_flag = 1 if img_basename in txt_basenames else 0
                    insert_callback(set_no, unique_name, ext.lstrip("."), type_code, target_path, len(data), label_flag)
                    image_count += 1
                except Exception as e:
                    errors.append(f"{basename}: {e}")
        
        # 第二轮：处理 .txt 标注文件，同步重命名
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
            
            if ext == ".txt":
                # 检查是否需要同步重命名
                txt_basename = basename
                
                # 如果是 classes.txt，保持原名
                if basename.lower() == "classes.txt":
                    unique_name = _get_unique_filename(target_dir, basename, used_names)
                    used_names.add(unique_name)
                else:
                    # 检查是否有对应的图片文件被重命名
                    # 例如：image1.jpg -> image1_1.jpg，则 image1.txt -> image1_1.txt
                    img_basename = basename.replace(".txt", "")
                    renamed = False
                    
                    # 查找对应的图片扩展名
                    for img_ext in IMAGE_EXTS:
                        img_name = img_basename + img_ext
                        if img_name in rename_map:
                            # 对应的图片文件被重命名了，同步重命名标注文件
                            new_img_name = rename_map[img_name]
                            new_txt_name = new_img_name.replace(img_ext, ".txt")
                            unique_name = new_txt_name
                            renamed = True
                            logger.info(f"标注文件同步重命名: {basename} -> {unique_name} (对应图片: {img_name} -> {new_img_name})")
                            break
                    
                    if not renamed:
                        # 没有对应的图片文件被重命名，检查是否需要添加序号
                        unique_name = _get_unique_filename(target_dir, basename, used_names)
                    
                    used_names.add(unique_name)
                
                # 保存 .txt 文件
                target_path = os.path.join(target_dir, unique_name)
                try:
                    data = zf.read(info)
                    with open(target_path, "wb") as f:
                        f.write(data)
                    txt_count += 1
                except Exception as e:
                    errors.append(f"{basename}: {e}")
            
            elif ext not in IMAGE_EXTS:
                # 非图片非 txt：跳过
                skipped_count += 1

    return {
        "image_count": image_count,
        "txt_count": txt_count,
        "skipped_count": skipped_count,
        "errors": errors,
    }
