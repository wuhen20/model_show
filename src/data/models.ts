export interface ModelInfo {
  id: string
  name: string
  baseModel: string
  version: string
  serviceType: string
  CPS: number
  TPS: number
  QPS: number
  owner: string
  status: 'running' | 'stopped' | 'error' | 'deploying'
  updateTime: string
}

export interface ServiceInfo {
  id: string
  name: string
  abilityType: string
  accessMode: string
  status: '已接入' | '测试中' | '已封装' | '试运行'
}

export interface ModelOutput {
  anomalyLevel: '正常' | '低风险' | '中风险' | '高风险'
  cause: string
  suggestions: string[]
  timestamp: string
}

export const modelList: ModelInfo[] = [
  {
    id: '1',
    name: 'Qwen3-14B-sichuan-chat',
    baseModel: 'Qwen3-14B',
    version: 'v1.6.2',
    serviceType: 'A100魔改',
    CPS: 128,
    TPS: 1.1,
    QPS: 1.5,
    owner: '王工',
    status: 'running',
    updateTime: '2025-10-19 09:30'
  },
  {
    id: '2',
    name: 'Qwen3-VL-visual',
    baseModel: 'Qwen3-VL',
    version: 'v1.0',
    serviceType: 'A100魔改',
    CPS: 86,
    TPS: 1.4,
    QPS: 1.6,
    owner: '赵工',
    status: 'running',
    updateTime: '2025-10-19 08:15'
  },
  {
    id: '3',
    name: 'Qwen3-14B-sichuan-vision',
    baseModel: 'Qwen3-14B',
    version: 'v2.0',
    serviceType: '4090服务器',
    CPS: 62,
    TPS: 1.4,
    QPS: 1.5,
    owner: '王工',
    status: 'running',
    updateTime: '2025-10-18 16:45'
  },
  {
    id: '4',
    name: 'Chroma2-context',
    baseModel: 'Chroma2',
    version: 'v1.0',
    serviceType: 'A100魔改',
    CPS: 78,
    TPS: 1.6,
    QPS: 1.6,
    owner: '赵工',
    status: 'running',
    updateTime: '2025-10-18 14:20'
  },
  {
    id: '5',
    name: 'ASR-Service-northbond',
    baseModel: 'Qwen-ASR',
    version: 'v1.0',
    serviceType: '通用服务器',
    CPS: 54,
    TPS: 0.9,
    QPS: 1.1,
    owner: '李工',
    status: 'running',
    updateTime: '2025-10-17 09:00'
  },
  {
    id: '6',
    name: 'Line-Detect-sichuan',
    baseModel: 'Qwen3-14B-sichuan',
    version: 'v1.0',
    serviceType: '4090服务器',
    CPS: 45,
    TPS: 1.0,
    QPS: 1.2,
    owner: '孙工',
    status: 'running',
    updateTime: '2025-10-16 11:30'
  },
  {
    id: '7',
    name: 'OCR-Detect-sichuan',
    baseModel: 'PaddleOCR-VL',
    version: 'v1.0',
    serviceType: '4090服务器',
    CPS: 38,
    TPS: 1.1,
    QPS: 1.0,
    owner: '陈工',
    status: 'running',
    updateTime: '2025-10-15 15:45'
  },
  {
    id: '8',
    name: 'OCR-Recog-sichuan',
    baseModel: 'PaddleOCR-VL',
    version: 'v1.0',
    serviceType: 'A100魔改',
    CPS: 22,
    TPS: 1.5,
    QPS: 1.4,
    owner: '周工',
    status: 'running',
    updateTime: '2025-10-14 10:20'
  }
]

export const serviceList: ServiceInfo[] = [
  {
    id: '1',
    name: '/v1/chat/completions',
    abilityType: '语言模型',
    accessMode: 'OpenAI兼容',
    status: '已接入'
  },
  {
    id: '2',
    name: '/v1/images/analyze',
    abilityType: '视觉识别',
    accessMode: '图片上传',
    status: '测试中'
  },
  {
    id: '3',
    name: '/v1/timeseries/forecast',
    abilityType: '时序预测',
    accessMode: 'CSV/JSON',
    status: '已封装'
  },
  {
    id: '4',
    name: '/v1/audio/transcriptions',
    abilityType: '语音转写',
    accessMode: '音频上传',
    status: '试运行'
  }
]

export const mockOutput: ModelOutput = {
  anomalyLevel: '低风险',
  cause: '台区线损率偏高(线损率8.72%,高于历史均值4.69%)，属于低风险告警',
  suggestions: [
    '建议检查计量装置是否正常工作，特别是智能电表的准确性',
    '排查是否存在窃电行为或异常用电情况',
    '检查线路是否存在老化、接触不良等问题',
    '建议安排现场巡检，核实实际用电情况与计量数据是否一致',
    '考虑进行台区负荷重新分配，平衡各相负载'
  ],
  timestamp: '2025-10-19 10:24:45'
}

export const statistics = {
  onlineModels: 18,
  deployedModels: 26,
  todayCalls: 128642,
  avgLatency: 1.18,
  successRate: 99.3,
  totalInterfaces: 32
}

export const recentTasks = [
  { id: '1', name: '新增Qwen3-14B-新版本', status: '处理中' },
  { id: '2', name: '扩容Chroma2-新版本', status: '待处理' },
  { id: '3', name: '下线旧版本-OCR服务', status: '待处理' },
  { id: '4', name: '补充标签数据集', status: '待处理' }
]

export const recentLogs = [
  { time: '10:24:45', action: '调用模型: Qwen3-14B-sichuan-chat' },
  { time: '10:23:15', action: '调用模型: Qwen3-VL-visual' },
  { time: '10:21:30', action: '保存场景: 台区线损分析 v2.0' },
  { time: '10:18:00', action: '用户登录: zhanggong' },
  { time: '10:15:20', action: '调用模型: Qwen3-14B-sichuan-chat' },
  { time: '10:12:00', action: '调用模型: ASR-Service-northbond' }
]

export const modelServiceStatus = [
  { name: 'Qwen3-14B-sichuan-chat', status: 'running', CPS: 128, TPS: 1.1, QPS: 1.5 },
  { name: 'Qwen3-VL-visual', status: 'running', CPS: 86, TPS: 1.4, QPS: 1.6 },
  { name: 'Chroma2-context', status: 'running', CPS: 78, TPS: 1.6, QPS: 1.6 },
  { name: 'ASR-Service-northbond', status: 'running', CPS: 54, TPS: 0.9, QPS: 1.1 }
]

export const abilityCategories = [
  { id: 'language', name: '语言模型能力', icon: 'message-square', count: 12 },
  { id: 'vision', name: '视觉模型能力', icon: 'image', count: 8 },
  { id: 'timeseries', name: '时序模型能力', icon: 'activity', count: 6 },
  { id: 'speech', name: '语音模型能力', icon: 'mic', count: 4 }
]

export const abilityCards = [
  { id: '1', name: '台区线损异常分析', type: '语言+时序', tag: '根因诊断', description: '融合台区时序数据与业务规则，定位线损异常原因并生成处置建议' },
  { id: '2', name: '采集自愈与智能运维', type: '语言+时序', tag: '运维增效', description: '识别采集故障模式，提供修复建议，提升运维效率与成功率' },
  { id: '3', name: '电压质量智能研判', type: '语言+时序', tag: '质量治理', description: '综合电压波动、谐波等指标，智能评估电压质量并给出治理建议' },
  { id: '4', name: '现场图片智能识别', type: '视觉+OCR', tag: '图像解析', description: '识别设备缺陷、表计读数与铭牌信息，辅助现场巡检与工单处理' }
]

export const frameworkLayers = [
  { name: '训推一体资源层', description: '统一调度GPU/CPU资源，支持训练、微调与推理一体化，弹性伸缩，保障性能与稳定性' },
  { name: '模型服务封装层', description: '标准化模型服务封装，兼容OpenAI接口规范，屏蔽底层差异，提供统一调用体验' },
  { name: '样本与知识沉淀层', description: '沉淀电力行业高质量样本与知识，支持版本管理、标签标注与增量更新，驱动模型效果提升' },
  { name: '体验与评估层', description: '提供可视化体验、量化评估与对比，支持场景化测试与反馈闭环，持续优化模型能力' }
]

export const invokeLogs = [
  { time: '11:38', count: 1245 },
  { time: '11:35', count: 1126 },
  { time: '11:30', count: 1038 },
  { time: '11:25', count: 1164 },
  { time: '11:20', count: 987 },
  { time: '11:15', count: 1056 },
  { time: '11:10', count: 1234 },
  { time: '11:05', count: 1189 },
  { time: '11:00', count: 1098 },
  { time: '10:55', count: 1210 },
  { time: '10:50', count: 1145 },
  { time: '10:45', count: 1078 }
]

export const sceneTemplates = [
  { id: '1', name: '台区线损分析', icon: 'trending-up' },
  { id: '2', name: '采集自愈分析', icon: 'wrench' },
  { id: '3', name: '电压质量研判', icon: 'zap' },
  { id: '4', name: '现场图片识别', icon: 'image' },
  { id: '5', name: '负荷预测', icon: 'bar-chart' }
]

export const invokeInfo = {
  endpoint: '/v1/chat/completions',
  method: 'POST',
  status: '正常',
  historyCalls: '1.18万',
  todayCalls: '1.126万',
  peakCalls: '1.038万',
  totalCalls: '2.64万'
}
