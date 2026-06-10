/**
 * 演示服务 API 封装：终端异常研判 & 电表异常研判
 */
const BASE_URL = (import.meta as any).env?.VITE_API_BASE || ''

// ============ 类型定义 ============

export interface DemoModelInfo {
  model_type: string
  n_features: number
  n_labels: number
  label_columns: string[]
  label_cn_map: Record<string, string>
  feature_columns: string[]
  feature_cn_map: Record<string, string>
  thresholds: Record<string, number>
  feature_importance?: Record<string, { features: string[]; importance: number[] }>
  is_tuned: boolean
  model_path: string
}

export interface DemoPerLabelMetrics {
  f1: number
  precision: number
  recall: number
  balanced_accuracy: number
  auc: number | null
}

export interface DemoOverallMetrics {
  micro_f1: number
  macro_f1: number
  micro_precision: number
  micro_recall: number
  subset_accuracy: number
  hamming_loss: number
  per_label: Record<string, DemoPerLabelMetrics>
}

export interface DemoPredictItem {
  index: number
  device_id: string | null
  features: Record<string, number | null>
  probs: Record<string, number>
  preds: Record<string, number>
  pred_labels: string[]
  pred_label_count: number
  primary_label: string | null
}

export interface DemoSummary {
  total_samples: number
  anomaly_samples: number | null
  pred_anomaly_samples?: number
  pos_counts?: Record<string, number>
  pred_pos_counts?: Record<string, number>
}

export interface DemoPredictResult {
  model_info: DemoModelInfo
  n_samples: number
  n_features: number
  n_labels: number
  feature_columns: string[]
  feature_cn_map: Record<string, string>
  label_columns: string[]
  label_cn_map: Record<string, string>
  thresholds: Record<string, number>
  predictions: DemoPredictItem[]
  summary: DemoSummary
  metrics: DemoOverallMetrics | null
  cooccurrence_matrix: number[][]
  pos_counts: number[]
  feature_importance?: Record<string, { features: string[]; importance: number[] }>
  error?: string
}

export interface DemoTuneCombo {
  combo_index: number
  params: Record<string, number>
  val_macro_f1: number
  val_micro_f1: number
}

export interface DemoTuneResult {
  grid_search: {
    n_combos: number
    time_elapsed_seconds: number
    best_params: Record<string, number>
    best_combo_index: number
    original_macro_f1: number
    tuned_macro_f1: number
    improvement: number
    grid_results: DemoTuneCombo[]
    original_full_metrics: DemoOverallMetrics
  }
  metrics: DemoOverallMetrics
  predictions: DemoPredictItem[]
  [key: string]: any
}
// DemoTuneResult 包含完整预测数据，扩展 DemoPredictResult 字段

export interface DemoTuneStatus {
  running: boolean
  message: string
  progress: number
}

// ============ API 函数 ============

/** 创建 demo API 客户端 */
export function createDemoApi(apiBase: string) {
  const base = apiBase // 如 '/api/demo/terminal'

  return {
    /** 健康检查 */
    async ping(): Promise<{ status: string; message: string }> {
      const resp = await fetch(`${BASE_URL}${base}/ping`)
      if (!resp.ok) throw new Error(`服务连接失败: ${resp.status}`)
      return resp.json()
    },

    /** 获取模型信息 */
    async modelInfo(): Promise<DemoModelInfo> {
      const resp = await fetch(`${BASE_URL}${base}/model_info`)
      if (!resp.ok) throw new Error(`获取模型信息失败: ${resp.status}`)
      return resp.json()
    },

    /** 获取演示 CSV */
    getDemoCsvUrl(): string {
      return `${BASE_URL}${base}/demo_csv`
    },

    /** 上传 CSV 并运行预测 */
    async predict(file: File): Promise<DemoPredictResult> {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch(`${BASE_URL}${base}/predict`, { method: 'POST', body: form })
      if (!resp.ok) throw new Error(`预测请求失败: ${resp.status}`)
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      return data
    },

    /** 超参数网格搜索调优 */
    async gridsearchTune(file: File): Promise<DemoTuneResult> {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch(`${BASE_URL}${base}/gridsearch_tune`, { method: 'POST', body: form })
      if (!resp.ok) throw new Error(`调优请求失败: ${resp.status}`)
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      return data
    },

    /** 获取调优状态 */
    async gridsearchStatus(): Promise<DemoTuneStatus> {
      const resp = await fetch(`${BASE_URL}${base}/gridsearch_status`)
      if (!resp.ok) throw new Error(`获取调优状态失败: ${resp.status}`)
      return resp.json()
    },

    /** 重置模型 */
    async resetModel(): Promise<{ status: string; message: string }> {
      const resp = await fetch(`${BASE_URL}${base}/reset_model`, { method: 'POST' })
      if (!resp.ok) throw new Error(`模型重置失败: ${resp.status}`)
      return resp.json()
    }
  }
}

export type DemoApi = ReturnType<typeof createDemoApi>

// ============ 电表健康评价 API ============

export interface MeterHealthUploadResult {
  task_id: string
  filename: string
  rows: number
  columns: number
  removal_rate: number | null
  has_mfr: boolean
  has_is_removed: boolean
}

export interface MeterHealthStatus {
  task_id: string
  status: string
  progress: number
  message: string
}

export interface MeterHealthTrainParams {
  task_id: string
  use_grid_search: boolean
  n_est_start?: number
  n_est_end?: number
  n_est_step?: number
  max_samp_start?: number
  max_samp_end?: number
  max_samp_step?: number
  max_feat_start?: number
  max_feat_end?: number
  max_feat_step?: number
}

export interface MeterHealthTrainResult {
  stats: Record<string, { mean: number; std: number; min: number; max: number; median: number }>
  grade_counts: Record<string, number>
  mfr_stats: Record<string, { mean: number; count: number; std: number }>
  charts: Record<string, string>
  validation: MeterHealthValidation
  validation_charts: Record<string, string>
  weights: Record<string, number>
  model_path: string
  result_csv_path: string
  total_rows: number
  grid_search: Record<string, any>
  use_grid_search: boolean
}

export interface MeterHealthValidation {
  train_auc?: number
  cv_mean_auc?: number
  cv_std_auc?: number
  overfit_gap?: number
  removed_rank_mean?: number
  fold_aucs?: number[]
  removed_ranks?: number[]
  module_aucs?: Record<string, number | null>
  warning?: string
}

export interface MeterHealthPredictResult {
  stats: Record<string, { mean: number; std: number; min: number; max: number; median: number }>
  grade_counts: Record<string, number>
  top_risk_meters: Record<string, any>[]
  result_csv_path: string
  total_rows: number
  de_count: number
}

/** 创建电表健康评价 API 客户端 */
export function createMeterHealthApi() {
  const base = '/api/demo/meter-health'

  return {
    async ping(): Promise<{ status: string; message: string }> {
      const resp = await fetch(`${BASE_URL}${base}/ping`)
      if (!resp.ok) throw new Error(`服务连接失败: ${resp.status}`)
      return resp.json()
    },

    getDemoCsvUrl(): string {
      return `${BASE_URL}${base}/demo_csv`
    },

    async upload(file: File): Promise<MeterHealthUploadResult> {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch(`${BASE_URL}${base}/upload`, { method: 'POST', body: form })
      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || '上传失败')
      }
      return resp.json()
    },

    async train(params: MeterHealthTrainParams): Promise<{ status: string; task_id: string }> {
      const form = new FormData()
      form.append('task_id', params.task_id)
      form.append('use_grid_search', String(params.use_grid_search))
      form.append('optimize', 'false')
      form.append('n_calls', '30')
      if (params.use_grid_search) {
        form.append('n_est_start', String(params.n_est_start ?? 100))
        form.append('n_est_end', String(params.n_est_end ?? 500))
        form.append('n_est_step', String(params.n_est_step ?? 100))
        form.append('max_samp_start', String(params.max_samp_start ?? 0.5))
        form.append('max_samp_end', String(params.max_samp_end ?? 1.0))
        form.append('max_samp_step', String(params.max_samp_step ?? 0.1))
        form.append('max_feat_start', String(params.max_feat_start ?? 0.5))
        form.append('max_feat_end', String(params.max_feat_end ?? 1.0))
        form.append('max_feat_step', String(params.max_feat_step ?? 0.1))
      }
      const resp = await fetch(`${BASE_URL}${base}/train`, { method: 'POST', body: form })
      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || '启动训练失败')
      }
      return resp.json()
    },

    async getStatus(taskId: string): Promise<MeterHealthStatus> {
      const resp = await fetch(`${BASE_URL}${base}/status/${taskId}`)
      if (!resp.ok) throw new Error(`获取状态失败: ${resp.status}`)
      return resp.json()
    },

    async getResults(taskId: string): Promise<MeterHealthTrainResult> {
      const resp = await fetch(`${BASE_URL}${base}/results/${taskId}`)
      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || '获取结果失败')
      }
      return resp.json()
    },

    async getValidation(taskId: string): Promise<{ validation: MeterHealthValidation; validation_charts: Record<string, string> }> {
      const resp = await fetch(`${BASE_URL}${base}/validation/${taskId}`)
      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || '获取验证结果失败')
      }
      return resp.json()
    },

    async predict(file: File, taskId: string): Promise<{ predict_task_id: string; status: string }> {
      const form = new FormData()
      form.append('file', file)
      form.append('task_id', taskId)
      const resp = await fetch(`${BASE_URL}${base}/predict`, { method: 'POST', body: form })
      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || '预测请求失败')
      }
      return resp.json()
    },

    async getPredictResults(taskId: string): Promise<MeterHealthPredictResult> {
      const resp = await fetch(`${BASE_URL}${base}/predict-results/${taskId}`)
      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || '获取预测结果失败')
      }
      return resp.json()
    },

    getDownloadUrl(taskId: string, fileType: 'result' | 'model' = 'result'): string {
      return `${BASE_URL}${base}/download/${taskId}?file_type=${fileType}`
    },
  }
}

export type MeterHealthApi = ReturnType<typeof createMeterHealthApi>