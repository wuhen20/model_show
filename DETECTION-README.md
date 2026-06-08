# 多模态大模型目标检测模块

## 概述

本模块基于多模态视觉大模型（如 Qwen2.5-VL），对电力行业场景图像进行智能目标检测与分析。支持上传图片、实时标注检测框、展示检测结果列表，并提供可配置的 API 参数与提示词管理。

## 检测场景

| 场景 | 说明 | 检测目标 |
|------|------|----------|
| 计量箱缺陷检测 | 电力计量箱外观图像缺陷识别 | 箱体破损、封印缺失、接线松动、锈蚀、标签模糊、箱门未关、箱体老化、表面脏污等 |
| 装表接电工艺检查 | 电表安装与接线工艺智能检查 |  |
| 电表示数识别 | 电表显示屏示数智能读取 |  |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript，ImageViewer（自研缩放/标注组件），ECharts |
| 后端 | Python + FastAPI，OpenAI SDK（兼容 OpenAI API 协议的视觉大模型） |
| 模型 | Qwen2.5-VL 等支持 `chat.completions` 图像输入的多模态大模型 |

## 目录结构

```
backend/app/api/routes/
└── detection.py                 # 检测 API（/api/detection/analyze、/api/detection/test-connection）

frontend/src/
├── views/
│   └── MultimodalDetection.vue  # 多模态检测页面（场景切换、配置面板、双视图、结果列表）
├── components/
│   └── ImageViewer.vue          # 图像查看器（缩放、拖拽、标注框绘制、高亮联动）
├── api/
│   └── chat.ts                  # 前端 API 封装（detectObjects、testApiConnection）
└── data/
    └── detectionScenes.ts       # 检测场景定义（提示词、模型配置、标签颜色映射）
```

## 后端 API

### POST `/api/detection/analyze`

上传图片并调用大模型进行目标检测。

**请求参数（FormData）：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `file` | UploadFile | 待检测图片（必填） |
| `endpoint` | string | 模型 API 地址 |
| `api_key` | string | API Key |
| `model_id` | string | 模型 ID（如 `qwen2.5-vl`） |
| `system_prompt` | string | 系统提示词 |
| `user_prompt` | string | 用户提示词 |
| `temperature` | float | 采样温度（默认 0.3） |
| `max_tokens` | int | 最大输出 token 数（默认 4096） |
| `enable_thinking` | bool | 是否开启思考模式（默认 false） |

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "detections": [
      {
        "label": "箱体破损",
        "confidence": 0.92,
        "bbox": [120, 80, 350, 290]
      }
    ],
    "raw_response": "...",
    "tokens": 1024,
    "model": "qwen2.5-vl",
    "image_size": { "width": 1920, "height": 1080 }
  }
}
```

### POST `/api/detection/test-connection`

测试模型 API 连接是否正常，返回可用模型列表。

## 坐标转换

模型返回的 `bbox_2d` 为 0-1000 归一化相对坐标（Qwen VL 格式），后端自动根据图片实际宽高转换为绝对像素坐标：

```
x_abs = int(x_rel / 1000 * image_width)
y_abs = int(y_rel / 1000 * image_height)
```

## 前端功能

- **场景切换**：顶部 Tab 切换三个检测场景，每个场景独立缓存配置（API 地址、模型、提示词、参数）
- **配置面板**：左侧可折叠面板，支持配置 API 地址/Key、系统/用户提示词、Temperature、Max Tokens、思考模式开关
- **配置持久化**：每个场景的配置独立存储到 `localStorage`，刷新后自动恢复
- **双视图对比**：原图与检测结果并排展示，支持鼠标滚轮缩放、拖拽平移，两侧视图同步联动
- **标注框渲染**：检测结果以彩色矩形框叠加在结果图上，点击结果列表行可高亮对应标注框
- **结果列表**：展示每个检测目标的类型、坐标、置信度，电表示数场景额外显示识别内容
- **原始响应**：可折叠查看模型原始返回文本，便于调试

## 快速使用

1. 启动前后端服务（参见项目根目录 `README.md`）
2. 访问 `/multimodal-detection` 页面
3. 在左侧配置面板填入 API 地址、Key 和模型 ID，点击"测试连接"验证
4. 选择检测场景，按需调整提示词
5. 点击"选择图片"上传待检测图片，点击"上传检测"执行检测
6. 查看结果图上的标注框和下方检测结果列表

## 配置项

后端 `.env` 中可设置默认值（前端可覆盖）：

| 环境变量 | 说明 |
|----------|------|
| `DETECTION_ENDPOINT` | 默认模型 API 地址 |
| `DETECTION_API_KEY` | 默认 API Key |
| `DETECTION_MODEL_ID` | 默认模型 ID |
| `DETECTION_SYSTEM_PROMPT` | 默认系统提示词 |
| `DETECTION_USER_PROMPT` | 默认用户提示词 |
| `DETECTION_TEMPERATURE` | 默认采样温度 |
| `DETECTION_MAX_TOKENS` | 默认最大 token 数 |
| `DETECTION_ENABLE_THINKING` | 默认是否开启思考模式 |
