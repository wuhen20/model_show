# 人工智能平台 · 知识图谱生成与展示系统

## 目录

- [系统概述](#系统概述)
- [目录结构](#目录结构)
- [核心设计](#核心设计)
  - [分库策略](#分库策略)
  - [数据流向](#数据流向)
  - [数据来源统一](#数据来源统一)
- [环境准备](#环境准备)
- [使用方法](#使用方法)
  - [启动服务](#启动服务)
  - [生成图谱](#生成图谱)
  - [查看结果](#查看结果)
- [图谱生成脚本详解](#图谱生成脚本详解)
  - [处理流程](#处理流程)
  - [关键参数](#关键参数)
  - [中文实体抽取](#中文实体抽取)
  - [并发与性能优化](#并发与性能优化)
  - [后台标签机制](#后台标签机制)
- [Memgraph 数据模型](#memgraph-数据模型)
- [后端 API](#后端-api)
- [前端展示](#前端展示)
- [数据备份](#数据备份)
- [重新生成图谱](#重新生成图谱)
- [常见问题](#常见问题)

---

## 系统概述

本系统从文件夹知识库中提取文档，通过 LightRAG + LLM 自动生成知识图谱，存入 Memgraph 图数据库，并在前端页面实时展示。首页数据完全基于文件系统实时扫描，确保数据一致性。

```
原始文档 → LightRAG(LLM抽取) → Memgraph(存储) → FastAPI(API) → Vue3(展示)
                ↘ 文件系统扫描 → 统计/趋势/资产数据 → 前端展示
```

---

## 目录结构

```
演示/
├── 知识库文件夹/                    # 原始文档（5个知识库，共3300个文件）
│   ├── 专家系统知识库/              # 210个文件
│   ├── 装表接电知识库/              # 19个文件
│   ├── 计量数字讲师/                # 830个文件
│   ├── 计量营销专业知识库/           # 2233个文件
│   └── 采集自愈知识库/              # 8个文件
│
├── generate_graphs.py              # 图谱生成脚本（核心）
├── graph_generation.log            # 生成日志（实时）
│
├── lightrag_data/                  # LightRAG 数据目录
│   ├── .env                        # LightRAG 配置
│   ├── knowledge_base/             # 当前工作空间（所有KB共享）
│   │   └── knowledge_base/
│   │       ├── kv_store_full_entities.json
│   │       ├── kv_store_full_relations.json
│   │       ├── kv_store_doc_status.json
│   │       ├── graph_chunk_entity_relation.graphml
│   │       ├── vdb_*.json          # 向量数据库
│   │       └── kv_store_*.json     # 其他KV存储
│   ├── 专家系统知识库/              # 按KB名备份
│   ├── 装表接电知识库/
│   └── graph_generation_summary.json  # 生成摘要
│
├── lightrag_env/                   # Python 虚拟环境
│
└── model_show/                     # 前后端
    ├── backend/                    # FastAPI 后端
    │   ├── app/
    │   │   ├── api/routes/
    │   │   │   ├── knowledge.py         # 知识API（统计/图谱/LightRAG代理）
    │   │   │   ├── folder_kb.py         # 文件夹KB API（趋势/资产/文件列表）
    │   │   │   └── kb_management.py     # KB管理CRUD
    │   │   ├── services/
    │   │   │   ├── memgraph_service.py   # Memgraph查询
    │   │   │   ├── lightrag_service.py   # LightRAG代理
    │   │   │   ├── folder_kb_service.py  # 文件夹KB扫描（核心数据源）
    │   │   │   └── db_service.py         # SQLite数据服务
    │   │   └── schemas/
    │   └── .env                    # 后端配置
    └── frontend/                   # Vue3 前端
        └── src/
            ├── components/
            │   ├── KnowledgeCharts.vue   # 知识资产库（饼图）
            │   ├── KnowledgeTrend.vue    # 知识更新趋势（堆叠柱状图）
            │   ├── KnowledgeSource.vue   # 知识来源分布
            │   ├── KnowledgeTable.vue    # 知识资产表格（只读展示）
            │   └── KnowledgeGraph.vue    # 知识图谱
            ├── views/
            │   ├── KnowledgeManagement.vue  # 知识管理页
            │   └── FolderKBDetail.vue       # KB详情页（含文件下钻）
            └── api/
                └── knowledge.ts        # API接口定义
```

---

## 核心设计

### 分库策略

**所有知识库共享同一个 LightRAG workspace**，通过 `kb_name` 属性区分归属：

| 概念 | 说明 |
|------|------|
| workspace | 固定为 `knowledge_base`，所有KB共用 |
| kb_name | 每个节点的属性，值为知识库中文名（如 `"专家系统知识库"`） |
| Memgraph label | 所有节点共享 `knowledge_base` label |
| 查询过滤 | `MATCH (n) WHERE n.kb_name = '专家系统知识库'` |

**为什么不每个KB用独立workspace？**
- 避免每个KB初始化一套Memgraph连接和索引
- 实体跨库合并更自然（如"DL/T 698"同时属于多个KB）
- 增量处理简单，新KB加入无需新建workspace

### 数据流向

```
1. 扫描文件夹        知识库文件夹/专家系统知识库/ → 10个文件路径
2. 读取文本          .docx/.txt/.xlsx → 纯文本
3. 批量插入          rag.ainsert(input=[...10个文本...], file_paths=[...10个名...])
4. LightRAG Pipeline  切片 → LLM抽取 → Embedding → Merge → 写入Memgraph
5. 后台标签          每10秒扫描未标记节点，按file_path匹配打kb_name
6. 备份              完成后复制JSON到 lightrag_data/<KB名>/ 目录
```

### 数据来源统一

**所有首页统计数据统一来源于文件系统实时扫描**，而非旧的静态 `parsed_data.json`：

| 数据项 | 来源 | 说明 |
|------|------|------|
| 知识总量 (3,300) | `folder_kb_service.scan_kb_asset_stats()` | 扫描5个KB目录 |
| 结构化/非结构化 | `folder_kb_service.scan_all_kb_files()` | 按文件名推断类型 |
| 覆盖业务域 (5) | `folder_kb_service.scan_kb_asset_stats()` | 一级目录即KB数 |
| 图谱实体数 | Memgraph 实时查询 | 后台异步刷新 |
| 知识更新趋势 | `folder_kb_service.scan_kb_trend_data()` | 按文件mtime按月统计 |
| 知识资产库饼图 | `folder_kb_service.scan_kb_asset_stats()` | 每个KB的文件数/大小 |
| 知识资产表格 | `folder_kb_service.scan_all_kb_files()` | 按Tab过滤排序 |
| 知识来源分布 | `parsed_data.json` 旧端点 | 依赖文件名语义分类 |

所有 `folder_kb_service` 函数带 60 秒 TTL 缓存，避免重复文件系统遍历。

---

## 环境准备

### 必须服务

| 服务 | 地址 | 说明 |
|------|------|------|
| Memgraph | bolt://localhost:7687 | 图数据库，Docker 启动 |
| SiliconFlow API | api.siliconflow.cn | LLM + Embedding |

### 启动 Memgraph

```bash
docker run -d --name memgraph -p 7687:7687 -p 7474:7474 memgraph/memgraph
```

### Python 环境

```bash
# 虚拟环境已存在，无需额外安装
E:\artificial\人工智能平台\演示\lightrag_env\Scripts\python.exe
```

### API Key

在 `lightrag_data/.env` 或脚本中配置：

```env
LLM_API_KEY=sk-xxx                    # SiliconFlow API Key
LLM_MODEL=Qwen/Qwen3.6-35B-A3B       # LLM模型
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B  # 嵌入模型
```

---

## 使用方法

### 启动服务

```bash
# 1. 确保 Memgraph 已运行
docker start memgraph

# 2. 启动后端（端口 3002）
cd E:\artificial\人工智能平台\演示\model_show\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 3002

# 3. 启动前端（端口 5173）
cd E:\artificial\人工智能平台\演示\model_show\frontend
npm run dev
```

浏览器打开 **http://localhost:5173**

### 生成图谱

```bash
cd E:\artificial\人工智能平台\演示
lightrag_env\Scripts\python.exe generate_graphs.py
```

脚本会：
- 扫描5个知识库，每个抽10个文件
- 批量插入 LightRAG，5路并行处理
- 后台每10秒自动打标签，边处理边可见
- 完成后备份到 `lightrag_data/<KB名>/`

### 查看结果

```bash
# 实时查看生成日志
tail -f graph_generation.log

# 查看 Memgraph 中各KB的实体数
lightrag_env\Scripts\python.exe -c "
from neo4j import GraphDatabase
d = GraphDatabase.driver('bolt://localhost:7687', auth=('', ''))
s = d.session()
r = s.run('MATCH (n) WHERE n.kb_name IS NOT NULL RETURN n.kb_name AS kb, count(n) AS cnt ORDER BY cnt DESC')
for rec in r: print(f'  {rec[\"kb\"]}: {rec[\"cnt\"]}')
s.close(); d.close()
"

# 查看 API 返回的统计（来自文件系统扫描）
curl -s http://127.0.0.1:3002/api/knowledge/stats | python -m json.tool
```

---

## 图谱生成脚本详解

### 处理流程

对每个知识库：

```
读取10个文件 → 批量ainsert → LightRAG并行处理5个文档 → 后台每10秒打kb_name标签 → 完成后备份
```

### 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `FILES_PER_KB` | 10 | 每个KB抽取的文件数 |
| `max_parallel_insert` | 5 | LightRAG 内部并行插入数 |
| `llm_model_max_async` | 5 | LLM 并发调用数 |
| `embedding_func_max_async` | 5 | Embedding 并发调用数 |
| `default_llm_timeout` | 300s | LLM 单次调用超时 |
| `default_embedding_timeout` | 120s | Embedding 单次调用超时 |
| `chunk_token_size` | 1200 | 切片大小 |

### 中文实体抽取

通过 `addon_params` 控制：

```python
addon_params={
    "language": "Chinese",       # 输出语言为中文
    "entity_types": [             # 实体类型列表（中文）
        "人物", "组织机构", "法律法规", "标准规范",
        "设备", "技术方法", "计量单位", "地理位置",
        "事件", "概念", "数据指标", "文档",
        "作业流程", "产品", "其他",
    ],
}
```

效果：
- 实体名称：`中华人民共和国计量法`（而非 `Measurement Law`）
- 实体类型：`法律法规`（而非 `Law`）
- 实体描述：中文描述
- 关系描述：中文描述

### 并发与性能优化

**关闭思考模式**（Qwen3 专用）：

```python
kwargs["extra_body"]["enable_thinking"] = False
```

SiliconFlow 的 Qwen3 模型默认开启思考模式（输出 `<think>...</think>` 标签），关闭后：
- 输出更精简，减少无效 token
- 响应速度约提升 30-50%

**自定义 Embedding 客户端**：

```python
_embed_client = _openai.AsyncOpenAI(
    timeout=120.0,    # 2分钟超时（默认60s太短）
    max_retries=5,    # 最多重试5次
)
```

### 后台标签机制

在 `ainsert` 运行期间，一个 asyncio 后台任务每 10 秒执行：

1. 查询 `kb_name IS NULL` 的节点
2. 按 `file_path CONTAINS filename` 匹配
3. 设置 `kb_name = 当前KB名`
4. 同时为两端都有 kb_name 的关系打标签

```
ainsert 运行中 ──────────────────────────────→ 完成
    │                                              │
    ├─ [BG-Tag] +42 nodes tagged                   │
    ├─ [BG-Tag] +38 nodes tagged                   │
    ├─ [BG-Tag] +55 nodes tagged   ← 每10秒       │
    ├─ [BG-Tag] +61 nodes tagged                   │
    │                                              │
    └──────────── Final: +7 nodes tagged ──────────┘
```

这样你在前端可以实时看到图谱数据增长，无需等全部完成。

---

## Memgraph 数据模型

### 节点

```
(:knowledge_base {
    entity_id:   "中华人民共和国计量法",          # 实体名称（中文，显示用）
    entity_type: "法律法规",                     # 实体类型（中文）
    description: "中国计量领域的基本法律...",      # 实体描述
    source_id:   "chunk-xxx<SEP>chunk-yyy",      # 来源切片ID
    file_path:   "5.中华人民共和计量法.docx",     # 来源文件名
    kb_name:     "专家系统知识库",                # 所属知识库
})
```

### 关系

```
(:knowledge_base)-[:DIRECTED {
    weight:      1.0,                             # 权重
    description: "计量法规定国务院负责批准...",     # 关系描述（中文）
    keywords:    "审批权限,法律授权",              # 关键词
    source_id:   "chunk-xxx",                     # 来源切片
    file_path:   "5.中华人民共和计量法.docx",      # 来源文件
    kb_name:     "专家系统知识库",                 # 所属知识库
}]->(:knowledge_base)
```

### 查询示例

```cypher
-- 查看所有知识库的实体数量
MATCH (n) WHERE n.kb_name IS NOT NULL
RETURN n.kb_name AS kb, count(n) AS cnt
ORDER BY cnt DESC;

-- 查看某个知识库的实体和关系
MATCH (n) WHERE n.kb_name = '专家系统知识库'
RETURN n.entity_id, n.entity_type, n.description
LIMIT 20;

-- 查看跨库关系
MATCH (a)-[r]->(b)
WHERE a.kb_name = '专家系统知识库' AND b.kb_name = '装表接电知识库'
RETURN a.entity_id, r.description, b.entity_id;
```

---

## 后端 API

### 知识统计（数据源：文件系统扫描）

```
GET /api/knowledge/stats
```

返回：
```json
{
  "total_count": 3300,
  "structured_count": 994,
  "unstructured_count": 2306,
  "graph_entities": 5274,       ← 从 Memgraph 实时查询
  "business_domains": 5,
  "completeness": 92.5,
  "availability": 95.8
}
```

- `total_count`、`structured_count`、`business_domains` 来自 `folder_kb_service` 文件系统扫描
- `graph_entities` 通过后台异步刷新：首次请求返回缓存值（可能为0），2秒后再次请求返回真实值

### 文件夹知识库（核心 API，数据源：文件系统扫描）

```
GET /api/knowledge/folder/bases                  # 列出所有KB
GET /api/knowledge/folder/bases/{name}/files     # KB文件列表（分页+关键词）
GET /api/knowledge/folder/bases/{name}/tags      # KB标签树
GET /api/knowledge/folder/bases/{name}/graph     # 合成图(fallback)
GET /api/knowledge/folder/bases/{name}/import    # 导入到DB系统

GET /api/knowledge/folder/trend                  # 知识更新趋势（按月）
GET /api/knowledge/folder/asset-stats            # 知识资产统计
GET /api/knowledge/folder/list                   # 跨KB文件列表（Tab过滤）
```

#### 知识更新趋势

```
GET /api/knowledge/folder/trend
```

返回近18个月每月各知识库的文件修改数量：
```json
{
  "months": ["2025-01", "2025-02", ..., "2026-06"],
  "series": [
    {"name": "计量营销专业知识库", "data": [0, 0, ..., 3], "color": "#00d4ff"},
    {"name": "计量数字讲师", "data": [0, 0, ..., 203], "color": "#00ff88"},
    ...
  ],
  "summary": {
    "new_count": 206,           # 本月修改过的文件数
    "new_change_pct": -69.3,    # 与上月环比变化
    "updated_count": 805,       # 近30天修改过的文件数
    "updated_change_pct": 26.4  # 与前30天环比变化
  }
}
```

#### 知识资产统计

```
GET /api/knowledge/folder/asset-stats
```

返回每个KB的文件数、总大小、文件类型分布：
```json
{
  "total_count": 3300,
  "total_size": 4363727811,
  "categories": [
    {"name": "计量营销专业知识库", "count": 2233, "size": 2045234207, "value": 67.7, "color": "#00d4ff",
     "extensions": [{"ext": ".docx", "count": 2212}, {"ext": ".txt", "count": 10}, ...]},
    ...
  ],
  "extension_summary": [
    {"ext": ".docx", "count": 3275, "value": 99.2},
    ...
  ]
}
```

#### 跨KB文件列表

```
GET /api/knowledge/folder/list?tab=latest&page_size=10
```

Tab 过滤逻辑：

| Tab | 逻辑 | 示例数量 |
|-----|------|---------|
| `latest` | 按修改时间倒序 | 3,300 |
| `popular` | 按质量评分倒序（标准文献5分 > 指导书4分 > 其他3分） | 3,300 |
| `valuable` | 仅 score≥5 的标准文献（JJG/GB/DLT/Q-GDW等前缀） | 425 |
| `pending` | 近7天内修改过的文件（刚入库，待处理） | 206 |

每条记录包含：`title`、`category_name`（所属KB）、`knowledge_type`（推断类型）、`source`（推断来源）、`score`、`status`、`update_time`。

类型推断规则（按文件名匹配）：
- 含 `JJG` → 检定规程，含 `GB` → 国家标准，含 `DLT/DL/` → 行业标准
- 含 `Q/GDW/QGDW` → 企业标准，含 `JJF` → 计量规范
- 含 `指导书` → 作业指导书，含 `管理办法/管理规定` → 管理制度
- 其他 → 技术文档

### 知识图谱

```
GET /api/knowledge/graph                      # 合并所有KB
GET /api/knowledge/graph?kb_name=专家系统知识库  # 指定KB
GET /api/knowledge/graph?workspace=cai_ji_zi_yu  # 按workspace(legacy)
```

---

## 前端展示

### 页面结构

| 页面 | 路径 | 说明 |
|------|------|------|
| 知识管理首页 | `/knowledge-management` | 统计卡片 + 趋势图 + 资产图 + 资产表 + 图谱 |
| 知识库管理 | `/knowledge-management?tab=management` | 文件夹KB卡片列表 |
| KB详情 | `/folder-kb/{name}` | 文件列表 + 图谱 + 导入（支持文件下钻） |
| 知识能力工具 | `/knowledge-management?tab=tools` | 工具集 |

### 首页布局

```
┌──────────────────────────────────────────────────────┐
│  统计卡片：知识总量 | 结构化知识 | 非结构化 | 图谱实体 | 业务域  │
├──────────────────┬──────────────────┬────────────────┤
│  知识资产库       │  知识来源分布     │  知识更新趋势    │
│  (饼图+图例)      │  (进度条)        │  (堆叠柱状图)    │
│                  │                  │  本月新增 | 30天  │
├──────────────────┴──────┬───────────┴────────────────┤
│  知识资产表格（只读）     │  知识图谱                    │
│  最新/热门/高价值/待审核  │  (ECharts力导向图)           │
└─────────────────────────┴────────────────────────────┘
```

**首页只做展示**：资产表格行不可点击、标题不可跳转，文件下钻功能在子库（FolderKBDetail）页面中。

### 图谱展示逻辑

```
页面加载
  │
  ├─ 首页图谱 → fetchKnowledgeGraph()（无kb_name，合并所有KB）
  │
  └─ KB详情图谱 → fetchKnowledgeGraph(kb_name)
       │
       ├─ Memgraph有数据？→ 用真实实体/关系渲染 ✓
       │
       └─ Memgraph无数据？→ fallback到目录结构合成图
```

### 统计数据来源

| 指标 | 来源 | 实时 |
|------|------|------|
| 知识总量 | 文件系统扫描 (folder_kb_service) | 是（60s缓存） |
| 结构化/非结构化 | 文件系统扫描 (类型推断) | 是（60s缓存） |
| 覆盖业务域 | 文件系统扫描 (一级目录数) | 是（60s缓存） |
| **图谱实体数** | **Memgraph 实时查询** | **是** |
| 知识更新趋势 | 文件系统扫描 (mtime按月统计) | 是（60s缓存） |
| 知识资产分布 | 文件系统扫描 (文件数/大小/类型) | 是（60s缓存） |
| 资产表格 | 文件系统扫描 (Tab过滤排序) | 是（60s缓存） |
| 来源分布 | parsed_data.json (旧端点) | 否 |

---

## 数据备份

脚本完成后，LightRAG 数据会复制到按 KB 名命名的备份目录：

```
lightrag_data/
├── knowledge_base/knowledge_base/   # 工作空间（当前数据）
├── 专家系统知识库/                    # 备份
│   ├── kv_store_full_entities.json
│   ├── kv_store_full_relations.json
│   ├── kv_store_doc_status.json
│   └── graph_chunk_entity_relation.graphml
├── 装表接电知识库/
├── 计量数字讲师/
├── 计量营销专业知识库/
└── 采集自愈知识库/
```

---

## 重新生成图谱

### 完全重置（清空所有数据）

```bash
# 1. 清空 LightRAG 工作空间
rm -rf E:\artificial\人工智能平台\演示\lightrag_data\knowledge_base

# 2. 清空 Memgraph
lightrag_env\Scripts\python.exe -c "
from neo4j import GraphDatabase
d = GraphDatabase.driver('bolt://localhost:7687', auth=('', ''))
d.session().run('MATCH (n) DETACH DELETE n')
d.close()
print('Done')
"

# 3. 重新运行
cd E:\artificial\人工智能平台\演示
lightrag_env\Scripts\python.exe generate_graphs.py
```

### 增量处理（保留已有数据）

直接运行 `generate_graphs.py`，它会：
- 保留已有的 LightRAG 工作空间数据
- 自动跳过已处理的文档（LightRAG 内部去重）
- 只处理新增文档
- 标签任务自动覆盖未标记的节点

---

## 常见问题

### Q: 生成速度很慢怎么办？

1. **确认思考模式已关闭**：脚本中 `enable_thinking=False`，Qwen3 默认开思考模式很慢
2. **增加并发**：修改 `max_parallel_insert=5` 为更大值（受 API 限流约束）
3. **减少文件数**：修改 `FILES_PER_KB = 10` 为更小值
4. **截断长文档**：脚本已限制最大 8000 字符

### Q: Embedding 超时怎么办？

SiliconFlow 的 Embedding API 偶尔超时，脚本已配置：
- `timeout=120s`（2分钟）
- `max_retries=5`（最多重试5次）

如果仍然超时，检查网络连接或更换 Embedding 模型。

### Q: 生成的是英文实体怎么办？

确认脚本中 `addon_params` 设置了：
```python
"language": "Chinese",
"entity_types": ["人物", "组织机构", ...],
```

这些参数告诉 LLM 用中文输出实体名称、类型和描述。

### Q: 页面上图谱实体数为0？

1. 确认 Memgraph 在运行：`docker ps | grep memgraph`
2. 确认有数据：访问 `http://127.0.0.1:3002/api/knowledge/stats`
3. 第一次请求 `graph_entities` 可能为0（后台异步刷新），刷新页面即可

### Q: 日志里出现 `LLM output format error` 警告？

这是正常的。LLM 偶尔输出格式不符（多一个字段或少分隔符），LightRAG 自动跳过这些行，不影响整体结果。常见于中文实体名包含特殊字符（如 `|`）的情况。

### Q: 如何只重新生成某个知识库？

1. 在 Memgraph 中删除该 KB 的节点：
```cypher
MATCH (n) WHERE n.kb_name = '专家系统知识库' DETACH DELETE n
```
2. 清空 LightRAG 工作空间（会丢失所有KB数据）或使用新workspace
3. 重新运行脚本（会自动跳过其他KB已处理的文档）

### Q: 切换Tab后图表排版被压缩？

切换到"知识库管理"再切回"首页"时，ECharts 因容器 `display:none` 导致宽度为0。已通过监听 Tab 切换并在回到首页时触发 `window.resize` 事件修复。如仍出现，手动调整浏览器窗口大小即可恢复。

### Q: 统计数据与知识库文件数量不一致？

确保后端使用的是最新代码。旧版 `/api/knowledge/stats` 从静态 `parsed_data.json` 读取（2,887条），新版从文件系统实时扫描（3,300条）。重启后端即可生效。
