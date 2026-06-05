<template>
  <div class="chart-card">
    <div class="card-title">知识资产库</div>
    <div ref="chartRef" class="chart-container"></div>
    <div class="legend-list">
      <div class="legend-item" v-for="item in chartData" :key="item.name">
        <span class="legend-dot" :style="{ backgroundColor: item.color }"></span>
        <span class="legend-name">{{ item.name }}</span>
        <span class="legend-value">{{ item.count }}份</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { fetchFolderKBAssetStats, type AssetStats, type AssetCategory } from '@/api/knowledge'

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

interface ChartItem {
  name: string
  value: number
  count: number
  color: string
  size: number
}

const defaultCategories: AssetCategory[] = [
  { name: '计量营销专业知识库', count: 2233, size: 2045234207, value: 67.7, color: '#00d4ff', extensions: [{ ext: '.docx', count: 2212 }, { ext: '.txt', count: 10 }, { ext: '.xlsx', count: 6 }, { ext: '.xls', count: 4 }, { ext: '.pdf', count: 1 }] },
  { name: '计量数字讲师', count: 830, size: 2078231728, value: 25.2, color: '#00ff88', extensions: [{ ext: '.docx', count: 830 }] },
  { name: '专家系统知识库', count: 210, size: 156237824, value: 6.4, color: '#a855f7', extensions: [{ ext: '.docx', count: 210 }] },
  { name: '装表接电知识库', count: 19, size: 64983040, value: 0.6, color: '#ffaa00', extensions: [{ ext: '.docx', count: 15 }, { ext: '.txt', count: 2 }, { ext: '.xlsx', count: 1 }, { ext: '.doc', count: 1 }] },
  { name: '采集自愈知识库', count: 8, size: 30408704, value: 0.2, color: '#ff5555', extensions: [{ ext: '.docx', count: 8 }] },
]

const defaultTotal = defaultCategories.reduce((s, c) => s + c.count, 0)

const chartData = ref<ChartItem[]>(defaultCategories.map(c => ({
  name: c.name,
  value: c.value,
  count: c.count,
  color: c.color,
  size: c.size,
})))

const totalCount = ref(defaultTotal)
const totalSize = ref(defaultCategories.reduce((s, c) => s + c.size, 0))

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
}

onMounted(async () => {
  try {
    const data: AssetStats = await fetchFolderKBAssetStats()
    if (data && data.categories && data.categories.length > 0) {
      chartData.value = data.categories.map(c => ({
        name: c.name,
        value: c.value,
        count: c.count,
        color: c.color,
        size: c.size,
      }))
      totalCount.value = data.total_count
      totalSize.value = data.total_size
    }
  } catch (e) { console.warn('[KnowledgeCharts] asset-stats failed:', e) }

  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value)

    const totalStr = totalCount.value.toLocaleString()
    const sizeStr = formatSize(totalSize.value)

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        borderColor: 'rgba(0, 212, 255, 0.3)',
        textStyle: { color: '#fff' },
        formatter: (p: any) => {
          const d = p.data as any
          return `${p.name}<br/>占比: ${p.value}%<br/>文件: ${d.count?.toLocaleString() || ''}份<br/>大小: ${d.sizeStr || ''}`
        }
      },
      series: [
        {
          type: 'pie',
          radius: ['50%', '75%'],
          center: ['50%', '50%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 8,
            borderColor: '#111827',
            borderWidth: 2
          },
          label: {
            show: true,
            position: 'center',
            formatter: () => `{total|${totalStr}}\n{label|知识总量}\n{size|${sizeStr}}`,
            rich: {
              total: { fontSize: 22, fontWeight: 'bold', color: '#ffffff', lineHeight: 30 },
              label: { fontSize: 12, color: 'rgba(255,255,255,0.5)', lineHeight: 20 },
              size: { fontSize: 11, color: 'rgba(255,255,255,0.35)', lineHeight: 18 },
            }
          },
          emphasis: { label: { show: true } },
          labelLine: { show: false },
          data: chartData.value.map(item => ({
            ...item,
            itemStyle: { color: item.color },
            count: item.count,
            sizeStr: formatSize(item.size),
          }))
        }
      ]
    }

    chartInstance.setOption(option)
    window.addEventListener('resize', handleResize)
  }
})

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose()
  }
  window.removeEventListener('resize', handleResize)
})

const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}
</script>

<style scoped>
.chart-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 16px;
}

.chart-container {
  width: 100%;
  height: 220px;
}

.legend-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-name {
  color: rgba(255, 255, 255, 0.7);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legend-value {
  color: #ffffff;
  font-weight: 500;
  white-space: nowrap;
}
</style>
