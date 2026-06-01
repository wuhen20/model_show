<template>
  <div class="chart-card">
    <div class="card-title">知识来源分布</div>
    <div class="source-list">
      <div class="source-item" v-for="item in sourceData" :key="item.name">
        <div class="source-info">
          <span class="source-name">{{ item.name }}</span>
          <div class="source-val">
            <span class="source-value">{{ item.value }}%</span>
            <span class="source-count">({{ item.count }}份)</span>
          </div>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: item.value + '%', backgroundColor: item.color }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchSourceDistribution, type SourceDistribution } from '@/api/knowledge'

const defaultData: (SourceDistribution & { count?: number })[] = [
  { name: '内部文档', value: 42.3, count: 0, color: '#00d4ff' },
  { name: '电力行业标准', value: 24.8, count: 0, color: '#00ff88' },
  { name: '国家标准', value: 15.6, count: 0, color: '#a855f7' },
  { name: '国家电网企业标准', value: 10.2, count: 0, color: '#ffaa00' },
  { name: '国家计量规程', value: 7.1, count: 0, color: '#ff5555' }
]

const sourceData = ref<(SourceDistribution & { count?: number })[]>(defaultData)

onMounted(async () => {
  try {
    const data = await fetchSourceDistribution()
    if (data && data.length > 0) {
      sourceData.value = data
    }
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

.source-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.source-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.source-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.source-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}

.source-val {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.source-value {
  font-size: 14px;
  color: #ffffff;
  font-weight: 600;
}

.source-count {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.progress-bar {
  height: 8px;
  background-color: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
}
</style>
