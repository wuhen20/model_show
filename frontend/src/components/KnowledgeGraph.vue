<template>
  <div class="knowledge-graph-card">
    <div class="graph-title-row">
      <div class="card-title">
        <template v-if="categoryId">{{ categoryId }} · </template>知识图谱
      </div>
      <div class="graph-title-actions">
        <el-button text size="small" class="graph-detail-btn" @click="showDetail = true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:3px">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
          查看详情
        </el-button>
        <el-button v-if="categoryId" text size="small" class="graph-back-btn" @click="emit('back')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M15 18l-6-6 6-6"/>
          </svg>
          返回全部
        </el-button>
      </div>
    </div>

    <div class="graph-body">
      <div ref="chartRef" class="graph-chart"></div>
      <div class="graph-sidebar">
        <div class="stat-block">
          <div class="stat-num">{{ formatNum(graphStats.entityCount) }}</div>
          <div class="stat-label">
            实体总数
            <span v-if="graphStats.renderedNodes && graphStats.renderedNodes < graphStats.entityCount"
              class="rendered-hint">已渲染{{ graphStats.renderedNodes }}</span>
          </div>
        </div>

        <div class="stat-block">
          <div class="stat-num">{{ formatNum(graphStats.relationCount) }}</div>
          <div class="stat-label">
            关系总数
            <span v-if="graphStats.renderedLinks && graphStats.renderedLinks < graphStats.relationCount"
              class="rendered-hint">已渲染{{ graphStats.renderedLinks }}</span>
          </div>
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

    <!-- Graph Detail Modal -->
    <GraphDetailModal
      v-model="showDetail"
      :title="detailTitle"
      :nodes="detailNodes"
      :links="detailLinks"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'
import { fetchKnowledgeGraph } from '@/api/knowledge'
import type { GraphNode, GraphLink } from '@/api/knowledge'
import GraphDetailModal from '@/components/GraphDetailModal.vue'

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let retryTimer: ReturnType<typeof setTimeout> | null = null

const props = defineProps<{
  categoryId?: string
  workspace?: string
  kbName?: string
}>()

const emit = defineEmits<{
  (e: 'back'): void
}>()

const graphStats = reactive({
  entityCount: 0, relationCount: 0, coverage: 0,
  renderedNodes: 0, renderedLinks: 0,  // actually rendered in chart
})

// Store full graph data for the detail modal
const graphNodes = ref<GraphNode[]>([])
const graphLinks = ref<GraphLink[]>([])
const detailNodes = ref<GraphNode[]>([])   // full data for detail modal
const detailLinks = ref<GraphLink[]>([])
const showDetail = ref(false)
let detailLoaded = false                    // avoid duplicate fetch

const detailTitle = computed(() => {
  if (props.categoryId) return `${props.categoryId} · 知识图谱详情`
  return '知识图谱详情'
})

function formatNum(n: number) {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function buildFallbackData() {
  const nodes: GraphNode[] = [
    { name: '采集自愈知识库', symbolSize: 55, category: 0, itemStyle: { color: '#00d4ff' }, entityType: '知识库', description: '采集自愈相关知识库', degree: 5 },
    { name: '采集常见故障', symbolSize: 30, category: 1, itemStyle: { color: '#00ff88' }, entityType: '概念', description: '采集系统中常见的故障类型', degree: 2 },
    { name: '集中器', symbolSize: 28, category: 1, itemStyle: { color: '#00ff88' }, entityType: '设备', description: '数据集中器设备', degree: 2 },
    { name: '采集器', symbolSize: 26, category: 1, itemStyle: { color: '#00ff88' }, entityType: '设备', description: '数据采集器设备', degree: 1 },
    { name: '消缺典型案例', symbolSize: 26, category: 1, itemStyle: { color: '#00ff88' }, entityType: '案例', description: '设备消缺的典型案例', degree: 1 },
    { name: '低压台区', symbolSize: 24, category: 1, itemStyle: { color: '#00ff88' }, entityType: '概念', description: '低压配电台区', degree: 2 },
    { name: '冻结曲线', symbolSize: 22, category: 1, itemStyle: { color: '#00ff88' }, entityType: '概念', description: '负荷冻结曲线', degree: 2 },
    { name: '故障排查', symbolSize: 24, category: 1, itemStyle: { color: '#00ff88' }, entityType: '方法', description: '故障排查方法与流程', degree: 2 },
    { name: '远程研判', symbolSize: 22, category: 1, itemStyle: { color: '#00ff88' }, entityType: '方法', description: '远程故障研判方法', degree: 1 },
    { name: '标准化作业', symbolSize: 20, category: 2, itemStyle: { color: '#ffaa00' }, entityType: '方法', description: '标准化作业流程', degree: 2 },
    { name: '七步法', symbolSize: 18, category: 2, itemStyle: { color: '#ffaa00' }, entityType: '方法', description: '故障处理七步法', degree: 1 },
    { name: '采集稳定性', symbolSize: 18, category: 2, itemStyle: { color: '#ffaa00' }, entityType: '指标', description: '采集成功率与稳定性指标', degree: 1 },
    { name: '现场装置', symbolSize: 16, category: 2, itemStyle: { color: '#ffaa00' }, entityType: '设备', description: '现场安装的各类装置', degree: 1 },
  ]
  const links: GraphLink[] = [
    { source: '采集自愈知识库', target: '采集常见故障', relType: 'CONTAINS', description: '知识库包含采集常见故障内容' },
    { source: '采集自愈知识库', target: '消缺典型案例', relType: 'CONTAINS', description: '知识库包含消缺典型案例' },
    { source: '采集自愈知识库', target: '低压台区', relType: 'COVERS', description: '知识库覆盖低压台区知识' },
    { source: '采集自愈知识库', target: '集中器', relType: 'COVERS', description: '知识库覆盖集中器相关知识' },
    { source: '采集自愈知识库', target: '故障排查', relType: 'COVERS', description: '知识库覆盖故障排查方法' },
    { source: '集中器', target: '采集器', relType: 'CONNECTS', description: '集中器连接采集器' },
    { source: '采集常见故障', target: '远程研判', relType: 'USES', description: '故障排查使用远程研判方法' },
    { source: '消缺典型案例', target: '七步法', relType: 'USES', description: '消缺案例采用七步法' },
    { source: '故障排查', target: '标准化作业', relType: 'FOLLOWS', description: '故障排查遵循标准化作业流程' },
    { source: '低压台区', target: '冻结曲线', relType: 'ANALYZES', description: '低压台区分析冻结曲线' },
    { source: '低压台区', target: '采集稳定性', relType: 'MEASURES', description: '低压台区衡量采集稳定性' },
    { source: '远程研判', target: '标准化作业', relType: 'FOLLOWS', description: '远程研判遵循标准化作业' },
    { source: '冻结曲线', target: '现场装置', relType: 'MONITORS', description: '冻结曲线监控现场装置' },
  ]
  return { nodes, links }
}

function initChart(nodes: GraphNode[], links: GraphLink[]) {
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
        if (p.dataType === 'node') {
          const d = p.data
          let html = `<b style="color:#00d4ff">${d.name}</b>`
          if (d.entityType) html += `<br/><span style="color:rgba(255,255,255,0.5)">类型:</span> ${d.entityType}`
          if (d.description) html += `<br/><span style="color:rgba(255,255,255,0.5)">描述:</span> ${d.description}`
          return html
        }
        if (p.dataType === 'edge') {
          const d = p.data
          let html = `<span style="color:#00d4ff">${d.source}</span> → <span style="color:#00ff88">${d.target}</span>`
          if (d.description) html += `<br/><span style="color:#ffaa00">${d.description}</span>`
          return html
        }
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
    // Query Memgraph via backend API — pass kbName for per-KB filter
    const data = await fetchKnowledgeGraph(
      props.workspace || undefined,
      props.kbName || props.categoryId || undefined,
    )
    if (data && data.nodes && data.nodes.length > 0) {
      const s = data.stats
      if (s) {
        graphStats.entityCount = s.entity_count
        graphStats.relationCount = s.relation_count
        graphStats.coverage = s.coverage
      }
      graphStats.renderedNodes = data.nodes.length
      graphStats.renderedLinks = data.links.length
      graphNodes.value = data.nodes
      graphLinks.value = data.links
      initChart(data.nodes, data.links)
      return
    }
  } catch (e) {
    console.warn('[KnowledgeGraph] Failed to load from backend:', e)
  }

  // Fallback to hardcoded data
  const fb = buildFallbackData()
  graphNodes.value = fb.nodes
  graphLinks.value = fb.links
  initChart(fb.nodes, fb.links)
  // Use real stats from backend only if available, otherwise show 0
  graphStats.entityCount = 0
  graphStats.relationCount = 0
  graphStats.coverage = 0
  graphStats.renderedNodes = 0
  graphStats.renderedLinks = 0
}

onMounted(async () => {
  await loadGraph()
  window.addEventListener('resize', handleResize)
})

watch(() => props.workspace, () => {
  loadGraph()
  detailLoaded = false
})

// When detail modal opens, load full graph if not already loaded
watch(showDetail, async (val) => {
  if (val && !detailLoaded) {
    try {
      // Request full data (max_nodes=5000) for detail view
      const data = await fetchKnowledgeGraph(
        props.workspace || undefined,
        props.kbName || props.categoryId || undefined,
        5000,
      )
      if (data && data.nodes && data.nodes.length > 0) {
        detailNodes.value = data.nodes
        detailLinks.value = data.links
        detailLoaded = true
      }
    } catch (e) {
      // Fallback: use same data as overview
      detailNodes.value = graphNodes.value
      detailLinks.value = graphLinks.value
    }
  } else if (val) {
    detailNodes.value = graphNodes.value
    detailLinks.value = graphLinks.value
  }
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

.graph-title-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.graph-detail-btn {
  color: #00d4ff !important;
  font-size: 12px;
  padding: 4px 8px;
  flex-shrink: 0;
  transition: all 0.2s;
}

.graph-detail-btn:hover {
  background: rgba(0,212,255,0.08) !important;
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

.rendered-hint {
  display: block;
  font-size: 10px;
  color: rgba(0, 212, 255, 0.6);
  margin-top: 2px;
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
