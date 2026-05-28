# 模型能力展示与体验工作台

基于 Vue 3 + TypeScript + Vite 构建的模型服务管理平台，提供模型能力展示、服务体验和调用监控等功能。

## 技术栈

| 技术 | 版本 |
|------|------|
| Vue | ^3.4 |
| TypeScript | ^5.3 |
| Vite | ^5.4 |
| Vue Router | ^4.3 |
| ECharts | ^5.5 |
| Element Plus | ^2.6+ |
| Sass | ^1.70 |

## 项目结构

```
model_show/
├── src/
│   ├── components/             # 公共组件
│   │   ├── Header.vue          # 顶部导航
│   │   ├── Sidebar.vue         # 侧边栏菜单
│   │   ├── StatsCard.vue       # 统计卡片
│   │   ├── ModelTable.vue      # 模型服务列表
│   │   ├── ServiceDetail.vue   # 服务详情面板
│   │   ├── TaskPanel.vue       # 待办事项面板
│   │   ├── FlowChart.vue       # 服务流量分布图表
│   │   ├── InvokeChart.vue     # 调用趋势图表
│   │   ├── InterfacePanel.vue  # 接口调试面板
│   │   └── ServiceOverview.vue # 服务质量概览
│   ├── views/                  # 页面
│   │   ├── Home.vue            # 工作台首页
│   │   ├── AbilityExperience.vue # 能力体验页
│   │   └── ModelService.vue    # 模型服务页
│   ├── data/                   # 模拟数据
│   │   └── models.ts
│   ├── router/                 # 路由配置
│   │   └── index.ts
│   ├── App.vue
│   ├── main.ts
│   └── style.scss              # 全局样式
├── index.html
├── package.json
├── vite.config.ts
└── tsconfig.json
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

## 快速开始

```bash
# 安装依赖
npm install --registry=https://registry.npmmirror.com

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览构建产物
npm run preview
```

启动后访问 `http://localhost:5173`

## 接口服务

| 接口路径 | 能力类型 | 接入方式 | 状态 |
|----------|----------|----------|------|
| `/v1/chat/completions` | 语言模型 | OpenAI兼容 | 已接入 |
| `/v1/images/analyze` | 视觉识别 | 图片上传 | 测试中 |
| `/v1/timeseries/forecast` | 时序预测 | CSV/JSON | 已封装 |
| `/v1/audio/transcriptions` | 语音转写 | 音频上传 | 试运行 |

## 模型列表

| 服务名称 | 基础模型 | QPS | 状态 |
|----------|----------|-----|------|
| Qwen3-14B-sichuan-chat | Qwen3-14B | 1.5 | 运行中 |
| Qwen3-VL-visual | Qwen3-VL | 1.6 | 运行中 |
| Qwen3-14B-sichuan-vision | Qwen3-14B | 1.5 | 运行中 |
| Chroma2-context | Chroma2 | 1.6 | 运行中 |
| ASR-Service-northbond | Qwen-ASR | 1.1 | 运行中 |
| Line-Detect-sichuan | Qwen3-14B-sichuan | 1.2 | 运行中 |
| OCR-Detect-sichuan | PaddleOCR-VL | 1.0 | 运行中 |
| OCR-Recog-sichuan | PaddleOCR-VL | 1.4 | 运行中 |