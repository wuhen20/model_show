# 用电公司小模型能力展示平台

> 面向 6 大业务场景、20 个小模型的能力展示与体验工作台。
> **当前状态：M1 骨架开发完成（后端 + 前端核心功能联调通过）。**

## 平台概览

- **6 大业务场景**：采集自愈 / 现场作业 / 负荷资源管理 / 台区四精管理 / 用电异常监控 / 资产管理
- **20 个小模型**：详见 `backend/app/registry/model_registry.py` 中的 `MODEL_REGISTRY`
- **7 大功能模块**：工作台首页、小模型管理、小模型训练、展示及体验、训练数据集管理、MCP 服务管理、MCP 服务测试
- **MVP 约束**：SQLite + 本地文件、全 CPU 推理、不接入鉴权

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端 | Vue 3 + TypeScript + Vite | ^3.4 / ^5.3 / ^5.4 |
| 前端 | Vue Router / Element Plus / ECharts | ^4.3 / ^2.9 / ^5.5 |
| 后端 | Python + FastAPI | >=3.10 / >=0.115 |
| 后端 | SQLAlchemy 2.0 + SQLite (WAL) | >=2.0 |
| 推理 | torch / xgboost-cpu / scikit-learn / joblib | CPU 版本 |
| MCP | mcp（FastMCP） | >=1.0.0 |
| LLM | OpenAI SDK（兼容百炼 DashScope） | >=1.50 |

## 项目结构

```
model_show/
├── frontend/                   # Vue 3 前端
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/routes/         # 4 大 API 路由（dashboard / models / predict / chat）
│   │   ├── services/           # ai_service（DashScope LLM）
│   │   ├── registry/           # 20 个模型注册表
│   │   ├── db/                 # SQLite ORM（model_metadata / model_version / invocation_log）
│   │   ├── schemas/            # Pydantic schema
│   │   ├── core/               # config（pydantic-settings）
│   │   └── main.py
│   ├── data/                   # 运行时数据（gitignore）
│   ├── models_pool/            # 模型权重根目录（gitignore）
│   └── requirements.txt
├── .gitignore
└── README.md
```

## 快速开始

### 1. 启动后端

```powershell
cd backend

# 安装 Python 依赖（推荐使用 py -3.11）
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制环境变量配置（首次运行）
copy .env.example .env
# 编辑 .env 填入 DASHSCOPE_API_KEY

# 启动后端服务（端口 3002）
.\.venv\Scripts\python.exe -m app.main
# 或:
# .\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 3002 --reload
```

API 文档：http://localhost:3002/docs

### 2. 启动前端

```powershell
cd frontend

# 安装依赖
npm install

# 启动开发服务器（端口 5173）
npm run dev

# 构建生产版本
npm run build

# 预览构建产物
npm run preview
```

启动后访问 `http://localhost:5173`。前端开发服务器通过 Vite proxy 将 `/api` 代理到后端 `localhost:3002`。

## 核心 API 一览

| 模块 | 接口 | 说明 |
|---|---|---|
| 首页 | `GET /api/dashboard/stats` | 6 张统计卡数据 |
| 首页 | `GET /api/dashboard/scene-summary` | 6 大场景概览 |
| 首页 | `GET /api/dashboard/invoke-trend` | 调用趋势（时间桶聚合） |
| 小模型管理 | `GET /api/models` | 小模型列表 |
| 小模型管理 | `GET /api/models/{code}` | 小模型详情 |
| 统一推理 | `POST /api/predict/{code}` | 统一推理入口（M1 mock） |
| 对话服务 | `POST /api/chat` | LLM 流式对话 |
| LLM 列表 | `GET /api/llm-models` | 对话用 LLM 列表 |
| 落地清单 | `GET /api/health` | 健康检查 |
| 文档 | `GET /docs` | Swagger API 文档 |

> 训练、数据集、MCP 模块的 API 待 M2+ 接入。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key（LLM 解读用） | 必填（对话功能需要） |
| `DASHSCOPE_BASE_URL` | API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `SERVER_PORT` | 后端端口 | `3002` |
| `CORS_ORIGIN` | 允许跨域来源（逗号分隔） | `http://localhost:5173,http://127.0.0.1:5173` |
| `DATA_DIR` | 数据根目录 | `./data` |
| `MODELS_POOL_DIR` | 模型权重根目录 | `./models_pool` |
| `MCP_PORT_RANGE` | MCP 子进程端口范围 | `8100-8199` |

## 开发约定

- Git 分支：`dev-algomodel`
- Windows 终端使用 PowerShell，**不要用 `&&`**，改用 `;` 或多行
- 虚拟环境调用使用 `.\.venv\Scripts\python.exe`，不依赖激活脚本
- npm 安装推荐 `--registry=https://registry.npmmirror.com` 加速
- 全部模型 CPU 推理
- **`.env` 文件已 gitignore，不要提交真实凭据**