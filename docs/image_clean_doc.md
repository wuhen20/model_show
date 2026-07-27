# 图像样本清洗改造说明

## 一、背景

原清洗流程使用 cleanvision 库，仅支持本地文件系统。为兼容对象存储（MinIO）模式，已替换为自实现版本。

- 原实现备份：[backend/app/services/_cleanvision_backup.py](../backend/app/services/_cleanvision_backup.py)（不会被调用）
- 新实现：[backend/app/services/image_clean_service.py](../backend/app/services/image_clean_service.py)
- 入口改造：[backend/app/api/routes/clean.py](../backend/app/api/routes/clean.py) 中 `_execute_image_clean_task`

## 二、支持的检测项

| 字典 SPARE1 | 中文名 | 检测级别 | 算法 |
|------------|--------|---------|------|
| blurry | 模糊 | 单图级 | FIND_EDGES + 灰度直方图 + 指数归一化 |
| dark | 过暗 | 单图级 | 灰度均值 |
| light | 过亮 | 单图级 | 灰度均值 |
| low_information | 信息量低 | 单图级 | 图像熵 |
| odd_aspect_ratio | 宽高比异常 | 单图级 | 固定阈值法（min比例） |
| grayscale | 灰度图像 | 单图级 | 通道一致性 |
| exact_duplicates | 完全重复 | 集合级 | MD5 哈希分组 |
| near_duplicates | 近似重复 | 集合级 | pHash 汉明距离 |
| odd_size | 异常大小 | 集合级 | 分辨率 IQR 离群点检测 |

## 三、检测算法详解

### 1. 模糊检测（blurry）

**算法**：FIND_EDGES 边缘检测 + 灰度直方图标准差 + 指数归一化（与 CleanVision 一致）

**原理**：对图像进行 FIND_EDGES 边缘滤波后计算像素方差（开根号），衡量边缘强度；同时计算灰度直方图标准差，衡量色彩分布丰富度。两者经指数归一化后综合评分，评分越低越模糊。

**预处理**：缩放到最长边 64px（`MAX_RESOLUTION_FOR_BLURRY`），使不同分辨率图像的评分落在可比范围内。

**实现**：
```python
from PIL import ImageFilter, ImageStat

# 1. 缩放到最长边 64px
ratio = max(pil_img.width, pil_img.height) / 64
resized = pil_img.resize((int(pil_img.width // ratio), int(pil_img.height // ratio)))
gray = resized.convert("L")

# 2. 边缘图方差开根号
blurriness = sqrt(ImageStat.Stat(gray.filter(FIND_EDGES)).var[0])

# 3. 灰度直方图标准差
grayscale_std = std(gray.histogram())

# 4. 归一化评分
blur_scores = 1 - exp(-blurriness * 0.01)
std_scores = 1 - exp(-grayscale_std * 0.01)
if std_scores <= 0.18:
    std_scores = 0
score = min(blur_scores + std_scores, 1)
```

**阈值**：`score < 0.29` 判定为模糊（可通过环境变量 `IMG_CLEAN_BLURRY` 调整）

**参数**（均可通过环境变量覆盖）：
- `IMG_CLEAN_BLURRY_NORM_FACTOR`（默认 0.01）：归一化因子
- `IMG_CLEAN_BLURRY_COLOR_THRESHOLD`（默认 0.18）：色彩评分置零阈值
- `IMG_CLEAN_BLURRY_MAX_RES`（默认 64）：缩放分辨率

**参考**：CleanVision `image_property.py` BlurrinessProperty 实现。

### 2. 过暗检测（dark）

**算法**：灰度均值

**实现**：
```python
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
mean = np.mean(gray)  # 0~255
```

**阈值**：`mean < 50` 判定为过暗（可通过 `IMG_CLEAN_DARK` 调整）

### 3. 过亮检测（light）

**算法**：灰度均值（同上）

**阈值**：`mean > 200` 判定为过亮（可通过 `IMG_CLEAN_LIGHT` 调整）

### 4. 信息量低检测（low_information）

**算法**：图像熵（Shannon Entropy）

**原理**：基于灰度直方图计算信息熵。熵越低，说明像素值分布越集中，图像信息量越少（如纯色背景、空白区域）。

**实现**：
```python
hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
hist = hist / hist.sum()
entropy = -sum(p * log2(p) for p in hist if p > 0)
```

**阈值**：`entropy < 4.5` 判定为信息量低（范围 0~8，可通过 `IMG_CLEAN_LOW_INFO` 调整）

### 5. 宽高比异常（odd_aspect_ratio）

**算法**：固定阈值法（与 CleanVision 一致）

**原理**：使用 `score = min(width/height, height/width)` 计算，score 始终 ∈ (0, 1]。score < threshold 判定为异常。

**实现**：
```python
ratio = width / height
score = min(ratio, 1.0 / ratio)  # 始终 ≤ 1
if score < threshold:
    # 异常（默认 threshold=0.35）
```

**阈值**：默认 0.35（可通过 `IMG_CLEAN_ASPECT_RATIO` 调整）

**阈值含义**：
- score < 0.35 → 宽高比 > **2.86:1** 或 < **1:2.86** 算异常
- score < 0.25 → 宽高比 > **4:1** 或 < **1:4** 算异常（更宽松）

**示例**：
| 宽高比 | score | 判定（threshold=0.35） |
|--------|-------|------------------------|
| 1:1（正方形） | 1.0 | 正常 |
| 16:9（横图） | 0.5625 | 正常 |
| 3:1 | 0.333 | 异常 |
| 10:1 | 0.1 | 异常 |

**为何不用 IQR**：
原实现采用基于集合的 IQR 统计法，但多样化图片集合（横图+竖图+方图混合）会导致 IQR 范围很大，正常图片也被误判为异常。固定阈值法是绝对标准，与集合无关，与 CleanVision 保持一致。

### 6. 灰度图像检测（grayscale）

**算法**：通道一致性检测

**原理**：彩色图像 R/G/B 三通道值不同；灰度图三通道值相同。

**实现**：
```python
b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
is_gray = np.array_equal(r, g) and np.array_equal(g, b)
```

**判定**：100% 像素满足 R==G==B 即为灰度图像。

### 7. 完全重复检测（exact_duplicates）

**算法**：基于解码像素的 MD5 哈希分组（与 CleanVision 一致）

**原理**：对图像解码后的像素数组计算 MD5，而非对文件字节计算。这样即使图片被复制、改文件名或重编码（文件字节不同但像素相同），仍能正确判定为完全重复。

**实现**：
```python
pixels = np.asarray(pil_img)
md5 = hashlib.md5(pixels.tobytes()).hexdigest()
# 按 md5 分组，每组保留第一张，其余标记为重复
```

**处理策略**：每个重复组保留第一张（A图），其余（B图）移动到隔离区。B图的 `repeat_file_path` 记录A图路径供前端对比展示。

**优先级**：当同一图片同时命中完全重复和近似重复时，只保留完全重复（对齐 CleanVision `_remove_exact_duplicates_from_near`）。

### 8. 近似重复检测（near_duplicates）

**算法**：感知哈希（pHash）+ 汉明距离

**原理**：pHash 通过 DCT 变换提取图像低频信息，对缩放、压缩、轻微修改具有鲁棒性。两张图 pHash 的汉明距离越小，越相似。

**实现**：
```python
from imagehash import phash
h = phash(pil_img, hash_size=8)  # 64-bit
# 计算两两汉明距离
distance = bin(hash1 ^ hash2).count("1")
```

**阈值**：`distance < 8` 判定为近似重复（可通过 `IMG_CLEAN_NEAR_DUP` 调整）

**性能优化**：避免 O(n²) 全量比较，采用分桶策略：
1. 取 pHash 高 32 位作为桶键
2. 仅同桶内两两比较
3. 额外检查相邻桶（高 32 位差 1）

**处理策略**：每组近似重复保留第一张，其余移动到隔离区。

### 9. 异常大小检测（odd_size）

**算法**：基于集合的分辨率 IQR 离群点检测

**原理**：与宽高比异常类似，使用图片面积（width × height）作为指标。

**实现**：
```python
areas = [f.width * f.height for f in features]
q1, q3 = np.percentile(areas, [25, 75])
iqr = q3 - q1
lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
```

**阈值**：1.5 倍 IQR（可通过 `IMG_CLEAN_IQR_K` 调整）

## 四、整体处理流程

### 异步执行架构

```
前端                          后端 API                    后台线程
 │                              │                          │
 │── POST /execute-clean-task ─>│                          │
 │                              │── 启动 daemon 线程 ──────>│
 │<── {async:true} 立即返回 ────│                          │
 │                              │                          │── 执行清洗任务
 │── setInterval 2s 轮询 ─────>│                          │   (特征提取/检测/移动)
 │   GET /query-clean-log       │                          │
 │<── 返回最新日志状态 ──────────│                          │
 │                              │                          │
 │   (status=03/04 停止轮询)    │                          │
 │                              │                          │── 更新任务状态
 │                              │                          │   02→03(成功)/04(失败)
```

### 后台线程处理流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 加载配置：解析清洗类型编码 → SPARE1 名称                  │
├─────────────────────────────────────────────────────────────┤
│ 2. 查询样本：query_original_samples(set_no)                  │
│    返回 [{sample_no, sample_name, file_path}, ...]          │
├─────────────────────────────────────────────────────────────┤
│ 3. 阶段一：分批多线程提取特征                                │
│    ┌──────────────────────────────────────────────────┐     │
│    │ for batch in samples[::BATCH_SIZE]:              │     │
│    │   ThreadPoolExecutor(max_workers=8):             │     │
│    │     并行执行：下载 + 解码 + 特征提取              │     │
│    │   # 主线程串行写日志，保证线程安全                │     │
│    └──────────────────────────────────────────────────┘     │
├─────────────────────────────────────────────────────────────┤
│ 4. 阶段二：执行所有检测（不移动任何文件）                    │
│    4.1 单图级：模糊/过暗/过亮/信息量低/灰度                  │
│    4.2 集合级：完全重复/近似重复/宽高比异常/异常大小          │
│    4.3 收集问题 sample_no 集合                              │
├─────────────────────────────────────────────────────────────┤
│ 5. 阶段三：统一移动问题图片                                  │
│    - 本地：shutil.move 到 sample_upload_dir/clean_result/    │
│    - MinIO：download → upload 到 clean_result/ 前缀 → delete │
│    - 插入 s_data_clean_pic 记录                              │
│    - 删除 s_original_sample_info 记录                        │
├─────────────────────────────────────────────────────────────┤
│ 6. 完成日志，更新任务状态                                    │
└─────────────────────────────────────────────────────────────┘
```

**关键设计**：
- **检测与移动分离**：阶段二只收集问题 sample_no，不移动文件；阶段三才统一移动。这样阶段二失败时原始文件未受影响。
- **多线程特征提取**：阶段一使用 `ThreadPoolExecutor` 并行下载/解码，主线程串行写日志保证线程安全。worker 只做 IO+计算，不访问数据库。

## 五、存储模式适配

### 本地存储模式（storage_type=01）

- 读取：`open(file_path, 'rb').read()`
- 移动：`shutil.move(src, dst)`，目标路径 `sample_upload_dir/clean_result/{task_no}/{filename}`

### MinIO 对象存储模式（storage_type=02）

- 读取：`download_image(file_path)`，自动解析 `minio://bucket/setNo/filename`
- 移动：先下载 bytes → 上传到 `clean_result/{task_no}/` 前缀 → 删除原对象
- 新路径格式：`minio://bucket/clean_result/{task_no}/{filename}`

### 路径自动分流

通过 `is_minio_path(file_path)` 判断（前缀 `minio://`），无需业务层感知存储模式。

## 六、内存与性能设计

### 异步执行机制

| 层 | 实现 | 说明 |
|----|------|------|
| API 层 | `threading.Thread(daemon=True)` | 启动后台线程，立即返回 `{"async": true}` |
| 前端 | `setInterval` 2 秒轮询 | 调用 `/query-clean-log` 获取最新日志状态 |
| 超时保护 | 30 分钟 | 超时自动停止轮询，提示用户手动刷新 |
| 重复执行保护 | 任务状态 02 时拒绝再次触发 | 防止并发执行同一任务 |

### 多线程特征提取

| 项 | 值 | 说明 |
|----|----|------|
| 线程池 | `ThreadPoolExecutor` | Python 标准库，无需额外依赖 |
| 线程数 | `MAX_WORKERS=8`（可配置） | IO 密集型场景，8 线程可充分利用带宽 |
| 批次大小 | `BATCH_SIZE=50`（可配置） | 每批提交线程池，批结束后释放图像数据 |
| 线程安全 | worker 不写日志/数据库 | 主线程串行写日志，避免并发冲突 |

**为何多线程有效**：
- MinIO 下载是 IO 密集型，GIL 在 IO 等待时释放
- cv2.imdecode 和 numpy 部分操作会释放 GIL
- 实测 8000 张图特征提取从单线程 ~10 分钟降至多线程 ~2 分钟（取决于网络带宽和 CPU 核数）

### 共享特征池

每张图提取后保留 `ImageFeatures` 数据类（约 100 字节），8000 张约 800KB，可控。

字段包括：宽高、MD5、pHash、亮度、拉普拉斯方差、熵、是否灰度。

### 检测与移动分离

```
阶段一：特征提取（不移动文件）
  ↓
阶段二：所有检测（仅记录问题 sample_no 到集合，不移动文件）
  ↓
阶段三：统一移动（遍历问题集合，逐个移动）
```

**优势**：
1. 阶段二失败时，原始文件完全未受影响，可重新执行
2. 阶段三移动失败的图片不影响其他图片，记录失败列表
3. 可在阶段二完成后、阶段三开始前插入"预览待移动列表"功能

### 集合级检测的复杂度

| 检测项 | 复杂度 | 8000 张预估耗时 |
|--------|--------|----------------|
| 完全重复 | O(n) | <1s |
| 近似重复 | O(n × k)，k 为桶大小 | 5~30s |
| 宽高比异常 | O(n) | <1s |
| 异常大小 | O(n) | <1s |

近似重复采用分桶策略，将 O(n²) 降至 O(n × k)，k 通常 < 50。

## 七、阈值配置

所有阈值支持通过环境变量覆盖，无需修改代码：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| IMG_CLEAN_BLURRY | 0.43 | 模糊检测：归一化评分上限（< 此值判定为模糊，范围 0~1） |
| IMG_CLEAN_BLURRY_NORM_FACTOR | 0.01 | 模糊检测：归一化因子（与 CleanVision normalizing_factor 一致） |
| IMG_CLEAN_BLURRY_COLOR_THRESHOLD | 0.18 | 模糊检测：色彩评分置零阈值（与 CleanVision color_threshold 一致） |
| IMG_CLEAN_BLURRY_MAX_RES | 64 | 模糊检测：缩放分辨率（最长边像素数） |
| IMG_CLEAN_DARK | 50 | 过暗检测：灰度均值下限 |
| IMG_CLEAN_LIGHT | 200 | 过亮检测：灰度均值上限 |
| IMG_CLEAN_LOW_INFO | 4.5 | 信息量低：图像熵下限 |
| IMG_CLEAN_ASPECT_RATIO | 0.35 | 宽高比异常：score 阈值（< 此值判定为异常） |
| IMG_CLEAN_NEAR_DUP | 8 | 近似重复：汉明距离上限 |
| IMG_CLEAN_IQR_K | 1.5 | IQR 离群点倍数（用于异常大小） |
| IMG_CLEAN_MIN_AREA | 10000 | 异常大小绝对最小面积阈值（像素数），当 IQR 下限为负数时作为兜底 |
| IMG_CLEAN_BATCH_SIZE | 50 | 分批处理大小 |
| IMG_CLEAN_MAX_WORKERS | 8 | 特征提取线程池大小 |

## 八、依赖库

| 库 | 用途 | 版本要求 |
|----|------|---------|
| opencv-python (cv2) | 图像处理、亮度/熵/灰度检测 | ≥4.5 |
| Pillow (PIL) | 图像解码、pHash 输入、模糊检测（FIND_EDGES/ImageStat） | ≥9.0 |
| imagehash | 感知哈希计算 | ≥4.0 |
| numpy | 数值计算 | ≥1.20 |

## 九、回滚机制

清洗支持回滚：将隔离区（`clean_result/{task_no}/`）中的图片移回原始样本集目录，恢复 `s_original_sample_info` 记录，并删除对应的 `s_data_clean_pic` 记录。

入口：[backend/app/api/routes/clean.py](../backend/app/api/routes/clean.py) 中 `rollback_clean_pics_api`，支持通过 `cleanLogId` 精确回滚某次执行结果（避免多次执行后回滚错误）。

### 处理流程

1. 查询任务节点获取原始样本集编号（set_no）及 set_path
2. 查询被清洗图片记录（优先 `cleanLogId` 精确查询，否则按 `taskNo`）
3. 按 file_path 去重，分离 MinIO 和本地两类任务
4. **MinIO 模式**：`ThreadPoolExecutor`（max_workers ≤ 8）并行执行 download → upload 回原前缀 → delete 隔离对象
5. **本地模式**：串行 `shutil.move`（同盘 rename 极快，无需并行），处理同名冲突
6. 收集成功项后统一 `batch_insert_original_sample_info` 批量插入，失败回退逐条插入
7. 删除 `s_data_clean_pic` 记录，清理空的隔离目录

### 关键设计

- **存储模式分流**：MinIO 走并行 IO（IO 密集），本地走串行 move（rename 仅元数据操作），各自发挥最优性能
- **批量入库**：恢复记录使用批量插入（executemany），失败自动回退逐条插入
- **错误隔离**：单张图片恢复失败不影响其他图片，失败项记录到 errors 列表
- **精确回滚**：`cleanLogId` 优先级高于 `taskNo`，支持多次执行后精确回滚某次结果

## 十、文件清单

| 文件 | 说明 |
|------|------|
| backend/app/services/image_clean_service.py | 新清洗服务（核心实现） |
| backend/app/services/_cleanvision_backup.py | 原 cleanvision 实现备份（已废弃） |
| backend/app/api/routes/clean.py | 路由层改造，调用新服务 |
| backend/app/core/database.py | 新增 query_original_samples 函数 |
