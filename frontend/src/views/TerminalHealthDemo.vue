<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { createTerminalHealthApi, type TerminalHealthApi, type TerminalHealthTrainResult, type TerminalHealthGridSearchResult, type TerminalHealthCVResult, type TerminalHealthPredictResult } from '@/api/demo'

const api: TerminalHealthApi = createTerminalHealthApi()

// 状态
const serverOnline = ref(false)
const loading = ref(false)
const loadingText = ref('')
const statusMsg = ref('请上传 CSV 训练数据')
const statusClass = ref('')

// 上传
const fileInputRef = ref<HTMLInputElement | null>(null)
const fileName = ref('')
const currentFile = ref<File | null>(null)
const dataInfo = ref<any>(null)

// 训练
const trainResult = ref<TerminalHealthTrainResult | null>(null)
const showTrainSection = ref(false)

// Grid Search
const showGsSection = ref(false)
const gsResult = ref<TerminalHealthGridSearchResult | null>(null)
const gsParams = ref({
  n_estimators_start: 100, n_estimators_end: 400, n_estimators_step: 100,
  max_samples_start: 0.5, max_samples_end: 1.0, max_samples_step: 0.1,
  max_features_start: 0.5, max_features_end: 1.0, max_features_step: 0.25,
  module: 'both',
})

// CV
const showCVSection = ref(false)
const cvResult = ref<TerminalHealthCVResult | null>(null)
const cvFolds = ref(5)

// 预测
const predictFileRef = ref<HTMLInputElement | null>(null)
const predictResult = ref<TerminalHealthPredictResult | null>(null)
const showPredictSection = ref(false)

// 图表 refs
const gradeChartRef = ref<HTMLDivElement | null>(null)
const scoreDistChartRef = ref<HTMLDivElement | null>(null)
const removalChartRef = ref<HTMLDivElement | null>(null)
const cvAucChartRef = ref<HTMLDivElement | null>(null)

const charts: Record<string, echarts.ECharts | null> = { grade: null, scoreDist: null, removal: null, cvAuc: null }

// 工具函数
function showLoading(msg: string) { loading.value = true; loadingText.value = msg }
function hideLoading() { loading.value = false }

function setStatus(msg: string, cls: string = '') { statusMsg.value = msg; statusClass.value = cls }

const scoreLabels: Record<string, string> = {
  score_years: '使用年限', score_comm: '通讯模块',
  score_module3: '终端特征', score_module4: '下挂设备',
  score_MFR: '厂商质量', total_score: '综合评分',
}

const gradeColors: Record<string, string> = {
  'B - 运行良好': '#22c55e', 'C - 重点关注': '#f59e0b',
  'D - 建议维修/拆换': '#ef4444', 'E - 超龄建议直接拆除': '#6b7280',
}

// ==================== 服务检查 ====================
async function checkServer() {
  try { await api.ping(); serverOnline.value = true } catch { serverOnline.value = false }
}
onMounted(checkServer)

// ==================== 上传 ====================
function triggerUpload() { fileInputRef.value?.click() }

async function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  currentFile.value = file
  fileName.value = file.name
  showLoading('正在上传数据...')
  setStatus('上传中...')
  try {
    await api.upload(file)
    const info = await api.dataInfo()
    dataInfo.value = info
    setStatus(`上传成功: ${info.rows} 行, ${info.columns} 列`, 'ok')
    showTrainSection.value = false
    showGsSection.value = false
    showCVSection.value = false
    showPredictSection.value = false
    trainResult.value = null; gsResult.value = null; cvResult.value = null; predictResult.value = null
  } catch (e: any) { setStatus('上传失败: ' + e.message, 'err') }
  finally { hideLoading() }
}

// ==================== 训练 ====================
async function trainModel(useOptimization: boolean) {
  if (!dataInfo.value) { setStatus('请先上传数据', 'err'); return }
  showLoading(useOptimization ? '正在优化训练...' : '正在快速训练...')
  setStatus('训练中...')
  try {
    const result = await api.train({ use_optimization: useOptimization, optimize_n_calls: 20 })
    trainResult.value = result
    showTrainSection.value = true
    setStatus(result.message, 'ok')
    nextTick(() => renderTrainCharts())
  } catch (e: any) { setStatus('训练失败: ' + e.message, 'err') }
  finally { hideLoading() }
}

function renderTrainCharts() {
  const data = trainResult.value
  if (!data) return

  // 等级分布饼图
  if (gradeChartRef.value) {
    if (charts.grade) charts.grade.dispose()
    charts.grade = echarts.init(gradeChartRef.value)
    const labels = Object.keys(data.grade_dist)
    charts.grade.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, textStyle: { color: '#9ca3af', fontSize: 12 } },
      series: [{
        type: 'pie', radius: ['40%', '70%'],
        data: labels.map(l => ({ name: l, value: data.grade_dist[l], itemStyle: { color: gradeColors[l] || '#6b7280' } })),
        label: { color: '#e4e7ed', fontSize: 12 },
      }]
    })
  }

  // 评分分布
  if (scoreDistChartRef.value && data.score_distribution) {
    if (charts.scoreDist) charts.scoreDist.dispose()
    charts.scoreDist = echarts.init(scoreDistChartRef.value)
    const sd = data.score_distribution
    charts.scoreDist.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: sd.labels, axisLabel: { rotate: 45, fontSize: 10, color: '#9ca3af' } },
      yAxis: { type: 'value', name: '样本数', nameTextStyle: { color: '#9ca3af' } },
      series: [{ type: 'bar', data: sd.counts, itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] } }]
    })
  }

  // 拆除 vs 运行
  if (removalChartRef.value && data.removal_distribution) {
    if (charts.removal) charts.removal.dispose()
    charts.removal = echarts.init(removalChartRef.value)
    const rd = data.removal_distribution
    const bins = 20; const step = 5
    const labels = Array.from({ length: bins }, (_, i) => `${i * step}-${(i + 1) * step}`)
    const hist = (arr: number[]) => {
      const counts = new Array(bins).fill(0)
      arr.forEach(v => { const idx = Math.min(Math.floor(v / step), bins - 1); if (idx >= 0) counts[idx]++ })
      return counts
    }
    charts.removal.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['已拆除', '运行中'], textStyle: { color: '#9ca3af' } },
      xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45, fontSize: 10, color: '#9ca3af' } },
      yAxis: { type: 'value', name: '样本数', nameTextStyle: { color: '#9ca3af' } },
      series: [
        { name: '已拆除', type: 'bar', data: hist(rd.removed), itemStyle: { color: 'rgba(239,68,68,0.6)', borderRadius: [4, 4, 0, 0] } },
        { name: '运行中', type: 'bar', data: hist(rd.normal), itemStyle: { color: 'rgba(34,197,94,0.6)', borderRadius: [4, 4, 0, 0] } },
      ]
    })
  }
}

// ==================== Grid Search ====================
async function runGridSearch() {
  if (!dataInfo.value) { setStatus('请先上传数据', 'err'); return }
  showLoading('正在执行 Grid Search...')
  setStatus('Grid Search 进行中...')
  try {
    const result = await api.gridSearch(gsParams.value)
    gsResult.value = result
    showGsSection.value = true
    setStatus(result.message, 'ok')
  } catch (e: any) { setStatus('Grid Search 失败: ' + e.message, 'err') }
  finally { hideLoading() }
}

// ==================== CV ====================
async function runCV() {
  if (!dataInfo.value) { setStatus('请先上传数据', 'err'); return }
  showLoading('正在执行交叉验证...')
  setStatus('交叉验证进行中...')
  try {
    const result = await api.crossValidate({ n_folds: cvFolds.value, use_optimization: false })
    cvResult.value = result
    showCVSection.value = true
    setStatus(result.message, 'ok')
    nextTick(() => renderCVChart())
  } catch (e: any) { setStatus('交叉验证失败: ' + e.message, 'err') }
  finally { hideLoading() }
}

function renderCVChart() {
  if (!cvAucChartRef.value || !cvResult.value) return
  if (charts.cvAuc) charts.cvAuc.dispose()
  charts.cvAuc = echarts.init(cvAucChartRef.value)
  const data = cvResult.value
  charts.cvAuc.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.auc_chart.labels, axisLabel: { color: '#9ca3af' } },
    yAxis: { type: 'value', min: 0, max: 1, name: 'AUC', nameTextStyle: { color: '#9ca3af' } },
    series: [{
      type: 'bar',
      data: data.auc_chart.values.map((v: number) => ({
        value: v, itemStyle: { color: v >= 0.8 ? '#22c55e' : v >= 0.7 ? '#f59e0b' : '#ef4444', borderRadius: [4, 4, 0, 0] }
      })),
      label: { show: true, position: 'top', color: '#e4e7ed', formatter: (p: any) => p.value.toFixed(4) }
    }]
  })
}

// ==================== 预测 ====================
function triggerPredict() { predictFileRef.value?.click() }

async function onPredictFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  showLoading('正在预测...')
  setStatus('预测中...')
  try {
    const result = await api.predict(file)
    predictResult.value = result
    showPredictSection.value = true
    setStatus(result.message, 'ok')
  } catch (e: any) { setStatus('预测失败: ' + e.message, 'err') }
  finally { hideLoading() }
}

function getGradeClass(grade: string): string {
  if (grade.includes('B')) return 'grade-b'
  if (grade.includes('C')) return 'grade-c'
  if (grade.includes('D')) return 'grade-d'
  return 'grade-e'
}
</script>

<template>
  <div class="th-root">
    <!-- Header -->
    <header class="th-header">
      <div>
        <h1>终端健康度评价系统</h1>
        <div class="sub">Isolation Forest + 多模块综合评分 · 5 模块加权评估</div>
      </div>
      <div class="server-info">
        <span class="server-dot" :class="serverOnline ? 'on' : 'off'"></span>
        <span>{{ serverOnline ? '服务就绪' : '服务未连接' }}</span>
      </div>
    </header>

    <main class="th-main">
      <!-- 加载遮罩 -->
      <div v-if="loading" class="loading-overlay">
        <div class="spinner"></div>{{ loadingText }}
      </div>

      <!-- 1. 数据上传 -->
      <div class="section-title">1. 数据上传</div>
      <div class="card">
        <div class="toolbar">
          <input ref="fileInputRef" type="file" accept=".csv" style="display:none" @change="onFileChange" />
          <button class="btn" @click="triggerUpload">选择 CSV 训练数据</button>
          <a v-if="serverOnline" :href="api.getDemoCsvUrl()" class="btn ghost">下载演示数据</a>
          <span v-if="fileName" class="file-name">{{ fileName }}</span>
          <span class="status" :class="statusClass">{{ statusMsg }}</span>
        </div>
        <div v-if="dataInfo" class="grid-4" style="margin-top:14px;">
          <div class="score-card"><div class="label">样本数</div><div class="value">{{ dataInfo.rows }}</div></div>
          <div class="score-card"><div class="label">特征数</div><div class="value">{{ dataInfo.columns }}</div></div>
          <div class="score-card"><div class="label">厂商数</div><div class="value">{{ dataInfo.manufacturer_count ?? '-' }}</div></div>
          <div class="score-card"><div class="label">拆除率</div><div class="value">{{ dataInfo.removal_rate ? (dataInfo.removal_rate * 100).toFixed(1) + '%' : '-' }}</div></div>
        </div>
      </div>

      <!-- 2. 模型训练 -->
      <div class="section-title">2. 模型训练</div>
      <div class="card">
        <div class="toolbar">
          <button class="btn" :disabled="!dataInfo" @click="trainModel(false)">快速训练（默认参数）</button>
          <button class="btn tune-btn" :disabled="!dataInfo" @click="trainModel(true)">优化训练（贝叶斯优化）</button>
        </div>
        <div v-if="showTrainSection && trainResult" class="train-results">
          <!-- 评分统计 -->
          <h3 style="margin-top:16px;">各模块评分统计</h3>
          <div class="grid-6">
            <div v-for="(val, key) in trainResult.score_stats" :key="key" class="score-card">
              <div class="label">{{ scoreLabels[key] || key }}</div>
              <div class="value">{{ val.mean }}</div>
              <div class="sub-text">std: {{ val.std }}</div>
            </div>
          </div>
          <!-- 等级分布 + 评分分布 -->
          <div class="grid-2" style="margin-top:16px;">
            <div>
              <h3>健康等级分布</h3>
              <div ref="gradeChartRef" class="chart" style="height:300px;"></div>
            </div>
            <div>
              <h3>综合评分分布</h3>
              <div ref="scoreDistChartRef" class="chart" style="height:300px;"></div>
            </div>
          </div>
          <!-- 拆除 vs 运行 -->
          <div v-if="trainResult.removal_distribution" style="margin-top:16px;">
            <h3>拆除 vs 运行 样本评分分布</h3>
            <div ref="removalChartRef" class="chart" style="height:300px;"></div>
          </div>
          <!-- 厂商分析 -->
          <div v-if="trainResult.mfr_analysis?.length" style="margin-top:16px;">
            <h3>厂商分析</h3>
            <div class="table-wrap">
              <table class="result-table">
                <thead><tr><th>厂商</th><th>平均综合评分</th><th>样本数</th><th>标准差</th></tr></thead>
                <tbody>
                  <tr v-for="m in trainResult.mfr_analysis" :key="m.MFR">
                    <td>{{ m.MFR }}</td><td>{{ m.mean }}</td><td>{{ m.count }}</td><td>{{ m.std ?? '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Grid Search -->
      <div class="section-title">3. Grid Search 超参数调优</div>
      <div class="card">
        <div class="grid-4" style="margin-bottom:12px;">
          <div><label class="form-label">n_estimators 起始</label><input type="number" class="form-input" v-model.number="gsParams.n_estimators_start" /></div>
          <div><label class="form-label">n_estimators 结束</label><input type="number" class="form-input" v-model.number="gsParams.n_estimators_end" /></div>
          <div><label class="form-label">n_estimators 步长</label><input type="number" class="form-input" v-model.number="gsParams.n_estimators_step" /></div>
        </div>
        <div class="grid-4" style="margin-bottom:12px;">
          <div><label class="form-label">max_samples 起始</label><input type="number" class="form-input" v-model.number="gsParams.max_samples_start" step="0.05" /></div>
          <div><label class="form-label">max_samples 结束</label><input type="number" class="form-input" v-model.number="gsParams.max_samples_end" step="0.05" /></div>
          <div><label class="form-label">max_samples 步长</label><input type="number" class="form-input" v-model.number="gsParams.max_samples_step" step="0.05" /></div>
        </div>
        <div class="grid-4" style="margin-bottom:12px;">
          <div><label class="form-label">max_features 起始</label><input type="number" class="form-input" v-model.number="gsParams.max_features_start" step="0.05" /></div>
          <div><label class="form-label">max_features 结束</label><input type="number" class="form-input" v-model.number="gsParams.max_features_end" step="0.05" /></div>
          <div><label class="form-label">max_features 步长</label><input type="number" class="form-input" v-model.number="gsParams.max_features_step" step="0.05" /></div>
        </div>
        <button class="btn tune-btn" :disabled="!dataInfo" @click="runGridSearch">执行 Grid Search</button>
        <div v-if="showGsSection && gsResult" style="margin-top:16px;">
          <div v-for="mod in gsResult.modules.filter(m => m.status === 'ok')" :key="mod.module" class="gs-module">
            <h3>{{ mod.module_name }}</h3>
            <div class="grid-4">
              <div class="score-card"><div class="label">最佳 AUC</div><div class="value">{{ mod.best_auc.toFixed(4) }}</div></div>
              <div class="score-card"><div class="label">最佳 n_estimators</div><div class="value">{{ mod.best_params.n_estimators }}</div></div>
              <div class="score-card"><div class="label">最佳 max_samples</div><div class="value">{{ mod.best_params.max_samples.toFixed(2) }}</div></div>
              <div class="score-card"><div class="label">最佳 max_features</div><div class="value">{{ mod.best_params.max_features.toFixed(2) }}</div></div>
            </div>
            <h4 style="margin-top:12px;">AUC 热力图</h4>
            <div v-for="(hm, mfKey) in mod.heatmaps" :key="mfKey" style="margin-bottom:12px;">
              <p style="color:#9ca3af;">max_features = {{ mfKey }}</p>
              <div class="heatmap-wrap">
                <table class="heatmap-table">
                  <thead><tr><th></th><th v-for="x in hm.x_labels" :key="x">n_est={{ x }}</th></tr></thead>
                  <tbody>
                    <tr v-for="(y, i) in hm.y_labels" :key="y">
                      <th>ms={{ y }}</th>
                      <td v-for="(val, j) in hm.matrix[i]" :key="j"
                        :style="{ background: `rgba(${Math.round(255*(1-(val/(mod.best_auc||1))))}, ${Math.round(255*(val/(mod.best_auc||1)))}, 80, 0.8)`, color: '#fff', fontWeight: 500 }">
                        {{ val.toFixed(4) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 4. 交叉验证 -->
      <div class="section-title">4. 模型验证 (K-Fold CV + AUC)</div>
      <div class="card">
        <div class="toolbar">
          <select class="form-select" v-model.number="cvFolds">
            <option :value="3">3 折</option><option :value="5">5 折</option><option :value="10">10 折</option>
          </select>
          <button class="btn tune-btn" :disabled="!dataInfo" @click="runCV">开始交叉验证</button>
        </div>
        <div v-if="showCVSection && cvResult" style="margin-top:16px;">
          <div class="grid-5">
            <div class="score-card"><div class="label">平均 AUC</div><div class="value">{{ cvResult.mean_auc?.toFixed(4) ?? '-' }}</div></div>
            <div class="score-card"><div class="label">AUC 标准差</div><div class="value">{{ cvResult.std_auc?.toFixed(4) ?? '-' }}</div></div>
            <div class="score-card"><div class="label">总体 AUC</div><div class="value">{{ cvResult.overall_auc?.toFixed(4) ?? '-' }}</div></div>
            <div class="score-card"><div class="label">拆除排名分位</div><div class="value">{{ cvResult.avg_rank_quantile ? (cvResult.avg_rank_quantile * 100).toFixed(1) + '%' : '-' }}</div></div>
            <div class="score-card"><div class="label">总体评价</div><div class="value" style="font-size:18px;">{{ cvResult.evaluation }}</div></div>
          </div>
          <div class="grid-2" style="margin-top:16px;">
            <div><h3>每折 AUC</h3><div ref="cvAucChartRef" class="chart" style="height:300px;"></div></div>
            <div>
              <h3>每折详细结果</h3>
              <div class="table-wrap">
                <table class="result-table">
                  <thead><tr><th>折</th><th>训练集</th><th>测试集</th><th>AUC</th><th>拆除数</th><th>排名分位</th></tr></thead>
                  <tbody>
                    <tr v-for="f in cvResult.fold_results" :key="f.fold">
                      <td>{{ f.fold }}</td><td>{{ f.train_size }}</td><td>{{ f.test_size }}</td>
                      <td><strong>{{ f.auc?.toFixed(4) ?? '-' }}</strong></td>
                      <td>{{ f.removed_count }}</td>
                      <td>{{ f.avg_rank_quantile ? (f.avg_rank_quantile * 100).toFixed(1) + '%' : '-' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 5. 预测 -->
      <div class="section-title">5. 数据预测</div>
      <div class="card">
        <div class="toolbar">
          <input ref="predictFileRef" type="file" accept=".csv" style="display:none" @change="onPredictFileChange" />
          <button class="btn" @click="triggerPredict">上传待预测 CSV</button>
        </div>
        <div v-if="showPredictSection && predictResult" style="margin-top:16px;">
          <div class="grid-4">
            <div class="score-card"><div class="label">预测样本数</div><div class="value">{{ predictResult.total_samples }}</div></div>
          </div>
          <div style="margin-top:8px;">
            <span v-for="(count, grade) in predictResult.grade_dist" :key="grade"
              class="grade-badge" :class="getGradeClass(grade)">{{ grade }}: {{ count }}</span>
          </div>
          <div class="table-wrap" style="margin-top:12px;">
            <table class="result-table">
              <thead><tr><th v-for="c in predictResult.columns" :key="c">{{ c }}</th><th>等级</th></tr></thead>
              <tbody>
                <tr v-for="(r, i) in predictResult.results.slice(0, 100)" :key="i">
                  <td v-for="c in predictResult.columns" :key="c">{{ r[c] ?? '-' }}</td>
                  <td><span class="grade-badge" :class="getGradeClass(r.grade || '')">{{ r.grade }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>

    <footer class="th-footer">终端健康度评价系统 · Isolation Forest + 多模块综合评分</footer>
  </div>
</template>

<style scoped>
/* ========== 基础变量 ========== */
.th-root {
  --bg: transparent;
  --card: rgba(17, 24, 39, 0.6);
  --border: rgba(0, 212, 255, 0.15);
  --text: #e4e7ed;
  --muted: rgba(255, 255, 255, 0.5);
  --primary: #3b82f6;
  --primary-dark: #2563eb;
  --gradient: linear-gradient(120deg, #1e40af, #3b82f6);
  --good: #22c55e;
  --warn: #f59e0b;
  --bad: #ef4444;
  --radius: 12px;
  --shadow: 0 4px 20px rgba(59, 130, 246, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  background: var(--bg);
  color: var(--text);
  font-size: 15px;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  min-height: 100%;
}
* { box-sizing: border-box; }

/* Header */
.th-header {
  padding: 24px 32px; background: var(--gradient); color: #fff;
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: var(--shadow); flex-wrap: wrap; gap: 8px;
}
.th-header h1 { margin: 0; font-size: 28px; font-weight: 600; }
.sub { font-size: 15px; opacity: .9; }
.server-info { display: flex; align-items: center; gap: 4px; font-size: 15px; }
.server-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
.server-dot.on { background: #4ade80; box-shadow: 0 0 6px #4ade80; }
.server-dot.off { background: #f87171; box-shadow: 0 0 6px #f87171; }

/* Main */
.th-main { padding: 24px 32px 48px; max-width: 1480px; margin: 0 auto; }

/* Section */
.section-title {
  margin: 32px 0 14px; font-size: 19px; font-weight: 600; color: var(--text);
  display: flex; align-items: center; gap: 10px;
}
.section-title::before { content: ""; width: 6px; height: 20px; background: var(--primary); border-radius: 3px; }

/* Cards */
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 22px 24px; box-shadow: var(--shadow);
}
.card h3 { margin: 0 0 8px; font-size: 18px; color: var(--text); }
.card h4 { margin: 6px 0; font-size: 15px; color: var(--muted); }

/* Toolbar */
.toolbar { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }
.file-name { font-size: 14px; color: var(--good); }
.status { font-size: 14px; color: var(--muted); margin-left: auto; }
.status.ok { color: var(--good); }
.status.err { color: var(--bad); }

/* Buttons */
.btn {
  display: inline-flex; align-items: center; gap: 6px; padding: 10px 20px;
  border-radius: 8px; border: none; cursor: pointer;
  background: var(--primary); color: #fff; font-size: 15px; font-weight: 500;
  transition: all .15s; white-space: nowrap; text-decoration: none;
}
.btn:hover { background: var(--primary-dark); }
.btn:disabled { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.3); cursor: not-allowed; }
.btn.ghost { background: rgba(59,130,246,0.1); color: #3b82f6; border: 1px solid rgba(59,130,246,0.2); }
.btn.ghost:hover { background: rgba(59,130,246,0.2); }
.btn.tune-btn { background: rgba(245,158,11,0.12); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.btn.tune-btn:hover { background: rgba(245,158,11,0.22); }

/* Grids */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
.grid-5 { display: grid; grid-template-columns: repeat(5, 1fr); gap: 18px; }
.grid-6 { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; }
@media (max-width: 980px) { .grid-2,.grid-4,.grid-5,.grid-6 { grid-template-columns: 1fr; } }

/* Score Card */
.score-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow);
  text-align: center;
}
.score-card .label { font-size: 15px; color: var(--muted); margin-bottom: 8px; }
.score-card .value {
  font-size: 36px; font-weight: 700; font-family: "SF Mono", Menlo, monospace; color: var(--text);
}
.sub-text { font-size: 13px; color: var(--muted); margin-top: 4px; }

/* Charts */
.chart { height: 300px; width: 100%; min-width: 300px; }

/* Tables */
.table-wrap { max-height: 400px; overflow: auto; }
.result-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.result-table th, .result-table td { padding: 10px 8px; text-align: center; border-bottom: 1px solid var(--border); }
.result-table thead th { background: rgba(59,130,246,0.08); color: #3b82f6; font-weight: 600; position: sticky; top: 0; }

/* Grade Badge */
.grade-badge { padding: 3px 10px; border-radius: 6px; font-size: 13px; font-weight: 500; margin-right: 6px; display: inline-block; }
.grade-b { background: rgba(34,197,94,0.15); color: #22c55e; }
.grade-c { background: rgba(245,158,11,0.15); color: #f59e0b; }
.grade-d { background: rgba(239,68,68,0.15); color: #ef4444; }
.grade-e { background: rgba(107,114,128,0.15); color: #9ca3af; }

/* Form */
.form-label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
.form-input {
  width: 100%; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border);
  background: rgba(0,0,0,0.4); color: var(--text); font-size: 14px;
}
.form-select {
  padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border);
  background: rgba(0,0,0,0.4); color: var(--text); font-size: 14px;
}

/* Heatmap */
.heatmap-wrap { overflow-x: auto; }
.heatmap-table { border-collapse: collapse; margin: 0 auto; }
.heatmap-table th, .heatmap-table td { padding: 6px 10px; text-align: center; font-size: 13px; border: 1px solid var(--border); }
.heatmap-table th { background: rgba(59,130,246,0.08); font-weight: 600; }

/* GS Module */
.gs-module { margin-top: 16px; padding: 12px; border: 1px solid var(--border); border-radius: 8px; }

/* Loading */
.loading-overlay {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(10,14,26,0.85); display: flex; align-items: center; justify-content: center;
  z-index: 999; font-size: 20px; color: var(--text);
}
.spinner {
  width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.1);
  border-top-color: var(--primary); border-radius: 50%;
  animation: spin .8s linear infinite; margin-right: 12px;
}
@keyframes spin { to { transform: rotate(360deg) } }

/* Footer */
.th-footer { text-align: center; color: var(--muted); font-size: 13px; padding: 24px; }
</style>