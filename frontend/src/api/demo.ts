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

// ============ 终端健康评价 API ============

export interface TerminalHealthDataInfo {
  status: string
  rows: number
  columns: number
  column_names: string[]
  removal_rate: number | null
  removal_count: number | null
  manufacturers: string[] | null
  manufacturer_count: number | null
}

export interface TerminalHealthScoreStats {
  mean: number
  std: number
  min: number
  max: number
  median: number
}

export interface TerminalHealthTrainResult {
  status: string
  message: string
  score_stats: Record<string, TerminalHealthScoreStats>
  grade_dist: Record<string, number>
  mfr_analysis: { MFR: string; mean: number; count: number; std: number }[] | null
  score_distribution: { counts: number[]; edges: number[]; labels: string[] } | null
  removal_distribution: { removed: number[]; normal: number[] } | null
  total_samples: number
  weights: Record<string, number>
}

export interface TerminalHealthGridSearchModule {
  status: string
  module: string
  module_name: string
  best_params: { n_estimators: number; max_samples: number; max_features: number }
  best_auc: number
  max_features_values: number[]
  heatmaps: Record<string, { x_labels: number[]; y_labels: number[]; matrix: number[][] }>
}

export interface TerminalHealthGridSearchResult {
  status: string
  message: string
  modules: TerminalHealthGridSearchModule[]
  auto_trained: boolean
}

export interface TerminalHealthCVResult {
  status: string
  message: string
  n_folds: number
  fold_results: {
    fold: number
    train_size: number
    test_size: number
    auc: number | null
    avg_rank_quantile: number | null
    removed_count: number
    mean_score: number
    std_score: number
  }[]
  mean_auc: number | null
  std_auc: number | null
  overall_auc: number | null
  avg_rank_quantile: number | null
  evaluation: string
  auc_chart: { labels: string[]; values: number[] }
}

export interface TerminalHealthPredictResult {
  status: string
  message: string
  results: Record<string, any>[]
  grade_dist: Record<string, number>
  total_samples: number
  columns: string[]
}

/** 创建终端健康评价 API 客户端 */
export function createTerminalHealthApi() {
  const base = '/api/demo/terminal-health'

  return {
    async ping(): Promise<{ status: string; message: string }> {
      const resp = await fetch(`${BASE_URL}${base}/ping`)
      if (!resp.ok) throw new Error(`服务连接失败: ${resp.status}`)
      return resp.json()
    },

    async modelInfo(): Promise<any> {
      const resp = await fetch(`${BASE_URL}${base}/model_info`)
      if (!resp.ok) throw new Error(`获取模型信息失败: ${resp.status}`)
      return resp.json()
    },

    getDemoCsvUrl(): string {
      return `${BASE_URL}${base}/demo_csv`
    },

    async upload(file: File): Promise<{ status: string; message: string; rows: number; columns: number }> {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch(`${BASE_URL}${base}/upload`, { method: 'POST', body: form })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '上传失败') }
      return resp.json()
    },

    async dataInfo(): Promise<TerminalHealthDataInfo> {
      const resp = await fetch(`${BASE_URL}${base}/data_info`)
      if (!resp.ok) throw new Error(`获取数据信息失败: ${resp.status}`)
      return resp.json()
    },

    async train(params: { use_optimization: boolean; optimize_n_calls: number }): Promise<TerminalHealthTrainResult> {
      const resp = await fetch(`${BASE_URL}${base}/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '训练失败') }
      return resp.json()
    },

    async gridSearch(params: Record<string, any>): Promise<TerminalHealthGridSearchResult> {
      const resp = await fetch(`${BASE_URL}${base}/grid_search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || 'Grid Search 失败') }
      return resp.json()
    },

    async crossValidate(params: { n_folds: number; use_optimization: boolean }): Promise<TerminalHealthCVResult> {
      const resp = await fetch(`${BASE_URL}${base}/cross_validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '交叉验证失败') }
      return resp.json()
    },

    async predict(file: File): Promise<TerminalHealthPredictResult> {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch(`${BASE_URL}${base}/predict`, { method: 'POST', body: form })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '预测失败') }
      return resp.json()
    },
  }
}

export type TerminalHealthApi = ReturnType<typeof createTerminalHealthApi>

// ============ 采集策略智能调度 API ============

export interface StrategyTableInfo {
  name: string
  rows: number
  columns: number
  size_kb: number
  missing?: boolean
  error?: string
}

export interface StrategyDatasetInfo {
  status: string
  path: string
  total_tables: number
  total_rows: number
  tables: StrategyTableInfo[]
  is_default: boolean
}

export interface StrategyRuleResult {
  status: string
  total: number
  by_scenario: Record<string, number>
  by_category: Record<string, number>
  recommendations: Record<string, any>[]
  scenario_meta?: Record<string, { name: string; category: string; action_type: string }>
}

export interface StrategyClusterResult {
  status: string
  total_terminals: number
  cluster_counts: Record<number, number>
  cluster_avg_curves: Record<number, number[]>
  cluster_meta: Record<string, { name: string; n_terminals: number }>
}

export interface StrategyPredictionResult {
  status: string
  dow: number
  curves: Record<number, { slot: number; hour: number; predicted_success: number }[]>
}

export interface StrategySchedule {
  cluster_id: number
  cluster_name: string
  schedule_id: string
  schedule_date: string
  recall_slots: number[]
  recall_times: string[]
  n_slots: number
  threshold: number
  min_predicted: number
  max_predicted: number
  mean_predicted: number
}

export interface StrategyScheduleResult {
  status: string
  schedule_date: string
  schedules: StrategySchedule[]
}

export interface StrategyPipelineResult {
  status: string
  today: string
  schedule_date: string
  rules: StrategyRuleResult
  clustering: { total_terminals: number; cluster_counts: Record<number, number> }
  prediction: { dow: number; curves: Record<number, any[]> }
  schedules: StrategySchedule[]
  strategy_comparison?: { total_c1: number; changes: StrategyChange[] }
  scenario_meta?: Record<string, { name: string; category: string; action_type: string }>
}

export interface StrategyChange {
  terminal_id: string
  scenario: string
  scenario_name: string
  original: string
  suggested: string
  freq_change: string
  data_item_change: string
  expected_benefit: string
  match_confidence: number
}

/** 创建采集策略 API 客户端 */
export function createStrategyApi() {
  const base = '/api/demo/strategy'

  return {
    async ping(): Promise<{ status: string; message: string }> {
      const resp = await fetch(`${BASE_URL}${base}/ping`)
      if (!resp.ok) throw new Error(`服务连接失败: ${resp.status}`)
      return resp.json()
    },

    async modelInfo(): Promise<any> {
      const resp = await fetch(`${BASE_URL}${base}/model_info`)
      if (!resp.ok) throw new Error(`获取模型信息失败: ${resp.status}`)
      return resp.json()
    },

    async scenarioMeta(): Promise<Record<string, { name: string; category: string; action_type: string }>> {
      const resp = await fetch(`${BASE_URL}${base}/scenario_meta`)
      if (!resp.ok) throw new Error(`获取场景信息失败: ${resp.status}`)
      return resp.json()
    },

    async datasetInfo(): Promise<StrategyDatasetInfo> {
      const resp = await fetch(`${BASE_URL}${base}/dataset_info`)
      if (!resp.ok) throw new Error(`获取数据集信息失败: ${resp.status}`)
      return resp.json()
    },

    async uploadDataset(file: File): Promise<{ status: string; message: string; path: string }> {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch(`${BASE_URL}${base}/upload_dataset`, { method: 'POST', body: form })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '上传失败') }
      return resp.json()
    },

    async runRules(): Promise<StrategyRuleResult> {
      const resp = await fetch(`${BASE_URL}${base}/run_rules`, { method: 'POST' })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '规则研判失败') }
      return resp.json()
    },

    async runClustering(): Promise<StrategyClusterResult> {
      const resp = await fetch(`${BASE_URL}${base}/run_clustering`, { method: 'POST' })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '聚类失败') }
      return resp.json()
    },

    async runPrediction(): Promise<StrategyPredictionResult> {
      const resp = await fetch(`${BASE_URL}${base}/run_prediction`, { method: 'POST' })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '预测失败') }
      return resp.json()
    },

    async runSchedule(): Promise<StrategyScheduleResult> {
      const resp = await fetch(`${BASE_URL}${base}/run_schedule`, { method: 'POST' })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '排程失败') }
      return resp.json()
    },

    async runFullPipeline(): Promise<StrategyPipelineResult> {
      const resp = await fetch(`${BASE_URL}${base}/run_full_pipeline`, { method: 'POST' })
      if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '全流程失败') }
      return resp.json()
    },

    getExportCsvUrl(): string {
      return `${BASE_URL}${base}/export_csv`
    },
  }
}

export type StrategyApi = ReturnType<typeof createStrategyApi>

// ============ 拆表/装表作业识别 API ============

export interface MeterOperationModelInfo {
  model_type: string
  model_path: string
  model_available: boolean
  classes: { id: number; name: string; cn: string }[]
  nameplate_classes?: { id: number; name: string; cn: string }[]
  config: Record<string, number>
  description: string
  main_model_path?: string
  nameplate_model_path?: string
  main_model_available?: boolean
  nameplate_model_available?: boolean
}

export interface MeterOperationTaskStatus {
  task_id: string
  status: string
  progress: number
  current_frame: number
  total_frames: number
  current_state: string
  error: string | null
}

export interface MeterOperationKeyFrame {
  title: string
  frame: number
  time_seconds: number
  image: string
}

export interface MeterOperationReportMeter {
  meter_id: number
  wire_removal_time?: number | null
  wire_installation_time?: number | null
  verified_time: number | null
}

export interface MeterOperationReport {
  final_state: string
  recognized_nameplate_text?: string | null
  meters: MeterOperationReportMeter[]
}

export interface MeterOperationResults {
  status: string
  task_id: string
  annotated_video_url: string
  report: MeterOperationReport
  key_frames: MeterOperationKeyFrame[]
  total_frames: number
  fps: number
  duration_seconds: number
}

/** 创建拆表作业识别 API 客户端 */
export function createMeterRemovalApi() {
  const base = '/api/demo/meter-removal'

  return {
    async ping(): Promise<{ status: string; message: string }> {
      const resp = await fetch(`${BASE_URL}${base}/ping`)
      if (!resp.ok) throw new Error(`服务连接失败: ${resp.status}`)
      return resp.json()
    },

    async modelInfo(): Promise<MeterOperationModelInfo> {
      const resp = await fetch(`${BASE_URL}${base}/model_info`)
      if (!resp.ok) throw new Error(`获取模型信息失败: ${resp.status}`)
      return resp.json()
    },

    async listVideos(): Promise<{ videos: string[]; directory: string }> {
      const resp = await fetch(`${BASE_URL}${base}/videos`)
      if (!resp.ok) throw new Error(`获取视频列表失败: ${resp.status}`)
      return resp.json()
    },

    getVideoUrl(filename: string): string {
      return `${BASE_URL}${base}/video/${encodeURIComponent(filename)}`
    },

    async analyze(file: File): Promise<{ status: string; task_id: string; message: string }> {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch(`${BASE_URL}${base}/analyze`, { method: 'POST', body: form })
      if (!resp.ok) throw new Error(`启动分析失败: ${resp.status}`)
      return resp.json()
    },

    async analyzeBuiltin(filename: string): Promise<{ status: string; task_id: string; message: string }> {
      const resp = await fetch(`${BASE_URL}${base}/analyze-builtin?filename=${encodeURIComponent(filename)}`, { method: 'POST' })
      if (!resp.ok) throw new Error(`启动分析失败: ${resp.status}`)
      return resp.json()
    },

    async getStatus(taskId: string): Promise<MeterOperationTaskStatus> {
      const resp = await fetch(`${BASE_URL}${base}/status/${taskId}`)
      if (!resp.ok) throw new Error(`获取状态失败: ${resp.status}`)
      return resp.json()
    },

    async getResults(taskId: string): Promise<MeterOperationResults> {
      const resp = await fetch(`${BASE_URL}${base}/results/${taskId}`)
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '获取结果失败')
      }
      return resp.json()
    },

    getAnnotatedVideoUrl(taskId: string): string {
      return `${BASE_URL}${base}/annotated-video/${taskId}`
    },
  }
}

export type MeterRemovalApi = ReturnType<typeof createMeterRemovalApi>

/** 创建装表作业识别 API 客户端 */
export function createMeterInstallApi() {
  const base = '/api/demo/meter-install'

  return {
    async ping(): Promise<{ status: string; message: string }> {
      const resp = await fetch(`${BASE_URL}${base}/ping`)
      if (!resp.ok) throw new Error(`服务连接失败: ${resp.status}`)
      return resp.json()
    },

    async modelInfo(): Promise<MeterOperationModelInfo> {
      const resp = await fetch(`${BASE_URL}${base}/model_info`)
      if (!resp.ok) throw new Error(`获取模型信息失败: ${resp.status}`)
      return resp.json()
    },

    async listVideos(): Promise<{ videos: string[]; directory: string }> {
      const resp = await fetch(`${BASE_URL}${base}/videos`)
      if (!resp.ok) throw new Error(`获取视频列表失败: ${resp.status}`)
      return resp.json()
    },

    getVideoUrl(filename: string): string {
      return `${BASE_URL}${base}/video/${encodeURIComponent(filename)}`
    },

    async analyze(file: File): Promise<{ status: string; task_id: string; message: string }> {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch(`${BASE_URL}${base}/analyze`, { method: 'POST', body: form })
      if (!resp.ok) throw new Error(`启动分析失败: ${resp.status}`)
      return resp.json()
    },

    async analyzeBuiltin(filename: string): Promise<{ status: string; task_id: string; message: string }> {
      const resp = await fetch(`${BASE_URL}${base}/analyze-builtin?filename=${encodeURIComponent(filename)}`, { method: 'POST' })
      if (!resp.ok) throw new Error(`启动分析失败: ${resp.status}`)
      return resp.json()
    },

    async getStatus(taskId: string): Promise<MeterOperationTaskStatus> {
      const resp = await fetch(`${BASE_URL}${base}/status/${taskId}`)
      if (!resp.ok) throw new Error(`获取状态失败: ${resp.status}`)
      return resp.json()
    },

    async getResults(taskId: string): Promise<MeterOperationResults> {
      const resp = await fetch(`${BASE_URL}${base}/results/${taskId}`)
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || '获取结果失败')
      }
      return resp.json()
    },

    getAnnotatedVideoUrl(taskId: string): string {
      return `${BASE_URL}${base}/annotated-video/${taskId}`
    },
  }
}

export type MeterInstallApi = ReturnType<typeof createMeterInstallApi>