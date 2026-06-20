<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { createStrategyApi, type StrategyApi, type StrategyDatasetInfo, type StrategyRuleResult, type StrategyClusterResult, type StrategyPredictionResult, type StrategyScheduleResult, type StrategyPipelineResult } from '@/api/demo'

const api: StrategyApi = createStrategyApi()

// 状态
const serverOnline = ref(false)
const loading = ref(false)
const loadingText = ref('')
const statusMsg = ref('请上传数据集 ZIP 或使用默认数据')
const statusClass = ref('')

// 上传
const fileInputRef = ref<HTMLInputElement | null>(null)
const fileName = ref('')
const datasetInfo = ref<StrategyDatasetInfo | null>(null)

// 各步骤结果
const ruleResult = ref<StrategyRuleResult | null>(null)
const scenarioMeta = ref<Record<string, { name: string; category: string; action_type: string }> | null>(null)
const clusterResult = ref<StrategyClusterResult | null>(null)
const predictResult = ref<StrategyPredictionResult | null>(null)
const scheduleResult = ref<StrategyScheduleResult | null>(null)
const pipelineResult = ref<StrategyPipelineResult | null>(null)

// 图表 refs
const barChartRef = ref<HTMLDivElement | null>(null)
const pieChartRef = ref<HTMLDivElement | null>(null)
const curveChartRef = ref<HTMLDivElement | null>(null)
const predChartRef = ref<HTMLDivElement | null>(null)

const charts: Record<string, echarts.ECharts | null> = { bar: null, pie: null, curve: null, pred: null }

const clusterColors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444']
const categoryNames: Record<string, string> = { C1: '策略调整', C2: '事件上报', C3: '处理流程', C4: '告警通知' }

function showLoading(msg: string) { loading.value = true; loadingText.value = msg }
function hideLoading() { loading.value = false }
function setStatus(msg: string, cls: string = '') { statusMsg.value = msg; statusClass.value = cls }

async function checkServer() {
  try { await api.ping(); serverOnline.value = true; loadDatasetInfo() } catch { serverOnline.value = false }
}
onMounted(checkServer)

async function loadDatasetInfo() {
  try { datasetInfo.value = await api.datasetInfo() } catch { /* ignore */ }
}

function triggerUpload() { fileInputRef.value?.click() }
async function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  fileName.value = file.name
  showLoading('正在上传数据集...')
  try {
    await api.uploadDataset(file)
    await loadDatasetInfo()
    setStatus('数据集上传成功', 'ok')
    ruleResult.value = null; clusterResult.value = null; predictResult.value = null; scheduleResult.value = null; pipelineResult.value = null; scenarioMeta.value = null
  } catch (e: any) { setStatus('上传失败: ' + e.message, 'err') }
  finally { hideLoading() }
}

// 规则研判
async function runRules() {
  showLoading('正在执行规则研判...')
  try {
    ruleResult.value = await api.runRules()
    scenarioMeta.value = ruleResult.value.scenario_meta || null
    setStatus(`规则研判完成: ${ruleResult.value.total} 条建议`, 'ok')
    nextTick(() => renderBarChart())
  } catch (e: any) { setStatus('规则研判失败: ' + e.message, 'err') }
  finally { hideLoading() }
}

function renderBarChart() {
  if (!barChartRef.value || !ruleResult.value) return
  if (charts.bar) charts.bar.dispose()
  charts.bar = echarts.init(barChartRef.value)
  const data = ruleResult.value
  const labels = Object.keys(data.by_scenario).sort()
  const meta = scenarioMeta.value || {}
  charts.bar.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const sid = params[0].name
        const m = meta[sid]
        return `<b>${sid}</b> ${m?.name || ''}<br/>命中数: ${params[0].value}<br/>类别: ${m?.category || ''}`
      }
    },
    legend: { data: ['命中数'], bottom: 0, textStyle: { color: '#9ca3af' } },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45, fontSize: 10, color: '#9ca3af' } },
    yAxis: { type: 'value', name: '条数', nameTextStyle: { color: '#9ca3af' } },
    series: [{
      type: 'bar', data: labels.map(l => data.by_scenario[l] || 0),
      itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] },
      label: { show: true, position: 'top', fontSize: 10, color: '#e4e7ed' }
    }]
  })
}

// 聚类
async function runClustering() {
  showLoading('正在执行聚类分析...')
  try {
    clusterResult.value = await api.runClustering()
    setStatus(`聚类完成: ${clusterResult.value.total_terminals} 个终端`, 'ok')
    nextTick(() => { renderPieChart(); renderCurveChart() })
  } catch (e: any) { setStatus('聚类失败: ' + e.message, 'err') }
  finally { hideLoading() }
}

function renderPieChart() {
  if (!pieChartRef.value || !clusterResult.value) return
  if (charts.pie) charts.pie.dispose()
  charts.pie = echarts.init(pieChartRef.value)
  const data = clusterResult.value
  const pieData = Object.entries(data.cluster_counts).map(([k, v]) => ({
    name: `簇 ${k}`, value: v, itemStyle: { color: clusterColors[Number(k)] }
  }))
  charts.pie.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: '#9ca3af' } },
    series: [{ type: 'pie', radius: ['40%', '70%'], data: pieData, label: { color: '#e4e7ed' } }]
  })
}

function renderCurveChart() {
  if (!curveChartRef.value || !clusterResult.value) return
  if (charts.curve) charts.curve.dispose()
  charts.curve = echarts.init(curveChartRef.value)
  const data = clusterResult.value
  const series: any[] = []
  for (const [cid, curve] of Object.entries(data.cluster_avg_curves)) {
    if (!curve.length) continue
    series.push({
      name: `簇 ${cid}`, type: 'line', data: curve,
      itemStyle: { color: clusterColors[Number(cid)] },
      lineStyle: { width: 2 }, symbol: 'none', smooth: true,
    })
  }
  charts.curve.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: series.map(s => s.name), bottom: 0, textStyle: { color: '#9ca3af' } },
    xAxis: { type: 'category', name: '时段 (15min)', nameTextStyle: { color: '#9ca3af' }, axisLabel: { color: '#9ca3af', interval: 11 } },
    yAxis: { type: 'value', name: '成功率', min: 0, max: 1, nameTextStyle: { color: '#9ca3af' } },
    series,
  })
}

// 预测
async function runPrediction() {
  showLoading('正在执行预测...')
  try {
    predictResult.value = await api.runPrediction()
    setStatus('预测完成', 'ok')
    nextTick(() => renderPredChart())
  } catch (e: any) { setStatus('预测失败: ' + e.message, 'err') }
  finally { hideLoading() }
}

function renderPredChart() {
  if (!predChartRef.value || !predictResult.value) return
  if (charts.pred) charts.pred.dispose()
  charts.pred = echarts.init(predChartRef.value)
  const data = predictResult.value
  const series: any[] = []
  const timeLabels = Array.from({ length: 96 }, (_, i) => `${String(Math.floor(i * 15 / 60)).padStart(2, '0')}:${String(i * 15 % 60).padStart(2, '0')}`)

  for (const [cid, curve] of Object.entries(data.curves)) {
    if (!curve?.length) continue
    series.push({
      name: `簇 ${cid}`, type: 'line',
      data: curve.map((p: any) => p.predicted_success),
      itemStyle: { color: clusterColors[Number(cid)] },
      lineStyle: { width: 2 }, symbol: 'none', smooth: true,
    })
  }
  charts.pred.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        let html = `<b>${timeLabels[params[0].dataIndex]}</b><br/>`
        params.forEach((p: any) => { html += `${p.marker} ${p.seriesName}: ${p.value.toFixed(4)}<br/>` })
        return html
      }
    },
    legend: { data: series.map(s => s.name), bottom: 0, textStyle: { color: '#9ca3af' } },
    xAxis: { type: 'category', data: timeLabels, name: '时间', nameTextStyle: { color: '#9ca3af' }, axisLabel: { color: '#9ca3af', interval: 11, fontSize: 10 } },
    yAxis: { type: 'value', name: '预测成功率', min: 0, max: 1, nameTextStyle: { color: '#9ca3af' } },
    series,
    grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
  })
}

// 排程
async function runSchedule() {
  showLoading('正在生成排程...')
  try {
    scheduleResult.value = await api.runSchedule()
    setStatus(`排程生成完成: ${scheduleResult.value.schedules.length} 个簇`, 'ok')
  } catch (e: any) { setStatus('排程失败: ' + e.message, 'err') }
  finally { hideLoading() }
}

// 全流程
async function runFullPipeline() {
  showLoading('正在执行全流程...')
  try {
    pipelineResult.value = await api.runFullPipeline()
    ruleResult.value = pipelineResult.value.rules
    scenarioMeta.value = pipelineResult.value.scenario_meta || null
    setStatus(`全流程完成: ${pipelineResult.value.rules.total} 条建议`, 'ok')
    nextTick(() => { renderBarChart(); renderPredChart() })
  } catch (e: any) { setStatus('全流程失败: ' + e.message, 'err') }
  finally { hideLoading() }
}
</script>

<template>
  <div class="st-root">
    <header class="st-header">
      <div>
        <h1>采集策略智能调度模型</h1>
        <div class="sub">K-means 聚类 + LightGBM 预测 + 17 场景规则研判 + 补召排程</div>
      </div>
      <div class="server-info">
        <span class="server-dot" :class="serverOnline ? 'on' : 'off'"></span>
        <span>{{ serverOnline ? '服务就绪' : '服务未连接' }}</span>
      </div>
    </header>

    <main class="st-main">
      <div v-if="loading" class="loading-overlay"><div class="spinner"></div>{{ loadingText }}</div>

      <!-- 1. 数据上传 -->
      <div class="section-title">1. 数据上传</div>
      <div class="card">
        <div class="toolbar">
          <input ref="fileInputRef" type="file" accept=".zip" style="display:none" @change="onFileChange" />
          <button class="btn" @click="triggerUpload">上传数据集 ZIP</button>
          <span v-if="fileName" class="file-name">{{ fileName }}</span>
          <span class="status" :class="statusClass">{{ statusMsg }}</span>
        </div>
        <div v-if="datasetInfo?.status === 'ok'" class="grid-4" style="margin-top:14px;">
          <div class="score-card"><div class="label">数据表数</div><div class="value">{{ datasetInfo.total_tables }}</div></div>
          <div class="score-card"><div class="label">总行数</div><div class="value">{{ (datasetInfo.total_rows / 10000).toFixed(1) }}万</div></div>
          <div class="score-card"><div class="label">数据源</div><div class="value" style="font-size:14px;">{{ datasetInfo.is_default ? '默认数据' : '上传数据' }}</div></div>
          <div class="score-card"><div class="label">已加载表</div><div class="value">{{ datasetInfo.tables.filter(t => !t.missing).length }}</div></div>
        </div>
      </div>

      <!-- 2. 规则研判 -->
      <div class="section-title">2. 规则研判（17 场景）</div>
      <div class="card">
        <button class="btn" @click="runRules">执行规则研判</button>
        <div v-if="ruleResult" style="margin-top:16px;">
          <div class="grid-4">
            <div class="score-card"><div class="label">总建议数</div><div class="value">{{ ruleResult.total }}</div></div>
            <div class="score-card"><div class="label">C1 策略调整</div><div class="value">{{ ruleResult.by_category?.C1 ?? 0 }}</div></div>
            <div class="score-card"><div class="label">C2 事件上报</div><div class="value">{{ ruleResult.by_category?.C2 ?? 0 }}</div></div>
            <div class="score-card"><div class="label">C3/C4 流程告警</div><div class="value">{{ (ruleResult.by_category?.C3 ?? 0) + (ruleResult.by_category?.C4 ?? 0) }}</div></div>
          </div>
          <div ref="barChartRef" class="chart" style="height:350px;margin-top:16px;"></div>

          <!-- 场景说明表 -->
          <div v-if="scenarioMeta" style="margin-top:16px;">
            <h3>场景说明</h3>
            <div class="table-wrap">
              <table class="result-table">
                <thead><tr><th>场景编号</th><th>场景名称</th><th>类别</th><th>命中数</th></tr></thead>
                <tbody>
                  <tr v-for="(meta, sid) in scenarioMeta" :key="sid">
                    <td><span class="tag">{{ sid }}</span></td>
                    <td style="text-align:left;">{{ meta.name }}</td>
                    <td>{{ categoryNames[meta.category] || meta.category }}</td>
                    <td><strong>{{ ruleResult?.by_scenario?.[sid] ?? 0 }}</strong></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div v-if="ruleResult.recommendations?.length" style="margin-top:16px;">
            <h3>推荐列表（前 {{ ruleResult.recommendations.length }} 条）</h3>
            <div class="table-wrap">
              <table class="result-table">
                <thead><tr><th>场景</th><th>终端ID</th><th>类别</th><th>动作摘要</th></tr></thead>
                <tbody>
                  <tr v-for="r in ruleResult.recommendations.slice(0, 20)" :key="r.rec_id">
                    <td><span class="tag">{{ r.matched_scenario_id }}</span></td>
                    <td>{{ r.terminal_id || r.area_id || '-' }}</td>
                    <td>{{ categoryNames[r.action_category] || r.action_category }}</td>
                    <td style="text-align:left;font-size:13px;">{{ r.action_summary }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. 聚类分析 -->
      <div class="section-title">3. K-means 聚类分析</div>
      <div class="card">
        <button class="btn" @click="runClustering">执行聚类分析</button>
        <div v-if="clusterResult" class="grid-2" style="margin-top:16px;">
          <div><h3>终端簇分布</h3><div ref="pieChartRef" class="chart" style="height:300px;"></div></div>
          <div><h3>各簇平均成功率曲线</h3><div ref="curveChartRef" class="chart" style="height:300px;"></div></div>
        </div>
      </div>

      <!-- 4. 预测与排程 -->
      <div class="section-title">4. 采集成功率预测与补召排程</div>
      <div class="card">
        <div class="toolbar">
          <button class="btn" @click="runPrediction">预测 24h 曲线</button>
          <button class="btn tune-btn" @click="runSchedule">生成补召排程</button>
        </div>
        <div v-if="predictResult" style="margin-top:16px;">
          <h3>各簇 24h 预测成功率曲线</h3>
          <div ref="predChartRef" class="chart" style="height:400px;"></div>
        </div>
        <div v-if="scheduleResult" style="margin-top:16px;">
          <h3>排程日期: {{ scheduleResult.schedule_date }}</h3>
          <div class="grid-4" style="margin-top:12px;">
            <div v-for="s in scheduleResult.schedules" :key="s.cluster_id" class="score-card">
              <div class="label">{{ s.cluster_name || ('簇 ' + s.cluster_id) }}</div>
              <div class="value" style="font-size:24px;">{{ s.recall_times.join(', ') }}</div>
              <div class="sub-text">预测均值: {{ s.mean_predicted.toFixed(3) }} · {{ s.n_slots }} 个时段</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 5. 全流程 + 导出 -->
      <div class="section-title">5. 一键全流程 + 结果导出</div>
      <div class="card">
        <div class="toolbar">
          <button class="btn" @click="runFullPipeline" style="font-size:17px;padding:14px 28px;">执行全流程</button>
          <a v-if="pipelineResult" class="btn ghost" :href="api.getExportCsvUrl()">下载中间表 CSV</a>
        </div>
        <div v-if="pipelineResult" style="margin-top:14px;color:var(--good);">
          全流程完成 · 日期: {{ pipelineResult.today }} · {{ pipelineResult.rules.total }} 条建议
        </div>

        <!-- 策略调整对比 -->
        <div v-if="pipelineResult?.strategy_comparison?.changes?.length" style="margin-top:20px;">
          <h3>策略调整前后对比（C1 类，共 {{ pipelineResult.strategy_comparison.total_c1 }} 条）</h3>
          <div class="table-wrap">
            <table class="result-table">
              <thead><tr><th>终端ID</th><th>场景</th><th>原策略</th><th>新策略</th><th>频率变化</th><th>预期收益</th></tr></thead>
              <tbody>
                <tr v-for="(c, i) in pipelineResult.strategy_comparison.changes" :key="i">
                  <td>{{ c.terminal_id }}</td>
                  <td><span class="tag">{{ c.scenario }}</span> {{ c.scenario_name }}</td>
                  <td style="color:#f59e0b;">{{ c.original }}</td>
                  <td style="color:#22c55e;">{{ c.suggested }}</td>
                  <td>{{ c.freq_change || '-' }}</td>
                  <td style="text-align:left;font-size:13px;max-width:200px;">{{ c.expected_benefit }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 成功率预期提升 -->
        <div v-if="pipelineResult?.schedules?.length" style="margin-top:20px;">
          <h3>优化后各簇补召排程与预期成功率</h3>
          <div class="grid-4" style="margin-top:12px;">
            <div v-for="s in pipelineResult.schedules" :key="s.cluster_id" class="score-card" style="border-color: rgba(34,197,94,0.3);">
              <div class="label">{{ s.cluster_name || ('簇 ' + s.cluster_id) }}</div>
              <div class="value" style="font-size:20px;color:#22c55e;">{{ s.recall_times.join(', ') }}</div>
              <div class="sub-text">
                平均预测: {{ s.mean_predicted.toFixed(3) }}<br/>
                最低: {{ s.min_predicted.toFixed(3) }} · 最高: {{ s.max_predicted.toFixed(3) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <footer class="st-footer">采集策略智能调度模型 · K-means + LightGBM + 17 场景规则</footer>
  </div>
</template>

<style scoped>
.st-root {
  --bg: transparent; --card: rgba(17,24,39,0.6); --border: rgba(0,212,255,0.15);
  --text: #e4e7ed; --muted: rgba(255,255,255,0.5); --primary: #3b82f6; --primary-dark: #2563eb;
  --gradient: linear-gradient(120deg, #1e40af, #3b82f6);
  --good: #22c55e; --warn: #f59e0b; --bad: #ef4444; --radius: 12px;
  --shadow: 0 4px 20px rgba(59,130,246,0.1), inset 0 1px 0 rgba(255,255,255,0.05);
  background: var(--bg); color: var(--text); font-size: 15px;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  min-height: 100%;
}
* { box-sizing: border-box; }

.st-header { padding: 24px 32px; background: var(--gradient); color: #fff; display: flex; align-items: center; justify-content: space-between; box-shadow: var(--shadow); flex-wrap: wrap; gap: 8px; }
.st-header h1 { margin: 0; font-size: 28px; font-weight: 600; }
.sub { font-size: 15px; opacity: .9; }
.server-info { display: flex; align-items: center; gap: 4px; font-size: 15px; }
.server-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
.server-dot.on { background: #4ade80; box-shadow: 0 0 6px #4ade80; }
.server-dot.off { background: #f87171; box-shadow: 0 0 6px #f87171; }

.st-main { padding: 24px 32px 48px; max-width: 1480px; margin: 0 auto; }

.section-title { margin: 32px 0 14px; font-size: 19px; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 10px; }
.section-title::before { content: ""; width: 6px; height: 20px; background: var(--primary); border-radius: 3px; }

.card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 22px 24px; box-shadow: var(--shadow); }
.card h3 { margin: 0 0 8px; font-size: 18px; color: var(--text); }

.toolbar { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }
.file-name { font-size: 14px; color: var(--good); }
.status { font-size: 14px; color: var(--muted); margin-left: auto; }
.status.ok { color: var(--good); } .status.err { color: var(--bad); }

.btn { display: inline-flex; align-items: center; gap: 6px; padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; background: var(--primary); color: #fff; font-size: 15px; font-weight: 500; transition: all .15s; white-space: nowrap; text-decoration: none; }
.btn:hover { background: var(--primary-dark); }
.btn:disabled { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.3); cursor: not-allowed; }
.btn.ghost { background: rgba(59,130,246,0.1); color: #3b82f6; border: 1px solid rgba(59,130,246,0.2); }
.btn.ghost:hover { background: rgba(59,130,246,0.2); }
.btn.tune-btn { background: rgba(245,158,11,0.12); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.btn.tune-btn:hover { background: rgba(245,158,11,0.22); }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
@media (max-width: 980px) { .grid-2,.grid-4 { grid-template-columns: 1fr; } }

.score-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow); text-align: center; }
.score-card .label { font-size: 15px; color: var(--muted); margin-bottom: 8px; }
.score-card .value { font-size: 36px; font-weight: 700; font-family: "SF Mono", Menlo, monospace; color: var(--text); }
.sub-text { font-size: 13px; color: var(--muted); margin-top: 4px; line-height: 1.6; }

.chart { height: 300px; width: 100%; min-width: 300px; }

.table-wrap { max-height: 400px; overflow: auto; }
.result-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.result-table th, .result-table td { padding: 10px 8px; text-align: center; border-bottom: 1px solid var(--border); }
.result-table thead th { background: rgba(59,130,246,0.08); color: #3b82f6; font-weight: 600; position: sticky; top: 0; }
.result-table tr:hover { background: rgba(59,130,246,0.05); }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; background: rgba(59,130,246,0.15); color: #3b82f6; }

.loading-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(10,14,26,0.85); display: flex; align-items: center; justify-content: center; z-index: 999; font-size: 20px; color: var(--text); }
.spinner { width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.1); border-top-color: var(--primary); border-radius: 50%; animation: spin .8s linear infinite; margin-right: 12px; }
@keyframes spin { to { transform: rotate(360deg) } }

.st-footer { text-align: center; color: var(--muted); font-size: 13px; padding: 24px; }
</style>
