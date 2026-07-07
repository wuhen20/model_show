<script setup lang="ts">
import { nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { createHeatingFraudApi, type HeatingFraudModelInfo, type HeatingFraudTrainStatus, type HeatingFraudPredictResult, type HeatingFraudRuleSpecItem } from '@/api/demo'

const api = createHeatingFraudApi()

const serverOnline = ref(false)
const loading = ref(false)
const loadingText = ref('')
const statusMsg = ref('')
const statusClass = ref('')
const activeTab = ref<'train' | 'predict' | 'evaluate'>('train')

// 模型信息
const modelInfo = ref<HeatingFraudModelInfo | null>(null)

// 训练
const trainFileRef = ref<HTMLInputElement | null>(null)
const trainDataInfo = ref<any>(null)
const trainStatus = ref<HeatingFraudTrainStatus | null>(null)
const trainResult = ref<any>(null)
const trainParams = ref({ n_trials: 100 })
const nTrialsOptions = [10, 50, 100]
let trainPollTimer: any = null

// 预测
const predictFileRef = ref<HTMLInputElement | null>(null)
const predictDataInfo = ref<any>(null)
const predictResult = ref<HeatingFraudPredictResult | null>(null)
const predictPage = ref(1)
const predictPageSize = 20

// 评估
const evalData = ref<any>(null)
const featureImportance = ref<{ feature: string; importance: number }[]>([])
const ruleSpec = ref<HeatingFraudRuleSpecItem[]>([])

// 图表 refs
const charts: Record<string, echarts.ECharts | null> = {}
const featImpChartRef = ref<HTMLDivElement | null>(null)
const riskDistTrainRef = ref<HTMLDivElement | null>(null)
const riskDistPredictRef = ref<HTMLDivElement | null>(null)
const foldRadarRef = ref<HTMLDivElement | null>(null)

function showLoading(msg: string) { loading.value = true; loadingText.value = msg }
function hideLoading() { loading.value = false }
function setStatus(msg: string, cls: string = '') { statusMsg.value = msg; statusClass.value = cls }

async function init() {
  try {
    await api.ping()
    serverOnline.value = true
    await loadModelInfo()
    await loadEvalData()
    await loadFeatureImportance()
    await loadRuleSpec()
    nextTick(() => { renderFeatImpChart(); renderFoldRadar() })
  } catch {
    serverOnline.value = false
  }
}

async function loadModelInfo() {
  try { modelInfo.value = await api.modelInfo() } catch {}
}

async function loadEvalData() {
  try { evalData.value = await api.evaluate() } catch {}
}

async function loadFeatureImportance() {
  try {
    const r = await api.featureImportance()
    featureImportance.value = r.data || []
    nextTick(() => renderFeatImpChart())
  } catch {}
}

async function loadRuleSpec() {
  try {
    const r = await api.ruleSpec()
    ruleSpec.value = r.data || []
  } catch {}
}

// ============ 训练 ============

function triggerTrainUpload() { trainFileRef.value?.click() }

async function onTrainFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  showLoading('上传训练数据...')
  try {
    const r = await api.uploadTrain(file)
    trainDataInfo.value = r
    setStatus(r.message, 'ok')
  } catch (err: any) {
    setStatus('上传失败: ' + err.message, 'err')
  } finally {
    hideLoading()
  }
}

async function startTrain() {
  showLoading('正在启动训练...')
  try {
    const r = await api.train(trainParams.value.n_trials)
    if (r.status === 'ok') {
      setStatus('训练已启动', 'ok')
      pollTrainStatus()
    } else {
      setStatus(r.message, 'err')
    }
  } catch (err: any) {
    setStatus('训练失败: ' + err.message, 'err')
  } finally {
    hideLoading()
  }
}

function pollTrainStatus() {
  if (trainPollTimer) clearInterval(trainPollTimer)
  trainPollTimer = setInterval(async () => {
    try {
      const st = await api.trainStatus()
      trainStatus.value = st
      if (!st.running) {
        clearInterval(trainPollTimer!)
        trainPollTimer = null
        if (st.result) {
          trainResult.value = st.result
          setStatus('训练完成', 'ok')
          await loadModelInfo()
          await loadFeatureImportance()
          await loadEvalData()
          nextTick(() => {
            renderRiskDistTrain()
            renderFeatImpChart()
            renderFoldRadar()
          })
        } else if (st.error) {
          setStatus('训练失败: ' + st.error, 'err')
        }
      }
    } catch {}
  }, 2000)
}

// ============ 预测 ============

function triggerPredictUpload() { predictFileRef.value?.click() }

async function onPredictFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  showLoading('上传预测数据...')
  try {
    const r = await api.uploadPredict(file)
    predictDataInfo.value = r
    setStatus(r.message, 'ok')
  } catch (err: any) {
    setStatus('上传失败: ' + err.message, 'err')
  } finally {
    hideLoading()
  }
}

async function runPredict() {
  showLoading('正在预测...')
  try {
    const r = await api.predict()
    if (r.status === 'error') {
      setStatus((r as any).message || '预测失败', 'err')
      return
    }
    predictResult.value = r
    predictPage.value = 1
    setStatus(`预测完成: ${r.n_samples} 条`, 'ok')
    nextTick(() => renderRiskDistPredict())
  } catch (err: any) {
    setStatus('预测失败: ' + err.message, 'err')
  } finally {
    hideLoading()
  }
}

function getPredictPageData() {
  if (!predictResult.value?.predictions) return []
  const start = (predictPage.value - 1) * predictPageSize
  return predictResult.value.predictions.slice(start, start + predictPageSize)
}

function getPredictTotalPages() {
  if (!predictResult.value?.predictions) return 1
  return Math.ceil(predictResult.value.predictions.length / predictPageSize)
}

// ============ 图表渲染 ============

function getChart(key: string, el: HTMLDivElement | null): echarts.ECharts | null {
  if (!el) return null
  if (charts[key]) { charts[key]!.dispose() }
  charts[key] = echarts.init(el)
  return charts[key]
}

function renderRiskDistTrain() {
  const dist = trainResult.value?.risk_distribution || evalData.value?.risk_distribution
  if (!dist) return
  const chart = getChart('riskDistTrain', riskDistTrainRef.value)
  if (!chart) return
  renderRiskBar(chart, dist, '训练风险等级分布')
}

function renderRiskDistPredict() {
  const dist = predictResult.value?.risk_distribution
  if (!dist) return
  const chart = getChart('riskDistPredict', riskDistPredictRef.value)
  if (!chart) return
  renderRiskBar(chart, dist, '预测风险等级分布')
}

function renderRiskBar(chart: echarts.ECharts, dist: Record<string, number>, title: string) {
  const order = ['高风险', '中风险', '低风险']
  const colors = ['#e74c3c', '#f39c12', '#27ae60']
  chart.setOption({
    title: { text: title, textStyle: { color: '#e4e7ed', fontSize: 14 }, left: 'center' },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: order, axisLabel: { color: '#9ca3af' } },
    yAxis: { type: 'value', axisLabel: { color: '#9ca3af' } },
    series: [{
      type: 'bar',
      data: order.map((k, i) => ({ value: dist[k] || 0, itemStyle: { color: colors[i], borderRadius: [4, 4, 0, 0] } })),
      label: { show: true, position: 'top', color: '#e4e7ed', fontSize: 12 },
    }],
    grid: { left: '5%', right: '5%', bottom: '10%', top: '15%', containLabel: true },
  })
}

function renderFeatImpChart() {
  const data = featureImportance.value
  if (!data.length) return
  const chart = getChart('featImp', featImpChartRef.value)
  if (!chart) return
  const sorted = [...data].sort((a, b) => b.importance - a.importance).slice(0, 20)
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', name: '重要性', nameTextStyle: { color: '#9ca3af' }, axisLabel: { color: '#9ca3af' } },
    yAxis: { type: 'category', data: sorted.map(d => d.feature).reverse(), axisLabel: { color: '#9ca3af', fontSize: 10 } },
    series: [{
      type: 'bar',
      data: sorted.map(d => d.importance).reverse(),
      itemStyle: { color: '#3b82f6', borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', fontSize: 10, color: '#e4e7ed', formatter: (p: any) => p.value.toFixed(4) },
    }],
    grid: { left: '3%', right: '10%', bottom: '5%', top: '5%', containLabel: true },
  })
}

function renderFoldRadar() {
  const folds = evalData.value?.fold_metrics || trainResult.value?.metrics?.fold_metrics
  if (!folds || !folds.length) return
  const chart = getChart('foldRadar', foldRadarRef.value)
  if (!chart) return
  const indicators = [
    { name: 'AUC', max: 1 }, { name: 'F1', max: 1 },
    { name: 'Precision', max: 1 }, { name: 'Recall', max: 1 },
    { name: 'Accuracy', max: 1 },
  ]
  chart.setOption({
    title: { text: '5-fold CV 雷达图', textStyle: { color: '#e4e7ed', fontSize: 14 }, left: 'center' },
    tooltip: {},
    legend: { bottom: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
    radar: { indicator: indicators, radius: '65%', splitArea: { areaStyle: { color: ['rgba(59,130,246,0.03)', 'rgba(59,130,246,0.06)'] } } },
    series: [{
      type: 'radar',
      data: folds.map((f: any) => ({
        name: `Fold ${f.fold}`,
        value: [f.auc, f.f1, f.precision, f.recall, f.accuracy],
        lineStyle: { width: 2 }, areaStyle: { opacity: 0.1 },
      })),
    }],
  })
}

// tab 切换时重渲染对应图表
watch(activeTab, (val) => {
  if (val === 'evaluate') {
    nextTick(() => { renderFeatImpChart(); renderFoldRadar() })
  } else if (val === 'train' && trainResult.value) {
    nextTick(() => { renderRiskDistTrain() })
  } else if (val === 'predict' && predictResult.value) {
    nextTick(() => { renderRiskDistPredict() })
  }
})

onMounted(init)
onBeforeUnmount(() => {
  if (trainPollTimer) clearInterval(trainPollTimer)
  Object.values(charts).forEach(c => c?.dispose())
})
</script>

<template>
  <div class="hf-root">
    <header class="hf-header">
      <div>
        <h1>电采暖高价低接研判</h1>
        <div class="sub">LightGBM + SHAP + 16维规则评分体系 · 二分类欺诈识别</div>
      </div>
      <div class="server-info">
        <span class="server-dot" :class="serverOnline ? 'on' : 'off'"></span>
        <span>{{ serverOnline ? '服务就绪' : '服务未连接' }}</span>
      </div>
    </header>

    <main class="hf-main">
      <div v-if="loading" class="loading-overlay">
        <div class="spinner"></div>{{ loadingText }}
      </div>

      <!-- 模型信息卡 -->
      <div class="card model-bar">
        <div class="info-grid">
          <div class="info-item"><span class="info-label">算法</span><span class="info-value">{{ modelInfo?.model_type || '-' }}</span></div>
          <div class="info-item"><span class="info-label">特征数</span><span class="info-value">{{ modelInfo?.n_features || '-' }}</span></div>
          <div class="info-item"><span class="info-label">阈值</span><span class="info-value">{{ modelInfo?.threshold?.toFixed(4) || '-' }}</span></div>
          <div class="info-item"><span class="info-label">CV折数</span><span class="info-value">{{ modelInfo?.config?.cv_folds || 5 }}</span></div>
          <div class="info-item"><span class="info-label">先验对齐</span><span class="info-value">{{ modelInfo?.config?.use_prior_align ? '已启用' : '未启用' }}</span></div>
          <div class="info-item"><span class="info-label">阈值优化</span><span class="info-value">F{{ modelInfo?.config?.threshold_opt_beta || 0.5 }}-beta</span></div>
          <div class="info-item"><span class="info-label">Optuna目标</span><span class="info-value">{{ modelInfo?.config?.optuna_objective?.toUpperCase() || 'AUC' }}</span></div>
          <div class="info-item"><span class="info-label">默认模型</span><span class="info-value" :class="modelInfo?.default_model_available ? 'ok' : 'err'">{{ modelInfo?.default_model_available ? '可用' : '不可用' }}</span></div>
        </div>
        <div class="toolbar" style="margin-top: 12px;">
          <span class="status" :class="statusClass">{{ statusMsg }}</span>
        </div>
      </div>

      <!-- Tab 导航 -->
      <nav class="tabs">
        <button class="tab-btn" :class="{ active: activeTab === 'train' }" @click="activeTab = 'train'">模型训练</button>
        <button class="tab-btn" :class="{ active: activeTab === 'predict' }" @click="activeTab = 'predict'">体验预测</button>
        <button class="tab-btn" :class="{ active: activeTab === 'evaluate' }" @click="activeTab = 'evaluate'">模型评估</button>
      </nav>

      <!-- Tab 1: 模型训练 -->
      <div v-show="activeTab === 'train'">
        <div class="grid-2">
          <!-- 左：训练数据上传 -->
          <div class="card">
            <h3>训练数据</h3>
            <input ref="trainFileRef" type="file" accept=".csv" style="display:none" @change="onTrainFileChange" />
            <div class="toolbar" style="margin-bottom: 16px;">
              <button class="btn" @click="triggerTrainUpload">上传训练 CSV</button>
              <a :href="api.getDemoCsvUrl()" class="btn ghost">下载体验数据</a>
            </div>
            <div v-if="trainDataInfo" class="info-box">
              <div class="info-row"><span>样本数:</span> {{ trainDataInfo.rows }}</div>
              <div class="info-row"><span>特征数:</span> {{ trainDataInfo.features }}</div>
              <div class="info-row"><span>含标签:</span> {{ trainDataInfo.has_label ? '是' : '否' }}</div>
              <div v-if="trainDataInfo.label_distribution" class="info-row">
                <span>标签分布:</span>
                <span v-for="d in trainDataInfo.label_distribution" :key="d.name" class="label-tag">{{ d.name }}: {{ d.value }}</span>
              </div>
            </div>

            <div style="margin-top: 20px;">
              <label class="form-label">Optuna 搜索轮数</label>
              <div class="radio-group">
                <button v-for="n in nTrialsOptions" :key="n" class="radio-btn" :class="{ active: trainParams.n_trials === n }" @click="trainParams.n_trials = n">{{ n }}</button>
              </div>
            </div>
            <div style="margin-top: 16px;">
              <button class="btn tune-btn" :disabled="!trainDataInfo && !serverOnline" @click="startTrain" style="font-size:16px; padding:12px 24px;">开始训练</button>
              <span v-if="!trainDataInfo" class="form-hint" style="margin-left: 8px;">（未上传数据将使用内置体验数据）</span>
            </div>
          </div>

          <!-- 右：训练进度与结果 -->
          <div class="card">
            <h3>训练进度与结果</h3>
            <div v-if="trainStatus && (trainStatus.running || trainStatus.progress > 0)" class="progress-wrap">
              <div class="progress-bar"><div class="progress-fill" :style="{ width: trainStatus.progress + '%' }"></div></div>
              <span class="progress-text">{{ trainStatus.message }} ({{ trainStatus.progress }}%)</span>
            </div>
            <div v-if="trainStatus?.error" class="error-msg">训练失败: {{ trainStatus.error }}</div>

            <template v-if="trainResult">
              <div class="grid-4" style="margin-top: 16px;">
                <div class="score-card"><div class="label">OOF AUC</div><div class="value">{{ trainResult.metrics.oof_auc.toFixed(4) }}</div></div>
                <div class="score-card"><div class="label">OOF F1</div><div class="value">{{ trainResult.metrics.oof_f1.toFixed(4) }}</div></div>
                <div class="score-card"><div class="label">Precision</div><div class="value">{{ trainResult.metrics.oof_precision.toFixed(4) }}</div></div>
                <div class="score-card"><div class="label">Recall</div><div class="value">{{ trainResult.metrics.oof_recall.toFixed(4) }}</div></div>
              </div>
              <div class="grid-4" style="margin-top: 12px;">
                <div class="score-card"><div class="label">最优阈值</div><div class="value">{{ trainResult.threshold.toFixed(4) }}</div></div>
                <div class="score-card"><div class="label">特征数</div><div class="value">{{ trainResult.n_features_used }}</div></div>
                <div class="score-card"><div class="label">Optuna最优</div><div class="value">{{ trainResult.optuna_best_value.toFixed(4) }}</div></div>
                <div class="score-card"><div class="label">OOF AP</div><div class="value">{{ trainResult.metrics.oof_ap?.toFixed(4) || '-' }}</div></div>
              </div>

              <!-- 图表区 -->
              <div v-if="trainResult.charts" style="margin-top: 16px;">
                <div class="chart-full">
                  <div class="chart-box"><img :src="'data:image/png;base64,' + trainResult.charts.roc_pr_curve" alt="ROC/PR" /></div>
                  <div class="chart-box"><img :src="'data:image/png;base64,' + trainResult.charts.confusion_matrix" alt="混淆矩阵" /></div>
                  <div class="chart-box"><img :src="'data:image/png;base64,' + trainResult.charts.shap_summary" alt="SHAP Summary" /></div>
                  <div class="chart-box"><img :src="'data:image/png;base64,' + trainResult.charts.shap_bar" alt="SHAP Bar" /></div>
                  <div class="chart-box"><img :src="'data:image/png;base64,' + trainResult.charts.rule_vs_model" alt="规则vs模型" /></div>
                  <div class="chart-box"><div ref="riskDistTrainRef" style="height: 360px;"></div></div>
                </div>
              </div>

              <!-- CV 指标表 -->
              <div v-if="trainResult.metrics.fold_metrics" style="margin-top: 16px;">
                <h4>5-fold CV 逐折指标</h4>
                <div class="table-wrap">
                  <table class="result-table">
                    <thead><tr><th>折</th><th>AUC</th><th>F1</th><th>Precision</th><th>Recall</th><th>Accuracy</th></tr></thead>
                    <tbody>
                      <tr v-for="f in trainResult.metrics.fold_metrics" :key="f.fold">
                        <td>Fold {{ f.fold }}</td>
                        <td>{{ f.auc.toFixed(4) }}</td>
                        <td>{{ f.f1.toFixed(4) }}</td>
                        <td>{{ f.precision.toFixed(4) }}</td>
                        <td>{{ f.recall.toFixed(4) }}</td>
                        <td>{{ f.accuracy.toFixed(4) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Optuna 最优参数 -->
              <div style="margin-top: 16px;">
                <h4>Optuna 最优参数</h4>
                <pre class="json-output">{{ JSON.stringify(trainResult.optuna_best_params, null, 2) }}</pre>
              </div>
            </template>
            <div v-else-if="!trainStatus?.running" class="placeholder">点击「开始训练」启动 Optuna 超参搜索 + 5-fold CV 训练流程</div>
          </div>
        </div>
      </div>

      <!-- Tab 2: 体验预测 -->
      <div v-show="activeTab === 'predict'">
        <div class="grid-2">
          <!-- 左：预测数据上传 -->
          <div class="card">
            <h3>预测数据</h3>
            <input ref="predictFileRef" type="file" accept=".csv" style="display:none" @change="onPredictFileChange" />
            <div class="toolbar" style="margin-bottom: 16px;">
              <button class="btn" @click="triggerPredictUpload">上传预测 CSV</button>
              <a :href="api.getPredictCsvUrl()" class="btn ghost">下载体验数据</a>
            </div>
            <div v-if="predictDataInfo" class="info-box">
              <div class="info-row"><span>样本数:</span> {{ predictDataInfo.rows }}</div>
              <div class="info-row"><span>特征数:</span> {{ predictDataInfo.features }}</div>
              <div class="info-row"><span>含meter_id:</span> {{ predictDataInfo.has_meter_id ? '是' : '否' }}</div>
            </div>
            <div style="margin-top: 20px;">
              <button class="btn" :disabled="!predictDataInfo && !serverOnline" @click="runPredict" style="font-size: 16px; padding: 12px 24px;">开始预测</button>
              <span v-if="!predictDataInfo" class="form-hint" style="margin-left: 8px;">（未上传数据将使用内置体验数据）</span>
            </div>
          </div>

          <!-- 右：预测结果 -->
          <div class="card">
            <h3>预测结果</h3>
            <template v-if="predictResult">
              <div class="grid-4" style="margin-bottom: 16px;">
                <div class="score-card"><div class="label">总样本数</div><div class="value">{{ predictResult.n_samples }}</div></div>
                <div class="score-card"><div class="label">高风险</div><div class="value" style="color: #e74c3c;">{{ predictResult.risk_distribution['高风险'] || 0 }}</div></div>
                <div class="score-card"><div class="label">中风险</div><div class="value" style="color: #f39c12;">{{ predictResult.risk_distribution['中风险'] || 0 }}</div></div>
                <div class="score-card"><div class="label">低风险</div><div class="value" style="color: #27ae60;">{{ predictResult.risk_distribution['低风险'] || 0 }}</div></div>
              </div>

              <!-- 图表 -->
              <div v-if="predictResult.charts" style="margin-bottom: 16px;">
                <div class="chart-full">
                  <div class="chart-box"><div ref="riskDistPredictRef" style="height: 360px;"></div></div>
                  <div class="chart-box"><img :src="'data:image/png;base64,' + predictResult.charts.rule_vs_model" alt="规则vs模型" /></div>
                  <div class="chart-box"><img :src="'data:image/png;base64,' + predictResult.charts.shap_summary" alt="SHAP Summary" /></div>
                  <div class="chart-box"><img :src="'data:image/png;base64,' + predictResult.charts.shap_bar" alt="SHAP Bar" /></div>
                  <div class="chart-box"><img :src="'data:image/png;base64,' + predictResult.charts.top_features_bar" alt="Top特征" /></div>
                </div>
              </div>

              <!-- 预测结果表格 -->
              <div class="table-wrap" style="max-height: 500px;">
                <table class="result-table">
                  <thead>
                    <tr><th>meter_id</th><th>预测标签</th><th>欺诈概率</th><th>风险等级</th><th>规则评分</th><th>规则命中</th><th>Top证据1</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="p in getPredictPageData()" :key="p.meter_id">
                      <td style="font-family: monospace; font-size: 12px;">{{ p.meter_id }}</td>
                      <td><span class="pred-tag" :class="p.pred_label === 'sus' ? 'sus' : 'honest'">{{ p.pred_label }}</span></td>
                      <td>{{ p.fraud_prob.toFixed(4) }}</td>
                      <td><span class="risk-tag" :class="p.risk_level === '高风险' ? 'high' : p.risk_level === '中风险' ? 'mid' : 'low'">{{ p.risk_level }}</span></td>
                      <td>{{ p.rule_score.toFixed(3) }}</td>
                      <td style="font-size: 11px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="p.rule_hits">{{ p.rule_hits }}</td>
                      <td style="font-size: 11px;">{{ p.top_evidence_1 }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- 分页 -->
              <div class="pagination">
                <button class="btn small" :disabled="predictPage <= 1" @click="predictPage--">上一页</button>
                <span>{{ predictPage }} / {{ getPredictTotalPages() }}</span>
                <button class="btn small" :disabled="predictPage >= getPredictTotalPages()" @click="predictPage++">下一页</button>
                <a :href="api.getDownloadUrl()" class="btn ghost small" style="margin-left: auto;">下载完整结果CSV</a>
              </div>
            </template>
            <div v-else class="placeholder">点击「开始预测」对体验数据进行欺诈推理</div>
          </div>
        </div>
      </div>

      <!-- Tab 3: 模型评估 -->
      <div v-show="activeTab === 'evaluate'">
        <!-- OOF 评估指标 -->
        <div class="section-title">OOF 评估指标</div>
        <div class="card">
          <div class="grid-4" v-if="evalData && evalData.oof_auc != null">
            <div class="score-card"><div class="label">OOF AUC</div><div class="value">{{ evalData.oof_auc.toFixed(4) }}</div></div>
            <div class="score-card"><div class="label">OOF AP</div><div class="value">{{ evalData.oof_ap?.toFixed(4) || '-' }}</div></div>
            <div class="score-card"><div class="label">OOF F1</div><div class="value">{{ evalData.oof_f1.toFixed(4) }}</div></div>
            <div class="score-card"><div class="label">OOF Precision</div><div class="value">{{ evalData.oof_precision.toFixed(4) }}</div></div>
            <div class="score-card"><div class="label">OOF Recall</div><div class="value">{{ evalData.oof_recall.toFixed(4) }}</div></div>
            <div class="score-card"><div class="label">OOF Accuracy</div><div class="value">{{ evalData.oof_accuracy?.toFixed(4) || '-' }}</div></div>
            <div class="score-card"><div class="label">最优阈值</div><div class="value">{{ evalData.threshold?.toFixed(4) || '-' }}</div></div>
            <div class="score-card"><div class="label">特征数</div><div class="value">{{ evalData.n_features_used || '-' }}</div></div>
          </div>
          <div v-else class="placeholder">暂无评估数据</div>
        </div>

        <!-- 5-fold CV 表 + 雷达图 -->
        <div class="section-title">5-fold 交叉验证</div>
        <div class="card">
          <div class="grid-2">
            <div>
              <div v-if="evalData?.fold_metrics" class="table-wrap">
                <table class="result-table">
                  <thead><tr><th>折</th><th>AUC</th><th>F1</th><th>Precision</th><th>Recall</th><th>Accuracy</th></tr></thead>
                  <tbody>
                    <tr v-for="f in evalData?.fold_metrics" :key="f.fold">
                      <td>Fold {{ f.fold }}</td>
                      <td>{{ f.auc.toFixed(4) }}</td>
                      <td>{{ f.f1.toFixed(4) }}</td>
                      <td>{{ f.precision.toFixed(4) }}</td>
                      <td>{{ f.recall.toFixed(4) }}</td>
                      <td>{{ f.accuracy.toFixed(4) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-if="evalData?.cv_avg_metrics" style="margin-top: 12px;">
                <h4>CV 平均指标</h4>
                <pre class="json-output">{{ JSON.stringify(evalData.cv_avg_metrics, null, 2) }}</pre>
              </div>
            </div>
            <div>
              <div ref="foldRadarRef" style="height: 400px;"></div>
            </div>
          </div>
        </div>

        <!-- 特征重要性 Top-20 -->
        <div class="section-title">特征重要性 Top-20</div>
        <div class="card">
          <div ref="featImpChartRef" style="height: 500px;"></div>
        </div>

        <!-- 16维规则评分体系 -->
        <div class="section-title">16维规则评分体系</div>
        <div class="card">
          <p class="desc">4物理判据 + 5行为假设 + 4 TP强化 + 3 FP排除，权重总和为0的平衡评分体系。</p>
          <div class="table-wrap" style="margin-top: 14px;">
            <table class="result-table">
              <thead>
                <tr><th>规则维度</th><th>阈值</th><th>方向</th><th>权重</th><th>分类</th><th>含义</th></tr>
              </thead>
              <tbody>
                <tr v-for="r in ruleSpec" :key="r.dimension" :class="r.category">
                  <td style="font-family: monospace; font-size: 12px; text-align: left;">{{ r.dimension }}</td>
                  <td>{{ r.threshold }}</td>
                  <td>{{ r.direction }}</td>
                  <td :style="{ color: r.weight > 0 ? '#e74c3c' : '#27ae60' }">{{ r.weight > 0 ? '+' : '' }}{{ r.weight }}</td>
                  <td><span class="cat-tag" :class="r.category">{{ r.category }}</span></td>
                  <td style="text-align: left; font-size: 12px;">{{ r.meaning }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 难例分析 -->
        <div v-if="evalData?.hard_cases" class="section-title">难例分析 (FN/FP)</div>
        <div v-if="evalData?.hard_cases" class="card">
          <div class="grid-2">
            <div>
              <h4>False Negatives (漏报)</h4>
              <div class="info-box"><span class="info-row">数量: {{ evalData.hard_cases.fn_count }}</span></div>
              <div v-if="evalData.hard_cases.fn_meters" class="meter-list">
                <span v-for="m in evalData.hard_cases.fn_meters" :key="m" class="meter-tag fn">{{ m }}</span>
              </div>
            </div>
            <div>
              <h4>False Positives (误报)</h4>
              <div class="info-box"><span class="info-row">数量: {{ evalData.hard_cases.fp_count }}</span></div>
              <div v-if="evalData.hard_cases.fp_meters" class="meter-list">
                <span v-for="m in evalData.hard_cases.fp_meters" :key="m" class="meter-tag fp">{{ m }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <footer class="hf-footer">电采暖高价低接研判系统 · LightGBM + SHAP + 16维规则评分</footer>
  </div>
</template>

<style scoped>
.hf-root {
  --bg: transparent; --card: rgba(17,24,39,0.6); --border: rgba(0,212,255,0.15);
  --text: #e4e7ed; --muted: rgba(255,255,255,0.5); --primary: #3b82f6;
  --good: #22c55e; --warn: #f59e0b; --bad: #ef4444; --radius: 12px;
  --shadow: 0 4px 20px rgba(59,130,246,0.1);
  background: var(--bg); color: var(--text); font-size: 15px;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  min-height: 100%;
}
* { box-sizing: border-box; }
.hf-header {
  padding: 24px 32px; background: linear-gradient(120deg, #1e40af, #3b82f6);
  color: #fff; display: flex; align-items: center; justify-content: space-between;
  box-shadow: var(--shadow); flex-wrap: wrap; gap: 8px;
}
.hf-header h1 { margin: 0; font-size: 28px; font-weight: 600; }
.sub { font-size: 15px; opacity: .9; }
.server-info { display: flex; align-items: center; gap: 4px; font-size: 15px; }
.server-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
.server-dot.on { background: #4ade80; box-shadow: 0 0 6px #4ade80; }
.server-dot.off { background: #f87171; }
.hf-main { padding: 24px 32px 48px; max-width: 1480px; margin: 0 auto; }

.model-bar { padding: 18px 24px; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.info-item { display: flex; flex-direction: column; gap: 4px; }
.info-label { font-size: 12px; color: var(--muted); }
.info-value { font-size: 16px; font-weight: 600; }
.info-value.ok { color: var(--good); }
.info-value.err { color: var(--bad); }

.section-title { margin: 32px 0 14px; font-size: 19px; font-weight: 600; display: flex; align-items: center; gap: 10px; }
.section-title::before { content: ""; width: 6px; height: 20px; background: var(--primary); border-radius: 3px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 22px 24px; box-shadow: var(--shadow); margin-bottom: 4px; }
.card h3 { margin: 0 0 12px; font-size: 18px; color: var(--text); }
.card h4 { margin: 0 0 8px; font-size: 15px; color: var(--text); }

.tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
.tab-btn {
  background: transparent; border: none; color: rgba(255,255,255,0.5);
  padding: 12px 24px; cursor: pointer; font-size: 15px;
  border-bottom: 2px solid transparent; transition: all 0.2s;
}
.tab-btn:hover { color: var(--primary); }
.tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); }

.toolbar { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }
.status { font-size: 14px; color: var(--muted); }
.status.ok { color: var(--good); }
.status.err { color: var(--bad); }

.btn {
  display: inline-flex; align-items: center; gap: 6px; padding: 10px 20px; border-radius: 8px;
  border: none; cursor: pointer; background: var(--primary); color: #fff; font-size: 15px;
  font-weight: 500; transition: all .15s; white-space: nowrap; text-decoration: none;
}
.btn:hover { background: #2563eb; }
.btn:disabled { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.3); cursor: not-allowed; }
.btn.ghost { background: rgba(59,130,246,0.1); color: #3b82f6; border: 1px solid rgba(59,130,246,0.2); }
.btn.small { padding: 4px 14px; font-size: 13px; }
.btn.tune-btn { background: rgba(245,158,11,0.12); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
@media (max-width: 980px) { .grid-2, .grid-4 { grid-template-columns: 1fr; } }

.score-card {
  background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 18px; box-shadow: var(--shadow); text-align: center;
}
.score-card .label { font-size: 15px; color: var(--muted); margin-bottom: 8px; }
.score-card .value { font-size: 32px; font-weight: 700; font-family: "SF Mono", Menlo, monospace; }

.chart-box { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px; overflow: hidden; }
.chart-box img { width: 100%; height: auto; display: block; }
.chart-full { display: flex; flex-direction: column; gap: 16px; }
.chart-full .chart-box { max-width: 100%; }
.chart { height: 300px; width: 100%; min-width: 300px; }

.desc { color: var(--muted); font-size: 14px; line-height: 1.7; }

.table-wrap { max-height: 500px; overflow: auto; }
.result-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.result-table th, .result-table td { padding: 10px 8px; text-align: center; border-bottom: 1px solid var(--border); }
.result-table thead th { background: rgba(59,130,246,0.08); color: #3b82f6; font-weight: 600; position: sticky; top: 0; }
.result-table tr:hover { background: rgba(59,130,246,0.05); }

.info-box { background: rgba(0,0,0,0.3); border-radius: 8px; padding: 14px; }
.info-row { display: flex; align-items: center; gap: 6px; font-size: 14px; margin-bottom: 6px; }
.info-row span:first-child { color: var(--muted); min-width: 70px; }
.label-tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; background: rgba(59,130,246,0.15); color: #3b82f6; margin-right: 4px; }

.form-label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
.form-hint { font-size: 12px; color: var(--muted); }
.radio-group { display: flex; gap: 8px; }
.radio-btn {
  padding: 8px 20px; border-radius: 8px; border: 1px solid var(--border);
  background: rgba(0,0,0,0.3); color: var(--muted); cursor: pointer; font-size: 15px; transition: all .15s;
}
.radio-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }

.progress-wrap { margin-bottom: 16px; }
.progress-bar { height: 8px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #22c55e); border-radius: 4px; transition: width .3s; }
.progress-text { display: block; margin-top: 8px; font-size: 13px; color: var(--muted); }

.error-msg { color: var(--bad); padding: 12px; background: rgba(239,68,68,0.1); border-radius: 8px; margin: 12px 0; }
.placeholder { color: rgba(255,255,255,0.4); padding: 30px; text-align: center; }

.json-output {
  background: rgba(0,0,0,0.4); padding: 12px; border-radius: 6px;
  font-size: 12px; font-family: monospace; overflow: auto; max-height: 300px;
  color: #e4e7ed;
}

.pred-tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.pred-tag.sus { background: rgba(239,68,68,0.15); color: #ef4444; }
.pred-tag.honest { background: rgba(34,197,94,0.15); color: #22c55e; }
.risk-tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.risk-tag.high { background: rgba(231,76,60,0.15); color: #e74c3c; }
.risk-tag.mid { background: rgba(243,156,18,0.15); color: #f39c12; }
.risk-tag.low { background: rgba(39,174,96,0.15); color: #27ae60; }

.cat-tag { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.cat-tag.物理判据 { background: rgba(59,130,246,0.15); color: #3b82f6; }
.cat-tag.行为假设 { background: rgba(168,85,247,0.15); color: #a855f7; }
.cat-tag.TP强化 { background: rgba(239,68,68,0.15); color: #ef4444; }
.cat-tag.FP排除 { background: rgba(34,197,94,0.15); color: #22c55e; }

.pagination { display: flex; align-items: center; gap: 12px; margin-top: 16px; justify-content: center; }

.meter-list { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 12px; }
.meter-tag { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-family: monospace; }
.meter-tag.fn { background: rgba(239,68,68,0.15); color: #ef4444; }
.meter-tag.fp { background: rgba(245,158,11,0.15); color: #f59e0b; }

.loading-overlay {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(10,14,26,0.85); display: flex; align-items: center; justify-content: center;
  z-index: 999; font-size: 20px;
}
.spinner {
  width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.1);
  border-top-color: var(--primary); border-radius: 50%; animation: spin .8s linear infinite; margin-right: 12px;
}
@keyframes spin { to { transform: rotate(360deg) } }
.hf-footer { text-align: center; color: var(--muted); font-size: 13px; padding: 24px; }
</style>
