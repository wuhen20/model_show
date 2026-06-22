<script setup lang="ts">
import { nextTick, onMounted, onBeforeUnmount, ref } from 'vue'
import * as echarts from 'echarts'

const serverOnline = ref(false)
const loading = ref(false)
const loadingText = ref('')
const statusMsg = ref('')
const statusClass = ref('')
const modelType = ref<'default' | 'trained'>('default')
const hasTrainedModel = ref(false)

// 训练
const trainFileRef = ref<HTMLInputElement | null>(null)
const trainDataInfo = ref<any>(null)
const trainStatus = ref<any>(null)
const trainMetrics = ref<any>(null)
const trainParams = ref({ n_trials: 10 })
let trainPollTimer: any = null

// 预测
const predictFileRef = ref<HTMLInputElement | null>(null)
const predictResult = ref<any>(null)

// 特征重要性
const featureImportance = ref<any[]>([])
const evalData = ref<any[]>([])

// 图表 refs
const pieChartRef = ref<HTMLDivElement | null>(null)
const barChartRef = ref<HTMLDivElement | null>(null)
const trainCurveRef = ref<HTMLDivElement | null>(null)
const featImpChartRef = ref<HTMLDivElement | null>(null)
const charts: Record<string, echarts.ECharts | null> = { pie: null, bar: null, trainCurve: null, featImp: null }

const BASE = '/api/demo/station-health'
const TARGET_NAMES = ['正常', '通信前置异常', '采集前置异常', '消息队列异常', '数据路由异常', '数据校核异常', '调控管理异常', '数据库异常']
const CLASS_COLORS = ['#22c55e', '#ef4444', '#f97316', '#eab308', '#a855f7', '#06b6d4', '#3b82f6', '#ec4899']

const modelInfos = [
  { name: 'XGBoost', type: '基模型', desc: '梯度提升集成模型，内置正则化与早停，Optuna 10轮+5折CV搜索', color: '#06b6d4' },
  { name: 'RandomForest', type: '基模型', desc: 'Bagging集成，与XGBoost形成互补，Optuna 10轮+5折CV搜索', color: '#8b5cf6' },
  { name: '1D-CNN', type: '基模型', desc: '一维卷积神经网络，学习特征局部关联，EarlyStopping+ReduceLROnPlateau', color: '#f59e0b' },
]

function showLoading(msg: string) { loading.value = true; loadingText.value = msg }
function hideLoading() { loading.value = false }
function setStatus(msg: string, cls: string = '') { statusMsg.value = msg; statusClass.value = cls }

async function checkServer() {
  try { const r = await fetch(`${BASE}/ping`); if (r.ok) { serverOnline.value = true; await loadData() } } catch { serverOnline.value = false }
}
async function loadData() {
  try { const r = await fetch(`${BASE}/model_info`); const d = await r.json(); hasTrainedModel.value = d.has_trained_model } catch {}
  try { const r = await fetch(`${BASE}/feature_importance`); const d = await r.json(); featureImportance.value = d.data || [] } catch {}
  try { const r = await fetch(`${BASE}/evaluate`); const d = await r.json(); if (d.status === 'ok') evalData.value = d.evaluations } catch {}
}

// 训练
function triggerTrainUpload() { trainFileRef.value?.click() }
async function onTrainFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]; if (!file) return
  showLoading('上传训练数据...')
  try {
    const form = new FormData(); form.append('file', file)
    const r = await fetch(`${BASE}/upload_train`, { method: 'POST', body: form })
    trainDataInfo.value = await r.json()
    setStatus(trainDataInfo.value.message, 'ok')
  } catch (e: any) { setStatus('上传失败: ' + e.message, 'err') }
  finally { hideLoading() }
}
async function startTrain() {
  showLoading('正在训练...')
  try {
    const form = new FormData(); form.append('n_trials', String(trainParams.value.n_trials))
    const r = await fetch(`${BASE}/train`, { method: 'POST', body: form })
    const d = await r.json()
    if (d.status === 'ok') { setStatus('训练已启动', 'ok'); pollTrainStatus() }
    else setStatus(d.message, 'err')
  } catch (e: any) { setStatus('训练失败: ' + e.message, 'err') }
  finally { hideLoading() }
}
function pollTrainStatus() {
  trainPollTimer = setInterval(async () => {
    try { const r = await fetch(`${BASE}/train_status`); trainStatus.value = await r.json()
      if (!trainStatus.value.running) { clearInterval(trainPollTimer!); trainMetrics.value = trainStatus.value.metrics; hasTrainedModel.value = true; setStatus(trainStatus.value.message, 'ok'); nextTick(() => { renderTrainCurveChart(); renderEvalBarChart() }) }
    } catch {}
  }, 2000)
}
function renderTrainCurveChart() {
  if (!trainCurveRef.value || !trainMetrics.value?.training_metrics) return
  if (charts.trainCurve) charts.trainCurve.dispose()
  charts.trainCurve = echarts.init(trainCurveRef.value)
  const tm = trainMetrics.value.training_metrics
  const series: any[] = []
  const colors = ['#06b6d4', '#8b5cf6', '#f59e0b']
  let idx = 0
  for (const [name, metrics] of Object.entries(tm)) {
    const m = metrics as any
    if (m.val_acc?.length) {
      series.push({ name: `${name.toUpperCase()} Train`, type: 'line', data: m.train_acc, lineStyle: { color: colors[idx], width: 2 }, symbol: 'none', smooth: true })
      series.push({ name: `${name.toUpperCase()} Val`, type: 'line', data: m.val_acc, lineStyle: { color: colors[idx], width: 2, type: 'dashed' }, symbol: 'none', smooth: true })
      idx++
    }
  }
  if (series.length === 0) return
  charts.trainCurve.setOption({
    tooltip: { trigger: 'axis' }, legend: { bottom: 0, textStyle: { color: '#9ca3af', fontSize: 10 } },
    xAxis: { type: 'category', name: 'Epoch', nameTextStyle: { color: '#9ca3af' }, axisLabel: { color: '#9ca3af' } },
    yAxis: { type: 'value', name: 'Accuracy', nameTextStyle: { color: '#9ca3af' } },
    series, grid: { left: '3%', right: '4%', bottom: '18%', top: '5%', containLabel: true },
  })
}
function renderEvalBarChart() {
  if (!barChartRef.value) return
  if (charts.bar) charts.bar.dispose()
  charts.bar = echarts.init(barChartRef.value)
  const data = trainMetrics.value?.results || evalData.value
  if (!data || data.length === 0) return
  const names = Object.keys(data).map(k => data[k].modelName || k)
  const accs = Object.values(data).map((v: any) => v.accuracy || 0)
  const f1s = Object.values(data).map((v: any) => v.f1_score || v.f1 || 0)
  charts.bar.setOption({
    tooltip: { trigger: 'axis' }, legend: { data: ['ACC', 'F1'], bottom: 0, textStyle: { color: '#9ca3af' } },
    xAxis: { type: 'category', data: names, axisLabel: { color: '#9ca3af', fontSize: 11 } },
    yAxis: { type: 'value', min: 0, max: 1, name: '分数', nameTextStyle: { color: '#9ca3af' } },
    series: [
      { name: 'ACC', type: 'bar', data: accs, itemStyle: { color: '#06b6d4', borderRadius: [4, 4, 0, 0] }, label: { show: true, position: 'top', fontSize: 10, color: '#e4e7ed', formatter: (p: any) => (p.value * 100).toFixed(1) + '%' } },
      { name: 'F1', type: 'bar', data: f1s, itemStyle: { color: '#8b5cf6', borderRadius: [4, 4, 0, 0] }, label: { show: true, position: 'top', fontSize: 10, color: '#e4e7ed', formatter: (p: any) => p.value.toFixed(4) } },
    ],
  })
}
async function resetModel() {
  if (!confirm('确认重置为默认模型？')) return
  await fetch(`${BASE}/reset_model`, { method: 'POST' })
  hasTrainedModel.value = false; modelType.value = 'default'; trainMetrics.value = null; trainStatus.value = null
  setStatus('已重置为默认模型', 'ok')
  nextTick(() => renderEvalBarChart())
}
function switchModel(type: 'default' | 'trained') { modelType.value = type }

// 预测
function triggerPredict() { predictFileRef.value?.click() }
async function onPredictFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]; if (!file) return
  showLoading('正在预测...')
  try {
    const form = new FormData(); form.append('file', file)
    const r = await fetch(`${BASE}/predict?model_type=${modelType.value}`, { method: 'POST', body: form })
    predictResult.value = await r.json()
    if (predictResult.value.status === 'error') { setStatus(predictResult.value.message, 'err'); return }
    setStatus(`预测完成: ${predictResult.value.n_samples} 条`, 'ok')
    nextTick(() => renderPieChart())
  } catch (e: any) { setStatus('预测失败: ' + e.message, 'err') }
  finally { hideLoading() }
}
function renderPieChart() {
  if (!pieChartRef.value || !predictResult.value?.predictions) return
  if (charts.pie) charts.pie.dispose()
  charts.pie = echarts.init(pieChartRef.value)
  const counts: Record<string, number> = {}
  predictResult.value.predictions.forEach((p: any) => { const n = p.stacking_prediction; counts[n] = (counts[n] || 0) + 1 })
  charts.pie.setOption({
    tooltip: { trigger: 'item' }, legend: { bottom: 0, textStyle: { color: '#9ca3af' } },
    series: [{ type: 'pie', radius: ['40%', '70%'], data: Object.entries(counts).map(([k, v], i) => ({ name: k, value: v, itemStyle: { color: CLASS_COLORS[i] || '#6b7280' } })), label: { color: '#e4e7ed' } }]
  })
}

onMounted(async () => { await checkServer(); nextTick(() => { renderEvalBarChart(); renderFeatImpChart() }) })
onBeforeUnmount(() => { if (trainPollTimer) clearInterval(trainPollTimer); Object.values(charts).forEach(c => c?.dispose()) })

function renderFeatImpChart() {
  if (!featImpChartRef.value || !featureImportance.value.length) return
  if (charts.featImp) charts.featImp.dispose()
  charts.featImp = echarts.init(featImpChartRef.value)
  const sorted = [...featureImportance.value].sort((a, b) => b.importance - a.importance)
  const top20 = sorted.slice(0, 20)
  charts.featImp.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', name: '重要性', nameTextStyle: { color: '#9ca3af' }, axisLabel: { color: '#9ca3af' } },
    yAxis: { type: 'category', data: top20.map(d => d.feature).reverse(), axisLabel: { color: '#9ca3af', fontSize: 10 }, inverse: true },
    series: [{ type: 'bar', data: top20.map(d => d.importance).reverse(), itemStyle: { color: '#3b82f6', borderRadius: [0, 4, 4, 0] }, label: { show: true, position: 'right', fontSize: 10, color: '#e4e7ed', formatter: (p: any) => p.value.toFixed(4) } }],
    grid: { left: '3%', right: '10%', bottom: '5%', top: '5%', containLabel: true },
  })
}
</script>

<template>
  <div class="sh-root">
    <header class="sh-header"><div><h1>主站异常研判系统</h1><div class="sub">XGBoost + RandomForest + 1D-CNN Stacking 集成 · 8 分类异常识别</div></div><div class="server-info"><span class="server-dot" :class="serverOnline ? 'on' : 'off'"></span><span>{{ serverOnline ? '服务就绪' : '服务未连接' }}</span></div></header>
    <main class="sh-main">
      <div v-if="loading" class="loading-overlay"><div class="spinner"></div>{{ loadingText }}</div>

      <!-- 模型状态栏 -->
      <div class="card model-bar">
        <div class="toolbar">
          <span class="model-badge" :class="modelType === 'default' ? 'badge-default' : 'badge-trained'">{{ modelType === 'default' ? '默认模型' : '训练后模型' }}</span>
          <div class="toggle-wrap" :class="{ disabled: !hasTrainedModel }">
            <span class="toggle-label" :class="{ active: modelType === 'default' }" @click="switchModel('default')">默认模型</span>
            <div class="toggle-track" @click="hasTrainedModel && switchModel(modelType === 'default' ? 'trained' : 'default')">
              <div class="toggle-thumb" :class="{ right: modelType === 'trained' }"></div>
            </div>
            <span class="toggle-label" :class="{ active: modelType === 'trained', dim: !hasTrainedModel }" @click="hasTrainedModel && switchModel('trained')">训练后模型</span>
          </div>
          <button v-if="hasTrainedModel" class="btn ghost small" @click="resetModel">重置模型</button>
          <span class="status" :class="statusClass">{{ statusMsg }}</span>
        </div>
      </div>

      <!-- 1. 数据上传 -->
      <div class="section-title">1. 数据上传</div>
      <div class="card">
        <div class="toolbar">
          <input ref="trainFileRef" type="file" accept=".csv" style="display:none" @change="onTrainFileChange" />
          <button class="btn" @click="triggerTrainUpload">上传训练 CSV</button>
          <a :href="`${BASE}/demo_csv`" class="btn ghost">下载演示数据</a>
        </div>
        <div v-if="trainDataInfo" class="grid-4" style="margin-top:14px;">
          <div class="score-card"><div class="label">样本数</div><div class="value">{{ trainDataInfo.rows }}</div></div>
          <div class="score-card"><div class="label">特征数</div><div class="value">{{ trainDataInfo.features }}</div></div>
          <div class="score-card"><div class="label">类别数</div><div class="value">{{ trainDataInfo.class_distribution?.length }}</div></div>
          <div class="score-card"><div class="label">状态</div><div class="value" style="font-size:16px;">{{ trainStatus?.running ? '训练中...' : (trainMetrics ? '完成' : '待训练') }}</div></div>
        </div>
        <div v-if="trainStatus?.running" class="progress-bar" style="margin-top:12px;"><div class="progress-fill" :style="{ width: trainStatus.progress + '%' }"></div><span class="progress-text">{{ trainStatus.message }} ({{ trainStatus.progress }}%)</span></div>
        <div v-if="trainMetrics" style="margin-top:16px;"><h3>训练指标曲线</h3><div ref="trainCurveRef" class="chart" style="height:350px;"></div>
          <div class="grid-4" style="margin-top:12px;"><div v-for="(val, key) in trainMetrics.results" :key="key" class="score-card"><div class="label">{{ key.toUpperCase() }}</div><div class="value" style="font-size:24px;">ACC: {{ (val.accuracy * 100).toFixed(1) }}%</div><div class="sub-text">F1: {{ (val.f1_score || val.f1).toFixed(4) }}</div></div></div>
        </div>
      </div>

      <!-- 2. 数据抽取 -->
      <div class="section-title">2. 数据抽取</div>
      <div class="card"><div class="grid-4"><div class="score-card"><div class="label">总样本数</div><div class="value">12,580</div></div><div class="score-card"><div class="label">特征维度</div><div class="value">66</div></div><div class="score-card"><div class="label">异常类别</div><div class="value">8</div></div><div class="score-card"><div class="label">集成策略</div><div class="value" style="font-size:18px;">Stacking</div></div></div></div>

      <!-- 3. 特征构建 -->
      <div class="section-title">3. 特征构建</div>
      <div class="card">
        <p class="desc">基于 XGBoost 特征重要性排序，删除 20 个低重要性特征，保留 46 个高重要性特征用于模型训练。</p>
        <div class="grid-2" style="margin-top:14px;">
          <div>
            <h3>Top 20 特征重要性</h3>
            <div ref="featImpChartRef" class="chart" style="height:500px;"></div>
          </div>
          <div>
            <h3>已删除特征（低重要性）</h3>
            <div class="table-wrap">
              <table class="result-table">
                <thead><tr><th>特征名</th><th>重要性</th></tr></thead>
                <tbody>
                  <tr v-for="f in [...featureImportance].sort((a,b)=>a.importance-b.importance).slice(0,20)" :key="f.feature">
                    <td style="text-align:left;font-size:13px;">{{ f.feature }}</td>
                    <td style="color:#ef4444;">{{ f.importance.toFixed(6) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- 4. 模型选择 -->
      <div class="section-title">4. 模型选择</div>
      <div class="card"><div class="grid-3"><div v-for="m in modelInfos" :key="m.name" class="model-card" :style="{ borderColor: m.color + '40' }"><h3 :style="{ color: m.color }">{{ m.name }}</h3><span class="model-type" :style="{ background: m.color + '20', color: m.color }">{{ m.type }}</span><p class="model-desc">{{ m.desc }}</p></div></div></div>

      <!-- 5. 训练调参 -->
      <div class="section-title">5. 训练调参</div>
      <div class="card">
        <p class="desc">XGBoost 和 RandomForest 使用 Optuna 超参数搜索（MedianPruner 剪枝），1D-CNN 使用 EarlyStopping + ReduceLROnPlateau。</p>
        <div class="grid-4" style="margin-top:14px;">
          <div><label class="form-label">Optuna 搜索轮数</label><input type="number" class="form-input" v-model.number="trainParams.n_trials" min="2" max="50" /></div>
          <div><label class="form-label">交叉验证折数</label><select class="form-select" disabled><option :value="5">5 折</option></select><span class="form-hint">（固定 5 折）</span></div>
          <div><label class="form-label">XGBoost 搜索范围</label><span class="form-hint">max_depth: 3-9, lr: 1e-3~1e-1, n_est: 50-500</span></div>
          <div><label class="form-label">RF 搜索范围</label><span class="form-hint">n_est: 100-800, max_depth: 3-15</span></div>
        </div>
        <div style="margin-top:14px;">
          <button class="btn tune-btn" :disabled="!trainDataInfo" @click="startTrain" style="font-size:16px;padding:12px 24px;">开始训练</button>
        </div>
      </div>

      <!-- 6. 评测验证与预测比对 -->
      <div class="section-title">6. 评测验证与预测比对</div>
      <div class="card">
        <div class="toolbar"><input ref="predictFileRef" type="file" accept=".csv" style="display:none" @change="onPredictFileChange" /><button class="btn" @click="triggerPredict">上传数据预测</button><a :href="`${BASE}/test_csv`" class="btn ghost">下载测试数据</a></div>
        <p class="desc" style="margin-top:12px;">{{ trainMetrics ? '训练后模型测试集指标' : '默认模型在测试集上的评测指标' }}</p>
        <div class="grid-2" style="margin-top:12px;">
          <div><h3>评测指标</h3><div ref="barChartRef" class="chart" style="height:320px;"></div></div>
          <div v-if="predictResult?.predictions"><h3>预测分布</h3><div ref="pieChartRef" class="chart" style="height:320px;"></div></div>
        </div>
        <div v-if="evalData.length" class="table-wrap" style="margin-top:12px;">
          <table class="result-table">
            <thead><tr><th>模型</th><th>Accuracy</th><th>F1 Score</th></tr></thead>
            <tbody><tr v-for="e in evalData" :key="e.modelName"><td style="font-weight:600;">{{ e.modelName }}</td><td style="color:#22c55e;">{{ (e.accuracy * 100).toFixed(1) }}%</td><td>{{ e.f1.toFixed(4) }}</td></tr></tbody>
          </table>
        </div>
        <div v-if="predictResult?.predictions" style="margin-top:16px;"><h3>预测样例</h3><div class="grid-3"><div v-for="(p, i) in predictResult.predictions.slice(0, 3)" :key="i" class="pred-card"><div class="pred-label" :class="p.stacking_prediction === '正常' ? 'normal' : 'abnormal'">{{ p.stacking_prediction }}</div><div class="pred-conf">置信度: {{ (p.confidence * 100).toFixed(1) }}%</div><div class="prob-bars"><div v-for="(prob, label) in p.probabilities" :key="label" class="prob-row"><span class="prob-name">{{ label }}</span><div class="prob-bar-bg"><div class="prob-bar-fill" :style="{ width: (prob * 100) + '%' }"></div></div><span class="prob-val">{{ (prob * 100).toFixed(1) }}%</span></div></div></div></div></div>
        <div v-else-if="predictResult" class="desc" style="margin-top:12px;">预测失败: {{ predictResult.message || '未知错误' }}</div>
      </div>
    </main>
    <footer class="sh-footer">主站异常研判系统 · XGBoost + RF + 1D-CNN · Stacking 集成</footer>
  </div>
</template>

<style scoped>
.sh-root { --bg: transparent; --card: rgba(17,24,39,0.6); --border: rgba(0,212,255,0.15); --text: #e4e7ed; --muted: rgba(255,255,255,0.5); --primary: #3b82f6; --good: #22c55e; --warn: #f59e0b; --bad: #ef4444; --radius: 12px; --shadow: 0 4px 20px rgba(59,130,246,0.1); background: var(--bg); color: var(--text); font-size: 15px; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; min-height: 100%; }
* { box-sizing: border-box; }
.sh-header { padding: 24px 32px; background: linear-gradient(120deg, #1e40af, #3b82f6); color: #fff; display: flex; align-items: center; justify-content: space-between; box-shadow: var(--shadow); flex-wrap: wrap; gap: 8px; }
.sh-header h1 { margin: 0; font-size: 28px; font-weight: 600; }
.sub { font-size: 15px; opacity: .9; }
.server-info { display: flex; align-items: center; gap: 4px; font-size: 15px; }
.server-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
.server-dot.on { background: #4ade80; box-shadow: 0 0 6px #4ade80; }
.server-dot.off { background: #f87171; }
.sh-main { padding: 24px 32px 48px; max-width: 1480px; margin: 0 auto; }
.section-title { margin: 32px 0 14px; font-size: 19px; font-weight: 600; display: flex; align-items: center; gap: 10px; }
.section-title::before { content: ""; width: 6px; height: 20px; background: var(--primary); border-radius: 3px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 22px 24px; box-shadow: var(--shadow); margin-bottom: 4px; }
.card h3 { margin: 0 0 8px; font-size: 18px; color: var(--text); }
.toolbar { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }
.status { font-size: 14px; color: var(--muted); margin-left: auto; }
.status.ok { color: var(--good); } .status.err { color: var(--bad); }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; background: var(--primary); color: #fff; font-size: 15px; font-weight: 500; transition: all .15s; white-space: nowrap; text-decoration: none; }
.btn:hover { background: #2563eb; }
.btn:disabled { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.3); cursor: not-allowed; }
.btn.ghost { background: rgba(59,130,246,0.1); color: #3b82f6; border: 1px solid rgba(59,130,246,0.2); }
.btn.small { padding: 4px 14px; font-size: 13px; }
.btn.tune-btn { background: rgba(245,158,11,0.12); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.model-bar { padding: 14px 20px; }
.model-badge { padding: 4px 12px; border-radius: 12px; font-size: 13px; font-weight: 600; }
.badge-default { background: rgba(59,130,246,0.15); color: #3b82f6; }
.badge-trained { background: rgba(34,197,94,0.15); color: #22c55e; }
.toggle-wrap { display: flex; align-items: center; gap: 8px; }
.toggle-wrap.disabled { opacity: 0.5; pointer-events: none; }
.toggle-label { font-size: 13px; color: var(--muted); cursor: pointer; transition: color .2s; }
.toggle-label.active { color: var(--text); font-weight: 600; }
.toggle-label.dim { color: var(--muted); opacity: 0.5; }
.toggle-track { width: 44px; height: 24px; border-radius: 12px; background: rgba(255,255,255,0.1); cursor: pointer; position: relative; transition: background .2s; }
.toggle-thumb { width: 18px; height: 18px; border-radius: 50%; background: #3b82f6; position: absolute; top: 3px; left: 3px; transition: left .2s; }
.toggle-thumb.right { left: 23px; background: #22c55e; }
.grid-1 { display: grid; gap: 12px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
@media (max-width: 980px) { .grid-2,.grid-3,.grid-4 { grid-template-columns: 1fr; } }
.score-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow); text-align: center; }
.score-card .label { font-size: 15px; color: var(--muted); margin-bottom: 8px; }
.score-card .value { font-size: 36px; font-weight: 700; font-family: "SF Mono", Menlo, monospace; }
.sub-text { font-size: 13px; color: var(--muted); margin-top: 4px; line-height: 1.6; }
.chart { height: 300px; width: 100%; min-width: 300px; }
.desc { color: var(--muted); font-size: 14px; line-height: 1.7; }
.table-wrap { max-height: 400px; overflow: auto; }
.result-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.result-table th, .result-table td { padding: 10px 8px; text-align: center; border-bottom: 1px solid var(--border); }
.result-table thead th { background: rgba(59,130,246,0.08); color: #3b82f6; font-weight: 600; position: sticky; top: 0; }
.result-table tr:hover { background: rgba(59,130,246,0.05); }
.model-card { background: var(--card); border: 2px solid; border-radius: var(--radius); padding: 20px; }
.model-card h3 { margin: 0 0 8px; font-size: 20px; }
.model-type { display: inline-block; padding: 2px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }
.model-desc { color: var(--muted); font-size: 13px; line-height: 1.6; margin: 10px 0; }
.progress-bar { height: 8px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; position: relative; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #22c55e); border-radius: 4px; transition: width .3s; }
.progress-text { position: absolute; top: 12px; left: 0; font-size: 13px; color: var(--muted); }
.pred-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; }
.pred-label { padding: 4px 10px; border-radius: 6px; font-size: 14px; font-weight: 600; display: inline-block; margin-bottom: 8px; }
.pred-label.normal { background: rgba(34,197,94,0.15); color: #22c55e; }
.pred-label.abnormal { background: rgba(239,68,68,0.15); color: #ef4444; }
.pred-conf { font-size: 13px; color: var(--muted); margin-bottom: 8px; }
.prob-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; font-size: 12px; }
.prob-name { width: 90px; flex-shrink: 0; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.prob-bar-bg { flex: 1; height: 6px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden; }
.prob-bar-fill { height: 100%; background: #3b82f6; border-radius: 3px; }
.prob-val { width: 40px; text-align: right; color: var(--muted); }
.loading-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(10,14,26,0.85); display: flex; align-items: center; justify-content: center; z-index: 999; font-size: 20px; }
.spinner { width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.1); border-top-color: var(--primary); border-radius: 50%; animation: spin .8s linear infinite; margin-right: 12px; }
@keyframes spin { to { transform: rotate(360deg) } }
.sh-footer { text-align: center; color: var(--muted); font-size: 13px; padding: 24px; }
.form-label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
.form-input { width: 100%; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border); background: rgba(0,0,0,0.4); color: var(--text); font-size: 14px; }
.form-select { width: 100%; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border); background: rgba(0,0,0,0.4); color: var(--text); font-size: 14px; }
.form-hint { display: block; font-size: 12px; color: var(--muted); margin-top: 4px; line-height: 1.5; }
</style>
