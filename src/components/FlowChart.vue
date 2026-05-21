<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const flowData = [
  { name: '语言服务', value: 46 },
  { name: '视觉服务', value: 21 },
  { name: '时序服务', value: 18 },
  { name: '语音服务', value: 15 }
]

onMounted(() => {
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value)
    renderChart()
    window.addEventListener('resize', handleResize)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})

const handleResize = () => {
  chartInstance?.resize()
}

const renderChart = () => {
  const option: echarts.EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}%',
      backgroundColor: 'rgba(17, 24, 39, 0.95)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#fff' }
    },
    series: [
      {
        name: '服务分布',
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: 'rgba(17, 24, 39, 0.9)',
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'outside',
          color: '#fff',
          fontSize: 11,
          formatter: '{b}\n{c}%'
        },
        labelLine: {
          lineStyle: { color: 'rgba(0, 212, 255, 0.3)' }
        },
        data: flowData.map((item, index) => ({
          ...item,
          itemStyle: {
            color: [
              '#00d4ff',
              '#00ff88',
              '#ffaa00',
              '#ff5555'
            ][index]
          }
        }))
      }
    ]
  }
  chartInstance?.setOption(option)
}
</script>

<template>
  <div class="flow-chart">
    <div class="chart-header">
      <span class="chart-title">服务拓扑与流量分布</span>
      <span class="chart-subtitle">总调用量占比（近24小时）</span>
    </div>
    <div ref="chartRef" class="chart-container"></div>
    <div class="legend">
      <div v-for="item in flowData" :key="item.name" class="legend-item">
        <span class="legend-dot" :style="{ background: ['#00d4ff', '#00ff88', '#ffaa00', '#ff5555'][flowData.indexOf(item)] }"></span>
        <span class="legend-text">{{ item.name }}</span>
        <span class="legend-value">{{ item.value }}%</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.flow-chart {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.chart-subtitle {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.chart-container {
  flex: 1;
  min-height: 200px;
}

.legend {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
}

.legend-value {
  font-size: 11px;
  color: #fff;
  font-weight: 500;
}
</style>
