<script setup lang="ts">
import { modelList } from '@/data/models'

const getStatusTag = (status: string) => {
  const tags: Record<string, { text: string; type: string }> = {
    running: { text: '运行中', type: 'success' },
    stopped: { text: '已停止', type: 'danger' },
    error: { text: '异常', type: 'danger' },
    deploying: { text: '部署中', type: 'warning' }
  }
  return tags[status] || { text: status, type: 'info' }
}
</script>

<template>
  <div class="model-table-container">
    <div class="table-header">
      <div class="header-left">
        <span class="title">服务列表</span>
      </div>
      <div class="header-right">
        <select class="filter-select">
          <option>全部</option>
          <option>运行中</option>
          <option>已停止</option>
          <option>部署中</option>
        </select>
      </div>
    </div>
    <div class="table-wrapper">
      <table class="model-table">
        <thead>
          <tr>
            <th>服务名称</th>
            <th>基础模型</th>
            <th>模型类型</th>
            <th>服务环境</th>
            <th>CPS</th>
            <th>TPS</th>
            <th>QPS</th>
            <th>负责人</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="model in modelList" :key="model.id">
            <td class="name-cell">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
              </svg>
              <span>{{ model.name }}</span>
            </td>
            <td>{{ model.baseModel }}</td>
            <td>{{ model.version }}</td>
            <td>{{ model.serviceType }}</td>
            <td>{{ model.CPS }}</td>
            <td>{{ model.TPS }}</td>
            <td>{{ model.QPS }}</td>
            <td>{{ model.owner }}</td>
            <td>
              <span class="status-tag" :class="getStatusTag(model.status).type">
                {{ getStatusTag(model.status).text }}
              </span>
            </td>
            <td class="action-cell">
              <button class="action-btn" title="启动">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M5 3v18M19 6l-7 6 7 6"/>
                </svg>
              </button>
              <button class="action-btn" title="停止">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M6 4h12v16H6z"/>
                </svg>
              </button>
              <button class="action-btn" title="配置">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 20V10"/>
                  <path d="M18 20V4"/>
                  <path d="M6 20v-6"/>
                </svg>
              </button>
              <button class="action-btn" title="日志">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                  <polyline points="10 9 9 9 8 9"/>
                </svg>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="table-footer">
      <span class="page-info">共 6 条</span>
      <div class="pagination">
        <button class="page-btn" disabled>上一页</button>
        <button class="page-btn active">1</button>
        <button class="page-btn">2</button>
        <button class="page-btn">3</button>
        <button class="page-btn">下一页</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-table-container {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 16px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left .title {
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

.table-wrapper {
  overflow-x: auto;
}

.model-table {
  width: 100%;
  border-collapse: collapse;
}

.model-table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  background: rgba(0, 212, 255, 0.05);
  border-bottom: 1px solid rgba(0, 212, 255, 0.2);
}

.model-table td {
  padding: 12px 16px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.status-tag.success {
  background: rgba(0, 255, 136, 0.2);
  color: #00ff88;
}

.status-tag.warning {
  background: rgba(255, 170, 0, 0.2);
  color: #ffaa00;
}

.status-tag.danger {
  background: rgba(255, 85, 85, 0.2);
  color: #ff5555;
}

.status-tag.info {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.action-cell {
  display: flex;
  gap: 8px;
}

.action-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 212, 255, 0.1);
  border: none;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-btn:hover {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(0, 212, 255, 0.1);
}

.page-info {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.pagination {
  display: flex;
  gap: 4px;
}

.page-btn {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.page-btn:hover:not(:disabled) {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.page-btn.active {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
