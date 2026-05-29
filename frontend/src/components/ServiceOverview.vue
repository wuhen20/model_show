<script setup lang="ts">
import { ref } from 'vue'
import { modelServiceStatus, statistics } from '@/data/models'

const activeFilter = ref('all')

const getStatusColor = (status: string) => {
  if (status === 'running') return '#00ff88'
  return '#ff5555'
}
</script>

<template>
  <div class="service-overview">
    <div class="overview-header">
      <div class="header-left">
        <span class="overview-title">服务质量概览</span>
      </div>
      <div class="header-right">
        <select class="filter-select">
          <option>全部</option>
          <option>语言模型</option>
          <option>视觉模型</option>
          <option>时序模型</option>
        </select>
      </div>
    </div>
    <div class="quality-stats">
      <div class="quality-item">
        <div class="quality-ring">
          <svg width="60" height="60" viewBox="0 0 60 60">
            <circle cx="30" cy="30" r="26" fill="none" stroke="rgba(0, 212, 255, 0.2)" stroke-width="4"/>
            <circle cx="30" cy="30" r="26" fill="none" stroke="#00ff88" stroke-width="4"
              stroke-linecap="round"
              :stroke-dasharray="`${statistics.successRate * 1.63} 163`"/>
          </svg>
          <div class="ring-content">
            <span class="ring-value">{{ statistics.successRate }}%</span>
            <span class="ring-label">成功率</span>
          </div>
        </div>
      </div>
      <div class="quality-item">
        <div class="quality-ring">
          <svg width="60" height="60" viewBox="0 0 60 60">
            <circle cx="30" cy="30" r="26" fill="none" stroke="rgba(0, 212, 255, 0.2)" stroke-width="4"/>
            <circle cx="30" cy="30" r="26" fill="none" stroke="#00d4ff" stroke-width="4"
              stroke-linecap="round"
              :stroke-dasharray="`${(100 - 0.7) * 1.63} 163`"/>
          </svg>
          <div class="ring-content">
            <span class="ring-value">0.7%</span>
            <span class="ring-label">错误率</span>
          </div>
        </div>
      </div>
      <div class="quality-item">
        <div class="quality-ring">
          <svg width="60" height="60" viewBox="0 0 60 60">
            <circle cx="30" cy="30" r="26" fill="none" stroke="rgba(0, 212, 255, 0.2)" stroke-width="4"/>
            <circle cx="30" cy="30" r="26" fill="none" stroke="#ffaa00" stroke-width="4"
              stroke-linecap="round"
              :stroke-dasharray="`${(100 - 1.2) * 1.63} 163`"/>
          </svg>
          <div class="ring-content">
            <span class="ring-value">1.2%</span>
            <span class="ring-label">超时率</span>
          </div>
        </div>
      </div>
      <div class="quality-item">
        <div class="quality-ring">
          <svg width="60" height="60" viewBox="0 0 60 60">
            <circle cx="30" cy="30" r="26" fill="none" stroke="rgba(0, 212, 255, 0.2)" stroke-width="4"/>
            <circle cx="30" cy="30" r="26" fill="none" stroke="#00d4ff" stroke-width="4"
              stroke-linecap="round"
              :stroke-dasharray="`${84.6 * 1.63} 163`"/>
          </svg>
          <div class="ring-content">
            <span class="ring-value">84.6%</span>
            <span class="ring-label">自有模型覆盖率</span>
          </div>
        </div>
      </div>
    </div>
    <div class="status-section">
      <div class="section-header">
        <span class="section-title">模型服务状态</span>
        <select class="filter-select small" v-model="activeFilter">
          <option value="all">全部</option>
          <option value="running">运行中</option>
          <option value="stopped">已停止</option>
        </select>
      </div>
      <div class="status-list">
        <div v-for="service in modelServiceStatus" :key="service.name" class="status-item">
          <div class="status-left">
            <span class="status-dot" :style="{ background: getStatusColor(service.status) }"></span>
            <span class="status-name">{{ service.name }}</span>
          </div>
          <div class="status-right">
            <div class="status-metrics">
              <span class="metric">CPS: {{ service.CPS }}</span>
              <span class="metric">TPS: {{ service.TPS }}</span>
              <span class="metric">QPS: {{ service.QPS }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.service-overview {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 12px;
}

.overview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.overview-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.filter-select {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  font-size: 12px;
  cursor: pointer;
}

.filter-select.small {
  padding: 4px 8px;
  font-size: 11px;
}

.quality-stats {
  display: flex;
  justify-content: space-around;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
}

.quality-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.quality-ring {
  position: relative;
  width: 60px;
  height: 60px;
}

.ring-content {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.ring-value {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.ring-label {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
}

.status-section {
  margin-top: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.status-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(0, 212, 255, 0.05);
  border-radius: 8px;
}

.status-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.9);
}

.status-right {
  display: flex;
}

.status-metrics {
  display: flex;
  gap: 16px;
}

.metric {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
}
</style>
