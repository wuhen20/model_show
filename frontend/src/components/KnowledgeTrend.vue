<template>
  <div class="chart-card">
    <div class="card-title">
      <span>知识更新趋势</span>
      <span class="subtitle">(按月)</span>
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
          <div class="summary-label">本月新增</div>
          <div class="summary-value">
            <span class="number">{{ summary.new_count.toLocaleString() }}</span>
            <span class="unit">份</span>
          </div>
          <div class="summary-trend" :class="summary.new_change_pct >= 0 ? 'trend-up' : 'trend-down'">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path :d="summary.new_change_pct >= 0 ? 'M5 10l7-7 7 7' : 'M19 14l-7 7-7-7'"/>
            </svg>
            {{ Math.abs(summary.new_change_pct) }}%
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
          <div class="summary-label">近30天更新</div>
          <div class="summary-value">
            <span class="number">{{ summary.updated_count.toLocaleString() }}</span>
            <span class="unit">份</span>
          </div>
          <div class="summary-trend" :class="summary.updated_change_pct >= 0 ? 'trend-up' : 'trend-down'">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path :d="summary.updated_change_pct >= 0 ? 'M5 10l7-7 7 7' : 'M19 14l-7 7-7-7'"/>
            </svg>
            {{ Math.abs(summary.updated_change_pct) }}%
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { fetchFolderKBTrend, type TrendData, type TrendSummary } from '@/api/knowledge'

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const defaultSummary: TrendSummary = {
  new_count: 0,
  new_change_pct: 0,
  updated_count: 0,
  updated_change_pct: 0,
}

const summary = ref<TrendSummary>({ ...defaultSummary })

onMounted(async () => {
  let trendData: TrendData | null = null

  try {
    const data = await fetchFolderKBTrend()
    if (data && data.months && data.months.length > 0) {
      trendData = data
      summary.value = data.summary
    }
  } catch {}

  // Fallback default months
  const months = trendData?.months || _defaultMonths()
  const series = trendData?.series || _defaultSeries()

  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value)

    // Short month labels: "2026-04" → "04月"
    const monthLabels = months.map((m: string) => {
      const parts = m.split('-')
      return parts.length >= 2 ? parts[1] + '月' : m
    })

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        borderColor: 'rgba(0, 212, 255, 0.3)',
        textStyle: { color: '#fff', fontSize: 12 },
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          if (!Array.isArray(params)) return ''
          const month = months[params[0]?.dataIndex] || ''
          let html = `<div style="margin-bottom:4px;font-weight:600">${month}</div>`
          let total = 0
          for (const p of params) {
            total += p.value
            html += `<div style="display:flex;align-items:center;gap:6px">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
              ${p.seriesName}: <b>${p.value}</b>份
            </div>`
          }
          html += `<div style="margin-top:4px;border-top:1px solid rgba(255,255,255,0.15);padding-top:4px">合计: <b>${total}</b>份</div>`
          return html
        },
      },
      legend: {
        data: series.map(s => s.name),
        bottom: 0,
        textStyle: { color: 'rgba(255,255,255,0.7)', fontSize: 10 },
        itemWidth: 10,
        itemHeight: 10,
        itemGap: 8,
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '20%',
        top: '3%',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: monthLabels,
        axisLine: { lineStyle: { color: 'rgba(0, 212, 255, 0.2)' } },
        axisLabel: { color: 'rgba(255,255,255,0.5)', fontSize: 10 },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLabel: { color: 'rgba(255,255,255,0.5)', fontSize: 10 },
      },
      series: series.map(s => ({
        name: s.name,
        type: 'bar' as const,
        stack: 'total',
        barWidth: '50%',
        itemStyle: {
          color: s.color,
          borderRadius: 0,
        },
        emphasis: {
          itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.3)' },
        },
        data: s.data,
      })),
    }

    // Add rounded corners to the topmost bar of each stack
    if (option.series && Array.isArray(option.series)) {
      const lastIndex = option.series.length - 1
      if ((option.series as any[])[lastIndex]) {
        (option.series as any[])[lastIndex].itemStyle.borderRadius = [3, 3, 0, 0]
      }
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

function _defaultMonths(): string[] {
  const now = new Date()
  const months: string[] = []
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }
  return months
}

function _defaultSeries() {
  const kbNames = ['计量营销专业知识库', '计量数字讲师', '专家系统知识库', '装表接电知识库', '采集自愈知识库']
  const colors = ['#00d4ff', '#00ff88', '#a855f7', '#ffaa00', '#ff5555']
  return kbNames.map((name, i) => ({
    name,
    data: [0, 0, 0, 0, 0, 0],
    color: colors[i],
  }))
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

.summary-trend.trend-down {
  color: #ff5555;
}
</style>
