<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="90%"
    top="3vh"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    class="graph-detail-dialog"
    destroy-on-close
  >
    <div class="detail-container">
      <!-- Stats bar -->
      <div class="stats-bar">
        <div class="stat-chip">
          <span class="stat-val">{{ stats?.entity_count ?? nodes.length }}</span>
          <span class="stat-lbl">节点</span>
        </div>
        <div class="stat-chip">
          <span class="stat-val">{{ stats?.relation_count ?? links.length }}</span>
          <span class="stat-lbl">边</span>
        </div>
        <div class="stats-spacer"></div>
        <div class="legend-bar">
          <span class="legend-item"><span class="dot" style="background:#00d4ff"></span>核心实体</span>
          <span class="legend-item"><span class="dot" style="background:#00ff88"></span>关联实体</span>
          <span class="legend-item"><span class="dot" style="background:#ffaa00"></span>边缘实体</span>
        </div>
      </div>

      <!-- Full-size ECharts graph -->
      <div class="detail-chart-wrapper">
        <div v-if="chartLoading" class="detail-loading">
          <div class="detail-loading-spinner">
            <div class="spinner-ring"></div>
            <span class="spinner-text">渲染图谱中...</span>
          </div>
        </div>
        <div ref="chartRef" class="detail-graph-chart"></div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import type { GraphNode, GraphLink, GraphStats } from '@/api/knowledge'

const props = defineProps<{
  modelValue: boolean
  title: string
  nodes: GraphNode[]
  links: GraphLink[]
  stats?: GraphStats | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const chartRef = ref<HTMLElement | null>(null)
const chartLoading = ref(false)
let chartInstance: echarts.ECharts | null = null

function initDetailChart() {
  if (!chartRef.value) return
  const el = chartRef.value
  if (el.clientWidth <= 0 || el.clientHeight <= 0) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartLoading.value = true
  chartInstance = echarts.init(el, 'dark')

  const categories = [
    { name: '核心实体' },
    { name: '关联实体' },
    { name: '边缘实体' },
  ]

  chartInstance.setOption({
    tooltip: {
      trigger: 'item',
      confine: true,
      backgroundColor: 'rgba(17,24,39,0.96)',
      borderColor: 'rgba(0,212,255,0.3)',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#fff', fontSize: 13, lineHeight: 20 },
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const d = params.data
          let html = `<div style="font-weight:600;font-size:14px;color:#00d4ff;margin-bottom:4px">${d.name}</div>`
          if (d.entityType) {
            html += `<div><span style="color:rgba(255,255,255,0.45)">实体类型</span>　<span style="color:#00ff88">${d.entityType}</span></div>`
          }
          if (d.degree !== undefined) {
            html += `<div><span style="color:rgba(255,255,255,0.45)">关联度</span>　<span style="color:#00d4ff">${d.degree}</span></div>`
          }
          if (d.description) {
            html += `<div style="margin-top:6px;color:rgba(255,255,255,0.85);max-width:320px;line-height:1.6">${d.description}</div>`
          }
          if (d.kbName) {
            html += `<div style="margin-top:4px"><span style="color:rgba(255,255,255,0.45)">所属知识库</span>　<span style="color:#ffaa00">${d.kbName}</span></div>`
          }
          return html
        }
        if (params.dataType === 'edge') {
          const d = params.data
          let html = `<div style="margin-bottom:4px">`
          html += `<span style="color:#00d4ff;font-weight:500">${d.source}</span>`
          html += ` <span style="color:rgba(255,255,255,0.4)">→</span> `
          html += `<span style="color:#00ff88;font-weight:500">${d.target}</span>`
          html += `</div>`
          if (d.relType) {
            html += `<div><span style="color:rgba(255,255,255,0.45)">关系类型</span>　<span style="color:#a855f7">${d.relType}</span></div>`
          }
          if (d.description) {
            html += `<div style="margin-top:6px;color:#ffaa00;max-width:360px;line-height:1.6">${d.description}</div>`
          }
          return html
        }
        return ''
      },
    },
    legend: {
      data: categories.map(c => c.name),
      textStyle: { color: 'rgba(255,255,255,0.6)', fontSize: 12 },
      bottom: 10,
      itemWidth: 12,
      itemHeight: 12,
    },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      categories,
      data: props.nodes,
      links: props.links,
      force: {
        repulsion: 250,
        gravity: 0.05,
        edgeLength: [60, 200],
        friction: 0.6,
      },
      label: {
        show: true,
        fontSize: 12,
        color: 'rgba(255,255,255,0.88)',
        formatter: (p: any) => {
          const n = p.name || ''
          return n.length > 14 ? n.slice(0, 14) + '..' : n
        },
      },
      lineStyle: {
        color: 'rgba(0,212,255,0.25)',
        curveness: 0.15,
        width: 1.5,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3, color: '#00d4ff' },
        label: { fontSize: 14, fontWeight: 'bold' },
      },
      edgeLabel: {
        show: false,
      },
    }],
  }, true)

  // Mark loading done after a short delay to let ECharts finish rendering
  setTimeout(() => {
    chartLoading.value = false
  }, 300)
}

function handleResize() {
  if (chartInstance) chartInstance.resize()
}

watch(() => props.modelValue, async (val) => {
  if (val) {
    await nextTick()
    setTimeout(() => {
      initDetailChart()
      window.addEventListener('resize', handleResize)
    }, 350)
  } else {
    window.removeEventListener('resize', handleResize)
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
  }
})

watch(() => [props.nodes, props.links], () => {
  if (props.modelValue) {
    nextTick(() => initDetailChart())
  }
}, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
/* ── Dialog overrides ── */
.graph-detail-dialog :deep(.el-dialog) {
  background: linear-gradient(180deg, rgba(17,24,39,0.98) 0%, rgba(10,14,26,0.96) 100%);
  border: 1px solid rgba(0,212,255,0.3);
  border-radius: 14px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.6), 0 0 60px rgba(0,212,255,0.08);
}

.graph-detail-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(0,212,255,0.12);
  padding: 14px 20px;
  margin-right: 0;
}

.graph-detail-dialog :deep(.el-dialog__title) {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.graph-detail-dialog :deep(.el-dialog__headerbtn .el-dialog__close) {
  color: rgba(255,255,255,0.5);
}

.graph-detail-dialog :deep(.el-dialog__body) {
  padding: 12px 16px 16px;
}

/* ── Stats bar ── */
.stats-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.stat-chip {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 4px 12px;
  background: rgba(0,212,255,0.06);
  border: 1px solid rgba(0,212,255,0.12);
  border-radius: 6px;
}

.stat-val {
  font-size: 16px;
  font-weight: 600;
  color: #00d4ff;
}

.stat-lbl {
  font-size: 11px;
  color: rgba(255,255,255,0.45);
}

.stats-spacer {
  flex: 1;
}

.legend-bar {
  display: flex;
  gap: 14px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: rgba(255,255,255,0.55);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* ── Graph ── */
.detail-chart-wrapper {
  position: relative;
  height: calc(80vh - 100px);
  min-height: 500px;
}

.detail-loading {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(17,24,39,0.8);
  border: 1px solid rgba(0,212,255,0.12);
  border-radius: 10px;
  backdrop-filter: blur(2px);
  animation: detailFadeIn 0.2s ease;
}

@keyframes detailFadeIn { from { opacity: 0; } to { opacity: 1; } }

.detail-loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.spinner-ring {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(0,212,255,0.15);
  border-top-color: #00d4ff;
  border-radius: 50%;
  animation: detailSpin 0.8s linear infinite;
}

@keyframes detailSpin { to { transform: rotate(360deg); } }

.spinner-text {
  font-size: 13px;
  color: rgba(255,255,255,0.7);
  letter-spacing: 0.5px;
}

.detail-graph-chart {
  height: 100%;
  width: 100%;
  border: 1px solid rgba(0,212,255,0.12);
  border-radius: 10px;
  background: rgba(17,24,39,0.5);
}
</style>

<style>
/* Global overrides for dialog overlay */
.graph-detail-dialog .el-overlay-dialog {
  backdrop-filter: blur(4px);
}
</style>
