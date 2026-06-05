# 模型能力展示与体验工作台 · 融合平台

基于 **Vue 3 + TypeScript + Vite** 前端 + **Python FastAPI** 后端的前后端分离架构。本项目在原“模型能力展示与体验工作台”基础上，**融合了 5 个分散子系统的全部功能**，统一在同一套依赖、框架与 UI 风格之下：

| 子系统（来源分支） | 融合后的功能模块 |
|---|---|
| `dev-algomodel` | **小模型平台**：平台概览 / 小模型管理 / 训练 / 体验 / 训练数据集 / MCP 服务管理 / MCP 服务测试 |
| `multimodal-llm` | **多模态目标检测**（计量箱缺陷 / 装表接电工艺 / 电表示数识别） |
| `sxy-sample-center` | **样本中心**：样本总览 / 样本集管理 / 样本详情（含图片 YOLO 标注、音频转写） |
| `liuqi-knowledgebase` | **知识管理**：知识图谱、文件夹知识库、用户自建知识库、创建向导 |
| `time-series-large-model` | **时序大模型**：时序样本集管理 / 时序模型服务（Chronos-2） / 时序模型分析（R²/MAPE） |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Vite，Vue Router，Element Plus + @element-plus/icons-vue，ECharts，axios，@vue-office（docx/excel/pdf/pptx），Sass |
| 后端 | Python + FastAPI + Uvicorn，OpenAI SDK，SQLAlchemy（小模型平台），PyMySQL（样本中心），neo4j/minio（知识管理），pandas/openpyxl/chronos-forecasting/torch（时序） |

## 统一导航（两级菜单）

```
工作台首页              /                          原系统智能问答工作台
能力体验                /ability-experience
模型服务 ▾
  ├ 模型服务总览        /model-service
  ├ 多模态目标检测       /multimodal-detection
  └ 时序模型服务        /timeseries/model-service
小模型平台 ▾（统一外壳 SmLayout）
  ├ 平台概览           /sm
  ├ 小模型管理         /models  (+ /models/:code)
  ├ 小模型训练         /training
  ├ 小模型体验         /experience  (+ /experience/:code)
  ├ 训练数据集         /datasets
  ├ MCP 服务管理       /mcp
  └ MCP 服务测试       /mcp/test
知识管理                /knowledge-management  (+ /knowledge-detail/:id、/knowledge-create、/knowledge-base/:id、/folder-kb/:name)
样本中心                /sample
样本集管理 ▾
  ├ 样本集管理         /sample-set  (+ /sample-detail)
  └ 时序样本集管理      /timeseries/sample-set
评测分析 ▾
  └ 时序模型分析        /timeseries/analysis
接口管理 / 场景配置 / 运行监控 / 日志中心 / 系统设置   （原系统预留入口）
```

> **布局约定**：原系统及知识管理/样本中心/多模态/时序等视图采用「每视图自带 Header+Sidebar」布局；小模型平台的内容型视图统一由 `layouts/SmLayout.vue` 外壳承载，并保留其原始路径（`/models`、`/experience` 等），因此内部跳转无需改动。

## 后端 API 命名空间

| 前缀 | 模块 |
|------|------|
| `/api/models`、`/api/chat`、`/api/llm-models` | 原系统：LLM 列表 / 对话 |
| `/api/sm/dashboard`、`/api/sm/models`、`/api/sm/predict` | 小模型平台（与原 LLM `/api/models` 区分，统一收敛到 `/api/sm`） |
| `/api/detection` | 多模态目标检测 |
| `/api/sample` | 样本中心（MySQL） |
| `/api/knowledge`、`/api/knowledge/folder` | 知识管理（Memgraph / LightRAG 可选） |
| `/api/upload`、`/api/process`、`/api/merge`、`/api/download`、`/api/predict`、`/api/analysis` | 时序功能 |

API 文档：http://localhost:3002/docs

## 快速开始

### 1. 后端（端口 3002）

```bash
cd backend
pip install -r requirements.txt
#   · RTX 50 系（Blackwell）：torch>=2.7.0 torchvision>=0.22.0 --index-url https://download.pytorch.org/whl/cu128
cp .env.example .env          # 填入 DASHSCOPE_API_KEY，按需配置 Memgraph/LightRAG/MySQL/Chronos 路径
python -m app.main            # 或 uvicorn app.main:app --host 0.0.0.0 --port 3002 --reload
```

> 各模块的外部依赖（样本中心 MySQL、知识管理 Memgraph/LightRAG、时序 Chronos-2 权重）均为**可选**：未启用时对应接口降级，平台与其它模块仍可正常启动运行。相关开关见 `app/core/config.py`（`memgraph_enabled`、`lightrag_enabled`、`db_*`、`CHRONOS2_MODEL_PATH` 等）。

### 2. 前端（端口 5173，`/api` 已代理到 3002）

```bash
cd frontend
npm install --registry=https://registry.npmmirror.com
npm run dev        # 开发
npm run build      # 生产构建
```

访问 `http://localhost:5173`

## 目录结构（融合后要点）

```
backend/
├── app/
│   ├── api/routes/   chat, models（LLM）, dashboard, sm_models, predict（小模型）, detection, sample, knowledge, folder_kb, kb_management
│   ├── core/         config.py（全模块配置并集）, database.py（样本中心 MySQL）
│   ├── db/ registry/ schemas/model.py   小模型平台（SQLAlchemy + 注册表）
│   ├── services/     ai_service + 知识管理服务（db/fake/folder_kb/lightrag/memgraph/storage/sync）
│   └── main.py       注册全部路由 + 统一 lifespan
├── routers/ services/ models/ predict_api_chronos2/   时序功能（顶层包，main.py 注入 sys.path）
└── requirements.txt  全模块依赖并集
frontend/src/
├── layouts/SmLayout.vue          小模型平台外壳
├── components/                   原系统 + 知识管理（Knowledge*/Tag*/Folder* 等）+ ImageViewer
├── views/                        全部模块页面
├── timeseries/                   时序功能前端（api/components/views/styles）
├── api/  chat.ts(含检测), models.ts(/api/sm), sample.ts, knowledge.ts
├── data/ models.ts(LLM/服务), smModels.ts(小模型), detectionScenes.ts
├── router/index.ts               统一路由
└── components/Sidebar.vue        统一两级导航
```
