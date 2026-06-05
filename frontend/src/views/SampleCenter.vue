<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import StatsCard from '@/components/StatsCard.vue'
import { getSampleStatistic, getSampleTrend, type SampleStatistic } from '@/api/sample'
import * as echarts from 'echarts'

const router = useRouter()

const activeTab = ref('all')
const domainChartRef = ref<HTMLElement | null>(null)
const qualityChartRef = ref<HTMLElement | null>(null)
const typeChartRef = ref<HTMLElement | null>(null)
const trendChartRef = ref<HTMLElement | null>(null)

let domainChart: echarts.ECharts | null = null
let qualityChart: echarts.ECharts | null = null
let typeChart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null

const statsData = ref([
  { title: '样本总量', value: '-', unit: '条', icon: 'sample-total' },
  { title: '样本集数量', value: '-', unit: '个', icon: 'sample-set' },
  { title: '已标注样本', value: '-', unit: '条', icon: 'sample-labeled', change: { value: '', type: 'up' as const } },
  { title: '高质量样本', value: '-', unit: '条', icon: 'sample-quality', change: { value: '', type: 'up' as const } },
  { title: '样本覆盖领域', value: '-', unit: '大类', icon: 'sample-domain' },
  { title: '样本质量等级', value: '-', unit: '', icon: 'sample-score' }
])

const domainData = ref([
  { name: '计量领域', percent: 28.4, count: 2544612, color: '#00d4ff' },
  { name: '采集运维领域', percent: 23.7, count: 2122351, color: '#00ff88' },
  { name: '电网运维领域', percent: 17.2, count: 1541228, color: '#a855f7' },
  { name: '设备管理领域', percent: 13.6, count: 1220885, color: '#ff6b6b' },
  { name: '市场与交易领域', percent: 9.7, count: 872145, color: '#ffd93d' },
  { name: '其他领域', percent: 7.4, count: 660120, color: '#6366f1' }
])

const qualityData = ref([
  { name: '优质', code: '01', percent: 70.6, count: 6325718, color: '#00d4ff' },
  { name: '良好', code: '02', percent: 22.8, count: 2043652, color: '#00ff88' },
  { name: '一般', code: '03', percent: 5.1, count: 456972, color: '#ffd93d' },
  { name: '较差', code: '04', percent: 1.5, count: 135999, color: '#ff6b6b' }
])

const typeData = ref<{ name: string; count: number; percent: number }[]>([])

const collectionStatus = [
  { name: '采集进行中', value: 18, unit: '个样本集', color: '#00d4ff' },
  { name: '待标注', value: 253417, unit: '条', color: '#ffaa00' },
  { name: '标注中', value: 128652, unit: '条', color: '#a855f7' },
  { name: '待质检', value: 86214, unit: '条', color: '#00ff88' },
  { name: '质检中', value: 65328, unit: '条', color: '#f472b6' },
  { name: '已完成', value: 7856214, unit: '条', color: '#00ff88' }
]

const tableData = ref([
  { name: '线损异常诊断样本集', domain: '计量领域', count: 512865, progress: 100, quality: 5, updateTime: '2026-04-24', status: '已完成' },
  { name: '采集异常识别样本集', domain: '采集运维领域', count: 468215, progress: 96, quality: 5, updateTime: '2026-04-24', status: '已完成' },
  { name: '电能表故障识别样本集', domain: '设备管理领域', count: 386542, progress: 93, quality: 5, updateTime: '2026-04-23', status: '已完成' },
  { name: '负荷预测样本集', domain: '电网运维领域', count: 612354, progress: 100, quality: 4, updateTime: '2026-04-23', status: '已完成' },
  { name: '作业风险识别样本集', domain: '电网运维领域', count: 298632, progress: 88, quality: 4, updateTime: '2026-04-22', status: '标注中' },
  { name: '市场交易预测样本集', domain: '市场与交易领域', count: 275641, progress: 85, quality: 4, updateTime: '2026-04-22', status: '标注中' }
])

const hotWords = [
  { text: '线损异常', size: 32, color: '#00d4ff' },
  { text: '采集异常', size: 28, color: '#a855f7' },
  { text: '电能表', size: 24, color: '#00ff88' },
  { text: '负荷曲线', size: 22, color: '#ffaa00' },
  { text: '三相不平衡', size: 18, color: '#ff5555' },
  { text: '低电压', size: 16, color: '#faad14' },
  { text: '失压', size: 16, color: '#f472b6' },
  { text: '谐波畸变', size: 15, color: '#00d4ff' },
  { text: '故障异常', size: 20, color: '#a855f7' },
  { text: '计量异常', size: 18, color: '#00ff88' },
  { text: '停电事件', size: 14, color: '#ffaa00' },
  { text: '高损台区', size: 16, color: '#ff5555' },
  { text: '采集失败', size: 15, color: '#faad14' },
  { text: '电表异常', size: 14, color: '#f472b6' },
  { text: '电压异常', size: 13, color: '#00d4ff' },
  { text: '作业安全', size: 14, color: '#a855f7' }
]

const monthNewCount = ref(0)
const monthQualityCount = ref(0)

function formatNumber(n: number): string {
  return n.toLocaleString()
}

const domainColors = ['#00d4ff', '#00ff88', '#a855f7', '#ff6b6b', '#ffd93d', '#6366f1', '#f472b6', '#34d399']
const qualityColors = ['#00d4ff', '#00ff88', '#ffd93d', '#ff6b6b']

async function loadStatistic() {
  try {
    const data = await getSampleStatistic()

    // 更新顶部统计卡片
    const total = data.sampleCount || 0
    const labeled = data.labeledCount || 0
    const highQuality = data.highQualityCount || 0
    const labelRate = total > 0 ? ((labeled / total) * 100).toFixed(1) : '0'
    const qualityRate = total > 0 ? ((highQuality / total) * 100).toFixed(1) : '0'

    const avgQualityScore = data.avgQualityScore || 0
    const avgQualityName = data.avgQualityName || '未评分'

    statsData.value = [
      { title: '样本总量', value: formatNumber(total), unit: '条', icon: 'sample-total' },
      { title: '样本集数量', value: formatNumber(data.setCount || 0), unit: '个', icon: 'sample-set' },
      { title: '已标注样本', value: formatNumber(labeled), unit: '条', icon: 'sample-labeled', change: { value: `标注率 ${labelRate}%`, type: 'up' as const } },
      { title: '高质量样本', value: formatNumber(highQuality), unit: '条', icon: 'sample-quality', change: { value: `占比 ${qualityRate}%`, type: 'up' as const } },
      { title: '样本覆盖领域', value: String(data.domainCount || 0), unit: '大类', icon: 'sample-domain' },
      { title: '平均样本质量', value: avgQualityScore.toFixed(1), unit: avgQualityName, icon: 'sample-score' }
    ]

    // 更新领域分布
    if (data.domainDistribution && data.domainDistribution.length > 0) {
      const domainTotal = data.domainDistribution.reduce((sum, d) => sum + (d.sampleCount || 0), 0)
      domainData.value = data.domainDistribution.map((d, idx) => ({
        name: d.domain,
        percent: domainTotal > 0 ? parseFloat(((d.sampleCount / domainTotal) * 100).toFixed(1)) : 0,
        count: d.sampleCount || 0,
        color: domainColors[idx % domainColors.length]
      }))
    }

    // 更新质量分布
    if (data.qualityDistribution && data.qualityDistribution.length > 0) {
      const qualityTotal = data.qualityDistribution.reduce((sum, d) => sum + (d.count || 0), 0)
      const codeMap: Record<string, string> = { '优质': '01', '良好': '02', '一般': '03', '较差': '04' }
      qualityData.value = data.qualityDistribution.map((d, idx) => ({
        name: d.qualityName,
        code: codeMap[d.qualityName] || '',
        percent: qualityTotal > 0 ? parseFloat(((d.count / qualityTotal) * 100).toFixed(1)) : 0,
        count: d.count || 0,
        color: qualityColors[idx % qualityColors.length]
      }))
    }

    // 更新类型分布
    if (data.typeDistribution && data.typeDistribution.length > 0) {
      const typeTotal = data.typeDistribution.reduce((sum, d) => sum + (d.count || 0), 0)
      typeData.value = data.typeDistribution.map((d) => ({
        name: d.typeName,
        count: d.count || 0,
        percent: typeTotal > 0 ? parseFloat(((d.count / typeTotal) * 100).toFixed(1)) : 0
      }))
    }

    // 更新趋势摘要
    monthNewCount.value = data.monthNewCount || 0
    monthQualityCount.value = data.monthQualityCount || 0

    // 重新渲染图表
    await nextTick()
    updateCharts()
  } catch (e) {
    console.error('加载统计数据失败:', e)
  }
}

async function loadTrend() {
  try {
    const data = await getSampleTrend()
    if (data.months && data.months.length > 0 && trendChart) {
      trendChart.setOption({
        xAxis: { data: data.months },
        series: [{ data: data.counts }]
      })
    }
  } catch (e) {
    console.error('加载趋势数据失败:', e)
  }
}

function initCharts() {
  if (domainChartRef.value) {
    domainChart = echarts.init(domainChartRef.value)
    domainChart.setOption({
      series: [{
        type: 'pie',
        radius: ['50%', '70%'],
        label: {
          show: true,
          position: 'center',
          formatter: `{total|${formatNumber(domainData.value.reduce((s, d) => s + d.count, 0))}}\n{label|样本总量}`,
          rich: {
            total: { fontSize: 20, fontWeight: 'bold', color: '#ffffff' },
            label: { fontSize: 12, color: 'rgba(255,255,255,0.5)' }
          }
        },
        data: domainData.value.map(item => ({
          value: item.count,
          name: item.name,
          itemStyle: { color: item.color }
        }))
      }]
    })
  }

  if (qualityChartRef.value) {
    qualityChart = echarts.init(qualityChartRef.value)
    qualityChart.setOption({
      series: [{
        type: 'pie',
        radius: ['50%', '70%'],
        label: {
          show: true,
          position: 'center',
          formatter: '{total|样本质量}\n{label|分布}',
          rich: {
            total: { fontSize: 16, fontWeight: 'bold', color: '#ffffff' },
            label: { fontSize: 12, color: 'rgba(255,255,255,0.5)' }
          }
        },
        data: qualityData.value.map(item => ({
          value: item.count,
          name: item.name,
          itemStyle: { color: item.color }
        }))
      }]
    })
  }

  if (typeChartRef.value) {
    typeChart = echarts.init(typeChartRef.value)
    updateTypeChartOption()
  }

  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value)
    trendChart.setOption({
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        data: ['03-26', '03-31', '04-05', '04-10', '04-15', '04-20', '04-24'],
        axisLine: { lineStyle: { color: 'rgba(0,212,255,0.2)' } },
        axisLabel: { color: 'rgba(255,255,255,0.5)' }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(0,212,255,0.1)' } },
        axisLabel: { color: 'rgba(255,255,255,0.5)' }
      },
      series: [{
        type: 'line',
        smooth: true,
        data: [250, 320, 380, 450, 620, 750, 890],
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 212, 255, 0.3)' },
              { offset: 1, color: 'rgba(0, 212, 255, 0.05)' }
            ]
          }
        },
        itemStyle: { color: '#00d4ff' },
        lineStyle: { width: 2 }
      }]
    })
  }
}

function updateCharts() {
  if (domainChart) {
    domainChart.setOption({
      series: [{
        type: 'pie',
        radius: ['50%', '70%'],
        label: {
          show: true,
          position: 'center',
          formatter: `{total|${formatNumber(domainData.value.reduce((s, d) => s + d.count, 0))}}\n{label|样本总量}`,
          rich: {
            total: { fontSize: 20, fontWeight: 'bold', color: '#ffffff' },
            label: { fontSize: 12, color: 'rgba(255,255,255,0.5)' }
          }
        },
        data: domainData.value.map(item => ({
          value: item.count,
          name: item.name,
          itemStyle: { color: item.color }
        }))
      }]
    })
  }
  if (qualityChart) {
    qualityChart.setOption({
      series: [{
        type: 'pie',
        radius: ['50%', '70%'],
        label: {
          show: true,
          position: 'center',
          formatter: '{total|样本质量}\n{label|分布}',
          rich: {
            total: { fontSize: 16, fontWeight: 'bold', color: '#ffffff' },
            label: { fontSize: 12, color: 'rgba(255,255,255,0.5)' }
          }
        },
        data: qualityData.value.map(item => ({
          value: item.count,
          name: item.name,
          itemStyle: { color: item.color }
        }))
      }]
    })
  }
  if (typeChart && typeData.value.length > 0) {
    updateTypeChartOption()
  }
}

const typeColors = ['#00d4ff', '#00ff88', '#a855f7', '#ff6b6b', '#ffd93d', '#6366f1']

function updateTypeChartOption() {
  if (!typeChart) return
  const data = typeData.value.slice().reverse()
  typeChart.setOption({
    grid: { left: '3%', right: '15%', bottom: '3%', top: '5%', containLabel: true },
    xAxis: {
      type: 'value',
      show: false
    },
    yAxis: {
      type: 'category',
      data: data.map(d => d.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: 'rgba(255,255,255,0.7)', fontSize: 13 }
    },
    series: [{
      type: 'bar',
      data: data.map((d, idx) => ({
        value: d.count,
        itemStyle: {
          color: typeColors[idx % typeColors.length],
          borderRadius: [0, 4, 4, 0]
        }
      })),
      barWidth: '60%',
      label: {
        show: true,
        position: 'right',
        color: 'rgba(255,255,255,0.7)',
        fontSize: 12,
        formatter: (params: any) => {
          const item = data[params.dataIndex]
          return item ? `${item.percent}%` : ''
        }
      }
    }]
  })
}

function handleResize() {
  domainChart?.resize()
  qualityChart?.resize()
  typeChart?.resize()
  trendChart?.resize()
}

onMounted(() => {
  initCharts()
  loadStatistic()
  loadTrend()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  domainChart?.dispose()
  qualityChart?.dispose()
  typeChart?.dispose()
  trendChart?.dispose()
})
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="样本中心" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="page-header">
          <div class="page-title">
            <h2>样本中心</h2>
            <p>构建高质量训练样本体系，支撑模型训练与业务应用</p>
          </div>
          <div class="page-actions">
            <el-button type="primary" @click="router.push('/sample-set')">样本集管理</el-button>
          </div>
        </div>

        <div class="stats-grid">
          <StatsCard
            v-for="stat in statsData"
            :key="stat.title"
            :title="stat.title"
            :value="stat.value"
            :unit="stat.unit"
            :icon="stat.icon"
            :change="stat.change"
          />
        </div>

        <div class="chart-row">
          <div class="chart-card">
            <h3 class="card-title">样本领域分布</h3>
            <div ref="domainChartRef" class="chart-container"></div>
            <div class="legend-list">
              <div class="legend-item" v-for="item in domainData" :key="item.name">
                <span class="legend-dot" :style="{ background: item.color }"></span>
                <span>{{ item.name }}</span>
                <span class="value">{{ item.percent }}% {{ item.count.toLocaleString() }} 条</span>
              </div>
            </div>
          </div>
          <div class="chart-card">
            <h3 class="card-title">样本质量分布</h3>
            <div ref="qualityChartRef" class="chart-container"></div>
            <div class="legend-list">
              <div class="legend-item" v-for="item in qualityData" :key="item.name">
                <span class="legend-dot" :style="{ background: item.color }"></span>
                <span>{{ item.name }}</span>
                <span class="value">{{ item.percent }}% {{ item.count.toLocaleString() }} 条</span>
              </div>
            </div>
          </div>
          <div class="chart-card">
            <h3 class="card-title">样本类型分布</h3>
            <div ref="typeChartRef" class="chart-container"></div>
            <div class="type-legend-list">
              <div class="legend-item" v-for="item in typeData" :key="item.name">
                <span class="legend-dot" :style="{ background: typeColors[typeData.indexOf(item) % typeColors.length] }"></span>
                <span>{{ item.name }}</span>
                <span class="value">{{ item.percent }}% {{ item.count.toLocaleString() }} 条</span>
              </div>
            </div>
          </div>
        </div>
        <div class="chart-row-full">
          <div class="chart-card">
            <h3 class="card-title">样本增长趋势</h3>
            <div ref="trendChartRef" class="chart-container-trend"></div>
            <div class="trend-summary">
              <div class="summary-item">
                <div class="label">本月新增样本</div>
                <div class="value">{{ formatNumber(monthNewCount) }} <span class="unit">条</span></div>
              </div>
              <div class="summary-item">
                <div class="label">本月质量样本</div>
                <div class="value">{{ formatNumber(monthQualityCount) }} <span class="unit">条</span></div>
                <div class="sub" v-if="monthNewCount > 0">占新增 {{ ((monthQualityCount / monthNewCount) * 100).toFixed(1) }}%</div>
              </div>
            </div>
          </div>
        </div>

        <div class="section-card">
          <div class="section-header">
            <h3>样本采集状态</h3>
            <el-button text type="primary">查看采集任务 →</el-button>
          </div>
          <div class="status-grid">
            <div class="status-card" v-for="status in collectionStatus" :key="status.name">
              <div class="status-dot" :style="{ background: status.color }"></div>
              <div class="status-info">
                <div class="status-name">{{ status.name }}</div>
                <div class="status-value">{{ status.value.toLocaleString() }} <span class="unit">{{ status.unit }}</span></div>
              </div>
            </div>
          </div>
        </div>

        <!-- 样本集管理和样本标签热词暂时隐藏 -->
        <!--
        <div class="bottom-row">
          <div class="table-card">
            <h3 class="card-title">样本集管理</h3>
            <el-tabs v-model="activeTab">
              <el-tab-pane label="全部样本集" name="all"></el-tab-pane>
              <el-tab-pane label="我创建的" name="created"></el-tab-pane>
              <el-tab-pane label="我参与的" name="involved"></el-tab-pane>
              <el-tab-pane label="重点样本集" name="key"></el-tab-pane>
            </el-tabs>
            <el-table :data="tableData" style="width: 100%">
              <el-table-column prop="name" label="样本集名称" min-width="180" />
              <el-table-column prop="domain" label="所属领域" width="120" />
              <el-table-column prop="count" label="样本数量" width="120">
                <template #default="{ row }">{{ row.count.toLocaleString() }} 条</template>
              </el-table-column>
              <el-table-column prop="progress" label="标注进度" width="140">
                <template #default="{ row }">
                  <el-progress :percentage="row.progress" :color="row.progress >= 100 ? '#00ff88' : '#00d4ff'" />
                </template>
              </el-table-column>
              <el-table-column prop="quality" label="质量等级" width="140">
                <template #default="{ row }">
                  <span :style="{ color: row.quality === '优质' ? '#00d4ff' : row.quality === '良好' ? '#67c23a' : row.quality === '一般' ? '#e6a23c' : '#f56c6c' }">{{ row.quality || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="updateTime" label="更新时间" width="120" />
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.status === '已完成' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150">
                <template #default>
                  <el-button text type="primary" size="small">查看</el-button>
                  <el-button text type="primary" size="small">管理</el-button>
                  <el-button text type="primary" size="small">更多</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="table-footer">
              <span>共 532 条</span>
              <el-pagination layout="prev, pager, next" :total="532" :page-size="20" />
            </div>
          </div>
          <div class="word-cloud-card">
            <div class="cloud-header">
              <h3>样本标签热词</h3>
              <el-button text type="primary">更多 →</el-button>
            </div>
            <div class="word-cloud">
              <span class="word" v-for="word in hotWords" :key="word.text" :style="{ fontSize: word.size + 'px', color: word.color }">
                {{ word.text }}
              </span>
            </div>
          </div>
        </div>
        -->

        <div class="footer-note">
          <div class="quality-explain">
            <span>质量等级说明：</span>
            <span class="star-explain"><span style="color:#f5a623">★★★★★</span> 优质</span>
            <span class="star-explain"><span style="color:#f5a623">★★★★</span><span style="color:rgba(255,255,255,0.15)">★</span> 良好</span>
            <span class="star-explain"><span style="color:#f5a623">★★★</span><span style="color:rgba(255,255,255,0.15)">★★</span> 一般</span>
            <span class="star-explain"><span style="color:#f5a623">★★</span><span style="color:rgba(255,255,255,0.15)">★★★</span> 较差</span>
          </div>
          <div class="update-info">
            数据每日凌晨更新，更新时间：2026-04-24 02:00:00
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped lang="scss">
.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 20px 24px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
}

.page-title h2 {
  font-size: 22px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 8px 0;
}

.page-title p {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.page-actions {
  display: flex;
  gap: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.chart-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.chart-row-full {
  margin-bottom: 20px;
}

.chart-row-full .chart-card {
  width: 100%;
}

.chart-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 16px 0;
}

.chart-container {
  width: 100%;
  height: 200px;
}

.chart-container-trend {
  width: 100%;
  height: 250px;
}

.type-legend-list {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.legend-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-item .value {
  margin-left: auto;
  color: #fff;
  font-weight: 500;
}

.trend-summary {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(0, 212, 255, 0.15);
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

.summary-item .label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 4px;
}

.summary-item .value {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.summary-item .unit {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.summary-item .trend-up {
  font-size: 12px;
  color: #00ff88;
}

.summary-item .sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.section-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  margin: 0;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}

.status-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(0, 212, 255, 0.1);
  border-radius: 10px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: all 0.3s ease;
}

.status-card:hover {
  border-color: rgba(0, 212, 255, 0.3);
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.1);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 8px currentColor;
}

.status-info .status-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 4px;
}

.status-info .status-value {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

.status-info .unit {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.bottom-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.table-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;

  :deep(.el-table) {
    --el-table-bg-color: transparent;
    --el-table-tr-bg-color: transparent;
    --el-table-header-bg-color: rgba(0, 212, 255, 0.08);
    --el-table-row-hover-bg-color: rgba(0, 212, 255, 0.08);
    --el-table-border-color: rgba(0, 212, 255, 0.12);
    --el-table-text-color: rgba(255, 255, 255, 0.85);
    --el-table-header-text-color: rgba(255, 255, 255, 0.65);
    background-color: transparent;

    th.el-table__cell {
      background: rgba(0, 212, 255, 0.08);
      color: rgba(255, 255, 255, 0.65);
      font-weight: 600;
      border-bottom: 1px solid rgba(0, 212, 255, 0.15);
    }

    td.el-table__cell {
      background: transparent;
      color: rgba(255, 255, 255, 0.85);
      border-bottom: 1px solid rgba(0, 212, 255, 0.1);
    }

    tr {
      background-color: transparent;
    }

    .el-table__body tr:hover > td.el-table__cell {
      background: rgba(0, 212, 255, 0.08);
    }

    .el-table__inner-wrapper::before {
      background-color: rgba(0, 212, 255, 0.12);
    }
  }

  :deep(.el-pagination) {
    --el-pagination-bg-color: transparent;
    --el-pagination-text-color: rgba(255, 255, 255, 0.6);
    --el-pagination-button-bg-color: rgba(255, 255, 255, 0.05);
    --el-pagination-button-color: rgba(255, 255, 255, 0.6);
    --el-pagination-hover-color: #00d4ff;
  }
}

.stars {
  display: flex;
  gap: 2px;
}

.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(0, 212, 255, 0.15);
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

.word-cloud-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
}

.cloud-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.cloud-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  margin: 0;
}

.word-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

.word {
  cursor: pointer;
  transition: all 0.3s;
  text-shadow: 0 0 10px currentColor;
}

.word:hover {
  transform: scale(1.15);
  text-shadow: 0 0 20px currentColor;
}

.footer-note {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.quality-explain {
  display: flex;
  gap: 16px;
  align-items: center;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.star-explain {
  display: flex;
  align-items: center;
  gap: 3px;
}

.update-info {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}
</style>
