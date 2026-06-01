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
│   │   │   └── ai_service.py    # AI 调用服务层
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

- 页面概览统计：知识总量、结构化/非结构化知识、图谱实体、业务域覆盖、完整度、可用性
- 分类分布环形图 + 知识来源分布 + 质量指标 + 知识趋势
- 知识库分类卡片：5大知识库（计量营销专业知识库、计量数字讲师、专家系统知识库、装表接电知识库、采集自愈知识库），支持分类下钻
- 知识资产库表格：按分类过滤、多Tab切换（最新/热门/高价值/待审核）、行点击查看详情
- 知识图谱：力导向图展示知识库→子分类→知识类型三层关系，支持拖拽交互
- 知识能力工具 + 业务领域概览
- 面包屑导航 + 返回全部按钮，支持分类过滤和全局视图切换

### 5. 知识详情页 `/knowledge-detail/:id`

- 知识标题与发布状态
- 元信息展示：所属知识库（可下钻跳转）、所属分类（可下钻跳转）、知识类型、来源、更新时间、质量评分
- 标签、知识描述、内容摘要、文件路径
- 返回按钮保留分类上下文

## 知识库数据

知识库数据来源于 `list.txt`（知识库目录树），通过后端解析生成 `parsed_data.json`：

| 知识库 | 文档数 | 子分类数 |
|--------|--------|---------|
| 计量营销专业知识库 | 2120 | 29 |
| 计量数字讲师 | 641 | 19 |
| 专家系统知识库 | 107 | 10 |
| 装表接电知识库 | 10 | 3 |
| 采集自愈知识库 | 8 | 1 |

## 快速开始

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
| `/api/knowledge/stats` | GET | 知识库统计概览 |
| `/api/knowledge/categories` | GET | 知识库分类列表 (支持 parent_id 过滤) |
| `/api/knowledge/list` | GET | 知识文档列表 (支持 category_id/keyword/tab 分页过滤) |
| `/api/knowledge/detail/{id}` | GET | 知识文档详情 |
| `/api/knowledge/source-distribution` | GET | 知识来源分布统计 |
| `/api/knowledge/category-distribution` | GET | 分类分布统计 |
| `/api/knowledge/quality-metrics` | GET | 知识质量指标 |
| `/api/knowledge/graph` | GET | 知识图谱数据 (节点+关系+统计) |

Swagger API 文档: http://localhost:3002/docs
