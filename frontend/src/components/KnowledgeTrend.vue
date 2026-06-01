<template>
  <div class="chart-card">
    <div class="card-title">
      <span>知识更新趋势</span>
      <span class="subtitle">(近30天)</span>
    </div>
    <div ref="chartRef" class="chart-container"></div>
    <div class="trend-summary">
      <div class="summary-item">
        <div class="summary-icon" style="background: rgba(0, 212, 255, 0.2);">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="12" y1="18" x2="12" y2="12"/>
            <line x1="9" y1="15" x2="15" y2="15"/>
          </svg>
        </div>
        <div class="summary-info">
          <div class="summary-label">新增知识</div>
          <div class="summary-value">
            <span class="number">568</span>
            <span class="unit">份</span>
          </div>
          <div class="summary-trend trend-up">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M5 10l7-7 7 7"/>
            </svg>
            12.5%
          </div>
        </div>
      </div>
      <div class="summary-item">
        <div class="summary-icon" style="background: rgba(0, 255, 136, 0.2);">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00ff88" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </div>
        <div class="summary-info">
          <div class="summary-label">更新知识</div>
          <div class="summary-value">
            <span class="number">1,245</span>
            <span class="unit">份</span>
          </div>
          <div class="summary-trend trend-up">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M5 10l7-7 7 7"/>
            </svg>
            15.3%
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

onMounted(() => {
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value)

    const dates = ['03-26', '03-28', '03-30', '04-02', '04-04', '04-06', '04-08', '04-10', '04-12', '04-14', '04-16', '04-18', '04-20', '04-23']
    const newData = [120, 280, 350, 420, 380, 450, 520, 480, 550, 620, 580, 650, 720, 680]
    const updateData = [280, 420, 550, 680, 620, 750, 880, 820, 950, 1080, 1020, 1150, 1280, 1245]

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        borderColor: 'rgba(0, 212, 255, 0.3)',
        textStyle: { color: '#fff' },
        axisPointer: { type: 'cross' }
      },
      legend: {
        data: ['新增知识', '更新知识'],
        bottom: 0,
        textStyle: { color: 'rgba(255,255,255,0.7)', fontSize: 12 }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        top: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dates,
        axisLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.2)' } },
        axisLabel: { color: 'rgba(255,255,255,0.5)', fontSize: 11 }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLabel: { color: 'rgba(255,255,255,0.5)', fontSize: 11 }
      },
      series: [
        {
          name: '新增知识',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2, color: '#00d4ff' },
          itemStyle: { color: '#00d4ff' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(0, 212, 255, 0.2)' },
                { offset: 1, color: 'rgba(0, 212, 255, 0.05)' }
              ]
            }
          },
          data: newData
        },
        {
          name: '更新知识',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2, color: '#00ff88' },
          itemStyle: { color: '#00ff88' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(0, 255, 136, 0.2)' },
                { offset: 1, color: 'rgba(0, 255, 136, 0.05)' }
              ]
            }
          },
          data: updateData
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

.subtitle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 400;
  margin-left: 4px;
}

.chart-container {
  width: 100%;
  height: 200px;
}

.trend-summary {
  display: flex;
  gap: 16px;
  margin-top: 16px;
}

.summary-item {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}

.summary-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.summary-info {
  flex: 1;
}

.summary-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 4px;
}

.summary-value {
  display: flex;
  align-items: baseline;
  gap: 2px;
  margin-bottom: 4px;
}

.summary-value .number {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
}

.summary-value .unit {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.summary-trend {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.summary-trend.trend-up {
  color: #00ff88;
}
</style>
