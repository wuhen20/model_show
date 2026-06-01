<template>
  <div class="knowledge-graph-card">
    <div class="graph-title-row">
      <div class="card-title">
        <template v-if="categoryId">{{ categoryId }} · </template>知识图谱
      </div>
      <el-button v-if="categoryId" text size="small" class="graph-back-btn" @click="emit('back')">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6"/>
        </svg>
        返回全部
      </el-button>
    </div>
    <div class="graph-body">
      <div ref="chartRef" class="graph-chart"></div>
      <div class="graph-sidebar">
        <div class="stat-block">
          <div class="stat-num">{{ formatNum(graphStats.entityCount) }}</div>
          <div class="stat-label">实体总数</div>
        </div>
        <div class="stat-block">
          <div class="stat-num">{{ formatNum(graphStats.relationCount) }}</div>
          <div class="stat-label">关系总数</div>
        </div>
        <div class="stat-block">
          <div class="stat-num">{{ graphStats.coverage }}%</div>
          <div class="stat-label">图谱覆盖率</div>
        </div>
        <div class="graph-legend">
          <div class="legend-row"><span class="dot" style="background:#00d4ff"></span>知识库</div>
          <div class="legend-row"><span class="dot" style="background:#00ff88"></span>子分类</div>
          <div class="legend-row"><span class="dot" style="background:#ffaa00"></span>知识类型</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let retryTimer: ReturnType<typeof setTimeout> | null = null

const props = defineProps<{
  categoryId?: string
}>()

const emit = defineEmits<{
  (e: 'back'): void
}>()

const graphStats = reactive({ entityCount: 36584, relationCount: 128652, coverage: 89.7 })

function formatNum(n: number) {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function buildGraphData() {
  const nodes: any[] = [
    { name: '计量营销专业知识库', symbolSize: 58, category: 0, itemStyle: { color: '#00d4ff' } },
    { name: '计量数字讲师', symbolSize: 48, category: 0, itemStyle: { color: '#00d4ff' } },
    { name: '专家系统知识库', symbolSize: 36, category: 0, itemStyle: { color: '#00d4ff' } },
    { name: '装表接电知识库', symbolSize: 28, category: 0, itemStyle: { color: '#00d4ff' } },
    { name: '采集自愈知识库', symbolSize: 24, category: 0, itemStyle: { color: '#00d4ff' } },

    { name: '工作指导', symbolSize: 32, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '作业指导', symbolSize: 28, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '技术文件', symbolSize: 26, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '检定规程', symbolSize: 30, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '管理制度', symbolSize: 24, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '培训资料', symbolSize: 22, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '国家电网企业标准', symbolSize: 26, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '行业标准', symbolSize: 24, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '电力行业标准', symbolSize: 22, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '课程资源', symbolSize: 28, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '考试题库', symbolSize: 26, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '实操指南', symbolSize: 22, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '专家规则', symbolSize: 24, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '故障案例', symbolSize: 22, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '装表接电', symbolSize: 18, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '采集运维', symbolSize: 18, category: 1, itemStyle: { color: '#00ff88' } },

    { name: '国家标准', symbolSize: 14, category: 2, itemStyle: { color: '#ffaa00' } },
    { name: '国家计量规程', symbolSize: 14, category: 2, itemStyle: { color: '#ffaa00' } },
    { name: '企业标准', symbolSize: 12, category: 2, itemStyle: { color: '#ffaa00' } },
    { name: '技术规范', symbolSize: 12, category: 2, itemStyle: { color: '#ffaa00' } },
    { name: '法律法规', symbolSize: 12, category: 2, itemStyle: { color: '#ffaa00' } },
    { name: '操作手册', symbolSize: 10, category: 2, itemStyle: { color: '#ffaa00' } },
    { name: '培训题库', symbolSize: 10, category: 2, itemStyle: { color: '#ffaa00' } },
    { name: '计量规范', symbolSize: 10, category: 2, itemStyle: { color: '#ffaa00' } },
  ]

  const links: any[] = [
    { source: '计量营销专业知识库', target: '工作指导' },
    { source: '计量营销专业知识库', target: '检定规程' },
    { source: '计量营销专业知识库', target: '国家电网企业标准' },
    { source: '计量营销专业知识库', target: '行业标准' },
    { source: '计量营销专业知识库', target: '管理制度' },
    { source: '计量营销专业知识库', target: '技术文件' },

    { source: '计量数字讲师', target: '课程资源' },
    { source: '计量数字讲师', target: '考试题库' },
    { source: '计量数字讲师', target: '实操指南' },
    { source: '计量数字讲师', target: '培训资料' },
    { source: '计量数字讲师', target: '作业指导' },

    { source: '专家系统知识库', target: '专家规则' },
    { source: '专家系统知识库', target: '故障案例' },
    { source: '专家系统知识库', target: '检定规程' },

    { source: '装表接电知识库', target: '装表接电' },
    { source: '装表接电知识库', target: '作业指导' },

    { source: '采集自愈知识库', target: '采集运维' },
    { source: '采集自愈知识库', target: '技术文件' },

    { source: '行业标准', target: '国家标准' },
    { source: '行业标准', target: '电力行业标准' },
    { source: '国家电网企业标准', target: '企业标准' },
    { source: '国家电网企业标准', target: '技术规范' },
    { source: '检定规程', target: '国家计量规程' },
    { source: '检定规程', target: '计量规范' },
    { source: '管理制度', target: '法律法规' },
    { source: '工作指导', target: '操作手册' },
    { source: '考试题库', target: '培训题库' },

    { source: '电力行业标准', target: '国家标准' },
    { source: '技术规范', target: '国家标准' },
    { source: '故障案例', target: '检定规程' },
  ]

  return { nodes, links }
}

function initChart() {
  if (!chartRef.value) return
  const w = chartRef.value.clientWidth
  if (w <= 0) {
    retryTimer = setTimeout(initChart, 200)
    return
  }

  chartInstance = echarts.init(chartRef.value)
  const { nodes, links } = buildGraphData()

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#fff', fontSize: 12 }
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes,
      links: links,
      roam: true,
      draggable: true,
      label: {
        show: true,
        position: 'bottom',
        fontSize: 10,
        color: 'rgba(255,255,255,0.75)',
        formatter: (p: any) => {
          const n = p.name || ''
          return n.length > 6 ? n.slice(0, 6) + '..' : n
        }
      },
      force: {
        repulsion: 180,
        edgeLength: [50, 100],
        gravity: 0.12
      },
      lineStyle: {
        color: 'rgba(0,212,255,0.3)',
        curveness: 0.15,
        width: 1.5
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3, color: '#00d4ff' }
      }
    }]
  }
  chartInstance.setOption(option)
}

onMounted(async () => {
  try {
    const resp = await fetch('/api/knowledge/graph')
    const json = await resp.json()
    if (json.code === 0 && json.data) {
      const s = json.data.stats
      if (s) {
        graphStats.entityCount = s.entity_count
        graphStats.relationCount = s.relation_count
        graphStats.coverage = s.coverage
      }
    }
  } catch {}

  initChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  if (retryTimer) clearTimeout(retryTimer)
  if (chartInstance) chartInstance.dispose()
  window.removeEventListener('resize', handleResize)
})

const handleResize = () => { if (chartInstance) chartInstance.resize() }
</script>

<style scoped>
.knowledge-graph-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 18px;
  height: 100%;
  box-sizing: border-box;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 12px 0;
}

.graph-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0;
}

.graph-title-row .card-title {
  margin: 0;
}

.graph-back-btn {
  color: #00d4ff !important;
  font-size: 12px;
  padding: 4px 8px;
  flex-shrink: 0;
}

.graph-body {
  display: flex;
  gap: 12px;
}

.graph-chart {
  flex: 1;
  height: 300px;
  min-width: 100px;
}

.graph-sidebar {
  width: 130px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.stat-block {
  padding: 10px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  border: 1px solid rgba(0, 212, 255, 0.08);
}

.stat-num {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  line-height: 1.2;
}

.stat-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 4px;
}

.graph-legend {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid rgba(0, 212, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.55);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
