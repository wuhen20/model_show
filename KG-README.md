# 人工智能平台 · 知识图谱生成与展示系统

## 目录

- [系统概述](#系统概述)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [环境准备](#环境准备)
  - [必须服务](#必须服务)
  - [Python 环境](#python-环境)
  - [前端环境](#前端环境)
- [核心设计](#核心设计)
  - [分库策略](#分库策略)
  - [数据流向](#数据流向)
  - [数据来源统一](#数据来源统一)
  - [存储架构](#存储架构)
  - [配置系统](#配置系统)
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
  - [知识统计](#知识统计数据源文件系统扫描)
  - [文件夹知识库](#文件夹知识库核心-api数据源文件系统扫描)
  - [知识库管理](#知识库管理-crud)
  - [知识图谱](#知识图谱)
  - [AI 对话](#ai-对话)
  - [模型配置](#模型配置)
- [前端展示](#前端展示)
  - [页面路由](#页面路由)
  - [知识管理首页](#知识管理首页)
  - [知识库详情页](#知识库详情页folderkbdetail)
  - [用户自建知识库详情页](#用户自建知识库详情页knowledgebasedetail)
  - [创建知识库向导](#创建知识库向导knowledgecreate)
  - [模型服务页](#模型服务页)
  - [能力体验页](#能力体验页)
  - [前端组件清单](#前端组件清单)
- [数据备份](#数据备份)
- [重新生成图谱](#重新生成图谱)
- [常见问题](#常见问题)

---

## 系统概述

本系统是一个完整的 AI 平台，包含**知识管理**、**模型服务**和**AI 对话**三大模块。知识管理模块从文件夹知识库中提取文档，通过 LightRAG + LLM 自动生成知识图谱，存入 Memgraph 图数据库，并在前端页面实时展示。首页数据完全基于文件系统实时扫描，确保数据一致性。

```
原始文档 → LightRAG(LLM抽取) → Memgraph(存储) → FastAPI(API) → Vue3(展示)
                ↘ 文件系统扫描 → 统计/趋势/资产数据 → 前端展示

用户提问 → AI Service(阿里百炼) → 流式响应 → 前端展示
文件上传 → 图片/文档分析 → 多模态响应 → 前端展示
```

---

## 技术栈

### 前端

| 依赖 | 版本 | 用途 |
|---|---|---|
| Vue 3 | ^3.4 | 前端框架 |
| Vue Router | ^4.3 | 路由管理 |
| Element Plus | ^2.9 | UI 组件库 |
| ECharts | ^5.5 | 图表与知识图谱可视化 |
| @vue-office/docx | ^1.6 | Word (.docx) 文档在线预览 |
| @vue-office/excel | ^1.7 | Excel (.xlsx/.xls) 表格在线预览 |
| @vue-office/pdf | ^2.0 | PDF 文件在线预览 |
| @vue-office/pptx | ^1.0 | PowerPoint (.pptx) 演示文稿在线预览 |
| vue-demi | ^0.14 | Vue 2/3 兼容层（vue-office 依赖） |
| Vite | ^5.4 | 构建工具 |
| TypeScript | ^5.3 | 类型检查 |
| Sass | ^1.70 | CSS 预处理器 |

### 后端

| 依赖 | 用途 |
|---|---|
| FastAPI | Web 框架 |
| Uvicorn | ASGI 服务器 |
| Pydantic / pydantic-settings | 数据校验与设置管理 |
| OpenAI | LLM 调用（对话 + LightRAG） |
| Neo4j | 图数据库驱动（Memgraph） |
| MinIO | 对象存储（可选） |
| httpx | 异步 HTTP 客户端 |
| python-multipart | 文件上传支持 |
| SQLite | 元数据存储（知识库/标签/文档/切片） |

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
    │   │   │   ├── knowledge.py         # 知识API（统计/图谱/LightRAG代理/质量度量）
    │   │   │   ├── folder_kb.py         # 文件夹KB API（趋势/资产/来源分布/文件列表/预览）
    │   │   │   ├── kb_management.py     # KB管理CRUD + 文档上传 + LightRAG同步
    │   │   │   ├── chat.py              # AI对话（流式/文件上传）
    │   │   │   └── models.py            # 模型配置API
    │   │   ├── services/
    │   │   │   ├── memgraph_service.py   # Memgraph查询
    │   │   │   ├── lightrag_service.py   # LightRAG代理
    │   │   │   ├── folder_kb_service.py  # 文件夹KB扫描（核心数据源）
    │   │   │   ├── db_service.py         # SQLite数据服务（KB/标签/文档/切片CRUD）
    │   │   │   ├── storage_service.py    # 文件存储抽象（本地/MinIO）
    │   │   │   ├── sync_service.py       # LightRAG增量同步
    │   │   │   └── ai_service.py         # AI对话服务（阿里百炼）
    │   │   ├── schemas/
    │   │   │   ├── chat.py               # 对话请求/响应模型
    │   │   │   ├── folder_kb.py          # 文件夹KB数据模型
    │   │   │   ├── knowledge.py          # 知识数据模型
    │   │   │   └── knowledge_base.py     # KB/标签/文档/切片数据模型
    │   │   └── core/
    │   │       └── config.py             # 全局配置（Pydantic Settings）
    │   ├── data/
    │   │   └── knowledge_metadata.db     # SQLite 元数据库
    │   ├── uploads/                      # 上传文件存储目录
    │   └── .env                          # 后端配置
    └── frontend/                   # Vue3 前端
        └── src/
            ├── components/
            │   ├── KnowledgeCharts.vue    # 知识资产库（环形图）
            │   ├── KnowledgeTrend.vue     # 知识更新趋势（堆叠柱状图）
            │   ├── KnowledgeSource.vue    # 知识来源分布（5大体系分类）
            │   ├── KnowledgeTable.vue     # 知识资产表格（只读展示）
            │   ├── KnowledgeGraph.vue     # 知识图谱
            │   ├── KnowledgeQuality.vue   # 知识质量概览（五维评估）
            │   ├── KnowledgeTools.vue     # 知识能力工具
            │   ├── GraphDetailModal.vue   # 图谱全屏详情模态框
            │   ├── FolderTagItem.vue      # 文件夹标签药片组件
            │   ├── StatsCard.vue          # 统计卡片组件
            │   ├── Header.vue             # 全局顶栏
            │   ├── Sidebar.vue            # 全局侧栏
            │   ├── ColorSelector.vue      # 颜色选择器（创建KB用）
            │   ├── IconSelector.vue       # 图标选择器（创建KB用）
            │   ├── TagNode.vue            # 标签树节点
            │   ├── TagCheckbox.vue        # 标签复选框
            │   ├── TagTreeReadonly.vue    # 只读标签树
            │   ├── BusinessDomain.vue     # 业务域卡片
            │   ├── ModelTable.vue         # 模型列表表格
            │   ├── ServiceDetail.vue      # 服务详情面板
            │   ├── ServiceOverview.vue    # 服务概览
            │   ├── TaskPanel.vue          # 任务面板
            │   ├── FlowChart.vue          # 流程图
            │   ├── InterfacePanel.vue     # 接口面板
            │   └── InvokeChart.vue        # 调用量图表
            ├── views/
            │   ├── Home.vue               # 模型服务首页
            │   ├── ModelService.vue       # 模型服务管理页
            │   ├── AbilityExperience.vue  # 能力体验页
            │   ├── KnowledgeManagement.vue  # 知识管理页
            │   ├── KnowledgeDetail.vue    # 知识详情页
            │   ├── KnowledgeCreate.vue    # 创建知识库向导
            │   ├── KnowledgeBaseDetail.vue  # 用户自建KB详情页
            │   └── FolderKBDetail.vue     # 文件夹KB详情页（含文件下钻）
            └── api/
                ├── knowledge.ts           # 知识管理API接口
                └── chat.ts                # AI对话API接口
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
| 知识来源分布 | `folder_kb_service.scan_kb_source_distribution()` | 5大体系分类（见下文） |

所有 `folder_kb_service` 函数带 60 秒 TTL 缓存，避免重复文件系统遍历。

**知识来源分布（5大体系分类）：**

来源分布基于文件系统实时扫描，按文件名语义分为5大体系：

| 体系 | 匹配规则 | 示例 |
|------|----------|------|
| 标准规范体系 | JJG/GB/DLT/Q-GDW/JJF 等标准前缀 | 检定规程、国家标准 |
| 作业指导体系 | 含"指导书"/"操作手册"关键词 | 作业指导书、操作手册 |
| 政策文档体系 | 含"条例"/"法"/"管理办法"关键词 | 法律法规、管理制度 |
| 培训考试体系 | 含"试题"/"题库"/"培训"关键词 | 培训资料、考试题库 |
| 技术文档体系 | 其他所有文档 | 技术方案、功能规范 |

### 存储架构

文件存储支持两种后端，通过 `storage_backend` 配置切换：

| 后端 | 配置值 | 说明 |
|------|--------|------|
| 本地文件系统 | `local`（默认） | 保存到 `uploads/{kb_id}/` 目录，重名文件自动加 hash 后缀 |
| MinIO 对象存储 | `minio` | 保存到 `kb-{workspace}` bucket，连接失败自动降级为本地存储 |

`storage_service.py` 提供统一接口：`save_file`、`get_file`、`delete_file`，上层业务无感知。

### 配置系统

后端使用 `pydantic-settings` 管理所有配置（`app/core/config.py`），支持环境变量和 `.env` 文件：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `server_port` | 3002 | 后端端口 |
| `demo_mode` | True | 演示模式（限制图谱返回节点数） |
| `graph_demo_max_nodes` | 2000 | 演示模式最大图谱节点数 |
| `storage_backend` | local | 文件存储后端（local/minio） |
| `upload_dir` | uploads | 上传文件目录 |
| `default_chunk_size` | 500 | 默认切片大小 |
| `default_chunk_overlap` | 50 | 默认切片重叠 |
| `default_parent_chunk_size` | 1500 | 默认父切片大小 |
| `dashscope_api_key` | 空 | 阿里百炼 API Key（对话用） |
| `dashscope_base_url` | 阿里百炼兼容端点 | OpenAI 兼容接口地址 |
| `lightrag_base_url` | http://127.0.0.1:9621 | LightRAG 服务地址 |
| `memgraph_uri` | bolt://localhost:7687 | Memgraph 连接地址 |
| `knowledge_base_dir` | 知识库文件夹 | 文件夹KB根目录 |
| `models` | [qwen-plus, qwen-vl-plus] | 可用模型列表配置 |

---

## 环境准备

### 必须服务

| 服务 | 地址 | 说明 |
|------|------|------|
| Memgraph | bolt://localhost:7687 | 图数据库，Docker 启动 |
| SiliconFlow API | api.siliconflow.cn | 图谱生成用 LLM + Embedding |
| 阿里百炼 API | dashscope.aliyuncs.com | AI 对话用 LLM（Qwen2-72B, Qwen-VL-Plus） |

### 启动 Memgraph

```bash
docker run -d --name memgraph -p 7687:7687 -p 7474:7474 memgraph/memgraph
```

### Python 环境

```bash
# 虚拟环境已存在，无需额外安装
E:\artificial\人工智能平台\演示\lightrag_env\Scripts\python.exe

# 安装后端依赖
cd model_show/backend
pip install -r requirements.txt
```

### 前端环境

```bash
# 安装依赖
cd model_show/frontend
npm install

# 开发模式启动（自动代理 API 到 3002 端口）
npm run dev

# 生产构建
npm run build
```

### API Key

在 `lightrag_data/.env` 或脚本中配置图谱生成 LLM：

```env
LLM_API_KEY=sk-xxx                    # SiliconFlow API Key
LLM_MODEL=Qwen/Qwen3.6-35B-A3B       # LLM模型
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B  # 嵌入模型
```

在 `model_show/backend/.env` 中配置 AI 对话 LLM：

```env
DASHSCOPE_API_KEY=sk-xxx              # 阿里百炼 API Key
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

### 知识质量度量

```
GET /api/knowledge/quality-metrics
```

返回五维评估指标：
```json
{
  "overall_score": 93.6,
  "metrics": [
    {"name": "准确性", "value": 94.2},
    {"name": "完整性", "value": 92.8},
    {"name": "时效性", "value": 93.1},
    {"name": "一致性", "value": 93.8},
    {"name": "可理解性", "value": 93.9}
  ]
}
```

### 文件夹知识库（核心 API，数据源：文件系统扫描）

```
GET /api/knowledge/folder/bases                  # 列出所有KB
GET /api/knowledge/folder/bases/{name}/files     # KB文件列表（分页+关键词）
GET /api/knowledge/folder/bases/{name}/tags      # KB标签树
GET /api/knowledge/folder/bases/{name}/graph     # 合成图(fallback)
GET /api/knowledge/folder/bases/{name}/preview/{path}  # 文件原始内容预览
POST /api/knowledge/folder/bases/{name}/import   # 导入到DB系统

GET /api/knowledge/folder/trend                  # 知识更新趋势（按月）
GET /api/knowledge/folder/asset-stats            # 知识资产统计
GET /api/knowledge/folder/list                   # 跨KB文件列表（Tab过滤）
GET /api/knowledge/folder/source-distribution    # 知识来源分布（5大体系分类）
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

#### 知识来源分布（5大体系）

```
GET /api/knowledge/folder/source-distribution
```

基于文件系统实时扫描，按文件名语义分为5大体系：
```json
[
  {"name": "标准规范体系", "value": 45.2, "count": 1492, "color": "#00d4ff"},
  {"name": "作业指导体系", "value": 18.5, "count": 611, "color": "#00ff88"},
  {"name": "政策文档体系", "value": 12.3, "count": 406, "color": "#a855f7"},
  {"name": "培训考试体系", "value": 8.7, "count": 287, "color": "#ffaa00"},
  {"name": "技术文档体系", "value": 15.3, "count": 504, "color": "#ff5555"}
]
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

### 知识库管理 CRUD

用户自建知识库的完整 CRUD，数据存储在 SQLite 中：

```
# 知识库
POST   /api/knowledge/bases                    # 创建知识库（含标签体系）
GET    /api/knowledge/bases/{kb_id}            # 获取知识库详情
PUT    /api/knowledge/bases/{kb_id}            # 更新知识库信息
DELETE /api/knowledge/bases/{kb_id}            # 删除知识库

# 标签
GET    /api/knowledge/bases/{kb_id}/tags       # 获取标签树
POST   /api/knowledge/bases/{kb_id}/tags       # 添加标签（支持子标签）
PUT    /api/knowledge/tags/{tag_id}            # 更新标签
DELETE /api/knowledge/tags/{tag_id}            # 删除标签（含子标签）

# 文档
POST   /api/knowledge/bases/{kb_id}/documents/upload  # 上传文档（必须选标签）
GET    /api/knowledge/bases/{kb_id}/documents          # 文档列表（分页）
GET    /api/knowledge/documents/{doc_id}               # 文档详情
DELETE /api/knowledge/documents/{doc_id}               # 删除文档

# 切片
GET    /api/knowledge/documents/{doc_id}/chunks         # 查看文档切片

# LightRAG 同步
POST   /api/knowledge/bases/{kb_id}/sync-lightrag      # 同步文档到 LightRAG
GET    /api/knowledge/bases/{kb_id}/sync-status         # 查看同步状态
```

**创建知识库**请求体包含：
- 基本信息：`name`、`description`、`icon`、`color`
- 切片配置：`chunk_size`、`chunk_overlap`、`chunking_strategy`（basic/parent_child）、`parent_chunk_size`、`chunk_separator`
- 标签体系：`tags[]`（支持无限层级嵌套，每个标签含 `level`、`name`、`parent_tag_id`、`children`）

**文档上传**必须选择至少一个标签，支持 FormData 多文件上传，可携带：
- `tag_ids`：已有标签 ID 列表
- `new_tags`：新建标签数据
- `chunk_size` / `chunk_overlap`：单次上传切片配置覆盖

**LightRAG 同步流程**：`sync_service.py` 将已完成（completed）的文档逐个读取并上传到 LightRAG，成功后标记为 `synced`，失败标记为 `failed` 并记录错误信息。

### 知识图谱

```
GET /api/knowledge/graph                      # 合并所有KB
GET /api/knowledge/graph?kb_name=专家系统知识库  # 指定KB
GET /api/knowledge/graph?workspace=cai_ji_zi_yu  # 按workspace(legacy)
GET /api/knowledge/graph?full=true            # 返回完整图谱（最多5000节点）
```

**Demo 模式**：当 `demo_mode=True` 时，图谱 API 返回完整统计信息，但实际节点/连线数限制为 `graph_demo_max_nodes`（默认2000），确保前端性能。`full=True` 可绕过此限制。

### AI 对话

```
POST /api/chat                   # 流式对话（SSE）
POST /api/chat/upload            # 带文件上传的对话
```

**流式对话**：使用 OpenAI 兼容协议（阿里百炼）实现流式输出，前端通过 SSE 接收：
- 请求体：`{ model_id, question, history[], stream: true }`
- 响应格式：`text/plain; charset=utf-8`，以 `\n\n---END---` 分隔元数据（token 数、模型名）
- 错误响应：以 `\n\n---ERROR---` 分隔错误信息

**文件上传对话**：支持图片和文档分析：
- 图片文件（jpg/png/gif/webp/bmp）→ 多模态视觉理解（Qwen-VL-Plus）
- 其他文件 → 追加文件名信息后文本对话（Qwen2-72B）

**模型配置**（在 `config.py` 中定义）：

| 模型 ID | 名称 | 类型 | 说明 |
|---------|------|------|------|
| `qwen-plus` | Qwen2-72B | 语言模型 | 复杂对话与分析，电力业务专用 system prompt |
| `qwen-vl-plus` | Qwen-VL-Plus | 视觉模型 | 多模态图像理解，电力设备图像分析 |

每个模型配置包含：`model_id`、`max_tokens`、`temperature`、`system_prompt`。

### 模型配置

```
GET /api/models                  # 获取可用模型列表
```

返回当前配置的所有模型信息，供前端模型选择器使用。

---

## 前端展示

### 页面路由

| 页面 | 路径 | 说明 |
|------|------|------|
| 模型服务首页 | `/` | 模型服务管理中心（统计卡片+模型列表+服务详情） |
| 模型服务管理 | `/model-service` | 模型服务管理详情页 |
| 能力体验 | `/ability-experience` | AI 能力体验（对话/文件分析） |
| 知识管理首页 | `/knowledge-management` | 统计卡片 + 趋势图 + 资产图 + 质量度量 + 资产表 + 图谱 |
| 知识库管理 | `/knowledge-management?tab=management` | 文件夹KB卡片列表 + 创建KB入口 |
| 知识能力工具 | `/knowledge-management?tab=tools` | 工具集 |
| 知识详情 | `/knowledge-detail/:id` | 单条知识详情页 |
| 创建知识库 | `/knowledge-create` | 三步创建向导 |
| 用户自建KB详情 | `/knowledge-base/:id` | 文档上传 + 管理 + 切片 + LightRAG同步 |
| 文件夹KB详情 | `/folder-kb/{name}` | 标签体系 + 文件列表 + 文件下钻预览 + 图谱 |

### 知识管理首页

```
┌──────────────────────────────────────────────────────┐
│  统计卡片：知识总量 | 结构化知识 | 非结构化 | 图谱实体 | 业务域  │
├──────────────────┬──────────────────┬────────────────┤
│  知识资产库       │  知识来源分布     │  知识更新趋势    │
│  (环形图+图例)    │  (5大体系进度条)  │  (堆叠柱状图)    │
│                  │                  │  本月新增 | 30天  │
├──────────────────┴──────┬───────────┴────────────────┤
│  知识资产表格（只读）     │  知识图谱 + 知识质量概览     │
│  最新/热门/高价值/待审核  │  (ECharts力导向图 + 五维)   │
└─────────────────────────┴────────────────────────────┘
```

**首页只做展示**：资产表格行不可点击、标题不可跳转，文件下钻功能在子库（FolderKBDetail）页面中。

**知识质量概览**（KnowledgeQuality 组件）：展示总体质量评分和五维指标（准确性、完整性、时效性、一致性、可理解性），数据来自 `/api/knowledge/quality-metrics` 端点。

### 知识库详情页（FolderKBDetail）

进入知识库详情后，左侧展示基本信息和标签体系，右侧展示文件列表与图谱。

**标签体系：** 目录结构自动解析为多层级标签树，以 chip/药片样式渲染（FolderTagItem 组件），颜色按层级区分：
- L1（一级）→ 青色 `#00d4ff`
- L2（二级）→ 绿色 `#00ff88`
- L3（三级）→ 紫色 `#c084fc`
- L4+（四级及以上）→ 琥珀色 `#ffaa00`

文件列表中的"关联标签"也使用相同配色，与标签体系统一。

**文件下钻与预览：** 点击文件列表中任意行，进入文件详情视图，展示文件元数据和在线预览。不同格式使用对应的预览组件：

| 格式 | 预览方式 |
|---|---|
| `.docx` | @vue-office/docx 原生渲染 |
| `.xlsx` / `.xls` | @vue-office/excel 原生渲染 |
| `.pptx` | @vue-office/pptx 幻灯片渲染 |
| `.pdf` | @vue-office/pdf 页面渲染 |
| `.txt` / `.md` / `.csv` / `.json` 等 | 纯文本预览（等宽字体） |
| `.jpg` / `.png` / `.gif` 等 | 图片预览 |
| 其他格式 | 提示下载 |

预览实现：前端 `fetch` 后端 `/preview/` 接口获取 ArrayBuffer，传递给 `@vue-office` 组件渲染。这样做避免了 CORS 和响应头兼容性问题。

**图谱全屏视图**（GraphDetailModal）：点击图谱"查看详情"打开，支持拖拽、缩放、点击节点查看实体详情，最多显示5000节点。

### 用户自建知识库详情页（KnowledgeBaseDetail）

用户通过创建向导建立的知识库，与文件夹知识库不同，支持完整的文档管理流程：

1. **左侧面板**：知识库信息、统计数据（文档数/切片数/待同步数）、标签树（只读）、标签选择、文件拖拽上传
2. **右侧文档列表**：文档状态流转（待处理 → 切片中 → 向量化 → 已完成/失败）、查看切片、同步到 LightRAG
3. **切片详情抽屉**：展示父切片和子切片内容，保留文档层次结构

### 创建知识库向导（KnowledgeCreate）

三步向导页面：
1. **基本信息**：名称、描述、图标（IconSelector）、主题色（ColorSelector）
2. **标签体系**：多层嵌套标签，支持无限层级，子标签选中时自动关联父级
3. **切片配置**：基础切片/父子切片策略、分隔符、切片大小/重叠、右侧实时预览

### 模型服务页

路径 `/`（默认首页）和 `/model-service`，展示模型服务管理中心：
- 统计卡片：在线服务数、已部署模型、今日调用量、平均响应、成功率、接口总数
- 模型列表（ModelTable）：按类型过滤（语言模型/视觉模型/全部）
- 服务详情面板（ServiceDetail）
- 调用量图表（InvokeChart）

### 能力体验页

路径 `/ability-experience`，提供 AI 对话交互界面：
- 模型选择（Qwen2-72B / Qwen-VL-Plus）
- 文本对话（流式输出）
- 文件上传分析（图片→视觉理解，其他→文本分析）

### 前端组件清单

| 组件 | 用途 |
|------|------|
| KnowledgeCharts.vue | 知识资产库环形图 |
| KnowledgeTrend.vue | 知识更新趋势堆叠柱状图 |
| KnowledgeSource.vue | 知识来源分布（5大体系进度条） |
| KnowledgeTable.vue | 知识资产表格（只读，Tab切换） |
| KnowledgeGraph.vue | 知识图谱（ECharts 力导向图） |
| KnowledgeQuality.vue | 知识质量概览（五维评估雷达） |
| KnowledgeTools.vue | 知识能力工具面板 |
| GraphDetailModal.vue | 图谱全屏详情模态框 |
| FolderTagItem.vue | 文件夹标签药片组件 |
| StatsCard.vue | 统计数据卡片 |
| Header.vue | 全局顶部栏 |
| Sidebar.vue | 全局侧边导航栏 |
| ColorSelector.vue | 颜色选择器 |
| IconSelector.vue | 图标选择器 |
| TagNode.vue | 标签树节点 |
| TagCheckbox.vue | 标签复选框 |
| TagTreeReadonly.vue | 只读标签树展示 |
| BusinessDomain.vue | 业务域卡片 |
| ModelTable.vue | 模型列表表格 |
| ServiceDetail.vue | 服务详情面板 |
| ServiceOverview.vue | 服务概览 |
| TaskPanel.vue | 任务面板 |
| FlowChart.vue | 流程图 |
| InterfacePanel.vue | 接口面板 |
| InvokeChart.vue | 调用量图表 |

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
| 来源分布 | 文件系统扫描 (5大体系分类) | 是（60s缓存） |
| 质量度量 | 静态数据 (quality-metrics端点) | 否 |

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

### Q: 文件预览提示"文件加载失败 (500)"？

1. **检查后端是否重启**：preview 接口是后端新增的路由，需要重启 uvicorn 才能生效
2. **中文文件名编码**：后端已使用 RFC 5987 编码处理 `Content-Disposition` 中的中文文件名，确保使用最新代码
3. **文件路径编码**：前端 `getFolderFilePreviewUrl()` 按路径段分别编码（保留 `/` 分隔符），不会对 `/` 编码为 `%2F`

### Q: 标签体系不显示？

确认后端 `/api/knowledge/folder/bases/{name}/tags` 接口正常返回数据。FolderTagItem 已抽为独立 SFC 组件（`src/components/FolderTagItem.vue`），如果显示异常，检查该组件是否正确加载。

### Q: Office 文件预览渲染失败？

- @vue-office 采用前端 `fetch → ArrayBuffer` 方式传入数据，绕开了 CORS 限制
- `.doc` / `.ppt` 等旧格式不支持在线预览（仅支持 `.docx` / `.xlsx` / `.pptx`）
- 大文件（>20MB）会被后端拒绝预览

### Q: AI 对话无响应？

1. 确认 `DASHSCOPE_API_KEY` 已配置在 `backend/.env` 中
2. 确认网络可达 `dashscope.aliyuncs.com`
3. 流式对话仅支持 `stream: true` 模式，非流式暂未实现

### Q: 文档上传后如何同步到知识图谱？

1. 文档上传后状态为 `pending`
2. 点击"同步到 LightRAG"按钮，调用 `POST /api/knowledge/bases/{kb_id}/sync-lightrag`
3. `sync_service.py` 读取已完成文档内容，逐个上传到 LightRAG
4. 成功后文档标记为 `synced`，图谱中即可检索到

### Q: 文件夹知识库如何导入为用户自建知识库？

调用 `POST /api/knowledge/folder/bases/{kb_name}/import`：
1. 验证文件夹KB存在且有文件
2. 在 SQLite 中创建 KB 记录，标签体系镜像文件夹结构
3. 逐个文件读取并保存到 uploads 目录，创建文档记录
4. 导入后即可使用文档管理、切片、LightRAG 同步等功能
