<script setup lang="ts">
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { createDemoApi, type DemoApi, type DemoPredictResult, type DemoTuneResult, type DemoModelInfo } from '@/api/demo'

// ===================== Props =====================
export interface DemoConfig {
  apiBase: string
  theme: { primary: string; primaryDark: string; gradient: string }
  title: string
  subtitle: string
  flowTitle: string
  flowInputDesc: string
  flowInputItems: string[]
  flowMechDesc: string
  flowMechItems: string[]
  nFeaturesLabel: string
  nFeaturesValue: string
  anomalyTableCols: { key: string; label: string }[]
  detailFeatureKeys: string[]
  hasFeatureImportance: boolean
  footer: string
  labelColors: string[]
}

const props = defineProps<{ config: DemoConfig }>()

// ===================== API =====================
const api: DemoApi = createDemoApi(props.config.apiBase)

// ===================== 响应式状态 =====================
const serverOnline = ref(false)
const modelInfo = ref<DemoModelInfo | null>(null)
const resultData = ref<DemoPredictResult | null>(null)
const loading = ref(false)
const loadingText = ref('正在运行模型预测...')
const statusMsg = ref('请上传 CSV 文件')
const statusClass = ref('')
const currentFile = ref<File | null>(null)
const activeLabelTab = ref('')
const showDeviceDetail = ref(false)
const detailPredIdx = ref(-1)
const showTuneSection = ref(false)

// 文件输入 ref
const fileInputRef = ref<HTMLInputElement | null>(null)
// 文件名显示
const fileName = ref('')

// ===================== ECharts 实例 =====================
const prfChartRef = ref<HTMLDivElement | null>(null)
const aucChartRef = ref<HTMLDivElement | null>(null)
const cooccurChartRef = ref<HTMLDivElement | null>(null)
const posF1ChartRef = ref<HTMLDivElement | null>(null)
const featImpChartRef = ref<HTMLDivElement | null>(null)
const tuneCompareChartRef = ref<HTMLDivElement | null>(null)

const charts: Record<string, echarts.ECharts | null> = {
  prf: null, auc: null, cooccur: null, posF1: null, featImp: null, tuneCompare: null
}

// ===================== 计算属性 =====================
const labels = computed(() => resultData.value?.label_columns || [])
const cnMap = computed(() => resultData.value?.label_cn_map || {})
const featCnMap = computed(() => resultData.value?.feature_cn_map || {})
const hasMetrics = computed(() => !!resultData.value?.metrics)

const hitPreds = computed(() =>
  resultData.value ? resultData.value.predictions.filter(p => p.pred_label_count > 0) : []
)

const labelCounts = computed(() => {
  const counts: Record<string, number> = {}
  labels.value.forEach(l => { counts[l] = hitPreds.value.filter(p => p.preds[l] === 1).length })
  return counts
})

const sortedLabels = computed(() =>
  [...labels.value].sort((a, b) => (labelCounts.value[b] || 0) - (labelCounts.value[a] || 0))
)

const currentTabHits = computed(() => {
  if (!resultData.value || !activeLabelTab.value) return []
  return hitPreds.value
    .filter(p => p.preds[activeLabelTab.value] === 1)
    .sort((a, b) => (b.probs[activeLabelTab.value] || 0) - (a.probs[activeLabelTab.value] || 0))
})

const detailPred = computed(() => {
  if (!resultData.value || detailPredIdx.value < 0) return null
  return resultData.value.predictions[detailPredIdx.value] || null
})

const sortedAllPredictions = computed(() => {
  if (!resultData.value) return []
  return [...resultData.value.predictions].sort((a, b) => b.pred_label_count - a.pred_label_count)
})

// ===================== 工具函数 =====================
function initCharts() {
  if (prfChartRef.value) charts.prf = echarts.init(prfChartRef.value)
  if (aucChartRef.value) charts.auc = echarts.init(aucChartRef.value)
  if (cooccurChartRef.value) charts.cooccur = echarts.init(cooccurChartRef.value)
  if (posF1ChartRef.value) charts.posF1 = echarts.init(posF1ChartRef.value)
  if (featImpChartRef.value) charts.featImp = echarts.init(featImpChartRef.value)
  // tuneCompareChartRef is not initialized here — it's rendered via v-if, initialized on demand in startGridSearch()
  drawEmptyCharts()
}

function drawEmptyCharts() {
  const emptyOpt = (text: string) => ({
    title: { text, left: 'center', top: 'center', textStyle: { color: 'rgba(255,255,255,0.4)', fontSize: 18 } },
    xAxis: {}, yAxis: {}, series: []
  })
  charts.prf?.setOption(emptyOpt('请上传数据'), true)
  charts.auc?.setOption(emptyOpt('请上传数据'), true)
  charts.cooccur?.setOption(emptyOpt('请上传含标签的数据'), true)
  charts.posF1?.setOption(emptyOpt('请上传含标签的数据'), true)
  charts.featImp?.setOption(emptyOpt('模型信息加载中...'), true)
  // tuneCompare is initialized lazily — skip empty chart
}

// ===================== 服务检查 =====================
async function checkServer() {
  try {
    const info = await api.modelInfo()
    serverOnline.value = true
    modelInfo.value = info
    if (props.config.hasFeatureImportance && info.feature_importance) {
      setTimeout(() => renderFeatImpChartFromModel(info), 100)
    }
  } catch {
    serverOnline.value = false
  }
}

function renderFeatImpChartFromModel(info: DemoModelInfo) {
  const fi = info.feature_importance
  if (!fi || !charts.featImp) return
  const cnMapLocal = info.feature_cn_map || {}
  const fiLabels = Object.keys(fi).slice(0, 6)

  if (fiLabels.length === 0) {
    charts.featImp.setOption({
      title: [{ text: '暂无特征重要性数据', left: 'center', top: 'center', textStyle: { color: 'rgba(255,255,255,0.4)', fontSize: 16 } }],
      xAxis: {}, yAxis: {}, series: []
    }, true)
    return
  }

  const nCols = 3
  const grids: any[] = [], xAxes: any[] = [], yAxes: any[] = [], series: any[] = [], titles: any[] = []
  fiLabels.forEach((label, idx) => {
    const impData = fi[label]
    const top10Imp = impData.importance.slice(0, 10)
    const top10Names = impData.features.slice(0, 10).map((f: string) => cnMapLocal[f] || f)
    const row = Math.floor(idx / nCols), col = idx % nCols
    const cellW = 100 / nCols
    grids.push({ left: `${col * cellW + 1}%`, right: `${(nCols - col - 1) * cellW + 1}%`, top: `${row * 50 + 3}%`, height: '42%' })
    xAxes.push({ type: 'value', max: 1, gridIndex: idx, axisLabel: { fontSize: 8 } })
    yAxes.push({ type: 'category', data: top10Names.reverse(), axisLabel: { fontSize: 10 }, inverse: true, gridIndex: idx })
    series.push({
      type: 'bar', data: top10Imp.reverse().map((v: number) => ({
        value: v, itemStyle: { color: v > 0.1 ? '#2563eb' : v > 0.01 ? '#60a5fa' : '#93c5fd', borderRadius: [0, 4, 4, 0] }
      })), xAxisIndex: idx, yAxisIndex: idx,
      label: { show: true, position: 'right', fontSize: 9, formatter: (p: any) => p.value > 0.001 ? p.value.toFixed(3) : '' }
    })
    titles.push({ text: (info.label_cn_map || {})[label] || label, left: `${col * cellW + cellW / 2 - 5}%`, top: `${row * 50 + 1}%`, textStyle: { fontSize: 12, fontWeight: 'bold' } })
  })
  charts.featImp.setOption({ title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series }, true)
}

// ===================== 上传 & 预测 =====================
async function uploadAndPredict(file: File) {
  currentFile.value = file
  fileName.value = file.name
  loading.value = true
  loadingText.value = '正在运行模型预测...'
  statusMsg.value = '正在上传并预测...'
  statusClass.value = ''
  try {
    const data = await api.predict(file)
    if (data.error) { statusMsg.value = '预测失败: ' + data.error; statusClass.value = 'err'; return }
    showTuneSection.value = false
    resultData.value = data
    if (sortedLabels.value.length > 0) {
      activeLabelTab.value = sortedLabels.value[0]
    }
    nextTick(() => renderAll())
    statusMsg.value = `预测完成 · 共 ${data.n_samples} 条样本`
    statusClass.value = 'ok'
  } catch (e: any) {
    statusMsg.value = '请求失败: ' + e.message
    statusClass.value = 'err'
  } finally {
    loading.value = false
  }
}

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  uploadAndPredict(file)
}

function triggerUpload() {
  fileInputRef.value?.click()
}

// ===================== 导出 CSV =====================
function exportCSV() {
  if (!resultData.value) return
  const headers = ['device_id', 'pred_label_count', 'hit_labels', 'primary_label']
  const rows = resultData.value.predictions.map(p =>
    [p.device_id || '', p.pred_label_count.toString(), (p.pred_labels || []).join(','), p.primary_label].join(',')
  )
  const csv = '\uFEFF' + headers.join(',') + '\n' + rows.join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = props.config.apiBase.includes('terminal') ? 'terminal_predictions.csv' : 'meter_predictions.csv'
  a.click()
}

// ===================== 超参数调优 =====================
async function startGridSearch() {
  if (!currentFile.value) { alert('请先上传包含标签列的 CSV 文件'); return }
  if (!resultData.value?.metrics) { alert('当前数据不含标签列，需要标签才能调优'); return }
  if (!confirm('即将执行超参数网格搜索微调。\n\n期间请勿关闭页面。\n\n确认开始？')) return

  loading.value = true
  loadingText.value = '正在执行超参数网格搜索...'
  statusMsg.value = '超参数调优进行中，请耐心等待...'
  statusClass.value = ''

  try {
    const data = await api.gridsearchTune(currentFile.value)
    const tuneData = data as unknown as DemoTuneResult
    // 更新结果
    resultData.value = data as unknown as DemoPredictResult
    showTuneSection.value = true
    nextTick(() => {
      // 使用 RAF 确保 KeepAlive 激活后 DOM 完全布局
      requestAnimationFrame(() => {
        setTimeout(() => {
          if (tuneCompareChartRef.value) {
            charts.tuneCompare?.dispose()
            charts.tuneCompare = echarts.init(tuneCompareChartRef.value)
          }
          renderAll()
          renderTuneResults(tuneData as any)
          setTimeout(() => { charts.tuneCompare?.resize() }, 150)
        }, 30)
      })
    })
    statusMsg.value = `超参数调优完成! 耗时 ${tuneData.grid_search.time_elapsed_seconds}s`
    statusClass.value = 'ok'
    checkServer()
  } catch (e: any) {
    alert('调优请求失败: ' + e.message)
    statusMsg.value = '调优请求失败: ' + e.message
    statusClass.value = 'err'
  } finally {
    loading.value = false
  }
}

async function resetModel() {
  if (!confirm('确认重置为原始模型？\n\n将丢弃调优结果，恢复使用原始权重。')) return
  try {
    await api.resetModel()
    statusMsg.value = '模型已重置为原始版本'
    statusClass.value = 'ok'
    showTuneSection.value = false
    await checkServer()
    if (currentFile.value) await uploadAndPredict(currentFile.value)
  } catch (e: any) {
    alert('重置请求失败: ' + e.message)
  }
}

// ===================== 选择标签 Tab =====================
function selectLabelTab(label: string) {
  activeLabelTab.value = label
}

// ===================== 设备详情 =====================
function openDeviceDetail(predIdx: number) {
  detailPredIdx.value = predIdx
  showDeviceDetail.value = true
  nextTick(() => {
    document.getElementById('deviceDetailAnchor')?.scrollIntoView({ behavior: 'smooth' })
  })
}

function closeDeviceDetail() {
  showDeviceDetail.value = false
  detailPredIdx.value = -1
}

// ===================== 渲染 =====================
function renderAll() {
  renderPRFChart()
  renderAUCChart()
  if (hasMetrics.value) {
    renderCooccurChart()
    renderPosF1Chart()
  } else {
    charts.cooccur?.setOption({
      title: [{ text: '当前数据无标签列，无法生成共现矩阵', left: 'center', top: 'center', textStyle: { color: 'rgba(255,255,255,0.4)', fontSize: 16 } }],
      xAxis: {}, yAxis: {}, series: []
    }, true)
    charts.posF1?.setOption({
      title: [{ text: '当前数据无标签列，无法评估F1', left: 'center', top: 'center', textStyle: { color: 'rgba(255,255,255,0.4)', fontSize: 16 } }],
      xAxis: {}, yAxis: {}, series: []
    }, true)
  }
  if (props.config.hasFeatureImportance && resultData.value?.feature_importance) {
    const info = resultData.value as unknown as DemoModelInfo
    setTimeout(() => renderFeatImpChartFromModel(info), 100)
  }
}

function setScoreCardClass(val: number | null, isLowBetter = false): string {
  if (val == null) return ''
  if (isLowBetter) return val < 0.02 ? 'good' : val < 0.1 ? 'warn' : 'bad'
  return val >= 0.9 ? 'good' : val >= 0.7 ? 'warn' : 'bad'
}

// ===================== ECharts 渲染函数 =====================
function renderPRFChart() {
  const data = resultData.value!
  const lbls = data.label_columns.map(l => data.label_cn_map[l] || l)
  const m = data.metrics
  const baseOpt: any = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '15%', containLabel: true },
    xAxis: { type: 'category', data: lbls, axisLabel: { rotate: 45, fontSize: 10 } },
    legend: { top: 5 }
  }
  if (!m) {
    const s = data.summary
    const predCounts = data.label_columns.map(l => s.pred_pos_counts?.[data.label_cn_map[l]] || 0)
    charts.prf?.setOption({
      ...baseOpt, yAxis: { type: 'value', name: '预测异常数' },
      series: [{ type: 'bar', data: predCounts, itemStyle: { color: '#f59e0b', borderRadius: [4, 4, 0, 0] }, label: { show: true, position: 'top', fontSize: 10 } }]
    }, true)
    return
  }
  charts.prf?.setOption({
    ...baseOpt, yAxis: { type: 'value', min: 0, max: 1.08, name: '分数' },
    legend: { data: ['Precision', 'Recall', 'F1'], top: 5 },
    series: [
      { name: 'Precision', type: 'bar', data: data.label_columns.map(l => m.per_label[l].precision), itemStyle: { color: '#2563eb' }, label: { show: true, position: 'top', fontSize: 9, formatter: (p: any) => p.value > 0 ? p.value.toFixed(2) : '' } },
      { name: 'Recall', type: 'bar', data: data.label_columns.map(l => m.per_label[l].recall), itemStyle: { color: '#16a34a' }, label: { show: true, position: 'top', fontSize: 9, formatter: (p: any) => p.value > 0 ? p.value.toFixed(2) : '' } },
      { name: 'F1', type: 'bar', data: data.label_columns.map(l => m.per_label[l].f1), itemStyle: { color: '#d97706' }, label: { show: true, position: 'top', fontSize: 9, formatter: (p: any) => p.value > 0 ? p.value.toFixed(2) : '' } }
    ]
  }, true)
}

function renderAUCChart() {
  const data = resultData.value!
  const lbls = data.label_columns.map(l => data.label_cn_map[l] || l)
  const m = data.metrics
  const aucData = data.label_columns.map(l => m ? (m.per_label[l].auc || 0) : 0)
  const colors = aucData.map(v => v >= 0.9 ? '#16a34a' : v >= 0.7 ? '#2563eb' : v > 0 ? '#d97706' : '#94a3b8')
  charts.auc?.setOption({
    tooltip: { trigger: 'axis', formatter: (p: any) => `${p[0].name}<br/>AUC: ${p[0].value.toFixed(4)}` },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: lbls, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value', min: 0, max: 1.05, name: 'AUC-ROC' },
    series: [{
      type: 'bar', data: aucData.map((v, i) => ({ value: v, itemStyle: { color: colors[i], borderRadius: [4, 4, 0, 0] } })),
      label: { show: true, position: 'top', fontSize: 9, formatter: (p: any) => p.value > 0 ? p.value.toFixed(4) : (m ? 'N/A' : '') }
    }]
  }, true)
}

function renderCooccurChart() {
  const data = resultData.value!
  const lbls = data.label_columns.map(l => data.label_cn_map[l] || l)
  const mat = data.cooccurrence_matrix
  const heatData: any[] = []
  for (let i = 0; i < mat.length; i++)
    for (let j = 0; j < mat[i].length; j++)
      heatData.push([j, i, mat[i][j]])
  const maxV = Math.max(...mat.flat()) || 1
  charts.cooccur?.setOption({
    tooltip: { position: 'top', formatter: (p: any) => `${lbls[p.data[1]]} & ${lbls[p.data[0]]}<br/>共现: ${p.data[2]}` },
    grid: { left: '15%', right: '10%', bottom: '10%', top: '5%' },
    xAxis: { type: 'category', data: lbls, axisLabel: { rotate: 45, fontSize: 9 }, position: 'top' },
    yAxis: { type: 'category', data: lbls, axisLabel: { fontSize: 9 }, inverse: true },
    visualMap: { min: 0, max: maxV, calculable: true, orient: 'vertical', right: 0, top: 'center', inRange: { color: ['#fef0d9', '#fdcc8a', '#fc8d59', '#e34a33', '#b30000'] } },
    series: [{ type: 'heatmap', data: heatData, label: { show: true, fontSize: 8, formatter: (p: any) => p.data[2] > 0 ? p.data[2] : '' } }]
  }, true)
}

function renderPosF1Chart() {
  const data = resultData.value!
  const m = data.metrics!
  const lbls = data.label_columns
  const pm = data.pos_counts
  const scatterData = lbls.map((l, i) => [pm[i], m.per_label[l].f1, data.label_cn_map[l] || l, m.per_label[l].auc || 0, pm[i] / data.n_samples])
  charts.posF1?.setOption({
    tooltip: { trigger: 'item', formatter: (p: any) => `${p.data[2]}<br/>正样本: ${p.data[0]}<br/>F1: ${p.data[1].toFixed(4)}<br/>AUC: ${p.data[3].toFixed(4)}` },
    grid: { left: '10%', right: '5%', bottom: '10%', top: '5%' },
    xAxis: { type: 'log', name: '正样本数(log)', nameLocation: 'center', nameGap: 30 },
    yAxis: { type: 'value', name: 'F1', min: -0.05, max: 1.08 },
    series: [{
      type: 'scatter', data: scatterData,
      symbolSize: (d: any) => Math.max((d[3] || 0) * 60, 20),
      itemStyle: {
        color: (d: any) => d[0] === 0 ? '#94a3b8' : d[4] < 0.001 ? '#ef4444' : d[4] < 0.01 ? '#d97706' : d[4] < 0.1 ? '#2563eb' : '#16a34a',
        shadowBlur: 8
      },
      label: { show: true, formatter: (p: any) => p.data[2], position: 'top', fontSize: 10, fontWeight: 'bold' }
    }]
  }, true)
}

function renderTuneResults(data0: any) {
  const gs = data0.grid_search
  if (!gs || !charts.tuneCompare) return

  const lbls = gs.grid_results.map((r: any) => '#' + r.combo_index)
  const macroData = gs.grid_results.map((r: any) => r.val_macro_f1)
  const microData = gs.grid_results.map((r: any) => r.val_micro_f1)
  const bestIdx = gs.best_combo_index - 1
  const macroColors = macroData.map((_: number, i: number) => i === bestIdx ? '#16a34a' : '#5470c6')

  charts.tuneCompare.setOption({
    title: [],
    tooltip: {
      trigger: 'axis',
      formatter: function (params: any) {
        let html = '<b>组合 ' + params[0].name + '</b><br/>'
        params.forEach((p: any) => { html += p.marker + ' ' + p.seriesName + ': ' + p.value.toFixed(4) + '<br/>' })
        const gr = gs.grid_results[params[0].dataIndex]
        html += '参数: ' + Object.entries(gr.params).map(([k, v]) => k + '=' + v).join(', ')
        return html
      }
    },
    legend: { data: ['Macro F1', 'Micro F1'], top: 5 },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '18%', containLabel: true },
    xAxis: { type: 'category', data: lbls, axisLabel: { fontSize: 11, fontWeight: 'bold' }, name: '参数组合编号', nameLocation: 'center', nameGap: 30 },
    yAxis: { type: 'value', min: 0, max: 1.05, name: 'F1 分数' },
    series: [
      {
        name: 'Macro F1', type: 'bar',
        data: macroData.map((v: number, i: number) => ({ value: v, itemStyle: { color: macroColors[i], borderRadius: [4, 4, 0, 0] } })),
        label: { show: true, position: 'top', fontSize: 10, formatter: (p: any) => p.value.toFixed(4) },
        markLine: { silent: true, data: [{ yAxis: gs.original_macro_f1, label: { formatter: '原始: ' + gs.original_macro_f1.toFixed(4) }, lineStyle: { color: '#ef4444', type: 'dashed' } }] }
      },
      {
        name: 'Micro F1', type: 'bar',
        data: microData.map((v: number, i: number) => ({ value: v, itemStyle: { color: i === bestIdx ? '#22c55e' : '#91cc75', borderRadius: [4, 4, 0, 0] } })),
        label: { show: true, position: 'top', fontSize: 10, formatter: (p: any) => p.value.toFixed(4) }
      }
    ]
  }, true)
}

// ===================== 生命周期 =====================
onMounted(async () => {
  await nextTick()
  // 使用 requestAnimationFrame 确保浏览器已完成布局计算，避免 ECharts 初始化时容器尺寸为 0
  requestAnimationFrame(() => {
    setTimeout(() => {
      initCharts()
    }, 50)
  })
  await checkServer()
  if (!serverOnline.value) {
    statusMsg.value = '后端服务未连接'
    statusClass.value = 'err'
  }
})

onBeforeUnmount(() => {
  Object.values(charts).forEach(c => c?.dispose())
})

// KeepAlive 激活时 resize 所有图表（切换 tab 后恢复正确尺寸）
onActivated(() => {
  nextTick(() => {
    requestAnimationFrame(() => {
      Object.values(charts).forEach(c => c?.resize())
    })
  })
})

watch(() => props.config.apiBase, () => {
  Object.values(charts).forEach(c => c?.dispose())
  nextTick(() => { initCharts(); checkServer() })
})
</script>

<template>
  <div class="demo-root" :style="{ '--primary': config.theme.primary, '--primary-dark': config.theme.primaryDark, '--gradient': config.theme.gradient }">
    <!-- Header -->
    <header class="demo-header">
      <div>
        <h1>{{ config.title }}</h1>
        <div class="sub">{{ config.subtitle }}</div>
      </div>
      <div class="server-info">
        <span class="server-dot" :class="serverOnline ? 'on' : 'off'"></span>
        <span>{{ serverOnline ? '服务就绪' : '服务未连接' }}</span>
        <span v-if="modelInfo" class="model-badge" :class="modelInfo.is_tuned ? 'tuned' : 'orig'">
          {{ modelInfo.is_tuned ? '🔧 调优模型' : '📦 原始模型' }}
        </span>
        <button v-if="modelInfo?.is_tuned" class="btn ghost small" @click="resetModel">↺ 重置模型</button>
      </div>
    </header>

    <main class="demo-main">
      <!-- 操作栏 -->
      <div class="toolbar">
        <input ref="fileInputRef" type="file" accept=".csv,.xlsx,.xls" style="display:none" @change="onFileChange" />
        <button class="btn" @click="triggerUpload">📁 选择数据文件</button>
        <button
          class="btn ghost tune-btn"
          :disabled="!hasMetrics"
          :title="hasMetrics ? '基于当前数据执行网格搜索' : '需要上传包含标签列的数据'"
          @click="startGridSearch"
        >🔧 超参数调优{{ hasMetrics ? '' : '（需标签列）' }}</button>
        <button class="btn ghost" :disabled="!resultData" @click="exportCSV">📥 导出结果 CSV</button>
        <span v-if="fileName" class="file-name">{{ fileName }}</span>
        <span class="status" :class="statusClass">{{ statusMsg }}</span>
      </div>

      <!-- 加载遮罩 -->
      <div v-if="loading" class="loading-overlay">
        <div class="spinner"></div>{{ loadingText }}
      </div>

      <!-- 算法流程 -->
      <div class="section-title">算法流程</div>
      <div class="card flow-card">
        <h3>{{ config.flowTitle }}</h3>
        <div class="grid-2" style="margin-top:14px;">
          <div>
            <p class="flow-desc-title">{{ config.flowInputDesc }}</p>
            <ul>
              <li v-for="item in config.flowInputItems" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div>
            <p class="flow-desc-title">{{ config.flowMechDesc }}</p>
            <ul>
              <li v-for="item in config.flowMechItems" :key="item" v-html="item"></li>
            </ul>
          </div>
        </div>
      </div>

      <!-- 数据概览 -->
      <div class="section-title">数据概览</div>
      <div class="grid-4">
        <div class="score-card"><div class="label">总样本数</div><div class="value">{{ resultData?.n_samples ?? '—' }}</div></div>
        <div class="score-card"><div class="label">含异常样本</div><div class="value">{{ resultData ? (resultData.summary.anomaly_samples ?? resultData.summary.pred_anomaly_samples ?? '—') : '—' }}</div></div>
        <div class="score-card"><div class="label">{{ config.nFeaturesLabel }}</div><div class="value">{{ resultData?.n_features ?? config.nFeaturesValue }}</div></div>
        <div class="score-card"><div class="label">异常类型数</div><div class="value">{{ resultData?.n_labels ?? (modelInfo?.n_labels ?? '—') }}</div></div>
      </div>

      <!-- 模型整体性能 -->
      <div class="section-title">模型整体性能 <span class="section-sub">（如数据含标签列则自动计算）</span></div>
      <div class="grid-5">
        <div class="score-card" :class="setScoreCardClass(resultData?.metrics?.micro_f1 ?? null)">
          <div class="label">Micro F1</div><div class="value">{{ resultData?.metrics?.micro_f1?.toFixed(4) ?? '—' }}</div>
          <div class="bar"><div class="bar-inner" :style="{ width: ((resultData?.metrics?.micro_f1 ?? 0) * 100) + '%' }"></div></div>
        </div>
        <div class="score-card" :class="setScoreCardClass(resultData?.metrics?.macro_f1 ?? null)">
          <div class="label">Macro F1</div><div class="value">{{ resultData?.metrics?.macro_f1?.toFixed(4) ?? '—' }}</div>
          <div class="bar"><div class="bar-inner" :style="{ width: ((resultData?.metrics?.macro_f1 ?? 0) * 100) + '%' }"></div></div>
        </div>
        <div class="score-card" :class="setScoreCardClass(resultData?.metrics?.subset_accuracy ?? null)">
          <div class="label">完全匹配率</div><div class="value">{{ resultData?.metrics?.subset_accuracy?.toFixed(4) ?? '—' }}</div>
          <div class="bar"><div class="bar-inner" :style="{ width: ((resultData?.metrics?.subset_accuracy ?? 0) * 100) + '%' }"></div></div>
        </div>
        <div class="score-card" :class="setScoreCardClass(resultData?.metrics?.hamming_loss ?? null, true)">
          <div class="label">汉明损失 ↓</div><div class="value">{{ resultData?.metrics?.hamming_loss?.toFixed(4) ?? '—' }}</div>
          <div class="bar"><div class="bar-inner hamming-bar" :style="{ width: ((resultData?.metrics?.hamming_loss ?? 0) * 100) + '%' }"></div></div>
        </div>
        <div class="score-card" :class="setScoreCardClass(resultData?.metrics?.micro_precision ?? null)">
          <div class="label">Micro Precision</div><div class="value">{{ resultData?.metrics?.micro_precision?.toFixed(4) ?? '—' }}</div>
          <div class="bar"><div class="bar-inner" :style="{ width: ((resultData?.metrics?.micro_precision ?? 0) * 100) + '%' }"></div></div>
        </div>
      </div>
      <div v-if="resultData && !hasMetrics" class="info-box">当前数据不含标签列，仅展示预测结果。如需评估指标，请上传包含标签列的数据。</div>

      <!-- 超参数调优结果 -->
      <template v-if="showTuneSection && resultData">
        <div class="section-title">🔧 超参数调优结果 <span class="section-sub" v-if="(resultData as any).grid_search">
          (耗时 {{ (resultData as any).grid_search.time_elapsed_seconds }}s · {{ (resultData as any).grid_search.n_combos }} 组参数)
        </span></div>
        <div class="grid-4">
          <div class="score-card"><div class="label">调优前 Macro F1</div>
            <div class="value">{{ (resultData as any).grid_search?.original_macro_f1?.toFixed(4) ?? (resultData as any).grid_search?.original_full_metrics?.macro_f1?.toFixed(4) ?? '—' }}</div></div>
          <div class="score-card"><div class="label">调优后 Macro F1</div>
            <div class="value">{{ (resultData as any).grid_search?.tuned_macro_f1?.toFixed(4) ?? '—' }}</div></div>
          <div class="score-card"><div class="label">F1 提升</div>
            <div class="value" :style="{ color: ((resultData as any).grid_search?.improvement ?? 0) > 0 ? '#16a34a' : ((resultData as any).grid_search?.improvement ?? 0) < 0 ? '#ef4444' : '#64748b' }">
              {{ ((resultData as any).grid_search?.improvement ?? 0) >= 0 ? '+' : '' }}{{ (resultData as any).grid_search?.improvement?.toFixed(4) ?? '—' }}</div></div>
          <div class="score-card"><div class="label">最佳参数</div>
            <div class="value" style="font-size:16px;" v-if="(resultData as any).grid_search?.best_params">
              {{ Object.entries((resultData as any).grid_search.best_params).map(([k,v]) => k+'='+v).join(' ') }}</div></div>
        </div>
        <div class="card" style="margin-top:16px;">
          <h3>各参数组合验证集性能对比</h3>
          <div ref="tuneCompareChartRef" class="chart" style="height:420px;min-width:300px;"></div>
        </div>
      </template>

      <!-- 各标签指标表 -->
      <div class="section-title">{{ hasMetrics ? '各标签性能指标（含标签评估）' : '各标签预测统计' }}</div>
      <div class="card table-card">
        <div class="table-wrap">
          <table class="result-table" v-if="resultData">
            <thead><tr><th>异常类型</th><th>标签名</th><th>预测异常数</th><th>F1</th><th>Precision</th><th>Recall</th><th>Balanced Acc</th><th>AUC</th><th>阈值</th></tr></thead>
            <tbody>
              <tr v-for="l in labels" :key="l">
                <td style="text-align:left;font-weight:600;">{{ cnMap[l] }}</td>
                <td style="font-family:monospace;">{{ l }}</td>
                <td>{{ hasMetrics ? (resultData.summary.pos_counts?.[cnMap[l]] ?? 0) : (resultData.summary.pred_pos_counts?.[cnMap[l]] ?? 0) }}</td>
                <td class="score-cell" :class="hasMetrics ? ((resultData.metrics!.per_label[l].f1 >= 0.8 ? 'high' : resultData.metrics!.per_label[l].f1 >= 0.5 ? 'mid' : 'low')) : ''">
                  {{ hasMetrics ? resultData.metrics!.per_label[l].f1.toFixed(4) : '—' }}</td>
                <td>{{ hasMetrics ? resultData.metrics!.per_label[l].precision.toFixed(4) : '—' }}</td>
                <td>{{ hasMetrics ? resultData.metrics!.per_label[l].recall.toFixed(4) : '—' }}</td>
                <td>{{ hasMetrics ? resultData.metrics!.per_label[l].balanced_accuracy.toFixed(4) : '—' }}</td>
                <td>{{ hasMetrics ? (resultData.metrics!.per_label[l].auc?.toFixed(4) ?? 'N/A') : 'N/A' }}</td>
                <td>{{ resultData.thresholds[l]?.toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty-table">请上传数据并运行预测</div>
        </div>
      </div>

      <!-- 可视化分析 -->
      <div class="section-title">可视化分析</div>
      <div class="grid-2">
        <div class="card"><h3>各标签 Precision / Recall / F1</h3><div ref="prfChartRef" class="chart chart-lg"></div></div>
        <div class="card"><h3>各标签 AUC-ROC</h3><div ref="aucChartRef" class="chart chart-lg"></div></div>
      </div>
      <div class="grid-2" style="margin-top:16px;">
        <div class="card"><h3>标签共现热力图</h3><div ref="cooccurChartRef" class="chart chart-lg"></div></div>
        <div class="card"><h3>正样本数 vs F1</h3><div ref="posF1ChartRef" class="chart chart-lg"></div></div>
      </div>
      <div v-if="config.hasFeatureImportance" class="grid-1" style="margin-top:16px;">
        <div class="card"><h3>特征重要性 Top-10（按标签）</h3><div ref="featImpChartRef" class="chart" style="height:500px;"></div></div>
      </div>

      <!-- 异常设备（按标签分类） -->
      <div class="section-title">异常{{ config.apiBase.includes('terminal') ? '终端' : '电表' }}预测结果（按标签分类）</div>
      <div class="card">
        <div class="label-tabs">
          <span
            v-for="l in sortedLabels" :key="l"
            class="label-tab"
            :class="{ active: activeLabelTab === l }"
            @click="selectLabelTab(l)"
          >{{ cnMap[l] }} <span class="count">({{ labelCounts[l] ?? 0 }})</span></span>
        </div>
        <div class="table-head-bar">
          <div v-if="activeLabelTab">【{{ cnMap[activeLabelTab] }}】命中列表</div>
          <div v-else>请先选择标签</div>
          <div>共 {{ currentTabHits.length }} 条</div>
        </div>
        <div class="table-wrap">
          <table class="result-table" v-if="currentTabHits.length > 0">
            <thead>
              <tr>
                <th>{{ config.apiBase.includes('terminal') ? '终端 ID' : '电表 ID' }}</th>
                <th>判定概率</th>
                <th>命中异常标签</th>
                <th v-for="col in config.anomalyTableCols" :key="col.key">{{ col.label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in currentTabHits.slice(0, 200)" :key="p.index">
                <td><b>{{ p.device_id || ('#' + p.index) }}</b></td>
                <td><span class="tag" :class="p.probs[activeLabelTab] >= 0.8 ? 'bad' : p.probs[activeLabelTab] >= 0.5 ? 'warn' : 'good'">{{ p.probs[activeLabelTab]?.toFixed(4) }}</span></td>
                <td style="text-align:left;font-size:13px;max-width:200px;">{{ p.pred_labels.map((l: string) => cnMap[l] || l).join(', ') }}</td>
                <td v-for="col in config.anomalyTableCols" :key="col.key">{{ p.features[col.key] ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty-table" style="padding:30px;">{{ activeLabelTab ? '该标签无命中异常设备' : '请先选择标签' }}</div>
        </div>
      </div>

      <!-- 全部预测结果 -->
      <div class="section-title">全部预测结果</div>
      <div class="card table-card">
        <div class="table-head-bar">
          <div>所有设备预测概览</div>
          <div>共 {{ resultData?.predictions.length ?? 0 }} 条 · 命中异常 {{ hitPreds.length }} 条</div>
        </div>
        <div class="table-wrap">
          <table class="result-table" v-if="resultData">
            <thead><tr><th>{{ config.apiBase.includes('terminal') ? '终端 ID' : '电表 ID' }}</th><th>异常数</th><th>命中异常标签</th><th>主要异常</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="p in sortedAllPredictions.slice(0, 100)" :key="p.index">
                <td>{{ p.device_id || ('#' + p.index) }}</td>
                <td><span class="tag" :class="p.pred_label_count > 0 ? 'bad' : 'good'">{{ p.pred_label_count }}</span></td>
                <td style="text-align:left;font-size:13px;max-width:250px;">{{ p.pred_labels.map((l: string) => cnMap[l] || l).join(', ') || '无' }}</td>
                <td style="font-weight:600;">{{ cnMap[p.primary_label || ''] || p.primary_label || '—' }}</td>
                <td><span class="clickable" @click="openDeviceDetail(p.index)">查看详情</span></td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty-table">请上传数据并运行预测</div>
        </div>
      </div>

      <!-- 设备详情 -->
      <template v-if="showDeviceDetail && detailPred">
        <div class="section-title" id="deviceDetailAnchor">设备异常预测详情</div>
        <div class="card">
          <div class="table-head-bar">
            <div>设备 <b>{{ detailPred.device_id || ('#' + detailPred.index) }}</b> · 命中 <b>{{ detailPred.pred_label_count }}</b> 类异常</div>
            <button class="btn ghost small" @click="closeDeviceDetail">✕ 关闭</button>
          </div>
          <div class="grid-2" style="margin-top:12px;">
            <div>
              <h3 style="margin-top:0;">关键特征</h3>
              <table class="result-table">
                <thead><tr><th>特征</th><th>中文名</th><th>数值</th></tr></thead>
                <tbody>
                  <tr v-for="k in config.detailFeatureKeys" :key="k">
                    <td style="font-family:monospace;">{{ k }}</td>
                    <td>{{ featCnMap[k] || k }}</td>
                    <td>{{ detailPred.features[k] ?? '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div>
              <h3 style="margin-top:0;">{{ labels.length }}类异常判定详情</h3>
              <table class="result-table">
                <thead><tr><th>异常类型</th><th>预测概率</th><th>阈值</th><th>判定结果</th></tr></thead>
                <tbody>
                  <tr v-for="l in labels" :key="l">
                    <td style="text-align:left;font-weight:600;">{{ cnMap[l] }}</td>
                    <td>
                      <div class="prob-bar-wrap">
                        <div class="prob-bar-bg">
                          <div class="prob-bar-fill"
                            :style="{
                              width: Math.round(detailPred.probs[l] * 100) + '%',
                              background: detailPred.preds[l] === 1 ? '#ef4444' : detailPred.probs[l] > 0.3 ? '#f59e0b' : '#60a5fa'
                            }"></div>
                        </div>
                        <span class="prob-val">{{ detailPred.probs[l].toFixed(4) }}</span>
                      </div>
                    </td>
                    <td>{{ (resultData!.thresholds[l] ?? 0.5).toFixed(2) }}</td>
                    <td><span class="tag" :class="detailPred.preds[l] === 1 ? 'bad' : 'good'">{{ detailPred.preds[l] === 1 ? '⚠ 异常' : '✓ 正常' }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </template>
    </main>

    <footer class="demo-footer">{{ config.footer }}</footer>
  </div>
</template>

<style scoped>
/* ========== CSS 变量 & 基础 ========== */
.demo-root {
  --bg: transparent;
  --card: rgba(17, 24, 39, 0.6);
  --border: rgba(0, 212, 255, 0.15);
  --text: #e4e7ed;
  --muted: rgba(255, 255, 255, 0.5);
  --good: #22c55e;
  --warn: #f59e0b;
  --bad: #ef4444;
  --shadow: 0 4px 20px rgba(0, 212, 255, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  --radius: 12px;
  background: var(--bg);
  color: var(--text);
  font-size: 15px;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  min-height: 100%;
}
* { box-sizing: border-box; }

/* Header */
.demo-header {
  padding: 24px 32px;
  background: var(--gradient);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: var(--shadow);
  flex-wrap: wrap;
  gap: 8px;
}
.demo-header h1 { margin: 0; font-size: 28px; letter-spacing: 1px; font-weight: 600; }
.sub { font-size: 15px; opacity: .9; }
.server-info { display: flex; align-items: center; gap: 4px; font-size: 15px; }
.server-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
.server-dot.on { background: #4ade80; box-shadow: 0 0 6px #4ade80; }
.server-dot.off { background: #f87171; box-shadow: 0 0 6px #f87171; }
.model-badge { margin-left: 12px; padding: 3px 12px; border-radius: 12px; font-size: 13px; font-weight: 600; }
.model-badge.orig { background: rgba(0, 212, 255, 0.12); color: #00d4ff; }
.model-badge.tuned { background: rgba(34, 197, 94, 0.12); color: #22c55e; }

/* Main */
.demo-main { padding: 24px 32px 48px; max-width: 1480px; margin: 0 auto; }

/* Toolbar */
.toolbar {
  display: flex; flex-wrap: wrap; gap: 14px; align-items: center;
  background: var(--card); padding: 16px 20px; border-radius: var(--radius);
  box-shadow: var(--shadow); margin-bottom: 24px;
}
.file-name { font-size: 14px; color: var(--good); }
.status { font-size: 14px; color: var(--muted); margin-left: auto; }
.status.ok { color: var(--good); }
.status.err { color: var(--bad); }

/* Buttons */
.btn {
  display: inline-flex; align-items: center; gap: 6px; padding: 10px 20px;
  border-radius: 8px; border: none; cursor: pointer;
  background: var(--primary); color: #fff; font-size: 15px; font-weight: 500;
  transition: all .15s; white-space: nowrap;
}
.btn:hover { background: var(--primary-dark); }
.btn.ghost { background: rgba(0, 212, 255, 0.1); color: #00d4ff; border: 1px solid rgba(0, 212, 255, 0.2); }
.btn.ghost:hover { background: rgba(0, 212, 255, 0.2); }
.btn.tune-btn { background: rgba(255, 170, 0, 0.12); color: #ffaa00; border: 1px solid rgba(255, 170, 0, 0.3); }
.btn.tune-btn:hover { background: rgba(255, 170, 0, 0.22); }
.btn:disabled { background: rgba(255, 255, 255, 0.08); color: rgba(255, 255, 255, 0.3); cursor: not-allowed; }
.btn.small { padding: 4px 12px; font-size: 13px; }

/* Grid */
.grid-1 { display: grid; gap: 18px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
.grid-5 { display: grid; grid-template-columns: repeat(5, 1fr); gap: 18px; }
@media (max-width: 980px) { .grid-2,.grid-4,.grid-5 { grid-template-columns: 1fr; } }

/* Cards */
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 22px 24px; box-shadow: var(--shadow);
}
.card h3 { margin: 0 0 12px; font-size: 18px; color: var(--text); display: flex; align-items: center; gap: 10px; }
.card h3::before { content: ""; width: 5px; height: 18px; background: var(--primary); border-radius: 2px; display: inline-block; }
.card p { margin: 8px 0; font-size: 15px; color: var(--muted); line-height: 1.8; }
.card ul { margin: 8px 0 0 22px; padding: 0; font-size: 15px; color: var(--muted); line-height: 1.9; }
.flow-card { padding: 22px 28px; }
.flow-card h3 { font-size: 20px; margin-bottom: 14px; }
.flow-desc-title { font-weight: 600; color: var(--text) !important; }

/* Section */
.section-title {
  margin: 32px 0 14px; font-size: 19px; font-weight: 600; color: var(--text);
  display: flex; align-items: center; gap: 10px;
}
.section-title::before { content: ""; width: 6px; height: 20px; background: var(--primary); border-radius: 3px; }
.section-sub { font-size: 14px; color: var(--muted); font-weight: 400; }

/* Score Card */
.score-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow);
  text-align: center; position: relative; overflow: hidden;
}
.score-card .label { font-size: 15px; color: var(--muted); margin-bottom: 10px; }
.score-card .value {
  font-size: 44px; font-weight: 700;
  font-family: "SF Mono", Menlo, monospace; color: var(--text); line-height: 1;
}
.score-card.good .value { color: var(--good); }
.score-card.warn .value { color: var(--warn); }
.score-card.bad .value { color: var(--bad); }
.bar { height: 6px; border-radius: 3px; background: rgba(0, 212, 255, 0.1); margin-top: 14px; overflow: hidden; }
.bar-inner { height: 100%; background: linear-gradient(90deg, #22c55e, var(--primary)); border-radius: 3px; transition: width .6s; }
.hamming-bar { background: linear-gradient(90deg, #ef4444, #22c55e) !important; }

/* Charts */
.chart { height: 320px; width: 100%; min-width: 300px; }
.chart-lg { height: 400px; min-width: 300px; }

/* Tables */
.table-card { padding: 0; overflow: hidden; }
.table-wrap { max-height: 560px; overflow: auto; }
.table-wrap > :first-child { max-height: none; }
.table-head-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 18px; border-bottom: 1px solid var(--border);
}
.result-table { width: 100%; border-collapse: collapse; font-size: 15px; }
.result-table th, .result-table td { padding: 12px 10px; text-align: center; border-bottom: 1px solid var(--border); }
.result-table thead th { background: rgba(0, 212, 255, 0.08); color: #00d4ff; font-weight: 600; position: sticky; top: 0; font-size: 15px; }
.result-table tr:hover { background: rgba(0, 212, 255, 0.05); }
.empty-table { text-align: center; padding: 40px; color: var(--muted); }

.tag { display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 13px; }
.tag.good { background: rgba(34, 197, 94, 0.15); color: var(--good); font-weight: 600; }
.tag.warn { background: rgba(245, 158, 11, 0.15); color: #f59e0b; font-weight: 600; }
.tag.bad { background: rgba(239, 68, 68, 0.15); color: var(--bad); font-weight: 600; }
.score-cell { font-family: "SF Mono", Menlo, monospace; font-weight: 600; }
.score-cell.high { color: var(--good); }
.score-cell.mid { color: var(--warn); }
.score-cell.low { color: var(--bad); }
.clickable { color: var(--primary); cursor: pointer; text-decoration: underline; }
.clickable:hover { color: var(--primary-dark); }

/* Label Tabs */
.label-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; padding: 0 18px; padding-top: 14px; }
.label-tab {
  padding: 6px 16px; border-radius: 20px; border: 1px solid var(--border);
  cursor: pointer; font-size: 14px; transition: all .15s; background: rgba(255, 255, 255, 0.05); color: var(--muted);
}
.label-tab:hover { border-color: var(--primary); color: var(--primary); }
.label-tab.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.label-tab .count { font-size: 12px; margin-left: 4px; opacity: .8; }

/* Loading */
.loading-overlay {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(10, 14, 26, 0.85); display: flex; align-items: center; justify-content: center;
  z-index: 999; font-size: 20px; color: var(--text);
}
.spinner {
  width: 40px; height: 40px; border: 4px solid rgba(255, 255, 255, 0.1);
  border-top-color: var(--primary); border-radius: 50%;
  animation: spin .8s linear infinite; margin-right: 12px;
}
@keyframes spin { to { transform: rotate(360deg) } }

/* Info box */
.info-box {
  background: rgba(0, 212, 255, 0.08); border: 1px solid rgba(0, 212, 255, 0.25); border-radius: 8px;
  padding: 12px 16px; font-size: 14px; color: #00d4ff;
  display: flex; align-items: center; gap: 8px; margin: 8px 0;
}
.info-box::before { content: "ℹ"; font-size: 18px; flex-shrink: 0; }

/* Prob bar */
.prob-bar-wrap { display: flex; align-items: center; gap: 8px; }
.prob-bar-bg { flex: 1; height: 8px; background: rgba(255, 255, 255, 0.08); border-radius: 4px; overflow: hidden; }
.prob-bar-fill { height: 100%; border-radius: 4px; transition: width .3s; }
.prob-val { font-family: monospace; font-weight: 600; font-size: 14px; min-width: 60px; }

/* Footer */
.demo-footer { text-align: center; color: var(--muted); font-size: 13px; padding: 24px; }
</style>