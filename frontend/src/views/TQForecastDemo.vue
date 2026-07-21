<script setup lang="ts">
import { nextTick, onMounted, onBeforeUnmount, ref, watch, computed } from 'vue'
import * as echarts from 'echarts'
import { createTQForecastApi, type TQForecastModelInfo, type TQTrainStatus, type TQPredictResult } from '@/api/demo'

const props = defineProps<{ modelKey: string }>()
const api = createTQForecastApi()

const serverOnline = ref(false)
const loading = ref(false)
const loadingText = ref('')
const activeTab = ref<'train' | 'predict' | 'evaluate'>('evaluate')
const activeModelKey = ref(props.modelKey)

// 子模型切换 (TQ-01: load_forecast <-> load_rate)
const showSubSelector = computed(() => props.modelKey === 'load_forecast')
const subModels = [
  { key: 'load_forecast', label: '负荷预测' },
  { key: 'load_rate', label: '负载率' },
]

// 模型信息
const modelInfo = ref<TQForecastModelInfo | null>(null)

// 训练
const trainStatus = ref<TQTrainStatus | null>(null)
const trainResult = ref<any>(null)
const nTrials = ref(10)
const trainChartRef = ref<HTMLElement | null>(null)
let trainChart: echarts.ECharts | null = null
let trainPollTimer: any = null

// 预测
const predictResult = ref<TQPredictResult | null>(null)

// 评估
const evalData = ref<any>(null)
const trainingLog = ref<any>(null)
const figures = ref<{ name: string; base64: string }[]>([])
// 分台区数据 computed
const perDistrict = computed<Record<string, any>>(() => evalData.value?.test?.per_district || evalData.value?.eval?.per_district || {})
const perDistrictCols = computed<string[]>(() => {
  const vals = Object.values(perDistrict.value)
  if (vals.length === 0) return []
  return Object.keys(vals[0] as any)
})

const evalChartRef = ref<HTMLElement | null>(null)
const evalStage2Ref = ref<HTMLElement | null>(null)
let evalChart: echarts.ECharts | null = null
let evalChart2: echarts.ECharts | null = null

// ── 数据加载 ──────────────────────────────
async function loadModelInfo() {
  try {
    modelInfo.value = await api.modelInfo(activeModelKey.value)
  } catch (e) { console.error('modelInfo', e) }
}

async function loadEvaluation() {
  try {
    evalData.value = await api.evaluate(activeModelKey.value)
  } catch (e) { console.error('evaluate', e) }
}

async function loadTrainingLog() {
  try {
    trainingLog.value = await api.trainingLog(activeModelKey.value)
  } catch (e) { console.error('trainingLog', e) }
}

async function loadFigures() {
  try {
    const resp = await api.figures(activeModelKey.value)
    figures.value = resp.data || []
  } catch (e) { console.error('figures', e) }
}

async function loadAll() {
  loading.value = true; loadingText.value = '加载模型信息...'
  await loadModelInfo()
  loadingText.value = '加载评估数据...'
  await Promise.all([loadEvaluation(), loadTrainingLog(), loadFigures()])
  loading.value = false
}

// ── 训练 ──────────────────────────────────
async function startTrain() {
  if (trainStatus.value?.running) return
  try {
    await api.train(activeModelKey.value, nTrials.value)
    startPolling()
  } catch (e: any) { alert('启动训练失败: ' + e.message) }
}

function startPolling() {
  stopPolling()
  trainPollTimer = setInterval(async () => {
    try {
      const st = await api.trainStatus(activeModelKey.value)
      trainStatus.value = st
      if (st.result) { trainResult.value = st.result; renderTrainChart() }
      if (!st.running) stopPolling()
    } catch (e) { console.error(e) }
  }, 2000)
}

function stopPolling() {
  if (trainPollTimer) { clearInterval(trainPollTimer); trainPollTimer = null }
}

function renderTrainChart() {
  if (!trainChartRef.value || !trainResult.value) return
  if (!trainChart) trainChart = echarts.init(trainChartRef.value)
  const log = trainResult.value.training_log || []
  trainChart.setOption({
    title: { text: 'Training Curve', left: 'center', textStyle: { color: '#e4e7ed' } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['Train Loss', 'Val Loss'], bottom: 0, textStyle: { color: '#aaa' } },
    grid: { left: '8%', right: '5%', top: '15%', bottom: '12%' },
    xAxis: { type: 'category', data: log.map((r: any) => r.epoch), name: 'Epoch', axisLabel: { color: '#aaa' } },
    yAxis: { type: 'log', name: 'Loss', axisLabel: { color: '#aaa' } },
    series: [
      { name: 'Train Loss', type: 'line', data: log.map((r: any) => r.train_loss), smooth: true, lineStyle: { color: '#3b82f6' } },
      { name: 'Val Loss', type: 'line', data: log.map((r: any) => r.val_loss), smooth: true, lineStyle: { color: '#ef4444' } },
    ],
  })
}

// ── 预测 ──────────────────────────────────
async function runPredict() {
  loading.value = true; loadingText.value = '正在运行预测...'
  try {
    predictResult.value = await api.predict(activeModelKey.value)
  } catch (e: any) { alert('预测失败: ' + e.message) }
  loading.value = false
}

// ── 评估图表 ──────────────────────────────
function renderEvalChart() {
  const log = trainingLog.value
  if (!log || !evalChartRef.value) return
  const stage1 = log.training_log_stage1 || log.training_log || []
  if (stage1.length === 0) return
  if (!evalChart) evalChart = echarts.init(evalChartRef.value)
  evalChart.setOption({
    title: { text: 'Stage 1 Training History', left: 'center', textStyle: { color: '#e4e7ed' } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['Train Loss', 'Val Loss'], bottom: 0, textStyle: { color: '#aaa' } },
    grid: { left: '8%', right: '5%', top: '15%', bottom: '12%' },
    xAxis: { type: 'category', data: stage1.map((r: any) => r.epoch), axisLabel: { color: '#aaa' } },
    yAxis: { type: 'value', name: 'Loss', axisLabel: { color: '#aaa' } },
    series: [
      { name: 'Train Loss', type: 'line', data: stage1.map((r: any) => r.train_loss), smooth: true, lineStyle: { color: '#3b82f6' } },
      { name: 'Val Loss', type: 'line', data: stage1.map((r: any) => r.val_loss), smooth: true, lineStyle: { color: '#ef4444' } },
    ],
  })
}

function renderEvalStage2() {
  const log = trainingLog.value
  if (!log || !evalStage2Ref.value) return
  const stage2 = log.training_log_stage2 || []
  if (stage2.length === 0) return
  if (!evalChart2) evalChart2 = echarts.init(evalStage2Ref.value)
  evalChart2.setOption({
    title: { text: 'Stage 2 Residual Training', left: 'center', textStyle: { color: '#e4e7ed' } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['Train Loss', 'Val Loss'], bottom: 0, textStyle: { color: '#aaa' } },
    grid: { left: '8%', right: '5%', top: '15%', bottom: '12%' },
    xAxis: { type: 'category', data: stage2.map((r: any) => r.epoch), axisLabel: { color: '#aaa' } },
    yAxis: { type: 'value', name: 'Loss', axisLabel: { color: '#aaa' } },
    series: [
      { name: 'Train Loss', type: 'line', data: stage2.map((r: any) => r.train_loss), smooth: true, lineStyle: { color: '#3b82f6' } },
      { name: 'Val Loss', type: 'line', data: stage2.map((r: any) => r.val_loss), smooth: true, lineStyle: { color: '#ef4444' } },
    ],
  })
}

// ── Tab 切换重渲染 ────────────────────────
watch(activeTab, (val) => {
  nextTick(() => {
    if (val === 'train' && trainResult.value) renderTrainChart()
    if (val === 'evaluate') { renderEvalChart(); renderEvalStage2() }
  })
})

// ── 子模型切换 ────────────────────────────
watch(activeModelKey, async () => {
  activeTab.value = 'evaluate'
  trainResult.value = null
  predictResult.value = null
  await loadAll()
})

// ── 生命周期 ──────────────────────────────
onMounted(async () => {
  try { await api.ping(); serverOnline.value = true } catch { serverOnline.value = false }
  await loadAll()
  nextTick(() => { renderEvalChart(); renderEvalStage2() })
})

onBeforeUnmount(() => {
  stopPolling()
  trainChart?.dispose(); evalChart?.dispose(); evalChart2?.dispose()
})
</script>

<template>
<div class="tq-demo" :style="{
  '--bg': 'transparent', '--card': 'rgba(17,24,39,0.6)', '--border': 'rgba(0,212,255,0.15)',
  '--text': '#e4e7ed', '--muted': 'rgba(255,255,255,0.5)', '--primary': '#3b82f6',
  '--good': '#22c55e', '--warn': '#f59e0b', '--bad': '#ef4444', '--radius': '12px',
}">
  <!-- 模型信息 -->
  <div class="card" v-if="modelInfo">
    <div class="info-header">
      <h3>{{ modelInfo.name }}</h3>
      <span class="badge" :class="modelInfo.has_trained_model ? 'badge-good' : 'badge-warn'">
        {{ modelInfo.has_trained_model ? '模型已加载' : '未训练' }}
      </span>
    </div>
    <div class="info-grid">
      <div class="info-item"><span class="label">编号</span><span class="value">{{ modelInfo.code }}</span></div>
      <div class="info-item"><span class="label">参数量</span><span class="value">{{ modelInfo.params?.toLocaleString() }}</span></div>
      <div class="info-item"><span class="label">输入</span><span class="value">{{ modelInfo.config.input_days }}天 → {{ modelInfo.config.output_days }}天</span></div>
      <div class="info-item"><span class="label">时序维度</span><span class="value">{{ modelInfo.config.time_series_dim }}</span></div>
      <div class="info-item"><span class="label">通道</span><span class="value">{{ modelInfo.config.channels.join(', ') }}</span></div>
      <div class="info-item"><span class="label">模型类型</span><span class="value">{{ modelInfo.model_type === 'two_stage' ? '两阶段(CNNLSTM+残差)' : '单阶段(CNNLSTM)' }}</span></div>
    </div>
    <div class="districts" v-if="modelInfo.districts?.length">
      <span class="label">台区:</span>
      <span v-for="d in modelInfo.districts" :key="d.id" class="district-tag">{{ d.name }}</span>
    </div>
  </div>

  <!-- 子模型选择器 (TQ-01) -->
  <div class="sub-selector" v-if="showSubSelector">
    <button v-for="sm in subModels" :key="sm.key"
      :class="['sub-btn', { active: activeModelKey === sm.key }]"
      @click="activeModelKey = sm.key">{{ sm.label }}</button>
  </div>

  <!-- Tab 导航 -->
  <div class="tabs">
    <button :class="{ active: activeTab === 'train' }" @click="activeTab = 'train'">模型训练</button>
    <button :class="{ active: activeTab === 'predict' }" @click="activeTab = 'predict'">体验预测</button>
    <button :class="{ active: activeTab === 'evaluate' }" @click="activeTab = 'evaluate'">模型评估</button>
  </div>

  <!-- Tab 1: 模型训练 -->
  <div v-show="activeTab === 'train'" class="tab-content">
    <div class="card">
      <h4>训练配置</h4>
      <div class="train-controls">
        <a :href="api.getPredictCsvUrl(activeModelKey)" target="_blank" class="btn btn-outline">下载体验数据</a>
        <label class="ctrl-label">Optuna轮次:
          <select v-model.number="nTrials" class="select">
            <option :value="5">5</option><option :value="10">10</option><option :value="20">20</option>
          </select>
        </label>
        <button class="btn btn-primary" @click="startTrain" :disabled="trainStatus?.running">
          {{ trainStatus?.running ? '训练中...' : '开始训练' }}
        </button>
      </div>
      <div class="progress-bar" v-if="trainStatus && (trainStatus.running || trainStatus.progress > 0)">
        <div class="progress-fill" :style="{ width: trainStatus.progress + '%' }"></div>
        <span class="progress-text">{{ trainStatus.message }} ({{ trainStatus.progress }}%)</span>
      </div>
    </div>

    <div class="card" v-if="trainResult">
      <h4>训练结果</h4>
      <div class="grid-4">
        <div class="score-card"><div class="label">Val Loss</div><div class="value">{{ trainResult.metrics.best_val_loss }}</div></div>
        <div class="score-card"><div class="label">Best Epoch</div><div class="value">{{ trainResult.metrics.best_epoch }}</div></div>
        <div class="score-card"><div class="label">参数量</div><div class="value">{{ trainResult.metrics.total_params?.toLocaleString() }}</div></div>
        <div class="score-card"><div class="label">训练轮数</div><div class="value">{{ trainResult.metrics.epochs_trained }}</div></div>
      </div>
      <div class="chart-full">
        <div class="chart-box"><div ref="trainChartRef" style="height: 360px;"></div></div>
      </div>
      <div v-if="trainResult.optuna_best_params && Object.keys(trainResult.optuna_best_params).length > 0">
        <h4>Optuna 最优参数</h4>
        <pre class="json-output">{{ JSON.stringify(trainResult.optuna_best_params, null, 2) }}</pre>
      </div>
    </div>
  </div>

  <!-- Tab 2: 体验预测 -->
  <div v-show="activeTab === 'predict'" class="tab-content">
    <div class="card">
      <h4>预测操作</h4>
      <div class="train-controls">
        <a :href="api.getPredictCsvUrl(activeModelKey)" target="_blank" class="btn btn-outline">下载体验数据</a>
        <button class="btn btn-primary" @click="runPredict" :disabled="loading">运行预测</button>
      </div>
    </div>

    <div class="card" v-if="predictResult">
      <h4>预测结果</h4>
      <div class="grid-4">
        <div class="score-card"><div class="label">MAE</div><div class="value">{{ predictResult.metrics.mae }}</div></div>
        <div class="score-card"><div class="label">RMSE</div><div class="value">{{ predictResult.metrics.rmse }}</div></div>
        <div class="score-card"><div class="label">MAPE</div><div class="value">{{ predictResult.metrics.mape }}%</div></div>
        <div class="score-card"><div class="label">CVRMSE</div><div class="value">{{ predictResult.metrics.cvrmse }}%</div></div>
      </div>
      <div class="chart-full">
        <div class="chart-box">
          <img :src="'data:image/png;base64,' + predictResult.charts.predict_compare" alt="预测对比图" />
        </div>
      </div>
      <div class="table-wrap">
        <table class="result-table">
          <thead><tr><th>台区</th><th>样本</th><th>时间</th><th>预测值</th><th>真实值</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in predictResult.predictions" :key="i">
              <td>{{ r.district }}</td><td>{{ r.sample }}</td><td>{{ r.time }}</td>
              <td>{{ r.predicted }}</td><td>{{ r.true }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <a :href="api.getDownloadUrl(activeModelKey)" target="_blank" class="btn btn-outline">下载结果CSV</a>
    </div>
  </div>

  <!-- Tab 3: 模型评估 -->
  <div v-show="activeTab === 'evaluate'" class="tab-content">
    <div class="card" v-if="evalData && !evalData.error">
      <h4>评估指标</h4>
      <template v-if="evalData.eval || evalData.test">
        <div class="grid-4" v-if="evalData.eval?.overall || evalData.test?.overall">
          <div class="score-card" v-for="(val, key) in (evalData.test?.overall || evalData.eval?.overall)" :key="key">
            <div class="label">{{ key }}</div><div class="value">{{ typeof val === 'number' ? val.toFixed(4) : val }}</div>
          </div>
        </div>
        <div v-if="evalData.test?.per_district || evalData.eval?.per_district" style="margin-top: 12px;">
          <h4>分台区指标</h4>
          <div class="table-wrap">
            <table class="result-table">
              <thead><tr><th>台区</th><th v-for="k in perDistrictCols" :key="k">{{ k }}</th></tr></thead>
              <tbody>
                <tr v-for="(d, eid) in perDistrict" :key="eid">
                  <td>{{ d.name || eid }}</td>
                  <td v-for="k in perDistrictCols.filter(x => x !== 'name')" :key="k">{{ typeof d[k] === 'number' ? d[k].toFixed(4) : d[k] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
      <template v-else-if="evalData.overall">
        <div class="grid-4">
          <div class="score-card" v-for="(val, key) in evalData.overall" :key="key">
            <div class="label">{{ key }}</div><div class="value">{{ typeof val === 'number' ? val.toFixed(4) : val }}</div>
          </div>
        </div>
      </template>
      <div v-if="evalData.config" style="margin-top: 12px;">
        <h4>模型配置</h4>
        <pre class="json-output">{{ JSON.stringify(evalData.config, null, 2) }}</pre>
      </div>
    </div>

    <div class="card" v-if="trainingLog && !trainingLog.error">
      <h4>训练历史曲线</h4>
      <div class="chart-full">
        <div class="chart-box"><div ref="evalChartRef" style="height: 360px;"></div></div>
        <div class="chart-box" v-if="trainingLog.training_log_stage2"><div ref="evalStage2Ref" style="height: 360px;"></div></div>
      </div>
    </div>

    <div class="card" v-if="figures.length > 0">
      <h4>预测对比图</h4>
      <div class="chart-full">
        <div class="chart-box" v-for="fig in figures" :key="fig.name">
          <h5>{{ fig.name }}</h5>
          <img :src="'data:image/png;base64,' + fig.base64" :alt="fig.name" />
        </div>
      </div>
    </div>
  </div>

  <div v-if="loading" class="loading-overlay">
    <div class="spinner"></div><p>{{ loadingText }}</p>
  </div>
</div>
</template>

<style scoped>
.tq-demo {
  background: var(--bg); color: var(--text); font-size: 15px;
  max-width: 1400px; margin: 0 auto; padding: 20px;
}
.card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 22px 24px; margin-bottom: 16px; }
.card h3 { margin: 0 0 12px; font-size: 18px; }
.card h4 { margin: 0 0 8px; font-size: 15px; }
.card h5 { margin: 0 0 6px; font-size: 13px; color: var(--muted); }
.info-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.badge { padding: 2px 10px; border-radius: 12px; font-size: 12px; }
.badge-good { background: rgba(34,197,94,0.2); color: var(--good); }
.badge-warn { background: rgba(245,158,11,0.2); color: var(--warn); }
.info-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.info-item { display: flex; gap: 6px; }
.info-item .label { color: var(--muted); min-width: 60px; }
.districts { margin-top: 8px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.district-tag { background: rgba(59,130,246,0.15); color: var(--primary); padding: 2px 8px; border-radius: 6px; font-size: 13px; }
.sub-selector { display: flex; gap: 8px; margin-bottom: 16px; }
.sub-btn { padding: 8px 20px; border-radius: 8px; border: 1px solid var(--border); background: var(--card); color: var(--text); cursor: pointer; }
.sub-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
.tabs button { padding: 10px 24px; background: none; border: none; border-bottom: 2px solid transparent; color: var(--muted); cursor: pointer; font-size: 15px; }
.tabs button.active { color: var(--text); border-bottom-color: var(--primary); }
.tab-content { min-height: 400px; }
.train-controls { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.btn { padding: 8px 20px; border-radius: 8px; border: 1px solid var(--border); cursor: pointer; font-size: 14px; text-decoration: none; display: inline-block; }
.btn-primary { background: var(--primary); color: #fff; border-color: var(--primary); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline { background: transparent; color: var(--text); }
.ctrl-label { display: flex; align-items: center; gap: 6px; color: var(--muted); }
.select { background: var(--card); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; }
.progress-bar { margin-top: 12px; background: rgba(255,255,255,0.05); border-radius: 8px; height: 32px; position: relative; overflow: hidden; }
.progress-fill { position: absolute; top: 0; left: 0; height: 100%; background: linear-gradient(90deg, var(--primary), #60a5fa); transition: width 0.3s; }
.progress-text { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 13px; white-space: nowrap; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.score-card { background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: 8px; padding: 12px; text-align: center; }
.score-card .label { color: var(--muted); font-size: 12px; margin-bottom: 4px; }
.score-card .value { font-size: 20px; font-weight: 600; }
.chart-full { display: flex; flex-direction: column; gap: 16px; }
.chart-box { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px; overflow: hidden; }
.chart-box img { width: 100%; height: auto; display: block; }
.table-wrap { overflow-x: auto; margin: 12px 0; }
.result-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.result-table th, .result-table td { padding: 8px 8px; text-align: center; border-bottom: 1px solid var(--border); }
.result-table th { color: var(--muted); }
.json-output { background: rgba(0,0,0,0.3); border: 1px solid var(--border); border-radius: 8px; padding: 12px; overflow-x: auto; font-size: 13px; white-space: pre-wrap; }
.loading-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 9999; }
.spinner { width: 40px; height: 40px; border: 3px solid rgba(255,255,255,0.2); border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
