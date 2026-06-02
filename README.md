# 模型能力展示与体验工作台

基于 **Vue 3 + TypeScript + Vite** 前端 + **Python FastAPI** 后端的前后端分离架构，提供模型能力展示、服务体验、知识管理等功能。

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端 | Vue 3 + TypeScript + Vite | ^3.4 / ^5.3 / ^5.4 |
| 前端 | Vue Router | ^4.3 |
| 前端 | Element Plus | ^2.9 |
| 前端 | ECharts | ^5.5 |
| 前端 | Sass | ^1.70 |
| 后端 | Python + FastAPI | >=3.10 / >=0.115 |
| 后端 | OpenAI SDK | >=1.50 |
| 后端 | Uvicorn (ASGI) | >=0.30 |
| 后端 | httpx (异步HTTP) | >=0.27 |
| 后端 | neo4j (Graph DB driver) | >=5.0 |
| 知识图谱 | LightRAG | ^1.4.16 |
| 图数据库 | Memgraph | via Docker |

## 项目结构

```
model_show/
├── frontend/                    # 前端 (Vue 3 + TypeScript + Vite)
│   ├── src/
│   │   ├── api/                 # API 请求层
│   │   │   ├── chat.ts          # 对话接口
│   │   │   └── knowledge.ts     # 知识管理接口
│   │   ├── components/          # 公共组件
│   │   │   ├── Header.vue       # 顶部导航
│   │   │   ├── Sidebar.vue      # 侧边栏菜单
│   │   │   ├── StatsCard.vue    # 统计卡片
│   │   │   ├── ModelTable.vue   # 模型服务列表
│   │   │   ├── ServiceDetail.vue # 服务详情面板
│   │   │   ├── TaskPanel.vue    # 待办事项面板
│   │   │   ├── FlowChart.vue    # 服务流量分布图表
│   │   │   ├── InvokeChart.vue  # 调用趋势图表
│   │   │   ├── InterfacePanel.vue # 接口调试面板
│   │   │   ├── ServiceOverview.vue # 服务质量概览
│   │   │   ├── KnowledgeCharts.vue    # 知识分类分布图
│   │   │   ├── KnowledgeGraph.vue     # 知识图谱
│   │   │   ├── KnowledgeQuality.vue   # 知识质量指标
│   │   │   ├── KnowledgeSource.vue    # 知识来源分布
│   │   │   ├── KnowledgeTable.vue     # 知识资产库表格
│   │   │   ├── KnowledgeTools.vue     # 知识能力工具
│   │   │   ├── KnowledgeTrend.vue     # 知识趋势图
│   │   │   └── BusinessDomain.vue     # 业务领域概览
│   │   ├── views/               # 页面
│   │   │   ├── Home.vue         # 工作台首页
│   │   │   ├── AbilityExperience.vue # 能力体验页
│   │   │   ├── ModelService.vue # 模型服务页
│   │   │   ├── KnowledgeManagement.vue # 知识管理页
│   │   │   └── KnowledgeDetail.vue     # 知识详情页
│   │   ├── data/                # 模拟数据
│   │   │   └── models.ts
│   │   ├── router/              # 路由配置
│   │   │   └── index.ts
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── style.scss
│   ├── public/                  # 静态资源
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── backend/                     # 后端 (Python FastAPI)
│   ├── app/
│   │   ├── api/routes/          # API 路由
│   │   │   ├── chat.py          # 对话接口 (流式+文件上传)
│   │   │   ├── models.py        # 模型列表接口
│   │   │   └── knowledge.py     # 知识管理接口
│   │   ├── core/
│   │   │   └── config.py        # 配置管理 (环境变量)
│   │   ├── schemas/
│   │   │   ├── chat.py          # 对话数据模型
│   │   │   └── knowledge.py     # 知识管理数据模型
│   │   ├── services/
│   │   │   ├── ai_service.py           # AI 调用服务层
│   │   │   ├── lightrag_service.py     # LightRAG HTTP 客户端
│   │   │   └── memgraph_service.py     # Memgraph 图数据库查询服务
│   │   └── main.py              # FastAPI 入口
│   ├── requirements.txt         # Python 依赖
│   ├── .env                     # 环境变量 (已 gitignore)
│   └── .env.example             # 环境变量模板
├── parsed_data.json             # 知识库结构化数据
├── list.txt                     # 知识库原始目录树
├── .gitignore
└── README.md
```

## 页面说明

### 1. 工作台首页 `/`

- 顶部统计卡片：在线服务数、已部署模型、今日调用量、平均响应、成功率、接口总数
- 模型服务列表：展示服务名称、基础模型、QPS、状态，支持筛选和操作
- 服务详情面板：基本信息、资源配置（GPU/显存/存储）、发布参数
- 待办事项与操作日志
- 服务流量分布饼图
- 调用趋势折线图
- 接口调试面板

### 2. 能力体验页 `/ability-experience`

- 四大模型方向入口：语言模型、视觉模型、时序模型、语音模型
- 业务场景能力卡片：台区线损分析、采集自愈、电压质量研判、现场图片识别
- 统一能力架构分层展示
- 在线体验输入区
- 接口服务目录

### 3. 模型服务页 `/model-service`

- 多模型选择器（Qwen3-14B / Qwen3-VL / Chroma2 / Qwen-ASR）
- 场景模板库
- 模型输出结果展示（异常等级、描述、处置建议）
- 调用与性能监控图表
- 服务质量概览

### 4. 知识管理页 `/knowledge-management`

- 页面概览统计：知识总量、结构化/非结构化知识、图谱实体（实时从 Memgraph 查询）、业务域覆盖、完整度、可用性
- 分类分布环形图 + 知识来源分布 + 质量指标 + 知识趋势
- 知识库分类卡片：5大知识库（计量营销专业知识库、计量数字讲师、专家系统知识库、装表接电知识库、采集自愈知识库），支持分类下钻
- 知识资产库表格：按分类过滤、多Tab切换（最新/热门/高价值/待审核）、行点击查看详情
  - 下钻「采集自愈知识库」时，文档列表从 LightRAG 实时获取，显示 LightRAG 处理状态（PROCESSED / PROCESSING / PENDING / FAILED）
- 知识图谱：
  - 全局视图：力导向图展示知识库→子分类→知识类型三层关系（来自静态 parsed_data.json）
  - 下钻视图：从 Memgraph 查询 LightRAG 提取的真实实体和关系，力导向图交互展示，节点按连接度分类着色
- 知识能力工具 + 业务领域概览
- 面包屑导航 + 返回全部按钮，支持分类过滤和全局视图切换

### 5. 知识详情页 `/knowledge-detail/:id`

- 知识标题与发布状态
- 元信息展示：所属知识库（可下钻跳转）、所属分类（可下钻跳转）、知识类型、来源、更新时间、质量评分
- 标签、知识描述、内容摘要、文件路径
- 返回按钮保留分类上下文

## 知识库数据

知识库数据来源于 `list.txt`（知识库目录树），通过后端解析生成 `parsed_data.json`：

| 知识库 | 文档数 | 子分类数 | 数据来源 |
|--------|--------|---------|---------|
| 计量营销专业知识库 | 2120 | 29 | 静态 parsed_data.json |
| 计量数字讲师 | 641 | 19 | 静态 parsed_data.json |
| 专家系统知识库 | 107 | 10 | 静态 parsed_data.json |
| 装表接电知识库 | 10 | 3 | 静态 parsed_data.json |
| 采集自愈知识库 | 8 | 1 | **LightRAG + Memgraph 实时数据** |

## LightRAG + Memgraph 知识图谱集成

### 架构说明

```
 ┌─────────────┐    HTTP API    ┌──────────────┐    Cypher     ┌──────────┐
 │  Vue 前端    │ ──────────→   │  FastAPI 后端  │ ──────────→  │  Memgraph │
 │  (5173)     │               │   (3002)      │              │  (7687)   │
 └─────────────┘               └───────┬───────┘              └─────┬────┘
                                       │                            │
                                       │ HTTP API                   │ Bolt
                                       ▼                            │
                               ┌──────────────┐                     │
                               │  LightRAG     │ ────────────────────┘
                               │  (9621)       │   实体/关系写入
                               └───────┬───────┘
                                       │
                                       │ LLM 抽取
                                       ▼
                               ┌──────────────┐
                               │  采集自愈文档   │
                               │  (8个 docx)   │
                               └──────────────┘
```

### 数据流

1. **文档入库**：将 docx 文件放入 `<input_dir>/<workspace>/` 目录，LightRAG 自动扫描并处理
2. **实体抽取**：LightRAG 调用 LLM（Qwen3.6-35B-A3B）从文档中抽取实体和关系
3. **图谱写入**：抽取结果写入 Memgraph（以 workspace label 隔离，如 `cai_ji_zi_yu`）
4. **前端查询**：用户点击知识库分类时，前端通过 API 获取实时数据
   - 知识列表：后端代理 LightRAG `/documents/paginated` API
   - 知识图谱：后端直接查询 Memgraph，返回 ECharts 兼容的 nodes/links 格式
   - 处理状态：后端代理 LightRAG `/documents/pipeline_status` API

### 关键配置

**LightRAG 配置** (`lightrag_data/.env`)：

```env
LIGHTRAG_GRAPH_STORAGE=MemgraphStorage
MEMGRAPH_URI=bolt://localhost:7687
LIGHTRAG_WORKSPACE=cai_ji_zi_yu
```

**后端配置** (`backend/app/core/config.py`)：

```python
lightrag_base_url: str = "http://127.0.0.1:9621"
memgraph_uri: str = "bolt://localhost:7687"
knowledge_bases: list[dict] = [
    {"id": "cai_ji_zi_yu", "name": "采集自愈知识库", "workspace": "cai_ji_zi_yu", ...},
]
```

### 新增后端服务

| 文件 | 说明 |
|------|------|
| `backend/app/services/lightrag_service.py` | LightRAG HTTP 客户端，代理文档列表、状态查询、图谱标签等 API |
| `backend/app/services/memgraph_service.py` | Memgraph 查询服务，使用 neo4j async driver 查询实体/关系，转为 ECharts 格式 |

### 新增/修改 API 端点

| 接口路径 | 方法 | 说明 | 变更 |
|----------|------|------|------|
| `/api/knowledge/bases` | GET | 获取知识库列表及处理状态 | **新增** |
| `/api/knowledge/pipeline-status` | GET | 文档处理管道状态 | **新增** |
| `/api/knowledge/list` | GET | 知识文档列表 | **修改** — 支持 workspace 参数，从 LightRAG 获取实时数据 |
| `/api/knowledge/graph` | GET | 知识图谱数据 | **修改** — 支持 workspace 参数，从 Memgraph 查询真实图谱 |
| `/api/knowledge/stats` | GET | 知识库统计概览 | **修改** — graph_entities 改为从 Memgraph 实时查询 |

### Memgraph 中的数据模型

LightRAG 将实体写入 Memgraph 时，每个节点带有 workspace label（如 `cai_ji_zi_yu`）：

```cypher
// 查询采集自愈知识库的实体数量
MATCH (n:`cai_ji_zi_yu`) RETURN count(n)

// 查询实体和关系
MATCH (n:`cai_ji_zi_yu`) RETURN n.entity_name, n.entity_type
MATCH (a:`cai_ji_zi_yu`)-[r]->(b:`cai_ji_zi_yu`) RETURN a.entity_name, type(r), b.entity_name
```

节点属性：`entity_id`, `entity_name`, `entity_type`, `description`
关系属性：`description`, `source_id`, `target_id`

## 快速开始

### 0. 启动 Memgraph（可选，知识图谱功能需要）

```bash
# 使用 Docker 启动 Memgraph
docker run -d --name memgraph -p 7687:7687 -p 7444:7444 memgraph/memgraph-platform

# 验证连接
python -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('bolt://localhost:7687'); print('OK')"
```

### 0.5 启动 LightRAG（可选，实时知识库功能需要）

```bash
# 在项目父目录下
cd ..

# 安装 LightRAG（已在 lightrag_env 虚拟环境中）
lightrag_env/Scripts/pip.exe install lightrag-hku neo4j

# 启动 LightRAG 服务
lightrag_env/Scripts/lightrag-server.exe \
  --host 127.0.0.1 --port 9621 \
  --working-dir lightrag_data \
  --input-dir 采集自愈知识库/新疆基层经验 \
  --workspace cai_ji_zi_yu \
  --llm-binding openai --embedding-binding openai

# 触发文档扫描
curl -X POST http://127.0.0.1:9621/documents/scan -H "LIGHTRAG-WORKSPACE: cai_ji_zi_yu"
```

> **注意**：即使不启动 Memgraph 和 LightRAG，前端也能正常运行，知识图谱和列表会使用静态 fallback 数据。

### 1. 启动后端

```bash
cd backend

# 安装 Python 依赖
pip install -r requirements.txt

# 复制环境变量配置 (首次运行)
cp .env.example .env
# 编辑 .env 填入你的 DASHSCOPE_API_KEY

# 启动后端服务 (端口 3002)
python -m uvicorn app.main:app --host 0.0.0.0 --port 3002
# 或: uvicorn app.main:app --host 0.0.0.0 --port 3002 --reload
```

API 文档自动生成: http://localhost:3002/docs

### 2. 启动前端

```bash
cd frontend

# 安装依赖
npm install --registry=https://registry.npmmirror.com

# 启动开发服务器 (端口 5173)
npm run dev

# 构建生产版本
npm run build

# 预览构建产物
npm run preview
```

启动后访问 `http://localhost:5173`

## API 接口

### 模型服务接口

| 接口路径 | 方法 | 说明 |
|----------|------|------|
| `/api/models` | GET | 获取可用模型列表 |
| `/api/chat` | POST | 流式对话 (SSE) |
| `/api/chat/upload` | POST | 文件上传对话 (支持图片) |
| `/api/health` | GET | 健康检查 |

### 知识管理接口

| 接口路径 | 方法 | 说明 |
|----------|------|------|
| `/api/knowledge/stats` | GET | 知识库统计概览（graph_entities 从 Memgraph 实时查询） |
| `/api/knowledge/categories` | GET | 知识库分类列表 (支持 parent_id 过滤) |
| `/api/knowledge/bases` | GET | **知识库列表**（含各库文档数、处理状态） |
| `/api/knowledge/pipeline-status` | GET | **文档处理管道状态**（支持 workspace 参数） |
| `/api/knowledge/list` | GET | 知识文档列表 (支持 category_id/keyword/tab/workspace 分页过滤) |
| `/api/knowledge/detail/{id}` | GET | 知识文档详情 |
| `/api/knowledge/source-distribution` | GET | 知识来源分布统计 |
| `/api/knowledge/category-distribution` | GET | 分类分布统计 |
| `/api/knowledge/quality-metrics` | GET | 知识质量指标 |
| `/api/knowledge/graph` | GET | 知识图谱数据（支持 workspace 参数，从 Memgraph 查询真实图谱） |

Swagger API 文档: http://localhost:3002/docs

## 变更记录

### 2026-06-02 LightRAG + Memgraph 知识图谱集成

**目标**：将 LightRAG 生成的采集自愈知识图谱同步到前端展示，并写入 Memgraph 图数据库。

**问题排查与修复**：

1. **文档未进入 LightRAG 处理管道**
   - 原因：LightRAG workspace 模式下，文档需放在 `<input_dir>/<workspace>/` 子目录，但文件放在了根目录
   - 修复：将 8 个 docx 文件移至 `<input_dir>/cai_ji_zi_yu/` 目录，并清理重复的 `_001`/`_002` 副本文件

2. **`/api/knowledge/bases` 返回 500 Internal Server Error**
   - 原因：`lightrag_service.get_status_counts()` 返回 `{"status_counts": {...}}` 嵌套结构，但路由代码对整个 dict 做了 `sum(values())`
   - 修复：在 `lightrag_service.py` 中提取内部的 `status_counts` 字典；路由中排除 `"all"` 键避免重复计数

3. **`/api/knowledge/list` 返回 422 Unprocessable Entity**
   - 原因：LightRAG `/documents/paginated` API 要求 `page_size >= 10`，前端可能传更小的值
   - 修复：在 `lightrag_service.py` 的 `get_documents_paginated()` 中增加 `safe_page_size = max(page_size, 10)`

4. **`/api/knowledge/stats` 的 graph_entities 是硬编码值**
   - 修复：改为异步函数，从 Memgraph 查询实际实体数量

5. **前端列表字段映射问题**
   - 修复：LightRAG 返回的 `file_path` → `title`（去掉扩展名），状态转大写，`updated_at` 截取日期部分

**新增文件**：
- `backend/app/services/lightrag_service.py` — LightRAG HTTP 客户端
- `backend/app/services/memgraph_service.py` — Memgraph 查询服务

**修改文件**：
- `backend/app/api/routes/knowledge.py` — 集成 LightRAG + Memgraph，新增 /bases、/pipeline-status 端点
- `backend/app/core/config.py` — 添加 LightRAG / Memgraph 连接配置、knowledge_bases 列表
- `backend/app/schemas/knowledge.py` — 扩展 status 枚举、新增 KnowledgeBase schema
- `backend/requirements.txt` — 添加 httpx、neo4j 依赖
- `frontend/src/api/knowledge.ts` — 新增 fetchKnowledgeBases、fetchPipelineStatus、fetchKnowledgeGraph(workspace)
- `frontend/src/components/KnowledgeGraph.vue` — 从 Memgraph 加载真实图谱数据
- `frontend/src/components/KnowledgeTable.vue` — 支持 workspace 过滤，LightRAG 状态标签
- `frontend/src/views/KnowledgeManagement.vue` — workspace 传递给子组件
