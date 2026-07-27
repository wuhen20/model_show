# 时序数据清洗算子说明文档

## 一、背景与概述

时序数据清洗采用**画布式流程编排**：用户在前端画布上拖拽算子节点并连线，后端按连线顺序依次执行各算子，对数据进行去重、空值补全、异常值处理、日期格式标准化等清洗操作，最终生成 JSON 格式的清洗结果文件。

- 管道入口：[backend/app/services/clean_operators/pipeline.py](../backend/app/services/clean_operators/pipeline.py) 中 `execute_clean_pipeline`
- 路由层：[backend/app/api/routes/clean.py](../backend/app/api/routes/clean.py) 中 `_execute_timeseries_clean_task`（后台线程异步执行）
- 算子目录：[backend/app/services/clean_operators/](../backend/app/services/clean_operators/)

## 二、整体架构

### 算子注册表

所有算子通过 `node_type` 注册到 `OPERATOR_REGISTRY`，管道按节点类型查找对应算子类执行。

| node_type | 算子类 | 文件 | 中文名 |
|-----------|--------|------|--------|
| source | SourceOperator | source.py | 数据源 |
| dedup | DedupOperator | dedup.py | 去重 |
| nullfill | NullfillOperator | nullfill.py | 通用空值处理 |
| nullfill_short | NullfillShortOperator | nullfill_short.py | 短期空值处理 |
| nullfill_medium | NullfillMediumOperator | nullfill_medium.py | 中期空值处理 |
| nullfill_long | NullfillLongOperator | nullfill_long.py | 长期空值处理 |
| outlier | OutlierOperator | outlier.py | 异常值处理 |
| dateformat | DateFormatOperator | dateformat.py | 日期格式标准化 |
| str2num | StrReplaceOperator | str_replace.py | 字符替换 |

> 注：`str2num` 是字符替换算子的历史 node_type，为兼容已存数据库配置而保留，实际逻辑为精确字符串替换。

### 算子基类与上下文

```python
class BaseOperator(ABC):
    node_type: str = ""

    @abstractmethod
    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        """执行算子逻辑，直接修改 ctx.df / ctx.total_count / ctx.removed_count，
        通过 ctx.log() 写日志。"""
```

`CleanContext` 在算子之间传递状态，关键字段：

| 字段 | 说明 |
|------|------|
| `df` | pandas.DataFrame，由 source 算子初始化，后续算子原地修改 |
| `columns` | 列名有序列表，由 source 算子填充 |
| `col_lower_map` | 小写列名 → 原始列名 映射，用于忽略大小写匹配字段 |
| `total_count` | 原始数据条数 |
| `removed_count` | 累计移除条数（去重、删除空值行等累加） |
| `log()` | 追加日志，同时写入数据库日志和系统日志 |

### 管道执行流程

```
1. 读取任务节点（raw_nodes）
2. _reorder_nodes_by_prev：根据 prev_node_id 重建画布连线顺序
   - 起点：prev_node_id 为 None 或空的节点
   - 沿链查找：prev_node_id == 上一节点 node_id
   - 孤立节点（未连入主链）按原顺序追加
3. 校验起点必须是 source
4. 创建 CleanContext
5. 按顺序执行各算子：
   for node in nodes:
       operator = OPERATOR_REGISTRY[node_type]()
       operator.execute(ctx, node, json.loads(node_config))
6. 生成清洗结果 JSON 文件（本地保存 / 上传 MinIO）
7. finish_clean_task_and_log：原子更新任务状态(03成功) + 日志状态
```

### 列名大小写处理

Oracle 数据库 `rowfactory` 会将列名统一转小写，且配置中的字段名大小写可能与数据库不一致。处理方式：

- source 算子读取时，Oracle 列名统一转小写存入 `columns`
- 构建 `col_lower_map = {列名小写: 原始列名}`
- 各算子通过 `ctx.col_lower_map[f.lower()]` 将配置字段名映射到 DataFrame 实际列名

## 三、算子详解

### 1. 数据源算子（source）

**作用**：读取数据库表数据，初始化 DataFrame，是流程的必选起点。

**配置项**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| tableName | string | 是 | 数据源表名 |

**实现**：

```python
conn = get_connection()
with conn.cursor() as cursor:
    _execute(cursor, _select_all_from(table_name))
    # Oracle 列名转小写，其他数据库保留原样
    if _is_oracle():
        columns = [desc[0].lower() for desc in cursor.description]
    else:
        columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
ctx.df = pd.DataFrame([dict(r) for r in rows], columns=columns)
ctx.col_lower_map = {c.lower(): c for c in ctx.df.columns}
```

**要点**：
- `SELECT *` 全表读取，无分页
- `_CiDict` 行对象转为普通 dict 避免 Oracle 大小写匹配问题
- 初始化 `total_count` 和 `col_lower_map` 供后续算子使用

### 2. 去重算子（dedup）

**作用**：按指定字段组合去重，保留首次出现的行，移除后续重复行。

**配置项**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| fields | string[] | 是 | 去重判定字段列表 |

**算法**：

```python
seen = set()
for row in rows:
    # 字段值拼接为元组作为唯一键（值统一转字符串）
    key = tuple(str(row.get(f, "")) for f in dedup_fields)
    if key not in seen:
        seen.add(key)
        deduped.append(row)
```

**要点**：
- 字段值统一 `str()` 转换后比较，避免类型差异（如 `1` vs `"1"`）
- 空值转为空字符串 `""` 参与 key 构建
- 移除条数累加到 `ctx.removed_count`

### 3. 通用空值处理算子（nullfill）

**作用**：提供 10 种空值处理策略，是空值处理的基础算子。短期/中期/长期空值算子在配置为统一策略时均委托给本算子。

**配置项**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| fields | string[] | 是 | - | 空值处理字段列表 |
| strategy | string | 否 | drop | 处理策略（见下表） |
| fillValue | string | 否 | "" | strategy=fill 时的填充值 |
| treatZeroAsNull | bool | 否 | false | 是否将数值列的 0 视为空值 |

**支持的策略**：

| strategy | 中文名 | 作用方向 | 说明 |
|----------|--------|---------|------|
| drop | 删除空值行 | - | 删除含空值的整行 |
| fill | 填充固定值 | - | 用 fillValue 填充，数值列自动转型 |
| ffill | 前向填充 | 纵向 | 用上一行的值填充 |
| bfill | 后向填充 | 纵向 | 用下一行的值填充 |
| interpolate | 线性插值 | 纵向 | pandas 线性插值，保留 4 位小数 |
| mean | 均值填充 | 纵向 | 用列均值填充，保留 4 位小数 |
| median | 中位数填充 | 纵向 | 用列中位数填充，保留 4 位小数 |
| hfill_forward | 横向向前填充 | 横向 | 用同行前一字段的值填充 |
| hfill_backward | 横向向后填充 | 横向 | 用同行后一字段的值填充 |
| hinterpolate | 横向插值 | 横向 | 同行字段间按列位置线性插值 |

**treatZeroAsNull 机制**：

当 `treatZeroAsNull=true` 时，数值列中值为 0 的单元格先被替换为 `NaN`，再按策略处理。仅对数值列生效，非数值列不受影响。

**数值型策略的转型**：

`interpolate` / `mean` / `median` 策略会先调用 `pd.to_numeric(df[f], errors="coerce")` 将字段转为数值类型，非数字字符串会被转为 `NaN`（会记录"非数值数据被转为空值"警告）。

**横向插值（hinterpolate）算法**：

对每行的缺失字段，在 fields 范围内向前/向后找最近的有效数值，按列位置做线性插值：

```python
interpolated = prev_val + (next_val - prev_val) * (col_pos - prev_pos) / (next_pos - prev_pos)
```

仅一端有值时直接用该端值填充；两端均无值时保留缺失。

### 4. 短期空值处理算子（nullfill_short）

**作用**：处理同行**单个字段缺失**（连续 1 个缺失点）的短期空值，采用横向滑动窗口均值补全。

**配置项**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| fields | string[] | 是 | - | 处理字段列表 |
| strategy | string | 否 | sliding_window | 策略，统一策略时委托 nullfill |
| windowSize | int | 否 | 3 | 滑动窗口大小（前后各取 N 个字段） |
| treatZeroAsNull | bool | 否 | false | 是否将 0 视为缺失 |

**策略分流**：

- 若 `strategy` 属于 nullfill 的 10 种统一策略，委托 `NullfillOperator` 执行
- 默认独有策略 `sliding_window`：横向滑动窗口均值

**sliding_window 算法**：

1. 按列在 `columns` 中的顺序排列 fields
2. 对每行检测连续缺失段
3. **只处理长度 = 1 的缺失段**（单个字段缺失）
4. 在缺失点前后各取 `windowSize` 个相邻字段的有效值
5. 用这些有效值的算术均值填充，保留 4 位小数

```python
# 收集窗口内有效值
win_vals = []
for k in range(current_idx - 1, max(current_idx - w - 1, -1), -1):
    nval = df.at[row, ordered[k][1]]
    if not _is_missing(nval, treat_zero_as_null):
        win_vals.append(float(nval))
# 后 w 个同理
filled_val = round(sum(win_vals) / len(win_vals), 4)
```

**判定边界**：连续缺失长度 ≠ 1 的段不处理（留给中期/长期算子）。

### 5. 中期空值处理算子（nullfill_medium）

**作用**：处理同行 **2-4 个连续字段缺失**的中期空值，采用横向拉格朗日插值补全。

**配置项**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| fields | string[] | 是 | - | 处理字段列表 |
| strategy | string | 否 | lagrange | 策略，统一策略时委托 nullfill |
| treatZeroAsNull | bool | 否 | false | 是否将 0 视为缺失 |

**策略分流**：同短期算子，统一策略委托 nullfill，默认独有策略 `lagrange`。

**lagrange 算法**：

1. 按列顺序排列 fields
2. 对每行检测连续缺失段，**只处理长度 2-4 的段**
3. 收集 gap 外的所有有效参考点
4. 参考点不足 2 个时跳过
5. 按距离 gap 中心排序，取最近的 6 个参考点（`margin=6`）
6. 用 `scipy.interpolate.lagrange` 构造多项式，对 gap 内每个位置求值
7. 结果保留 4 位小数

**数值稳定性兜底**：

当拉格朗日插值出现数值不稳定（参考值过大 `>1e308`、非有限值、线性代数错误）时，回退到线性插值（`_linear_fallback_row`）：用 gap 两端最近的有效值做线性插值，仅一端有值时用该端值填充。

```python
# 数值稳定性检查
if not np.all(np.isfinite(y_valid)) or np.max(np.abs(y_valid)) > 1e308:
    filled = _linear_fallback_row(...)  # 线性插值回退
    continue
try:
    poly = lagrange(x_valid, y_valid)
    for idx in range(s, e):
        val = float(poly(float(idx)))
except (ValueError, np.linalg.LinAlgError):
    filled = _linear_fallback_row(...)  # 线性插值回退
```

### 6. 长期空值处理算子（nullfill_long）

**作用**：处理同行**连续 ≥5 个字段缺失**且占比低于阈值的长期空值，采用 KNN 补全。

**配置项**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| fields | string[] | 是 | - | 处理字段列表 |
| strategy | string | 否 | knn | 策略，统一策略时委托 nullfill |
| knnK | int | 否 | 5 | KNN 的 K 值 |
| maxNanRatio | float | 否 | 0.5 | 连续缺失占比上限（超过则不处理） |
| treatZeroAsNull | bool | 否 | false | 是否将 0 视为缺失 |

**策略分流**：同上，默认独有策略 `knn`。

**长期缺失判定**：

```python
# 连续缺失 >= 5 个字段 且 占比 < maxNanRatio 才处理
if length >= 5 and (length / n_fields) < max_nan_ratio:
    long_gap_positions.add((row, field_name))
```

`maxNanRatio` 用于过滤"整行大部分缺失"的极端情况（占比超阈值的不补全，避免 KNN 无有效参考）。

**KNN 补全算法**：

1. 检测横向长期缺失位置集合 `long_gap_positions`
2. 构建 KNN 特征矩阵：用 DataFrame 中**所有数值列**作为特征（不止 fields）
3. `treatZeroAsNull=true` 时，特征矩阵中的 0 替换为 NaN
4. 过滤缺失过多的行（NaN 占比 > 60% 的行不参与训练）
5. 用 `sklearn.impute.KNNImputer` 补全（`weights="distance"` 距离加权）
6. **只填充 long_gap_positions 中的位置**，其他位置保持 KNN 补全前的值不变

```python
k = min(knn_k, int(valid_train_mask.sum()))  # K 不超过有效样本数
imputer = KNNImputer(n_neighbors=k, weights="distance")
imputed = imputer.fit_transform(feature_matrix)
# 仅回填长期缺失位置
for row, col_name in long_gap_positions:
    imputed_val = imputed[df.index.get_loc(row), ci]
    if should_fill and not np.isnan(imputed_val):
        df.at[row, col_name] = round(imputed_val, 4)
```

**要点**：
- KNN 利用全表数值列信息，比单纯横向插值更适合长段缺失
- 只填充检测出的长期缺失位置，避免误改其他空值（其他空值由前序算子处理）
- 有效样本不足 2 个时跳过

### 7. 异常值处理算子（outlier）

**作用**：检测数值字段中的异常值（负值、绝对值超阈值），将异常值置为 NaN。

**配置项**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| fields | string[] | 是 | - | 检测字段列表 |
| checkNegative | bool | 否 | true | 是否检测负值 |
| absThreshold | number | 否 | - | 绝对值阈值（≥0 生效） |
| strategy | string | 否 | setnull | 处理策略，目前仅支持 setnull |

**检测条件**：

两个条件可叠加（OR 关系）：

- `checkNegative=true`：任一字段值 < 0 判定为异常行
- `absThreshold ≥ 0`：任一字段绝对值 > 阈值判定为异常行

**处理逻辑（setnull）**：

逐字段构建单元格级掩码，将该字段中满足异常条件的**单元格**置为 NaN（不是整行删除）：

```python
for f in outlier_fields:
    cell_mask = pd.Series(False, index=df.index)
    if check_negative:
        cell_mask = cell_mask | (df[f] < 0)
    if threshold_val is not None and threshold_val >= 0:
        cell_mask = cell_mask | (df[f].abs() > threshold_val)
    df[f] = df[f].mask(cell_mask, np.nan)
```

**要点**：
- 字段会先转为数值类型（`pd.to_numeric` 非数字转 NaN）
- 使用 `df[f].mask()` 而非 `df.loc[...] = np.nan`，赋值更可靠
- 置空后会验证首行赋值结果并记录日志
- 置空后的 NaN 可由后续空值处理算子补全

### 8. 日期格式标准化算子（dateformat）

**作用**：将日期字段从多种源格式自动识别并统一转换为目标格式。

**配置项**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| field | string | 是 | - | 日期字段名（单个） |
| targetFormat | string | 否 | %Y-%m-%d | 目标格式，仅支持 YYYY-MM-DD / YYYY-MM-DD HH:MM:SS |

> **约束**：配置中**不含源格式**，由后端自动匹配 13 种常见格式。目标格式仅支持 `YYYY-MM-DD` 和 `YYYY-MM-DD HH:MM:SS` 两项。

**自动识别的 13 种格式**：

```
%Y-%m-%d %H:%M:%S.%f     2024-01-01 12:30:45.123
%Y-%m-%d %H:%M:%S        2024-01-01 12:30:45
%Y-%m-%d                 2024-01-01
%Y/%m/%d %H:%M:%S        2024/01/01 12:30:45
%Y/%m/%d                 2024/01/01
%Y%m%d%H%M%S             20240101123045
%Y%m%d                   20240101
%Y年%m月%d日 %H:%M:%S     2024年01月01日 12:30:45
%Y年%m月%d日              2024年01月01日
%d/%m/%Y %H:%M:%S        01/01/2024 12:30:45
%d/%m/%Y                 01/01/2024
%m-%d-%Y %H:%M:%S        01-01-2024 12:30:45
%m-%d-%Y                 01-01-2024
```

**匹配算法**：

1. 字段转为字符串（处理 varchar 和非 varchar 类型）
2. 依次尝试 13 种格式，用 `pd.to_datetime(format=fmt, errors="coerce")` 匹配
3. 已匹配的行从后续格式的尝试中排除（`remaining_mask`）
4. 13 种格式都无法解析的行，尝试 pandas 自动推断（`pd.to_datetime(errors="coerce")`）
5. 仍无法解析的行保留原值
6. 按目标格式 `strftime` 重新输出为字符串

**日志输出**：记录匹配到的格式（或"多种格式"/"自动推断"）、成功/失败行数。

### 9. 字符替换算子（str2num）

**作用**：对指定字段执行精确字符串替换，将 `replaceFrom` 替换为 `replaceTo`（可为空表示删除）。

**配置项**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| fields | string[] | 是 | 处理字段列表 |
| replaceFrom | string | 是 | 需替换的字符（非空） |
| replaceTo | string | 否 | 替换为的字符，空表示删除 |

**约束**：`fields` 和 `replaceFrom` 均不能为空，否则跳过。

**算法**：

```python
series = df[f].astype(str).where(df[f].notna(), "")
# 精确字符串替换（不使用正则）
df[f] = series.str.replace(replace_from, replace_to, regex=False)
```

**要点**：
- **精确字符串替换**：`regex=False`，不做正则转义，直接 `str.replace`
- **不做数值转换**：纯字符串操作，不会将 "123" 转为数字 123
- 空值（NaN）先转为空字符串 `""` 再参与替换
- `replaceTo` 为空时表示删除 `replaceFrom`（替换为空字符串）
- 每个字段单独统计替换行数并记录日志

## 四、空值处理策略体系

时序数据清洗的空值处理是核心能力，由 4 个算子协同构成**纵向 + 横向**、**短中长期分级**的完整体系。

### 纵向 vs 横向

| 方向 | 含义 | 适用策略 |
|------|------|---------|
| 纵向 | 沿行方向（同一列的不同行） | drop / fill / ffill / bfill / interpolate / mean / median |
| 横向 | 沿列方向（同一行的不同字段） | hfill_forward / hfill_backward / hinterpolate / sliding_window / lagrange / knn |

### 横向空值的短/中/长期分级

横向空值处理按同行连续缺失字段数分级，对应不同的补全算法：

| 级别 | 算子 | 连续缺失字段数 | 补全算法 | 占比约束 |
|------|------|--------------|---------|---------|
| 短期 | nullfill_short | 1（单个字段） | 滑动窗口均值 | 无 |
| 中期 | nullfill_medium | 2-4 | 拉格朗日插值 | 无 |
| 长期 | nullfill_long | ≥5 | KNN 补全 | 占比 < maxNanRatio（默认 0.5） |

**分级原理**：
- **短期**（1 个缺失）：缺失信息少，用相邻字段均值即可，简单高效
- **中期**（2-4 个缺失）：需要更精确的拟合，拉格朗日多项式插值能捕捉非线性趋势
- **长期**（≥5 个缺失）：横向信息不足以可靠插值，引入全表数值列做 KNN，利用样本间相似性补全

### 统一策略的委托机制

短期/中期/长期三个算子都支持 nullfill 的 10 种统一策略。当配置的 `strategy` 属于统一策略集合时，直接委托 `NullfillOperator` 执行，不再走横向分级逻辑：

```python
_UNIFIED_STRATEGIES = {
    "drop", "fill", "ffill", "bfill", "interpolate",
    "mean", "median", "hfill_forward", "hfill_backward", "hinterpolate",
}
if strategy in _UNIFIED_STRATEGIES:
    NullfillOperator().execute(ctx, node, config)
    return
```

这样设计允许用户在同一个算子上灵活切换"统一策略"或"分级独有策略"。

## 五、整体处理流程

### 异步执行架构

```
前端                          后端 API                    后台线程
 │                              │                          │
 │── POST /execute-clean-task ─>│                          │
 │                              │── 更新任务状态 02 ───────>│
 │                              │── 创建执行日志 log_id ───>│
 │                              │── 启动 daemon 线程 ──────>│
 │<── {async:true} 立即返回 ────│                          │
 │                              │                          │── execute_clean_pipeline
 │── setInterval 2s 轮询 ─────>│                          │   (按画布顺序执行算子)
 │   GET /query-clean-log       │                          │
 │<── 返回最新日志状态 ──────────│                          │
 │                              │                          │── 生成结果 JSON
 │   (status=03/04 停止轮询)    │                          │── finish_clean_task_and_log
 │                              │                          │   (原子更新任务+日志状态)
```

### 管道内部流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 读取任务节点，按 prev_node_id 重建画布连线顺序            │
├─────────────────────────────────────────────────────────────┤
│ 2. 校验起点必须是 source                                     │
├─────────────────────────────────────────────────────────────┤
│ 3. 创建 CleanContext                                         │
├─────────────────────────────────────────────────────────────┤
│ 4. 按顺序执行各算子：                                        │
│    source → dedup → nullfill* → outlier → dateformat → ...  │
│    每个算子：                                                │
│      - json.loads(node_config) 解析配置                      │
│      - OPERATOR_REGISTRY[node_type].execute(ctx, node, cfg) │
│      - 原地修改 ctx.df                                       │
│      - ctx.log() 写日志                                      │
├─────────────────────────────────────────────────────────────┤
│ 5. 生成清洗结果 JSON：                                       │
│    - DataFrame 转记录列表（NaN→null, Timestamp→isoformat）   │
│    - 本地模式：保存到 sample_upload_dir/clean_result/        │
│    - MinIO 模式：上传到 clean_result/ 前缀                   │
├─────────────────────────────────────────────────────────────┤
│ 6. finish_clean_task_and_log：原子更新任务状态(03) + 日志     │
│    - 任务状态 02→03(成功)/04(失败)                          │
│    - 日志状态 02→03(成功)/04(失败)                          │
│    - 写入 total_count / removed_count / result_count        │
│    - 写入结果文件 file_name / file_path                      │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计

- **画布连线顺序重建**：通过 `prev_node_id` 链式查找重建执行顺序，支持用户自定义算子执行顺序
- **原子状态更新**：`finish_clean_task_and_log` 在同一事务中更新任务状态和日志状态，确保前端轮询看到日志"已完成"时任务状态也已同步
- **结果文件双存储适配**：本地模式保存到 `clean_result/` 目录，MinIO 模式上传到 `clean_result/` 前缀，路径前缀 `minio://` 自动分流
- **算子无状态**：每个算子实例只执行一次 `execute`，状态全部通过 `CleanContext` 传递，无副作用

## 六、配置项参考

### 节点公共字段（存于 s_data_clean_task_node）

| 字段 | 说明 |
|------|------|
| node_id | 节点 ID |
| node_type | 节点类型（对应算子 node_type） |
| node_name | 节点名称 |
| node_config | 节点配置（JSON 字符串） |
| prev_node_id | 前一节点 ID（用于重建连线顺序） |
| pos_x / pos_y | 画布坐标（仅前端展示用） |

### 各算子配置项汇总

| 算子 | 配置项 | 默认值 |
|------|--------|--------|
| source | tableName | - |
| dedup | fields | - |
| nullfill | fields, strategy, fillValue, treatZeroAsNull | drop, "", false |
| nullfill_short | fields, strategy, windowSize, treatZeroAsNull | sliding_window, 3, false |
| nullfill_medium | fields, strategy, treatZeroAsNull | lagrange, false |
| nullfill_long | fields, strategy, knnK, maxNanRatio, treatZeroAsNull | knn, 5, 0.5, false |
| outlier | fields, checkNegative, absThreshold, strategy | -, true, -, setnull |
| dateformat | field, targetFormat | -, %Y-%m-%d |
| str2num | fields, replaceFrom, replaceTo | -, -, - |

## 七、依赖库

| 库 | 用途 | 版本要求 |
|----|------|---------|
| pandas | DataFrame 操作、日期解析、空值处理 | ≥1.3 |
| numpy | 数值计算 | ≥1.20 |
| scipy | 拉格朗日插值（nullfill_medium） | ≥1.7 |
| scikit-learn | KNN 补全（nullfill_long） | ≥1.0 |

## 八、文件清单

| 文件 | 说明 |
|------|------|
| backend/app/services/clean_operators/pipeline.py | 管道执行入口，按画布顺序执行算子 |
| backend/app/services/clean_operators/base.py | 算子基类 BaseOperator 与上下文 CleanContext |
| backend/app/services/clean_operators/__init__.py | 算子注册表 OPERATOR_REGISTRY |
| backend/app/services/clean_operators/source.py | 数据源算子 |
| backend/app/services/clean_operators/dedup.py | 去重算子 |
| backend/app/services/clean_operators/nullfill.py | 通用空值处理算子（10 种策略） |
| backend/app/services/clean_operators/nullfill_short.py | 短期空值处理算子（滑动窗口均值） |
| backend/app/services/clean_operators/nullfill_medium.py | 中期空值处理算子（拉格朗日插值） |
| backend/app/services/clean_operators/nullfill_long.py | 长期空值处理算子（KNN 补全） |
| backend/app/services/clean_operators/outlier.py | 异常值处理算子 |
| backend/app/services/clean_operators/dateformat.py | 日期格式标准化算子 |
| backend/app/services/clean_operators/str_replace.py | 字符替换算子（node_type=str2num） |
| backend/app/api/routes/clean.py | 路由层，`_execute_timeseries_clean_task` 后台线程包装 |
