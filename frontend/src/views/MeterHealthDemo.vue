<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { createMeterHealthApi, type MeterHealthTrainResult, type MeterHealthPredictResult } from '@/api/demo'

const api = createMeterHealthApi()

// 状态
const currentTaskId = ref<string | null>(null)
const currentPredictTaskId = ref<string | null>(null)
const trainCompleted = ref(false)
const errorMsg = ref('')

// 步骤1: 上传
const uploadFile = ref<File | null>(null)
const uploadInfo = ref<{ filename: string; rows: number; columns: number; removal_rate: number | null } | null>(null)
const uploading = ref(false)

// 步骤2: 训练
const useGridSearch = ref(true)
const gridParams = ref({
  n_est_start: 100, n_est_end: 500, n_est_step: 100,
  max_samp_start: 0.5, max_samp_end: 1.0, max_samp_step: 0.1,
  max_feat_start: 0.5, max_feat_end: 1.0, max_feat_step: 0.1,
})
const training = ref(false)
const trainProgress = ref(0)
const trainMessage = ref('')

// 步骤3: 训练结果
const trainResult = ref<MeterHealthTrainResult | null>(null)

// 步骤4: 网格搜索
const gridSearchExpanded = ref(true)

// 步骤5: 验证
const validationExpanded = ref(true)

// 步骤6: 预测
const predictFile = ref<File | null>(null)
const predictFileName = ref('')
const predicting = ref(false)
const predictProgress = ref(0)
const predictMessage = ref('')
const predictResult = ref<MeterHealthPredictResult | null>(null)

// 定时器
let trainPollTimer: ReturnType<typeof setInterval> | null = null
let predictPollTimer: ReturnType<typeof setInterval> | null = null

onUnmounted(() => {
  if (trainPollTimer) clearInterval(trainPollTimer)
  if (predictPollTimer) clearInterval(predictPollTimer)
})

// 网格参数组合数
function calcGridComboCount() {
  const { n_est_start, n_est_end, n_est_step, max_samp_start, max_samp_end, max_samp_step, max_feat_start, max_feat_end, max_feat_step } = gridParams.value
  const nEstCount = Math.floor((n_est_end - n_est_start) / n_est_step) + 1
  const maxSampCount = Math.floor((max_samp_end - max_samp_start) / max_samp_step) + 1
  const maxFeatCount = Math.floor((max_feat_end - max_feat_start) / max_feat_step) + 1
  return Math.max(0, nEstCount) * Math.max(0, maxSampCount) * Math.max(0, maxFeatCount)
}

// 步骤1: 上传
async function handleUpload(file: File) {
  if (!file.name.endsWith('.csv')) {
    errorMsg.value = '仅支持 CSV 文件！'
    return
  }
  uploading.value = true
  errorMsg.value = ''
  try {
    const data = await api.upload(file)
    currentTaskId.value = data.task_id
    uploadInfo.value = {
      filename: data.filename,
      rows: data.rows,
      columns: data.columns,
      removal_rate: data.removal_rate,
    }
    uploadFile.value = file
    trainResult.value = null
    predictResult.value = null
    trainCompleted.value = false
  } catch (e: any) {
    errorMsg.value = e?.message || '上传失败'
  } finally {
    uploading.value = false
  }
}

function onUploadChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) handleUpload(file)
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  const file = e.dataTransfer?.files?.[0]
  if (file) handleUpload(file)
}

// 步骤2: 训练
async function startTraining() {
  if (!currentTaskId.value) return
  const total = calcGridComboCount()
  if (useGridSearch.value && total > 500) {
    if (!confirm(`参数组合数较多 (${total} 种 × 2个模块)，可能需要较长时间。是否继续？`)) return
  }

  training.value = true
  trainProgress.value = 0
  trainMessage.value = '正在启动...'
  errorMsg.value = ''

  try {
    await api.train({
      task_id: currentTaskId.value,
      use_grid_search: useGridSearch.value,
      ...gridParams.value,
    })
    trainPollTimer = setInterval(pollTrainStatus, 2000)
  } catch (e: any) {
    errorMsg.value = e?.message || '训练启动失败'
    training.value = false
  }
}

async function pollTrainStatus() {
  if (!currentTaskId.value) return
  try {
    const data = await api.getStatus(currentTaskId.value)
    trainProgress.value = data.progress
    trainMessage.value = data.message

    if (data.status === 'completed') {
      if (trainPollTimer) clearInterval(trainPollTimer)
      trainPollTimer = null
      training.value = false
      trainCompleted.value = true
      await loadTrainResults()
      await loadValidation()
    } else if (data.status === 'error') {
      if (trainPollTimer) clearInterval(trainPollTimer)
      trainPollTimer = null
      training.value = false
      errorMsg.value = '训练失败: ' + data.message
    }
  } catch (e) {
    console.error('轮询状态失败:', e)
  }
}

async function loadTrainResults() {
  if (!currentTaskId.value) return
  try {
    trainResult.value = await api.getResults(currentTaskId.value)
  } catch (e: any) {
    errorMsg.value = e?.message || '加载结果失败'
  }
}

async function loadValidation() {
  // validation is already in trainResult
}

// 步骤6: 预测
function onPredictChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) {
    predictFile.value = file
    predictFileName.value = file.name
  }
}

function onPredictDrop(e: DragEvent) {
  e.preventDefault()
  const file = e.dataTransfer?.files?.[0]
  if (file) {
    predictFile.value = file
    predictFileName.value = file.name
  }
}

async function startPrediction() {
  if (!currentTaskId.value || !predictFile.value) return
  predicting.value = true
  predictProgress.value = 0
  predictMessage.value = '正在启动预测...'
  errorMsg.value = ''

  try {
    const data = await api.predict(predictFile.value, currentTaskId.value)
    currentPredictTaskId.value = data.predict_task_id
    predictPollTimer = setInterval(pollPredictStatus, 1500)
  } catch (e: any) {
    errorMsg.value = e?.message || '预测启动失败'
    predicting.value = false
  }
}

async function pollPredictStatus() {
  if (!currentPredictTaskId.value) return
  try {
    const data = await api.getStatus(currentPredictTaskId.value)
    predictProgress.value = data.progress
    predictMessage.value = data.message

    if (data.status === 'completed') {
      if (predictPollTimer) clearInterval(predictPollTimer)
      predictPollTimer = null
      predicting.value = false
      predictResult.value = await api.getPredictResults(currentPredictTaskId.value)
    } else if (data.status === 'error') {
      if (predictPollTimer) clearInterval(predictPollTimer)
      predictPollTimer = null
      predicting.value = false
      errorMsg.value = '预测失败: ' + data.message
    }
  } catch (e) {
    console.error('轮询预测状态失败:', e)
  }
}

// 标签映射
const labelMap: Record<string, string> = {
  score_years: '使用年限', score_comm: '通讯模块',
  score_module3: '电气异常', score_module4: '采集完整率',
  score_MFR: '厂商质量', total_score: '综合评分'
}
const gradeColors: Record<string, string> = {
  'B - 运行良好': '#00ff88',
  'C - 重点关注': '#ffaa00',
  'D - 建议维修/拆换': '#ff5555',
  'E - 超龄建议直接拆除': '#cc3333'
}
</script>

<template>
  <div class="mh-demo">
    <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>

    <!-- 步骤1: 上传训练数据 -->
    <div class="card">
      <div class="card-header">
        <span class="step-badge">1</span>
        <h2>上传训练数据</h2>
        <span class="status-dot" :class="{ success: uploadInfo, running: uploading }"></span>
      </div>
      <div class="card-body">
        <div
          v-if="!uploadInfo"
          class="upload-area"
          @dragover.prevent
          @drop="onDrop"
          @click="($refs.uploadInput as HTMLInputElement)?.click()"
        >
          <div class="upload-icon">📁</div>
          <p>拖拽 CSV 文件到此处，或点击选择文件</p>
          <button class="btn btn-outline">选择文件</button>
          <input ref="uploadInput" type="file" accept=".csv" hidden @change="onUploadChange" />
        </div>
        <div v-else class="file-info">
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">文件名</span>
              <span class="info-value">{{ uploadInfo.filename }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">数据行数</span>
              <span class="info-value">{{ uploadInfo.rows.toLocaleString() }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">特征列数</span>
              <span class="info-value">{{ uploadInfo.columns }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">拆除率</span>
              <span class="info-value">{{ uploadInfo.removal_rate !== null ? uploadInfo.removal_rate + '%' : '无拆除标签' }}</span>
            </div>
          </div>
          <button class="btn btn-outline" style="margin-top:12px;" @click="uploadInfo = null; trainResult = null; uploadFile = null">重新上传</button>
        </div>
      </div>
    </div>

    <!-- 步骤2: 训练配置 -->
    <div class="card" v-if="uploadInfo">
      <div class="card-header">
        <span class="step-badge">2</span>
        <h2>训练配置 & 执行</h2>
        <span class="status-dot" :class="{ success: trainCompleted, running: training }"></span>
      </div>
      <div class="card-body">
        <div class="config-row">
          <label class="checkbox-label">
            <input type="checkbox" v-model="useGridSearch" />
            <span>启用网格搜索超参数优化（Grid Search，遍历所有参数组合）</span>
          </label>
        </div>
        <div v-if="useGridSearch" class="grid-params-section">
          <p class="card-desc">设置网格搜索参数范围（模块3和模块4使用相同的搜索范围，分别展示各自最优参数）</p>
          <div class="optimize-params-grid">
            <div class="optimize-param-group">
              <h4>n_estimators</h4>
              <div class="param-inputs">
                <label>起始 <input type="number" v-model.number="gridParams.n_est_start" min="10" step="10" /></label>
                <label>结束 <input type="number" v-model.number="gridParams.n_est_end" min="10" step="10" /></label>
                <label>步长 <input type="number" v-model.number="gridParams.n_est_step" min="10" step="10" /></label>
              </div>
            </div>
            <div class="optimize-param-group">
              <h4>max_samples</h4>
              <div class="param-inputs">
                <label>起始 <input type="number" v-model.number="gridParams.max_samp_start" min="0.1" max="1" step="0.1" /></label>
                <label>结束 <input type="number" v-model.number="gridParams.max_samp_end" min="0.1" max="1" step="0.1" /></label>
                <label>步长 <input type="number" v-model.number="gridParams.max_samp_step" min="0.05" max="0.5" step="0.05" /></label>
              </div>
            </div>
            <div class="optimize-param-group">
              <h4>max_features</h4>
              <div class="param-inputs">
                <label>起始 <input type="number" v-model.number="gridParams.max_feat_start" min="0.1" max="1" step="0.1" /></label>
                <label>结束 <input type="number" v-model.number="gridParams.max_feat_end" min="0.1" max="1" step="0.1" /></label>
                <label>步长 <input type="number" v-model.number="gridParams.max_feat_step" min="0.05" max="0.5" step="0.05" /></label>
              </div>
            </div>
          </div>
          <div class="optimize-info">
            预计参数组合数: <strong>{{ calcGridComboCount() }} 种</strong>（× 2个模块）
          </div>
        </div>
        <button class="btn btn-primary" :disabled="training" @click="startTraining">
          {{ training ? '⏳ 训练中...' : '🚀 开始训练' }}
        </button>
        <div v-if="training" class="progress-section">
          <div class="progress-bar-container">
            <div class="progress-bar" :style="{ width: trainProgress + '%' }"></div>
          </div>
          <div class="progress-text">
            <span>{{ trainProgress }}%</span>
            <span>{{ trainMessage }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 步骤3: 训练结果 -->
    <div class="card" v-if="trainResult">
      <div class="card-header">
        <span class="step-badge">3</span>
        <h2>训练结果</h2>
      </div>
      <div class="card-body">
        <!-- 图表 -->
        <div class="charts-grid">
          <div class="chart-container" v-if="trainResult.charts?.score_distribution">
            <h3>综合评分分布</h3>
            <img :src="'data:image/png;base64,' + trainResult.charts.score_distribution" alt="评分分布" />
          </div>
          <div class="chart-container" v-if="trainResult.charts?.module_boxplot">
            <h3>各模块评分分布</h3>
            <img :src="'data:image/png;base64,' + trainResult.charts.module_boxplot" alt="模块评分" />
          </div>
          <div class="chart-container" v-if="trainResult.charts?.mfr_comparison">
            <h3>厂商平均评分对比</h3>
            <img :src="'data:image/png;base64,' + trainResult.charts.mfr_comparison" alt="厂商对比" />
          </div>
          <div class="chart-container" v-if="trainResult.charts?.mfr_removal">
            <h3>厂商拆除率对比</h3>
            <img :src="'data:image/png;base64,' + trainResult.charts.mfr_removal" alt="厂商拆除率" />
          </div>
        </div>

        <!-- 统计表 -->
        <div class="table-section" v-if="trainResult.stats">
          <h3>各模块评分统计</h3>
          <div class="table-wrapper">
            <table>
              <thead>
                <tr><th>模块</th><th>均值</th><th>标准差</th><th>中位数</th><th>最小值</th><th>最大值</th></tr>
              </thead>
              <tbody>
                <tr v-for="(val, key) in trainResult.stats" :key="key">
                  <td><strong>{{ labelMap[key] || key }}</strong></td>
                  <td>{{ val.mean }}</td><td>{{ val.std }}</td><td>{{ val.median }}</td>
                  <td>{{ val.min }}</td><td>{{ val.max }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 等级分布 -->
        <div class="grade-section" v-if="trainResult.grade_counts">
          <h3>健康等级分布</h3>
          <div class="grade-bars">
            <div v-for="(count, grade) in trainResult.grade_counts" :key="grade" class="grade-bar-item">
              <span class="grade-label">{{ grade }}</span>
              <div class="grade-bar-track">
                <div class="grade-bar-fill" :style="{ width: (count / trainResult.total_rows * 100).toFixed(1) + '%', background: gradeColors[grade] || '#555' }"></div>
              </div>
              <span class="grade-count">{{ count }} ({{ (count / trainResult.total_rows * 100).toFixed(1) }}%)</span>
            </div>
          </div>
        </div>

        <!-- 权重 -->
        <div class="weights-section" v-if="trainResult.weights">
          <h3>评分权重</h3>
          <div>
            <span v-for="(w, k) in trainResult.weights" :key="k" class="weight-tag">{{ labelMap[k] || k }}: {{ (w * 100).toFixed(0) }}%</span>
          </div>
        </div>

        <!-- 下载 -->
        <div class="action-row" v-if="currentTaskId">
          <a class="btn btn-success" :href="api.getDownloadUrl(currentTaskId, 'result')" target="_blank">📥 下载评分结果 CSV</a>
          <a class="btn btn-outline" :href="api.getDownloadUrl(currentTaskId, 'model')" target="_blank">💾 下载训练模型 PKL</a>
        </div>
      </div>
    </div>

    <!-- 步骤4: 网格搜索结果 -->
    <div class="card" v-if="trainResult?.use_grid_search && trainResult?.grid_search && Object.keys(trainResult.grid_search).length">
      <div class="card-header" @click="gridSearchExpanded = !gridSearchExpanded" style="cursor:pointer;">
        <span class="step-badge">4</span>
        <h2>网格搜索结果 (Grid Search)</h2>
        <span style="margin-left:auto;font-size:12px;color:rgba(255,255,255,0.5);">{{ gridSearchExpanded ? '▼' : '▶' }}</span>
      </div>
      <div class="card-body" v-if="gridSearchExpanded">
        <div v-for="(modData, modKey) in (trainResult.grid_search as Record<string, any>)" :key="modKey">
          <div class="best-params-card">
            <h3>🏆 {{ modData.module_name }} — 最佳参数</h3>
            <div class="best-params-grid">
              <div class="param-item">
                <span class="param-label">n_estimators</span>
                <span class="param-value">{{ modData.best_params?.n_estimators || '-' }}</span>
              </div>
              <div class="param-item">
                <span class="param-label">max_samples</span>
                <span class="param-value">{{ modData.best_params?.max_samples?.toFixed?.(2) || modData.best_params?.max_samples || '-' }}</span>
              </div>
              <div class="param-item">
                <span class="param-label">max_features</span>
                <span class="param-value">{{ modData.best_params?.max_features?.toFixed?.(2) || modData.best_params?.max_features || '-' }}</span>
              </div>
              <div class="param-item highlight">
                <span class="param-label">最佳 AUC</span>
                <span class="param-value">{{ modData.best_params?.best_auc || '-' }}</span>
              </div>
            </div>
          </div>
          <div class="table-section">
            <h3>📊 {{ modData.module_name }} — 全部参数组合 (按 AUC 降序)</h3>
            <div class="table-wrapper" style="max-height:400px;overflow-y:auto;">
              <table>
                <thead>
                  <tr><th>排名</th><th>n_estimators</th><th>max_samples</th><th>max_features</th><th>平均 AUC</th><th>AUC 标准差</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(r, i) in (modData.grid_results || [])" :key="i"
                    :class="{ 'best-row': r.n_estimators === modData.best_params?.n_estimators && Math.abs(r.max_samples - (modData.best_params?.max_samples || 0)) < 0.01 && Math.abs(r.max_features - (modData.best_params?.max_features || 0)) < 0.01 }">
                    <td>{{ i + 1 }}</td>
                    <td>{{ r.n_estimators }}</td>
                    <td>{{ r.max_samples?.toFixed?.(2) || r.max_samples }}</td>
                    <td>{{ r.max_features?.toFixed?.(2) || r.max_features }}</td>
                    <td><strong>{{ r.mean_auc }}</strong></td>
                    <td>{{ r.std_auc }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 步骤5: 模型验证 -->
    <div class="card" v-if="trainResult?.validation">
      <div class="card-header" @click="validationExpanded = !validationExpanded" style="cursor:pointer;">
        <span class="step-badge">5</span>
        <h2>模型验证 (K-fold CV + AUC)</h2>
        <span style="margin-left:auto;font-size:12px;color:rgba(255,255,255,0.5);">{{ validationExpanded ? '▼' : '▶' }}</span>
      </div>
      <div class="card-body" v-if="validationExpanded">
        <div v-if="trainResult.validation.warning" class="warning-text">{{ trainResult.validation.warning }}</div>
        <template v-else>
          <div class="metrics-grid">
            <div class="metric-card" v-if="trainResult.validation.train_auc !== undefined">
              <div class="metric-value">{{ trainResult.validation.train_auc }}</div>
              <div class="metric-label">训练集 AUC</div>
            </div>
            <div class="metric-card" v-if="trainResult.validation.cv_mean_auc !== undefined">
              <div class="metric-value">{{ trainResult.validation.cv_mean_auc }}</div>
              <div class="metric-label">CV 平均 AUC</div>
            </div>
            <div class="metric-card" v-if="trainResult.validation.cv_std_auc !== undefined">
              <div class="metric-value">±{{ trainResult.validation.cv_std_auc }}</div>
              <div class="metric-label">CV AUC 标准差</div>
            </div>
            <div class="metric-card" :class="Math.abs(trainResult.validation.overfit_gap || 0) > 0.1 ? 'metric-warning' : 'metric-ok'" v-if="trainResult.validation.overfit_gap !== undefined">
              <div class="metric-value">{{ trainResult.validation.overfit_gap }}</div>
              <div class="metric-label">过拟合指标 (Train - CV)</div>
            </div>
            <div class="metric-card" :class="(trainResult.validation.removed_rank_mean || 1) < 0.2 ? 'metric-ok' : 'metric-warning'" v-if="trainResult.validation.removed_rank_mean !== undefined">
              <div class="metric-value">{{ trainResult.validation.removed_rank_mean }}</div>
              <div class="metric-label">拆除样本平均排名分位数</div>
            </div>
            <div class="metric-card" v-for="(auc, mod) in trainResult.validation.module_aucs" :key="mod">
              <div class="metric-value">{{ auc !== null ? auc : 'N/A' }}</div>
              <div class="metric-label">{{ mod === 'module3' ? '电气模块 AUC' : '采集模块 AUC' }}</div>
            </div>
          </div>
          <div class="chart-container" v-if="trainResult.validation_charts?.cv_auc">
            <h3>K-fold AUC</h3>
            <img :src="'data:image/png;base64,' + trainResult.validation_charts.cv_auc" alt="CV AUC" />
          </div>
          <div class="chart-container" v-if="trainResult.validation_charts?.removed_ranks">
            <h3>拆除样本排名分布</h3>
            <img :src="'data:image/png;base64,' + trainResult.validation_charts.removed_ranks" alt="排名分布" />
          </div>
          <div class="fold-detail" v-if="trainResult.validation.fold_aucs">
            <h3>各折 AUC 详情</h3>
            <div class="fold-list">
              <span v-for="(auc, i) in trainResult.validation.fold_aucs" :key="i" class="fold-item">折{{ i + 1 }}: <strong>{{ auc }}</strong></span>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 步骤6: 预测新数据 -->
    <div class="card" v-if="trainCompleted">
      <div class="card-header">
        <span class="step-badge">6</span>
        <h2>预测新数据</h2>
        <span class="status-dot" :class="{ success: predictResult, running: predicting }"></span>
      </div>
      <div class="card-body">
        <div
          v-if="!predictFile"
          class="upload-area"
          @dragover.prevent
          @drop="onPredictDrop"
          @click="($refs.predictInput as HTMLInputElement)?.click()"
        >
          <div class="upload-icon">📊</div>
          <p>上传待预测的 CSV 文件</p>
          <button class="btn btn-outline">选择文件</button>
          <input ref="predictInput" type="file" accept=".csv" hidden @change="onPredictChange" />
        </div>
        <div v-else>
          <div class="file-info" style="margin-bottom:12px;">
            <span>📄 {{ predictFileName }}</span>
          </div>
          <button class="btn btn-primary" :disabled="predicting" @click="startPrediction">
            {{ predicting ? '⏳ 预测中...' : '🔮 开始预测' }}
          </button>
        </div>
        <div v-if="predicting" class="progress-section">
          <div class="progress-bar-container">
            <div class="progress-bar" :style="{ width: predictProgress + '%' }"></div>
          </div>
          <div class="progress-text">
            <span>{{ predictProgress }}%</span>
            <span>{{ predictMessage }}</span>
          </div>
        </div>

        <!-- 预测结果 -->
        <div v-if="predictResult" style="margin-top:20px;">
          <h3>预测结果统计</h3>
          <div class="table-wrapper" v-if="predictResult.stats">
            <table>
              <thead>
                <tr><th>模块</th><th>均值</th><th>标准差</th><th>中位数</th><th>最小值</th><th>最大值</th></tr>
              </thead>
              <tbody>
                <tr v-for="(val, key) in predictResult.stats" :key="key">
                  <td><strong>{{ labelMap[key] || key }}</strong></td>
                  <td>{{ val.mean }}</td><td>{{ val.std }}</td><td>{{ val.median }}</td>
                  <td>{{ val.min }}</td><td>{{ val.max }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <h3 style="margin-top:20px;">高风险电表 (D/E 级，共 {{ predictResult.de_count }} 个)</h3>
          <div class="table-wrapper" v-if="predictResult.top_risk_meters?.length">
            <table>
              <thead>
                <tr><th>电表ID</th><th>厂商</th><th>总分</th><th>等级</th><th>年限分</th><th>通讯分</th><th>电气分</th><th>采集分</th><th>厂商分</th></tr>
              </thead>
              <tbody>
                <tr v-for="(meter, i) in predictResult.top_risk_meters" :key="i">
                  <td>{{ meter.meter_id || '-' }}</td>
                  <td>{{ meter.MFR || '-' }}</td>
                  <td><strong>{{ meter.total_score?.toFixed?.(1) || meter.total_score }}</strong></td>
                  <td><span :class="(meter.grade || '').includes('E') ? 'grade-e' : 'grade-d'">{{ meter.grade }}</span></td>
                  <td>{{ meter.score_years?.toFixed?.(1) || '-' }}</td>
                  <td>{{ meter.score_comm?.toFixed?.(1) || '-' }}</td>
                  <td>{{ meter.score_module3?.toFixed?.(1) || '-' }}</td>
                  <td>{{ meter.score_module4?.toFixed?.(1) || '-' }}</td>
                  <td>{{ meter.score_MFR?.toFixed?.(1) || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <a v-if="currentPredictTaskId" class="btn btn-success" style="margin-top:16px;" :href="api.getDownloadUrl(currentPredictTaskId, 'result')" target="_blank">📥 下载预测结果 CSV</a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mh-demo { color: #e4e7ed; }

.error-bar { padding: 10px 16px; background: rgba(255,85,85,0.15); border: 1px solid #ff5555; border-radius: 8px; margin-bottom: 16px; color: #ff5555; font-size: 13px; }

/* 卡片 */
.card {
  background: rgba(17,24,39,0.6);
  border: 1px solid rgba(0,212,255,0.15);
  border-radius: 10px;
  margin-bottom: 16px;
  overflow: hidden;
}
.card-header {
  padding: 14px 20px;
  border-bottom: 1px solid rgba(0,212,255,0.1);
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(0,212,255,0.04);
}
.card-header h2 { font-size: 16px; font-weight: 600; margin: 0; flex: 1; }
.card-body { padding: 20px; }

/* 步骤徽章 */
.step-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: 50%;
  background: rgba(0,212,255,0.2); color: #00d4ff; font-weight: 700; font-size: 15px; flex-shrink: 0;
}

/* 状态指示器 */
.status-dot { width: 10px; height: 10px; border-radius: 50%; background: rgba(255,255,255,0.2); flex-shrink: 0; }
.status-dot.success { background: #00ff88; }
.status-dot.running { background: #ffaa00; animation: pulse 1s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* 上传区域 */
.upload-area {
  border: 2px dashed rgba(0,212,255,0.2); border-radius: 10px;
  padding: 36px; text-align: center; cursor: pointer;
  transition: all 0.2s; background: rgba(0,212,255,0.03);
}
.upload-area:hover { border-color: #00d4ff; background: rgba(0,212,255,0.08); }
.upload-icon { font-size: 44px; margin-bottom: 10px; }
.upload-area p { color: rgba(255,255,255,0.5); margin-bottom: 14px; font-size: 14px; }

/* 文件信息 */
.file-info {
  background: rgba(0,212,255,0.08); border: 1px solid rgba(0,212,255,0.2);
  border-radius: 8px; padding: 16px;
}
.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.info-item { display: flex; flex-direction: column; gap: 4px; }
.info-label { font-size: 11px; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 0.5px; }
.info-value { font-size: 17px; font-weight: 600; color: #00d4ff; }

/* 按钮 */
.btn {
  display: inline-block; padding: 9px 22px; border: none; border-radius: 8px;
  font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; text-decoration: none;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: linear-gradient(135deg, #00d4ff, #0099cc); color: #0d1117; }
.btn-primary:hover:not(:disabled) { box-shadow: 0 0 20px rgba(0,212,255,0.4); }
.btn-success { background: #00ff88; color: #0d1117; }
.btn-success:hover { background: #00cc66; }
.btn-outline { background: transparent; color: #00d4ff; border: 1px solid rgba(0,212,255,0.3); }
.btn-outline:hover { background: rgba(0,212,255,0.1); }

/* 配置行 */
.config-row { display: flex; align-items: center; gap: 20px; margin-bottom: 16px; flex-wrap: wrap; }
.checkbox-label { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 14px; }
.checkbox-label input[type="checkbox"] { width: 17px; height: 17px; accent-color: #00d4ff; }
.card-desc { color: rgba(255,255,255,0.4); font-size: 13px; margin-bottom: 16px; }

/* 网格参数 */
.grid-params-section { background: rgba(0,212,255,0.04); border: 1px solid rgba(0,212,255,0.1); border-radius: 10px; padding: 18px; margin-bottom: 16px; }
.optimize-params-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.optimize-param-group { background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 12px 14px; }
.optimize-param-group h4 { margin: 0 0 8px; font-size: 13px; color: #00d4ff; font-weight: 600; }
.param-inputs { display: flex; gap: 8px; flex-wrap: wrap; }
.param-inputs label { display: flex; flex-direction: column; font-size: 10px; color: rgba(255,255,255,0.4); gap: 4px; flex: 1; min-width: 60px; }
.param-inputs input {
  padding: 7px 8px; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px;
  font-size: 13px; font-family: monospace; text-align: center;
  background: rgba(0,0,0,0.4); color: #e4e7ed;
}
.param-inputs input:focus { outline: none; border-color: #00d4ff; }
.optimize-info { margin-top: 14px; padding: 10px 16px; background: rgba(0,212,255,0.1); border-radius: 8px; font-size: 14px; color: #00d4ff; text-align: center; }
.optimize-info strong { font-size: 18px; }

/* 进度条 */
.progress-section { margin-top: 14px; }
.progress-bar-container { width: 100%; height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
.progress-bar { height: 100%; background: linear-gradient(90deg, #00d4ff, #00ff88); border-radius: 4px; transition: width 0.5s ease; }
.progress-text { display: flex; justify-content: space-between; margin-top: 6px; font-size: 12px; color: rgba(255,255,255,0.5); }

/* 图表 */
.charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; margin-bottom: 20px; }
.chart-container { background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 14px; margin-bottom: 14px; }
.chart-container h3 { font-size: 14px; margin: 0 0 10px; color: rgba(255,255,255,0.6); }
.chart-container img { width: 100%; height: auto; border-radius: 4px; }

/* 表格 */
.table-section { margin-bottom: 20px; }
.table-section h3, .grade-section h3, .weights-section h3 { font-size: 15px; margin-bottom: 10px; color: rgba(255,255,255,0.7); }
.table-wrapper { overflow-x: auto; border: 1px solid rgba(0,212,255,0.1); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead { background: rgba(0,212,255,0.08); }
th { padding: 10px 14px; text-align: left; font-weight: 600; color: rgba(255,255,255,0.6); border-bottom: 1px solid rgba(0,212,255,0.15); white-space: nowrap; }
td { padding: 8px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); color: #e4e7ed; }
tbody tr:hover { background: rgba(0,212,255,0.05); }
.best-row { background: rgba(0,255,136,0.08); font-weight: 600; }

/* 等级分布 */
.grade-bars { display: flex; flex-direction: column; gap: 8px; }
.grade-bar-item { display: flex; align-items: center; gap: 10px; }
.grade-label { width: 170px; font-size: 12px; font-weight: 600; text-align: right; flex-shrink: 0; }
.grade-bar-track { flex: 1; height: 22px; background: rgba(255,255,255,0.06); border-radius: 4px; overflow: hidden; }
.grade-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; min-width: 2px; }
.grade-count { width: 90px; font-size: 12px; color: rgba(255,255,255,0.5); flex-shrink: 0; }

/* 权重 */
.weights-section { margin-bottom: 16px; }
.weight-tag { display: inline-block; background: rgba(0,212,255,0.12); color: #00d4ff; padding: 5px 12px; border-radius: 16px; font-size: 12px; font-weight: 600; margin-right: 6px; margin-bottom: 6px; }

/* 操作行 */
.action-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }

/* 最佳参数 */
.best-params-card {
  background: rgba(0,255,136,0.06); border: 1px solid rgba(0,255,136,0.2);
  border-radius: 10px; padding: 18px; margin-bottom: 18px;
}
.best-params-card h3 { margin: 0 0 14px; color: #00ff88; font-size: 16px; }
.best-params-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; }
.param-item { background: rgba(0,0,0,0.3); border-radius: 8px; padding: 10px 14px; text-align: center; }
.param-item.highlight { background: rgba(255,170,0,0.1); border: 1px solid rgba(255,170,0,0.3); }
.param-label { display: block; font-size: 11px; color: rgba(255,255,255,0.4); margin-bottom: 4px; text-transform: uppercase; }
.param-value { display: block; font-size: 18px; font-weight: 700; color: #e4e7ed; }
.param-item.highlight .param-value { color: #ffaa00; }

/* 验证指标 */
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 16px; }
.metric-card { background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 16px; text-align: center; }
.metric-value { font-size: 26px; font-weight: 700; color: #00d4ff; margin-bottom: 4px; }
.metric-label { font-size: 12px; color: rgba(255,255,255,0.4); }
.metric-ok .metric-value { color: #00ff88; }
.metric-warning .metric-value { color: #ff5555; }

/* 折叠 */
.fold-detail { margin-top: 14px; }
.fold-detail h3 { font-size: 14px; margin-bottom: 8px; color: rgba(255,255,255,0.6); }
.fold-list { display: flex; gap: 10px; flex-wrap: wrap; }
.fold-item { background: rgba(0,212,255,0.08); padding: 6px 14px; border-radius: 8px; font-size: 13px; border: 1px solid rgba(0,212,255,0.15); }

/* 预警 */
.warning-text { color: #ffaa00; text-align: center; padding: 20px; }

/* 预测等级 */
.grade-d { color: #ff5555; font-weight: 600; }
.grade-e { color: #cc3333; font-weight: 700; }

@media (max-width: 768px) {
  .charts-grid { grid-template-columns: 1fr; }
  .metrics-grid { grid-template-columns: repeat(2, 1fr); }
  .grade-label { width: 120px; font-size: 11px; }
}
</style>