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
          <div class="legend-row"><span class="dot" style="background:#00d4ff"></span>核心实体</div>
          <div class="legend-row"><span class="dot" style="background:#00ff88"></span>关联实体</div>
          <div class="legend-row"><span class="dot" style="background:#ffaa00"></span>边缘实体</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'
import { fetchKnowledgeGraph } from '@/api/knowledge'

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let retryTimer: ReturnType<typeof setTimeout> | null = null

const props = defineProps<{
  categoryId?: string
  workspace?: string
}>()

const emit = defineEmits<{
  (e: 'back'): void
}>()

const graphStats = reactive({ entityCount: 0, relationCount: 0, coverage: 0 })

function formatNum(n: number) {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function buildFallbackData() {
  const nodes: any[] = [
    { name: '采集自愈知识库', symbolSize: 55, category: 0, itemStyle: { color: '#00d4ff' } },
    { name: '采集常见故障', symbolSize: 30, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '集中器', symbolSize: 28, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '采集器', symbolSize: 26, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '消缺典型案例', symbolSize: 26, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '低压台区', symbolSize: 24, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '冻结曲线', symbolSize: 22, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '故障排查', symbolSize: 24, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '远程研判', symbolSize: 22, category: 1, itemStyle: { color: '#00ff88' } },
    { name: '标准化作业', symbolSize: 20, category: 2, itemStyle: { color: '#ffaa00' } },
    { name: '七步法', symbolSize: 18, category: 2, itemStyle: { color: '#ffaa00' } },
    { name: '采集稳定性', symbolSize: 18, category: 2, itemStyle: { color: '#ffaa00' } },
    { name: '现场装置', symbolSize: 16, category: 2, itemStyle: { color: '#ffaa00' } },
  ]
  const links: any[] = [
    { source: '采集自愈知识库', target: '采集常见故障' },
    { source: '采集自愈知识库', target: '消缺典型案例' },
    { source: '采集自愈知识库', target: '低压台区' },
    { source: '采集自愈知识库', target: '集中器' },
    { source: '采集自愈知识库', target: '故障排查' },
    { source: '集中器', target: '采集器' },
    { source: '采集常见故障', target: '远程研判' },
    { source: '消缺典型案例', target: '七步法' },
    { source: '故障排查', target: '标准化作业' },
    { source: '低压台区', target: '冻结曲线' },
    { source: '低压台区', target: '采集稳定性' },
    { source: '远程研判', target: '标准化作业' },
    { source: '冻结曲线', target: '现场装置' },
  ]
  return { nodes, links }
}

function initChart(nodes: any[], links: any[]) {
  if (!chartRef.value) return
  const w = chartRef.value.clientWidth
  if (w <= 0) {
    retryTimer = setTimeout(() => initChart(nodes, links), 200)
    return
  }

  if (chartInstance) {
    chartInstance.dispose()
  }
  chartInstance = echarts.init(chartRef.value)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#fff', fontSize: 12 },
      formatter: (p: any) => {
        if (p.dataType === 'node') return p.name || ''
        if (p.dataType === 'edge') return `${p.data.source} → ${p.data.target}`
        return ''
      }
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
        color: 'rgba(255,255,255,0.8)',
        formatter: (p: any) => {
          const n = p.name || ''
          return n.length > 8 ? n.slice(0, 8) + '..' : n
        }
      },
      force: {
        repulsion: 200,
        edgeLength: [40, 120],
        gravity: 0.08
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

async function loadGraph() {
  try {
    // When workspace is specified, query Memgraph via backend API
    const data = await fetchKnowledgeGraph(props.workspace || undefined)
    if (data && data.nodes && data.nodes.length > 0) {
      const s = data.stats
      if (s) {
        graphStats.entityCount = s.entity_count
        graphStats.relationCount = s.relation_count
        graphStats.coverage = s.coverage
      }
      initChart(data.nodes, data.links)
      return
    }
  } catch (e) {
    console.warn('[KnowledgeGraph] Failed to load from backend:', e)
  }

  // Fallback to hardcoded data
  const fb = buildFallbackData()
  initChart(fb.nodes, fb.links)
  graphStats.entityCount = 36584
  graphStats.relationCount = 128652
  graphStats.coverage = 89.7
}

onMounted(async () => {
  await loadGraph()
  window.addEventListener('resize', handleResize)
})

watch(() => props.workspace, () => {
  loadGraph()
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
