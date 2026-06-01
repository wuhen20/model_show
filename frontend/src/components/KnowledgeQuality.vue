<template>
  <div class="chart-card">
    <div class="card-title">知识质量概览</div>

    <div class="quality-score">
      <div class="score-circle">
        <div class="score-value">
          <span class="number">{{ overallScore }}</span>
          <span class="unit">分</span>
        </div>
      </div>
      <div class="score-label">知识质量评分</div>
    </div>

    <div class="quality-metrics">
      <div class="metric-item" v-for="metric in metrics" :key="metric.name">
        <span class="metric-name">{{ metric.name }}</span>
        <div class="metric-right">
          <div class="metric-bar-bg">
            <div class="metric-bar-fill" :style="{ width: metric.value + '%' }"></div>
          </div>
          <span class="metric-value">{{ metric.value }}分</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchQualityMetrics, type QualityMetrics } from '@/api/knowledge'

const overallScore = ref(93.6)
const metrics = ref([
  { name: '准确性', value: 94.2 },
  { name: '完整性', value: 92.8 },
  { name: '时效性', value: 93.1 },
  { name: '一致性', value: 93.8 },
  { name: '可理解性', value: 93.9 }
])

onMounted(async () => {
  try {
    const data: QualityMetrics = await fetchQualityMetrics()
    overallScore.value = data.overall_score
    metrics.value = data.metrics
  } catch {}
})
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

.quality-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 24px;
}

.score-circle {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
  box-shadow: 0 4px 20px rgba(0, 212, 255, 0.3);
}

.score-value {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.score-value .number {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  line-height: 1;
}

.score-value .unit {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
}

.score-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.quality-metrics {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.metric-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  flex-shrink: 0;
  width: 60px;
}

.metric-right {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-bar-bg {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  overflow: hidden;
}

.metric-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #00d4ff 0%, #00ff88 100%);
  transition: width 0.6s ease;
}

.metric-value {
  font-size: 13px;
  color: #ffffff;
  font-weight: 600;
  width: 45px;
  text-align: right;
  flex-shrink: 0;
}
</style>
