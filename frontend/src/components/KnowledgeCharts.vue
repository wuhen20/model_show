<template>
  <div class="chart-card">
    <div class="card-title">知识分类分布</div>
    <div ref="chartRef" class="chart-container"></div>
    <div class="legend-list">
      <div class="legend-item" v-for="item in chartData" :key="item.name">
        <span class="legend-dot" :style="{ backgroundColor: item.color }"></span>
        <span class="legend-name">{{ item.name }}</span>
        <span class="legend-value">{{ item.value }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { fetchCategoryDistribution, type CategoryDistribution } from '@/api/knowledge'

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const defaultData: CategoryDistribution[] = [
  { name: '计量营销专业知识库', value: 73.5, count: 2120, color: '#00d4ff' },
  { name: '装表接电知识库', value: 22.6, count: 651, color: '#00ff88' },
  { name: '专家系统知识库', value: 3.7, count: 107, color: '#a855f7' },
  { name: '采集自愈知识库', value: 0.3, count: 8, color: '#ffaa00' },
]

const chartData = ref<CategoryDistribution[]>(defaultData)

onMounted(async () => {
  try {
    const data = await fetchCategoryDistribution()
    if (data && data.length > 0) {
      chartData.value = data
    }
  } catch {}

  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value)

    const totalCount = chartData.value.reduce((s, i) => s + (i.count || 0), 0)
    const totalStr = totalCount > 0 ? totalCount.toLocaleString() : '0'

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        borderColor: 'rgba(0, 212, 255, 0.3)',
        textStyle: { color: '#fff' },
        formatter: (p: any) => `${p.name}: ${p.value}% (${(p.data as any).count || ''}份)`
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
            formatter: () => `{total|${totalStr}}\n{label|知识总量}`,
            rich: {
              total: { fontSize: 24, fontWeight: 'bold', color: '#ffffff', lineHeight: 32 },
              label: { fontSize: 12, color: 'rgba(255,255,255,0.5)', lineHeight: 20 }
            }
          },
          emphasis: { label: { show: true } },
          labelLine: { show: false },
          data: chartData.value.map(item => ({
            ...item,
            itemStyle: { color: item.color },
            count: item.count
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
  height: 240px;
}

.legend-list {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
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
}
</style>
