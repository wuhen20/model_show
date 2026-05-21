<script setup lang="ts">
import { ref } from 'vue'
import { recentTasks, recentLogs } from '@/data/models'

const activeFilter = ref('all')

const filters = [
  { id: 'all', name: '全部' },
  { id: 'processing', name: '处理中' },
  { id: 'pending', name: '待处理' }
]

const getStatusClass = (status: string) => {
  if (status === '处理中') return 'processing'
  if (status === '待处理') return 'pending'
  return 'completed'
}
</script>

<template>
  <div class="task-panel">
    <div class="panel-header">
      <div class="header-left">
        <span class="panel-title">待办事项</span>
        <button class="more-btn">查看全部</button>
      </div>
      <div class="filter-tabs">
        <button
          v-for="filter in filters"
          :key="filter.id"
          class="filter-tab"
          :class="{ active: activeFilter === filter.id }"
          @click="activeFilter = filter.id"
        >
          {{ filter.name }}
        </button>
      </div>
    </div>
    <div class="task-list">
      <div v-for="task in recentTasks" :key="task.id" class="task-item">
        <div class="task-info">
          <span class="task-name">{{ task.name }}</span>
        </div>
        <span class="task-status" :class="getStatusClass(task.status)">
          {{ task.status }}
        </span>
      </div>
    </div>
    <div class="divider"></div>
    <div class="panel-header">
      <span class="panel-title">最近操作日志</span>
    </div>
    <div class="log-list">
      <div v-for="(log, index) in recentLogs" :key="index" class="log-item">
        <span class="log-time">{{ log.time }}</span>
        <span class="log-action">{{ log.action }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-panel {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.more-btn {
  padding: 4px 10px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.more-btn:hover {
  background: rgba(0, 212, 255, 0.1);
  color: #00d4ff;
}

.filter-tabs {
  display: flex;
  gap: 4px;
}

.filter-tab {
  padding: 4px 10px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.filter-tab:hover {
  background: rgba(0, 212, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
}

.filter-tab.active {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(0, 212, 255, 0.05);
  border-radius: 8px;
}

.task-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.9);
}

.task-status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.task-status.processing {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.task-status.pending {
  background: rgba(255, 170, 0, 0.2);
  color: #ffaa00;
}

.task-status.completed {
  background: rgba(0, 255, 136, 0.2);
  color: #00ff88;
}

.divider {
  height: 1px;
  background: rgba(0, 212, 255, 0.15);
  margin: 16px 0;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.log-item {
  display: flex;
  gap: 12px;
}

.log-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  min-width: 60px;
}

.log-action {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
}
</style>
