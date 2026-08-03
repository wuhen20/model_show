"""图像样本清洗服务（自实现版本）

替代 cleanvision，同时支持本地存储与 MinIO 对象存储模式。

设计要点：
1. 流式处理：逐张加载图片，提取特征后立即释放原始数据，控制内存峰值
2. 共享特征池：所有图片特征（哈希、pHash、宽高等）存于内存，供集合级检测使用
3. 分批处理 + 多线程：每批 N 张图，使用线程池并行下载/解码/提取特征
4. 双存储适配：通过 file_path 前缀自动分流本地/MinIO 读取逻辑
5. 检测与移动分离：检测阶段仅记录问题 sample_no，移动阶段统一处理

检测项：
- blurry        模糊（FIND_EDGES 边缘检测 + 灰度直方图）
- dark          过暗（平均亮度）
- light         过亮（平均亮度）
- low_information 信息量低（图像熵）
- odd_aspect_ratio 宽高比异常（固定阈值法）
- grayscale     灰度图像（通道一致性）
- exact_duplicates 完全重复（MD5 哈希）
- near_duplicates  近似重复（pHash 汉明距离）
- odd_size      异常大小（分辨率 IQR 离群点）
"""
import hashlib
import io
import logging
import os
import shutil
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
from PIL import Image
from imagehash import phash

from app.core.config import settings
from app.services.sample_minio_service import (
    is_minio_enabled, is_minio_path, parse_object_id,
    download_image, upload_image, delete_object, list_object_names,
)

logger = logging.getLogger("app.image_clean")

# ============================================================================
# 检测阈值（可通过环境变量覆盖）
# ============================================================================

# 模糊检测：归一化评分 < 此值判定为模糊（与 CleanVision 一致，评分范围 0~1，越小越模糊）
BLURRY_THRESHOLD = float(os.environ.get("IMG_CLEAN_BLURRY", "0.3"))

# 模糊检测归一化因子（指数归一化，与 CleanVision normalizing_factor 一致）
BLURRY_NORM_FACTOR = float(os.environ.get("IMG_CLEAN_BLURRY_NORM_FACTOR", "0.01"))

# 模糊检测色彩阈值：灰度直方图标准差归一化评分 <= 此值时置零（与 CleanVision color_threshold 一致）
BLURRY_COLOR_THRESHOLD = float(os.environ.get("IMG_CLEAN_BLURRY_COLOR_THRESHOLD", "0.18"))

# 模糊检测缩放分辨率：最长边缩放到此值再计算（与 CleanVision MAX_RESOLUTION_FOR_BLURRY_DETECTION 一致）
MAX_RESOLUTION_FOR_BLURRY = int(os.environ.get("IMG_CLEAN_BLURRY_MAX_RES", "64"))

# 过暗检测：灰度均值 < 此值判定为过暗（0-255）
DARK_THRESHOLD = float(os.environ.get("IMG_CLEAN_DARK", "50"))

# 过亮检测：灰度均值 > 此值判定为过亮（0-255）
LIGHT_THRESHOLD = float(os.environ.get("IMG_CLEAN_LIGHT", "200"))

# 信息量低：图像熵 < 此值判定为信息量低（0-8）
LOW_INFO_THRESHOLD = float(os.environ.get("IMG_CLEAN_LOW_INFO", "4.5"))

# 近似重复：pHash 汉明距离 < 此值判定为近似重复
NEAR_DUP_THRESHOLD = int(os.environ.get("IMG_CLEAN_NEAR_DUP", "8"))

# 宽高比异常：score = min(w/h, h/w)，score < 阈值判定为异常（与 CleanVision 一致）
ASPECT_RATIO_THRESHOLD = float(os.environ.get("IMG_CLEAN_ASPECT_RATIO", "0.35"))

# IQR 离群点倍数（用于异常大小）
IQR_K = float(os.environ.get("IMG_CLEAN_IQR_K", "1.5"))

# 异常大小绝对最小面积阈值（像素数）：当 IQR 下限为负数时，作为兜底下限
# 默认 10000 px（约 100×100），正常图片远大于此值不会被误判
MIN_AREA_THRESHOLD = int(os.environ.get("IMG_CLEAN_MIN_AREA", "10000"))

# 分批处理大小：每批加载的图片数量
BATCH_SIZE = int(os.environ.get("IMG_CLEAN_BATCH_SIZE", "50"))

# 特征提取线程池大小（IO 密集型 + cv2/numpy 释放 GIL，可设置较大值）
MAX_WORKERS = int(os.environ.get("IMG_CLEAN_MAX_WORKERS", "8"))

# 清洗类型编码 → 内部检测项名称映射（与 PIC_CLEAN_TYPE 字典 SPARE1 对齐）
# 字典 SPARE1 字段沿用 cleanvision 命名，便于前端字典维护兼容
ISSUE_NAMES = {
    "blurry": "模糊",
    "dark": "过暗",
    "light": "过亮",
    "low_information": "信息量低",
    "odd_aspect_ratio": "宽高比异常",
    "grayscale": "灰度图像",
    "exact_duplicates": "完全重复",
    "near_duplicates": "近似重复",
    "odd_size": "异常大小",
}

# 集合级检测项：需要全量特征才能判定
SET_LEVEL_ISSUES = {"exact_duplicates", "near_duplicates", "odd_aspect_ratio", "odd_size"}
# 单图检测项：仅凭自身特征即可判定
PER_IMAGE_ISSUES = {"blurry", "dark", "light", "low_information", "grayscale"}


# ============================================================================
# 特征数据结构
# ============================================================================

@dataclass
class ImageFeatures:
    file_path: str          # 数据库存储的原始路径（本地绝对路径或 minio:// URL）
    sample_no: str          # 样本编号
    sample_name: str        # 样本名称
    width: int = 0
    height: int = 0
    md5_hash: str = ""      # 完全重复检测（基于解码像素）
    phash_value: int = 0    # 近似重复检测（64-bit）
    mean_brightness: float = 0.0
    blurriness_score: float = 0.0  # 模糊评分（CleanVision 归一化，0~1，越小越模糊）
    entropy: float = 0.0
    is_grayscale: bool = False
    load_failed: bool = False  # 加载失败的图片，不参与检测


@dataclass
class SetLevelIssue:
    """集合级检测结果项

    repeat_file_path 仅重复检测有值，指向被重复的保留方(A图)原始路径，
    用于写入 s_data_clean_pic.repeat_file_path 供前端对比展示。
    """
    issue: str                  # exact_duplicates / near_duplicates / odd_aspect_ratio / odd_size
    repeat_file_path: str = ""  # 对比图(保留方)原始路径; 仅重复检测有值


# ============================================================================
# 图片读取（本地/MinIO 双适配）
# ============================================================================

def _read_image_bytes(file_path: str) -> Optional[bytes]:
    """根据路径前缀读取图片二进制内容"""
    try:
        if is_minio_path(file_path):
            return download_image(file_path)
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return f.read()
        logger.warning(f"文件不存在: {file_path}")
        return None
    except Exception as e:
        logger.warning(f"读取图片失败: {file_path}, error: {e}")
        return None


def _decode_image(image_bytes: bytes):
    """解码图片二进制为 PIL.Image + numpy 数组"""
    # PIL 用于元数据/格式信息
    pil_img = Image.open(io.BytesIO(image_bytes))
    pil_img.load()
    # OpenCV 用于像素级计算（拉普拉斯、熵等）
    # cv2.imdecode 接受 numpy 数组
    nparr = np.frombuffer(image_bytes, np.uint8)
    cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return pil_img, cv_img


# ============================================================================
# 特征提取
# ============================================================================

def _compute_md5(pil_img: Image.Image) -> str:
    """对解码后的图像像素计算 MD5（与 CleanVision 一致）

    区别于对文件字节算 MD5：复制原图改文件名或重编码后文件字节不同但像素相同，
    基于像素的 MD5 仍能正确判定为完全重复。
    """
    pixels = np.asarray(pil_img)
    return hashlib.md5(pixels.tobytes()).hexdigest()


def _compute_phash(pil_img: Image.Image) -> int:
    """计算 64-bit 感知哈希，返回整数便于汉明距离计算"""
    h = phash(pil_img, hash_size=8)  # 8x8 = 64bit
    # 转 int
    return int(str(h), 16)


def _compute_brightness(cv_img) -> float:
    """计算灰度均值"""
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img
    return float(np.mean(gray))


def _compute_blurriness(pil_img: Image.Image) -> float:
    """按 CleanVision 算法计算归一化模糊评分（0~1，越小越模糊）

    步骤（对齐 cleanvision/image_property.py BlurrinessProperty）：
    1. 缩放到最长边 MAX_RESOLUTION_FOR_BLURRY（默认 64px）
    2. 转灰度
    3. blurriness = sqrt(FIND_EDGES(gray) 的方差)
    4. grayscale_std = std(gray.histogram())
    5. 归一化：blur_scores = 1 - exp(-blurriness * norm_factor)
              std_scores = 1 - exp(-grayscale_std * norm_factor)
              std_scores <= color_threshold 时置零
    6. score = min(blur_scores + std_scores, 1)
    """
    from PIL import ImageFilter, ImageStat

    # 1. 缩放到最长边 64px
    ratio = max(pil_img.width, pil_img.height) / MAX_RESOLUTION_FOR_BLURRY
    if ratio > 1:
        resized = pil_img.resize(
            (max(int(pil_img.width // ratio), 1), max(int(pil_img.height // ratio), 1))
        )
    else:
        resized = pil_img.copy()
    gray = resized.convert("L")

    # 2. 边缘图方差开根号
    edges = gray.filter(ImageFilter.FIND_EDGES)
    blurriness = float(np.sqrt(ImageStat.Stat(edges).var[0]))

    # 3. 灰度直方图标准差
    grayscale_std = float(np.std(gray.histogram()))

    # 4. 归一化评分
    blur_scores = 1.0 - float(np.exp(-1.0 * blurriness * BLURRY_NORM_FACTOR))
    std_scores = 1.0 - float(np.exp(-1.0 * grayscale_std * BLURRY_NORM_FACTOR))
    if std_scores <= BLURRY_COLOR_THRESHOLD:
        std_scores = 0.0
    return float(min(blur_scores + std_scores, 1.0))


def _compute_entropy(cv_img) -> float:
    """计算图像熵（基于灰度直方图）
    范围 0~8（8 bit 灰度，最大熵 log2(256)=8）
    """
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    hist = hist / (hist.sum() + 1e-12)
    nonzero = hist[hist > 0]
    return float(-np.sum(nonzero * np.log2(nonzero)))


def _check_grayscale(cv_img) -> bool:
    """检测是否为灰度图像（R==G==B 对所有像素成立）"""
    if len(cv_img.shape) < 3 or cv_img.shape[2] < 3:
        return True
    b, g, r = cv_img[:, :, 0], cv_img[:, :, 1], cv_img[:, :, 2]
    return bool(np.array_equal(r, g) and np.array_equal(g, b))


def _extract_features(file_path: str, sample_no: str, sample_name: str) -> ImageFeatures:
    """提取单张图片的所有特征"""
    feat = ImageFeatures(file_path=file_path, sample_no=sample_no, sample_name=sample_name)
    image_bytes = _read_image_bytes(file_path)
    if not image_bytes:
        feat.load_failed = True
        return feat

    try:
        pil_img, cv_img = _decode_image(image_bytes)
        if cv_img is None:
            feat.load_failed = True
            return feat

        feat.width = pil_img.width
        feat.height = pil_img.height
        feat.md5_hash = _compute_md5(pil_img)
        feat.phash_value = _compute_phash(pil_img)
        feat.mean_brightness = _compute_brightness(cv_img)
        feat.blurriness_score = _compute_blurriness(pil_img)
        feat.entropy = _compute_entropy(cv_img)
        feat.is_grayscale = _check_grayscale(cv_img)
    except Exception as e:
        logger.warning(f"特征提取失败: {file_path}, error: {e}")
        feat.load_failed = True

    return feat


# ============================================================================
# 检测算法
# ============================================================================

def _detect_per_image_issues(feat: ImageFeatures, configured_issues: set) -> set:
    """单图级检测：返回该图命中的问题类型集合"""
    hits = set()
    if feat.load_failed:
        return hits

    if "blurry" in configured_issues and feat.blurriness_score < BLURRY_THRESHOLD:
        hits.add("blurry")
    if "dark" in configured_issues and feat.mean_brightness < DARK_THRESHOLD:
        hits.add("dark")
    if "light" in configured_issues and feat.mean_brightness > LIGHT_THRESHOLD:
        hits.add("light")
    if "low_information" in configured_issues and feat.entropy < LOW_INFO_THRESHOLD:
        hits.add("low_information")
    if "grayscale" in configured_issues and feat.is_grayscale:
        hits.add("grayscale")
    return hits


def _hamming_distance(a: int, b: int) -> int:
    """计算两个 64-bit 整数的汉明距离"""
    return bin(a ^ b).count("1")


def _detect_exact_duplicates(features: list, configured_issues: set) -> dict:
    """完全重复检测：按 MD5 分组，每组保留第一张，其余标记为问题图片

    Returns:
        {file_path: SetLevelIssue} 待移除图片映射，repeat_file_path 指向保留方(A图)
    """
    if "exact_duplicates" not in configured_issues:
        return {}

    groups = defaultdict(list)
    for feat in features:
        if feat.load_failed or not feat.md5_hash:
            continue
        groups[feat.md5_hash].append(feat)

    problems = {}
    for md5, group in groups.items():
        if len(group) < 2:
            continue
        # 保留第一张(A图)，其余标记为问题
        keeper = group[0]
        for feat in group[1:]:
            problems[feat.file_path] = SetLevelIssue(
                issue="exact_duplicates",
                repeat_file_path=keeper.file_path,
            )
    return problems


def _detect_near_duplicates(features: list, configured_issues: set) -> dict:
    """近似重复检测：pHash 汉明距离 < 阈值

    采用分组策略：相同 pHash 高 32 位的图片先粗筛，再两两精比较，降低 O(n²) 复杂度。

    Returns:
        {file_path: SetLevelIssue} 待移除图片映射（每组保留第一张），repeat_file_path 指向保留方(A图)
    """
    if "near_duplicates" not in configured_issues:
        return {}

    candidates = [f for f in features if not f.load_failed and f.phash_value > 0]
    if len(candidates) < 2:
        return {}

    # 按高 32 位分桶，仅同桶内两两比较
    buckets = defaultdict(list)
    for feat in candidates:
        high_bits = feat.phash_value >> 32
        buckets[high_bits].append(feat)

    # 额外检查相邻桶（高 32 位差 1）
    sorted_keys = sorted(buckets.keys())
    pair_buckets = defaultdict(list)
    for k in sorted_keys:
        pair_buckets[k] = list(buckets[k])
        if k - 1 in buckets:
            pair_buckets[k].extend(buckets[k - 1])

    problems = {}
    visited = set()  # 已被标记为重复的图片不再作为"保留"方
    for bucket_key, bucket_feats in pair_buckets.items():
        if len(bucket_feats) < 2:
            continue
        n = len(bucket_feats)
        for i in range(n):
            if bucket_feats[i].file_path in visited:
                continue
            for j in range(i + 1, n):
                if bucket_feats[j].file_path in visited:
                    continue
                dist = _hamming_distance(bucket_feats[i].phash_value, bucket_feats[j].phash_value)
                if dist < NEAR_DUP_THRESHOLD:
                    # 保留 i(A图)，标记 j 为重复
                    keeper = bucket_feats[i]
                    visited.add(bucket_feats[j].file_path)
                    problems[bucket_feats[j].file_path] = SetLevelIssue(
                        issue="near_duplicates",
                        repeat_file_path=keeper.file_path,
                    )
    return problems


def _detect_odd_aspect_ratio(features: list, configured_issues: set) -> dict:
    """宽高比异常：与 CleanVision 一致的固定阈值法

    score = min(width/height, height/width)，始终 ∈ (0, 1]
    score < threshold 判定为异常（默认 threshold=0.35）

    等价于：宽高比 > 1/0.35 ≈ 2.86 或 < 0.35 算异常
    - 正方形 1:1 → score=1.0 → 正常
    - 16:9 → score=0.5625 → 正常
    - 3:1 → score=0.333 → 异常
    - 10:1 → score=0.1 → 异常
    """
    if "odd_aspect_ratio" not in configured_issues:
        return {}

    valid = [f for f in features if not f.load_failed and f.width > 0 and f.height > 0]
    if not valid:
        return {}

    threshold = ASPECT_RATIO_THRESHOLD
    problems = {}
    for feat in valid:
        ratio = feat.width / feat.height
        score = min(ratio, 1.0 / ratio)
        if score < threshold:
            problems[feat.file_path] = SetLevelIssue(issue="odd_aspect_ratio")
    return problems


def _detect_odd_size(features: list, configured_issues: set) -> dict:
    """异常大小：基于集合 IQR 检测分辨率离群点

    增加绝对最小面积阈值作为兜底：当 IQR 下限为负数时（数据集分辨率差异大导致），
    使用 MIN_AREA_THRESHOLD 确保能检出真正的小尺寸异常图片。
    """
    if "odd_size" not in configured_issues:
        return {}

    valid = [f for f in features if not f.load_failed and f.width > 0 and f.height > 0]
    if len(valid) < 4:
        return {}

    areas = np.array([f.width * f.height for f in valid])
    q1, q3 = np.percentile(areas, [25, 75])
    iqr = q3 - q1
    lower = q1 - IQR_K * iqr
    upper = q3 + IQR_K * iqr

    # 兜底机制：IQR 下限为负数时，使用绝对最小面积阈值
    if lower < 0:
        lower = MIN_AREA_THRESHOLD

    problems = {}
    for feat in valid:
        area = feat.width * feat.height
        if area < lower or area > upper:
            problems[feat.file_path] = SetLevelIssue(issue="odd_size")
    return problems


# ============================================================================
# 文件移动（本地/MinIO 双适配）
# ============================================================================

def _move_image_to_quarantine(file_path: str, task_no: str, file_name_hint: str = "") -> str:
    """将问题图片移动到隔离区，返回新路径

    本地模式：移动到 sample_upload_dir/clean_result/{task_no}/{filename}
    MinIO 模式：上传到 minio://bucket/clean_result/{task_no}/{filename}，删除原对象
    """
    src_name = file_name_hint or os.path.basename(file_path)
    if not src_name:
        src_name = f"image_{hash(file_path) & 0xFFFF:x}"

    if is_minio_path(file_path):
        # MinIO 模式：下载后上传到隔离前缀，再删除原对象
        quarantine_set_no = f"clean_result/{task_no}"
        try:
            image_bytes = download_image(file_path)
            # 推断 Content-Type
            ext = os.path.splitext(src_name)[1].lower()
            ct_map = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
                ".tif": "image/tiff", ".tiff": "image/tiff",
            }
            content_type = ct_map.get(ext, "application/octet-stream")
            new_path = upload_image(quarantine_set_no, src_name, image_bytes, content_type=content_type)
            delete_object(file_path)
            return new_path
        except Exception as e:
            logger.error(f"MinIO 移动失败: {file_path}, error: {e}")
            raise

    # 本地模式
    base_dir = getattr(settings, "sample_upload_dir", "") or os.path.abspath("uploads")
    target_dir = os.path.join(base_dir, "clean_result", task_no)
    os.makedirs(target_dir, exist_ok=True)
    dst_path = os.path.join(target_dir, src_name)

    # 同名冲突处理
    if os.path.exists(dst_path):
        name, ext = os.path.splitext(src_name)
        dst_path = os.path.join(target_dir, f"{name}_{hash(file_path) & 0xFFFF:x}{ext}")

    shutil.move(file_path, dst_path)
    return dst_path


# ============================================================================
# 主流程
# ============================================================================

def execute_image_clean_task(
    task: dict,
    task_no: str,
    set_no: str,
    clean_type_codes: list,
    deps: dict,
    log_id: int = None,
) -> dict:
    """执行图像清洗任务主入口（异步后台线程调用）

    设计原则：
    1. 检测与移动分离：检测阶段仅收集问题 sample_no，不移动任何文件；
       所有检测完成后统一进入移动阶段，保证可回滚性。
    2. 多线程特征提取：使用 ThreadPoolExecutor 并行下载/解码，主线程统一写日志。
    3. 线程安全：worker 只做 IO + 计算，不写数据库；日志写入由主线程串行执行。

    Args:
        task: 任务对象（含 task_name 等）
        task_no: 任务编号
        set_no: 原始样本集编号
        clean_type_codes: 清洗类型编码列表（PIC_CLEAN_TYPE.CODE_VALUE）
        deps: 依赖注入字典，包含数据库操作函数：
            - update_clean_task_status
            - insert_clean_log, append_clean_log, finish_clean_log
            - query_pic_clean_type_dict
            - query_original_samples (返回 sample_no/sample_name/file_path)
            - insert_clean_pic_record
            - delete_original_sample_info_by_path
        log_id: 已创建的日志记录 ID（API 层传入）

    Returns:
        {"code": 0/1, "message": str, "data": {...})}

    注意：任务状态"执行中"(02)已在 API 层启动后台线程前更新，
    此处不再重复更新。日志记录也已在 API 层创建，使用传入的 log_id。
    """
    update_clean_task_status = deps["update_clean_task_status"]
    insert_clean_log = deps["insert_clean_log"]
    append_clean_log = deps["append_clean_log"]
    finish_clean_log = deps["finish_clean_log"]
    finish_clean_task_and_log = deps["finish_clean_task_and_log"]
    query_pic_clean_type_dict = deps["query_pic_clean_type_dict"]
    insert_clean_pic_record = deps["insert_clean_pic_record"]
    # 批量插入函数（可选依赖，缺失时回退到逐条插入）
    insert_clean_pic_records_batch = deps.get("insert_clean_pic_records_batch")
    # 标记法：批量更新清洗标记（替代旧的 delete_original_sample_info_by_path）
    batch_update_clean_flag = deps.get("batch_update_clean_flag")
    query_original_samples = deps.get("query_original_samples")

    total_count = 0
    removed_count = 0

    try:
        logger.info(f"继续执行图像清洗任务：{task.get('task_name', task_no)}")

        # 1. 解析清洗类型字典
        append_clean_log(log_id, "正在加载清洗类型配置...")
        dict_rows = query_pic_clean_type_dict()
        code_to_issue = {}  # {CODE_VALUE: SPARE1}
        for row in dict_rows:
            code_val = row.get("CODE_VALUE", "")
            spare1 = row.get("SPARE1", "")
            code_name = row.get("CODE_NAME", "")
            if code_val in clean_type_codes and spare1:
                code_to_issue[code_val] = spare1

        if not code_to_issue:
            raise ValueError("配置的清洗类型在字典中未找到对应记录")

        configured_issues = set(code_to_issue.values())
        type_names = ', '.join(ISSUE_NAMES.get(s, s) for s in configured_issues)
        append_clean_log(log_id, f"配置的检测类型：{type_names}")
        logger.info(f"配置的检测类型：{type_names}")

        # 2. 查询原始样本列表
        append_clean_log(log_id, "正在查询样本文件路径...")
        if not query_original_samples:
            raise ValueError("缺少依赖 query_original_samples")
        samples = query_original_samples(set_no)
        # samples 应为 list[dict]: {sample_no, sample_name, file_path}

        if not samples:
            raise ValueError(f"原始样本集下未找到样本文件（set_no={set_no}）")

        total_count = len(samples)
        append_clean_log(log_id, f"共 {total_count} 个样本文件")
        logger.info(f"共 {total_count} 个样本文件")

        # ============ 阶段一：分批多线程提取特征 ============
        # worker 只做：下载 + 解码 + 特征提取，不写日志不写数据库
        # 主线程串行写日志，保证日志顺序与线程安全
        append_clean_log(log_id, f"开始提取图片特征（分批 {BATCH_SIZE} 张/批，{MAX_WORKERS} 线程并行）...")
        all_features: list[ImageFeatures] = []
        failed_count = 0

        for batch_start in range(0, len(samples), BATCH_SIZE):
            batch = samples[batch_start:batch_start + BATCH_SIZE]
            # 过滤掉无 file_path 的样本
            batch_tasks = [
                (s.get("file_path") or "", str(s.get("sample_no") or ""), s.get("sample_name") or "")
                for s in batch if s.get("file_path")
            ]
            if not batch_tasks:
                continue

            # 多线程提取本批特征
            batch_features: list[ImageFeatures] = []
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(batch_tasks))) as executor:
                future_to_task = {
                    executor.submit(_extract_features, fp, sno, sname): (fp, sno)
                    for fp, sno, sname in batch_tasks
                }
                for future in as_completed(future_to_task):
                    try:
                        feat = future.result()
                        batch_features.append(feat)
                        if feat.load_failed:
                            failed_count += 1
                    except Exception as e:
                        # 单张失败不影响整体
                        fp, sno = future_to_task[future]
                        logger.warning(f"特征提取异常: {fp}, {e}")
                        failed_count += 1
                        batch_features.append(ImageFeatures(
                            file_path=fp, sample_no=sno, sample_name="", load_failed=True
                        ))

            all_features.extend(batch_features)

            # 进度日志（主线程串行写入）
            processed = min(batch_start + BATCH_SIZE, len(samples))
            append_clean_log(log_id, f"特征提取进度：{processed}/{total_count}")
            logger.info(f"特征提取进度：{processed}/{total_count}")

        append_clean_log(log_id, f"特征提取完成，失败 {failed_count} 张")
        logger.info(f"特征提取完成，失败 {failed_count} 张")

        # ============ 阶段二：执行所有检测（不移动任何文件）============
        # 检测结果以 sample_no 为 key 收集，便于后续统一移动
        append_clean_log(log_id, "正在执行单图级检测...")
        # {sample_no: set(issue_names)} 每张图命中的问题集合
        problems_by_sample_no: dict[str, set] = defaultdict(set)
        per_image_issues = configured_issues & PER_IMAGE_ISSUES
        for feat in all_features:
            hits = _detect_per_image_issues(feat, per_image_issues)
            if hits:
                problems_by_sample_no[feat.sample_no] |= hits

        append_clean_log(log_id, "正在执行集合级检测...")
        set_level_results: dict[str, SetLevelIssue] = {}
        # 按优先级合并：完全重复 > 近似重复 > 宽高比 > 大小
        # 同一 file_path 只保留首个（最高优先级）检测结果，
        # 避免完全重复被近似重复覆盖（对齐 CleanVision _remove_exact_duplicates_from_near）
        for detect_fn in [
            _detect_exact_duplicates,
            _detect_near_duplicates,
            _detect_odd_aspect_ratio,
            _detect_odd_size,
        ]:
            result = detect_fn(all_features, configured_issues)
            for fp, issue_item in result.items():
                if fp not in set_level_results:
                    set_level_results[fp] = issue_item

        # 合并集合级结果到 problems_by_sample_no
        # 集合级检测返回 {file_path: SetLevelIssue}，需转换为 sample_no
        path_to_feat = {f.file_path: f for f in all_features}
        # 重复检测的对比图(A图)原始路径映射: {B图sample_no: A图原始file_path}
        repeat_map_by_sample_no: dict[str, str] = {}
        for file_path, issue_item in set_level_results.items():
            feat = path_to_feat.get(file_path)
            if feat:
                problems_by_sample_no[feat.sample_no].add(issue_item.issue)
                if issue_item.repeat_file_path:
                    # 同一图实际不会同时命中两种重复检测，setdefault 防御性保留首个
                    repeat_map_by_sample_no.setdefault(feat.sample_no, issue_item.repeat_file_path)

        # 移除空问题集合（防御性）
        problems_by_sample_no = {k: v for k, v in problems_by_sample_no.items() if v}

        # ============ 阶段三：标记问题图片（CLEAN_FLAG=1，不移动文件） ============
        # 检测全部完成，开始统一标记。此阶段前任何失败都不会影响原始数据。
        problem_count = len(problems_by_sample_no)
        append_clean_log(log_id, f"检测完成，共发现 {problem_count} 张问题图片，开始标记...")
        logger.info(f"检测完成，共发现 {problem_count} 张问题图片")

        issue_to_code = {v: k for k, v in code_to_issue.items()}
        marked_count = 0
        mark_failed_count = 0

        # 第一步: 收集问题图片的 sample_no，批量标记 CLEAN_FLAG=1
        problem_sample_nos = []
        # 待写记录列表: (sample_no, feat)
        marked_records: list[tuple[str, ImageFeatures]] = []

        for sample_no, issue_set in problems_by_sample_no.items():
            feat = next((f for f in all_features if f.sample_no == sample_no), None)
            if not feat:
                continue
            problem_sample_nos.append(sample_no)
            marked_records.append((sample_no, feat))

        # 批量更新清洗标记
        if problem_sample_nos and batch_update_clean_flag is not None:
            try:
                marked_count = batch_update_clean_flag(problem_sample_nos, "1")
                logger.info(f"批量标记 CLEAN_FLAG=1: {marked_count} 条")
            except Exception as e_mark:
                logger.exception(f"批量标记清洗标记失败: {e_mark}")
                mark_failed_count = len(problem_sample_nos)
        elif problem_sample_nos:
            mark_failed_count = len(problem_sample_nos)
            logger.warning("batch_update_clean_flag 未注入，跳过标记步骤")

        # 第二步: 收集所有清洗记录并批量插入（file_path 存原始路径，不再移动文件）
        clean_records_to_insert = []
        for sample_no, feat in marked_records:
            issue_set = problems_by_sample_no[sample_no]

            # 查找对比图(A图)信息（A图仍在原位置，直接用原始路径）
            repeat_file_name = ""
            repeat_file_path = ""
            a_original_path = repeat_map_by_sample_no.get(sample_no)
            if a_original_path:
                repeat_file_path = a_original_path
                a_feat = path_to_feat.get(a_original_path)
                repeat_file_name = a_feat.sample_name if a_feat else os.path.basename(a_original_path)

            # 构建清洗记录（file_path 存原始路径，用于 serve-image 展示）
            clean_type_str = ",".join(sorted(issue_to_code[i] for i in issue_set if i in issue_to_code))
            clean_records_to_insert.append({
                "task_no": task_no,
                "clean_type": clean_type_str,
                "file_name": feat.sample_name,
                "file_path": feat.file_path,
                "clean_log_id": log_id,
                "repeat_file_name": repeat_file_name,
                "repeat_file_path": repeat_file_path,
                "sample_no": feat.sample_no,
            })

        # 批量插入清洗记录（单连接单事务）
        if clean_records_to_insert:
            if insert_clean_pic_records_batch is not None:
                # 优先走批量插入
                try:
                    insert_clean_pic_records_batch(clean_records_to_insert)
                    logger.info(f"批量插入清洗记录 {len(clean_records_to_insert)} 条")
                except Exception as e_batch:
                    logger.exception(f"批量插入清洗记录失败，回退到逐条插入: {e_batch}")
                    # 回退到逐条插入（单条失败不阻断整体流程）
                    for rec in clean_records_to_insert:
                        try:
                            insert_clean_pic_record(
                                rec["task_no"], rec["clean_type"], rec["file_name"], rec["file_path"],
                                clean_log_id=rec["clean_log_id"],
                                repeat_file_name=rec["repeat_file_name"],
                                repeat_file_path=rec["repeat_file_path"],
                                sample_no=rec.get("sample_no"),
                            )
                        except Exception as e_single:
                            logger.warning(f"单条插入清洗记录失败: {rec['file_name']}, {e_single}")
            else:
                # 兼容旧版 clean.py（未注入批量函数）：逐条插入
                for rec in clean_records_to_insert:
                    try:
                        insert_clean_pic_record(
                            rec["task_no"], rec["clean_type"], rec["file_name"], rec["file_path"],
                            clean_log_id=rec["clean_log_id"],
                            repeat_file_name=rec["repeat_file_name"],
                            repeat_file_path=rec["repeat_file_path"],
                            sample_no=rec.get("sample_no"),
                        )
                    except Exception as e_single:
                        logger.warning(f"单条插入清洗记录失败: {rec['file_name']}, {e_single}")

        removed_count = marked_count
        result_count = total_count - removed_count
        msg = f"标记完成：成功标记 {marked_count} 张问题图片（CLEAN_FLAG=1），失败 {mark_failed_count} 张"
        append_clean_log(log_id, msg)
        logger.info(msg)

        # 原子完成：在同一个事务中同时更新任务状态和日志状态
        # 确保前端轮询看到日志"已完成"时，任务状态也一定已更新，所有操作已真正完成
        finish_clean_task_and_log(
            task_no=task_no, task_status="03", last_execute_flag=1,
            record_id=log_id, execute_status="03",
            total_count=total_count, removed_count=removed_count, result_count=result_count,
            log_content="图像清洗执行完成，问题图片已标记（CLEAN_FLAG=1）",
        )
        logger.info(f"图像清洗任务 {task_no} 执行完成")

        return {
            "code": 0,
            "message": f"执行成功，共检测 {total_count} 张图片，标记 {removed_count} 张问题图片",
            "data": {"fileName": "", "filePath": "", "resultCount": result_count},
        }

    except Exception as e:
        err_msg = str(e)
        logger.exception("图像清洗任务执行异常")
        # 原子完成：在同一个事务中同时更新任务状态和日志状态
        try:
            if log_id:
                finish_clean_task_and_log(
                    task_no=task_no, task_status="04", last_execute_flag=2,
                    record_id=log_id, execute_status="04",
                    total_count=total_count, removed_count=removed_count,
                    result_count=total_count - removed_count,
                    log_content=f"执行失败：{err_msg}",
                )
            else:
                update_clean_task_status(task_no, "04", last_execute_flag=2)
        except Exception:
            pass
        return {"code": 1, "message": f"执行失败: {err_msg}"}
