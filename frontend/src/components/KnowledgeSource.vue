<template>
  <div class="chart-card">
    <div class="card-title">知识来源分布</div>
    <div class="source-list">
      <div class="source-item" v-for="item in sourceData" :key="item.name">
        <div class="source-info">
          <div class="source-name-group">
            <span class="source-dot" :style="{ backgroundColor: item.color }"></span>
            <span class="source-name">{{ item.name }}</span>
          </div>
          <div class="source-val">
            <span class="source-value">{{ item.value }}%</span>
            <span class="source-count">({{ item.count }}份)</span>
          </div>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: item.value + '%', backgroundColor: item.color }"></div>
        </div>
        <div class="source-desc" v-if="item.description">{{ item.description }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchSourceDistribution, fetchFolderKBSourceDistribution } from '@/api/knowledge'

interface SourceItem {
  name: string
  value: number
  count: number
  color: string
  description?: string
}

const defaultData: SourceItem[] = [
  { name: '标准规范体系', value: 22.8, count: 751, color: '#00d4ff', description: '国标/行标/企标/检定规程等规范性文件' },
  { name: '作业指导体系', value: 18.8, count: 621, color: '#00ff88', description: '作业指导书/操作手册/技术方案等操作类文件' },
  { name: '培训考试体系', value: 1.4, count: 45, color: '#a855f7', description: '培训资料/试题库等培训类文件' },
  { name: '管理制度体系', value: 4.5, count: 149, color: '#ffaa00', description: '管理办法/管理规定等制度类文件' },
  { name: '技术文档体系', value: 52.5, count: 1734, color: '#ff5555', description: '通用技术文档/参考资料' },
]

const sourceData = ref<SourceItem[]>(defaultData)

onMounted(async () => {
  try {
    const data = await fetchFolderKBSourceDistribution()
    if (data && data.length > 0) {
      sourceData.value = data
    }
  } catch {
    // Fallback to old API
    try {
      const data = await fetchSourceDistribution()
      if (data && data.length > 0) {
        sourceData.value = data.map(d => ({
          name: d.name,
          value: d.value,
          count: d.count,
          color: d.color,
        }))
      }
    } catch {}
  }
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
  gap: 14px;
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

.source-name-group {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.source-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.source-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-val {
  display: flex;
  align-items: baseline;
  gap: 4px;
  flex-shrink: 0;
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

.source-desc {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  line-height: 1.4;
}
</style>
