# 样本集删除功能实施计划

## Context

当前样本集卡片操作菜单中的"删除"按钮是 `disabled` 状态，无法点击。用户需要实现删除空样本集的功能，删除时需清理数据库记录和本地/MinIO 存储路径。

## 改动范围

### 1. 后端：新增删除函数（db_sample.py）

**`delete_sample_set(set_no: str)`** — 删除高质量样本集
- 检查 s_sample_info 中是否有该 set_no 的样本，有则拒绝
- 检查 s_sample_directory 中是否有该 set_no 的目录记录，有则拒绝
- 查询 set_path（用于删除存储）
- 删除 s_sample_set 记录
- 删除本地目录或 MinIO 前缀

**`delete_original_sample_set(set_no: str)`** — 删除原始样本集
- 检查 s_original_sample_info 中是否有该 set_no 的样本，有则拒绝
- 检查 s_sample_directory 中是否有该 set_no 的目录记录，有则拒绝
- 检查 s_data_collect_task 中是否有关联该 set_no 的采集任务，有则拒绝
- 查询 set_path
- 删除 s_original_sample_set 记录
- 删除本地目录或 MinIO 前缀

存储删除逻辑（两种模式）：
- **本地模式**：`shutil.rmtree(set_path)` 删除整个样本集目录
- **MinIO 模式**：列出 `set_no/` 前缀下所有对象，逐个删除

### 2. 后端：新增 API 端点

**sample.py**: `POST /delete-sample-set`
- 参数: `{ setNo: string }`
- 调用 delete_sample_set

**original_sample.py**: `POST /delete-original-sample-set`
- 参数: `{ setNo: string }`
- 调用 delete_original_sample_set

### 3. 前端：新增 API 函数

**sample.ts**: `deleteSampleSet(setNo: string)`
**originalSample.ts**: `deleteOriginalSampleSet(setNo: string)`

### 4. 前端：启用删除按钮

**SampleSetManagement.vue**:
- 移除 `disabled` 属性
- 添加 `handleDelete(item)` 函数：ElMessageBox 确认 → 调用 API → ElMessage 提示 → 刷新列表

**OriginalSampleSetManagement.vue**: 同上

## 关键文件

| 文件 | 改动 |
|------|------|
| `backend/app/core/db_sample.py` | 新增 delete_sample_set、delete_original_sample_set |
| `backend/app/api/routes/sample.py` | 新增 /delete-sample-set 端点 |
| `backend/app/api/routes/original_sample.py` | 新增 /delete-original-sample-set 端点 |
| `frontend/src/api/sample.ts` | 新增 deleteSampleSet 函数 |
| `frontend/src/api/originalSample.ts` | 新增 deleteOriginalSampleSet 函数 |
| `frontend/src/views/SampleSetManagement.vue` | 启用删除按钮 + handleDelete |
| `frontend/src/views/OriginalSampleSetManagement.vue` | 启用删除按钮 + handleDelete |

## 可复用的现有代码

- `db_sample.get_sample_set_path(set_no)` — 查询 set_path
- `db_sample.delete_directory(dir_id)` — 参考 delete 模式
- `sample_minio_service.delete_object(object_id)` — MinIO 删除对象
- `sample_minio_service.list_object_names(set_no)` — 列出 MinIO 对象
- `config.py` 的 `use_minio` 配置项 — 判断存储模式

## 验证

1. 创建一个空样本集 → 点删除 → 确认 → 成功删除，列表刷新
2. 创建一个有样本的样本集 → 点删除 → 提示"样本集不为空，无法删除"
3. 原始样本集被采集任务关联 → 点删除 → 提示"该样本集被采集任务引用"
4. 本地模式：删除后确认文件夹已删除
5. MinIO 模式：删除后确认对象已清除
