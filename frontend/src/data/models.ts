// 小模型与场景的前端类型定义 + 静态常量（场景目录、icon 映射）
// 模型清单由后端 /api/models 返回，本文件不再维护静态模型数据

export type SceneCode = 'ZJ' | 'XC' | 'FH' | 'TQ' | 'YD' | 'ZC'

export type IoType = 'timeseries' | 'image' | 'tabular' | 'multimodal'

export type ModelStatus = 'running' | 'planned' | 'offline' | 'error'

export interface SceneInfo {
  code: SceneCode
  name: string
  description: string
  icon: string
  count?: number
  running?: number
  total?: number
  today_calls?: number
  online_rate?: number
}

export interface ModelBrief {
  code: string
  name: string
  scene: SceneCode
  io_type: IoType
  backend_type: string
  status: ModelStatus
  current_version?: string | null
}

export interface ModelDetail extends ModelBrief {
  description?: string | null
  input_spec: { field: string; type?: string; required?: boolean }[]
  output_spec: { field: string; description?: string }[]
  sub_scenes?: string[] | null
  updated_at?: string | null
}

export interface DashboardStats {
  scene_count: number
  model_count: number
  running_models: number
  training_tasks: number
  mcp_services: number
  today_calls: number
  avg_latency_ms: number
  success_rate: number
}

export interface InvokeTrendPoint {
  time: string
  count: number
}

// 6 大场景目录（与后端 SCENE_CATALOG 对齐）
export const sceneCatalog: SceneInfo[] = [
  { code: 'ZJ', name: '采集自愈', description: '采集系统自愈与运维智能化', icon: 'wrench' },
  { code: 'XC', name: '现场作业', description: '现场作业行为识别与稽核', icon: 'camera' },
  { code: 'FH', name: '负荷资源管理', description: '负荷资源评估、申报与调控', icon: 'battery' },
  { code: 'TQ', name: '台区四精管理', description: '台区精准运维与用户分析', icon: 'grid' },
  { code: 'YD', name: '用电异常监控', description: '用电异常识别与欺诈研判', icon: 'alert' },
  { code: 'ZC', name: '资产管理', description: '电力资产数字化识别', icon: 'tag' }
]

export const ioTypeLabels: Record<IoType, string> = {
  timeseries: '时序',
  image: '图像',
  tabular: '表格',
  multimodal: '多模态'
}

export const statusLabels: Record<ModelStatus, { text: string; type: string }> = {
  running: { text: '运行中', type: 'success' },
  planned: { text: '待训练', type: 'info' },
  offline: { text: '已下线', type: 'warning' },
  error: { text: '异常', type: 'danger' }
}

// ── 数据集相关类型 ──────────────────────────────────────────────────────────────────

export type DatasetFormat = 'csv' | 'txt' | 'jpg' | 'png' | 'mp4' | 'zip'
export type DatasetType = 'general' | 'yolo_detection'

export const datasetFormatLabels: Record<DatasetFormat, string> = {
  csv: 'CSV', txt: 'TXT', jpg: 'JPG', png: 'PNG', mp4: 'MP4', zip: 'ZIP'
}

export const datasetTypeLabels: Record<DatasetType, string> = {
  general: '通用', yolo_detection: 'YOLO 目标检测'
}

export interface DatasetBrief {
  id: number
  name: string
  scene: SceneCode
  model_code?: string | null
  format: DatasetFormat
  dataset_type: DatasetType
  description?: string | null
  classes?: string[] | null
  image_count: number
  label_count: number
  sample_count: number
  file_count: number
  size_bytes: number
  current_version?: string | null
  version_count: number
  created_at?: string | null
}

export interface DatasetVersionBrief {
  id: number
  version: string
  file_count: number
  sample_count: number
  size_bytes: number
  created_at?: string | null
}

export interface DatasetDetail extends DatasetBrief {
  schema_json?: string | null
  updated_at?: string | null
  versions: DatasetVersionBrief[]
}

export interface YoloObject {
  class_id: number
  class_name: string
  cx: number
  cy: number
  w: number
  h: number
}

export interface YoloPreviewItem {
  image_url: string
  image_file: string
  objects: YoloObject[]
}

export interface DatasetPreviewRow {
  [key: string]: string
}
