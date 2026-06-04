# 模型能力展示与体验工作台

基于 **Vue 3 + TypeScript + Vite** 前端 + **Python FastAPI** 后端的前后端分离架构，提供模型能力展示、服务体验和调用监控等功能。

> **v2 更新**：已集成「多维度异构时序数据样本处理系统」的全部能力，新增**时序样本集管理**、**时序模型服务（Chronos-2 预测）**、**时序模型分析（R²/MAPE 评估）**三大模块，与原系统统一为单一前后端。详见下文「时序功能」章节。

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端 | Vue 3 + TypeScript + Vite | ^3.4 / ^5.3 / ^5.4 |
| 前端 | Vue Router | ^4.3 |
| 前端 | Element Plus + @element-plus/icons-vue | ^2.9 / ^2.3 |
| 前端 | ECharts | ^5.5 |
| 前端 | axios | ^1.6 |
| 前端 | Sass | ^1.70 |
| 后端 | Python + FastAPI | >=3.10 / >=0.115 |
| 后端 | OpenAI SDK | >=1.50 |
| 后端 | Uvicorn (ASGI) | >=0.30 |
| 后端 | pandas / openpyxl / xlrd | >=2.2 / >=3.1 / >=2.0 |
| 后端 | chronos-forecasting（时序预测） | >=2.2 |
| 后端 | PyTorch（GPU 加速，cu128） | >=2.7 |

## 项目结构

```
model_show/
├── frontend/                    # 前端 (Vue 3 + TypeScript + Vite)
│   ├── src/
│   │   ├── api/                 # 原系统 API 请求层
│   │   │   └── chat.ts
│   │   ├── components/          # 公共组件
│   │   │   ├── Header.vue       # 顶部导航
│   │   │   ├── Sidebar.vue      # 侧边栏菜单（两级可展开）
│   │   │   ├── StatsCard.vue    # 统计卡片
│   │   │   ├── ModelTable.vue   # 模型服务列表
│   │   │   ├── ServiceDetail.vue # 服务详情面板
│   │   │   ├── TaskPanel.vue    # 待办事项面板
│   │   │   ├── FlowChart.vue    # 服务流量分布图表
│   │   │   ├── InvokeChart.vue  # 调用趋势图表
│   │   │   ├── InterfacePanel.vue # 接口调试面板
│   │   │   └── ServiceOverview.vue # 服务质量概览
│   │   ├── views/               # 页面
│   │   │   ├── Home.vue         # 工作台首页
│   │   │   ├── AbilityExperience.vue # 能力体验页
│   │   │   ├── ModelService.vue # 模型服务页
│   │   │   ├── TimeSeriesSampleSet.vue     # 时序样本集管理（含 4 个 Tab）
│   │   │   ├── TimeSeriesModelService.vue  # 时序模型服务（数据预测）
│   │   │   └── TimeSeriesAnalysis.vue      # 时序模型分析（数据分析）
│   │   ├── timeseries/          # 集成自 data-analysis 的时序功能前端
│   │   │   ├── api/index.js     # 时序接口请求层 (axios, baseURL=/api)
│   │   │   ├── views/           # 上传/预处理/整合/下载/预测/分析 视图
│   │   │   ├── components/      # ColumnMapper / FileUploader / StatStrip 等
│   │   │   └── styles/theme.css # Element Plus 深色科技主题（与本系统风格一致）
│   │   ├── data/                # 模拟数据
│   │   │   └── models.ts
│   │   ├── router/index.ts      # 路由配置
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── style.scss
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── backend/                     # 后端 (Python FastAPI，统一端口 3002)
│   ├── app/                     # 原系统（对话/模型）
│   │   ├── api/routes/
│   │   │   ├── chat.py          # 对话接口 (流式+文件上传)
│   │   │   └── models.py        # 模型列表接口
│   │   ├── core/config.py       # 配置管理 (环境变量)
│   │   ├── schemas/chat.py      # Pydantic 数据模型
│   │   ├── services/ai_service.py # AI 调用服务层
│   │   └── main.py              # FastAPI 入口（注册原系统 + 时序路由）
│   ├── routers/                 # ★ 时序功能路由 (upload/process/merge/download/predict/analysis)
│   ├── services/                # ★ 时序业务服务 (csv_parser/data_transformer/data_merger/predict_service/file_manager)
│   ├── models/schemas.py        # ★ 时序 Pydantic 模型
│   ├── predict_api_chronos2/    # ★ Chronos-2 预测原生接口 (Api/，不含 ~900MB 权重)
│   ├── data/                    # ★ 时序运行期数据 (uploads/processed/merged/predicted，已 gitignore)
│   ├── requirements.txt         # Python 依赖（含时序所需 pandas/torch/chronos）
│   ├── .env                     # 环境变量 (已 gitignore)
│   └── .env.example             # 环境变量模板
├── .gitignore
└── README.md
```

> 标注 ★ 的目录为本次集成新增；Chronos-2 模型权重（约 900MB）未纳入仓库，通过环境变量指向本地模型目录（见「环境变量说明」）。

## 导航结构（两级菜单）

| 一级目录 | 二级目录 | 对应功能 |
|----------|----------|----------|
| 工作台首页 | — | 原系统首页 |
| 能力体验 | — | 原系统能力体验 |
| 模型服务 | 模型服务总览 / **时序模型服务** | 原模型服务 / **时序数据预测** |
| 接口管理 / 场景配置 | — | 原系统 |
| 样本中心 | — | 原系统 |
| **样本集管理** | **时序样本集管理** | **上传 / 预处理 / 整合 / 下载** |
| 评测分析 | **时序模型分析** | **时序预测结果分析与评估** |
| 运行监控 / 日志中心 / 系统设置 | — | 原系统 |

## 页面说明

### 1. 工作台首页 `/`

- 顶部统计卡片：在线服务数、已部署模型、今日调用量、平均响应、成功率、接口总数
- 模型服务列表、服务详情面板、待办事项、流量分布饼图、调用趋势折线图、接口调试面板

### 2. 能力体验页 `/ability-experience`

- 四大模型方向入口：语言模型、视觉模型、时序模型、语音模型
- 业务场景能力卡片、统一能力架构分层、在线体验输入区、接口服务目录

### 3. 模型服务页 `/model-service`

- 多模型选择器、场景模板库、模型输出结果展示、调用与性能监控图表、服务质量概览

### 4. 时序样本集管理 `/timeseries/sample-set`

单页内通过顶部 Tab 集成时序样本全流程（菜单层级保持两级）：

- **数据上传**：支持 CSV / XLSX / XLS，多编码自动识别，智能推荐时间列/小时列，表头预览
- **数据预处理**：日期型 / 小时型 / 日期时间型三种时间标准化，输出统一为 `*_new.csv`
- **样本整合**：主表 + 多副表关联（INNER / LEFT JOIN），输出 `*_merge.csv`
- **文件下载与管理**：预处理 / 整合 / 预测 文件的列表、下载与删除

### 5. 时序模型服务 `/timeseries/model-service`

- 基于 **Amazon Chronos-2** 的时间序列预测
- 选择源文件（已上传/已处理/已整合）→ 配置时间列、目标字段、预测长度、分位数、模型目录 → 执行预测
- 输出 `*_predicted.csv`（按分位数展开）+ 元数据 JSON
- 自动选择 GPU(bfloat16) / CPU(float32) 回退

### 6. 时序模型分析 `/timeseries/analysis`

- 选择实际值与预测值文件，ECharts 多序列对比可视化
- 计算精度指标 **R²（决定系数）** 与 **MAPE（平均绝对百分比误差）**，支持时间对齐与区间筛选

## 快速开始

### 1. 启动后端

> ⚠️ 集成时序功能后，后端在 import 时即加载 `torch` / `chronos`，因此**必须在已安装 GPU 版 PyTorch + chronos-forecasting 的 Python 环境中运行**（本机为 conda 环境 `DataAnalysis`）。

```bash
cd backend

# 安装依赖（torch 需按显卡选择 CUDA 版本，见 requirements.txt 注释）
pip install -r requirements.txt
# RTX 50 系（Blackwell / sm_120）示例：
#   pip install torch>=2.7.0 torchvision>=0.22.0 --index-url https://download.pytorch.org/whl/cu128

# 复制环境变量配置 (首次运行)
cp .env.example .env
# 编辑 .env 填入 DASHSCOPE_API_KEY；如需自定义时序模型路径可设 CHRONOS2_MODEL_PATH

# 启动后端服务 (端口 3002，同时提供原系统接口与时序接口)
python -m app.main
# 或: uvicorn app.main:app --host 0.0.0.0 --port 3002 --reload
```

API 文档自动生成: http://localhost:3002/docs

### 2. 启动前端

```bash
cd frontend

# 安装依赖
npm install --registry=https://registry.npmmirror.com

# 启动开发服务器 (端口 5173，/api 已代理到 3002)
npm run dev

# 构建生产版本 / 预览
npm run build
npm run preview
```

启动后访问 `http://localhost:5173`

## API 接口

### 原系统

| 接口路径 | 方法 | 说明 |
|----------|------|------|
| `/api/models` | GET | 获取可用模型列表 |
| `/api/chat` | POST | 流式对话 (SSE) |
| `/api/chat/upload` | POST | 文件上传对话 (支持图片) |
| `/api/health` | GET | 健康检查 |
| `/docs` | GET | Swagger API 文档 |

### 时序功能

| 接口路径 | 方法 | 说明 |
|----------|------|------|
| `/api/upload/` `/api/upload/list` `/api/upload/{id}/headers` `/api/upload/{id}/preview` | POST/GET | 数据上传、表头、预览 |
| `/api/process/configure` `/api/process/{id}/execute` `/api/process/batch-execute` | POST | 预处理配置与执行 |
| `/api/merge/available-files` `/api/merge/execute` `/api/merge/list` `/api/merge/download/{id}` | GET/POST | 样本整合 |
| `/api/download/processed` `/api/download/merged` `/api/download/download/{id}` | GET/DELETE | 文件下载与管理 |
| `/api/predict/models` `/api/predict/available-files` `/api/predict/execute` `/api/predict/list` | GET/POST | 数据预测（Chronos-2） |
| `/api/analysis/available-files` `/api/analysis/get-data` `/api/analysis/calculate-metrics` | GET/POST | 数据分析（R²/MAPE） |

## 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key | (必填) |
| `DASHSCOPE_BASE_URL` | API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `SERVER_PORT` | 后端端口 | `3002` |
| `CORS_ORIGIN` | 允许跨域来源 | `*` |
| `CHRONOS2_MODEL_PATH` | 时序预测默认模型目录 | 由 `app/main.py` 指向本地 Chronos-2 目录 |
| `CHRONOS2_MODEL_ROOT` | 扫描可选模型的根目录 | 同上父目录 |
| `CHRONOS2_FORCE_CPU` | 设为 `1` 强制 CPU 推理 | (未设置=自动选 GPU) |

> 说明：Chronos-2 权重（约 900MB）未纳入仓库。`app/main.py` 通过 `os.environ.setdefault` 将上述模型路径默认指向本地 `data-analysis` 中已验证的模型目录；如在其它机器部署，请将 `CHRONOS2_MODEL_PATH` / `CHRONOS2_MODEL_ROOT` 指向实际模型位置。
