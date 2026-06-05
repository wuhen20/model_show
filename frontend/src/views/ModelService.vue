<script setup lang="ts">
import { ref } from 'vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import StatsCard from '@/components/StatsCard.vue'
import ModelTable from '@/components/ModelTable.vue'
import ServiceDetail from '@/components/ServiceDetail.vue'
import TaskPanel from '@/components/TaskPanel.vue'
import { statistics } from '@/data/models'

const activeFilter = ref('all')
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="模型服务管理中心" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="stats-grid">
          <StatsCard
            title="在线服务数"
            :value="statistics.onlineModels"
            icon="online-models"
            :change="{ value: '较昨日 +1', type: 'up' }"
          />
          <StatsCard
            title="已部署模型"
            :value="statistics.deployedModels"
            icon="deployed-models"
            :change="{ value: '较昨日 +1', type: 'up' }"
          />
          <StatsCard
            title="今日调用量"
            :value="statistics.todayCalls.toLocaleString()"
            unit="次"
            icon="today-calls"
            :change="{ value: '较昨日 +12.8%', type: 'up' }"
          />
          <StatsCard
            title="平均响应"
            :value="statistics.avgLatency"
            unit="s"
            icon="avg-latency"
            :change="{ value: '较昨日 -0.09s', type: 'down' }"
          />
          <StatsCard
            title="成功率"
            :value="statistics.successRate"
            unit="%"
            icon="success-rate"
            :change="{ value: '较昨日 +0.5%', type: 'up' }"
          />
          <StatsCard
            title="接口总数"
            :value="statistics.totalInterfaces"
            icon="total-interfaces"
          />
        </div>

        <div class="main-grid">
          <div class="left-column">
            <div class="model-workspace">
              <div class="workspace-header">
                <span class="workspace-title">模型服务工作区</span>
                <div class="workspace-filters">
                  <button
                    class="filter-btn"
                    :class="{ active: activeFilter === 'all' }"
                    @click="activeFilter = 'all'"
                  >全部</button>
                  <button
                    class="filter-btn"
                    :class="{ active: activeFilter === 'language' }"
                    @click="activeFilter = 'language'"
                  >语言模型</button>
                  <button
                    class="filter-btn"
                    :class="{ active: activeFilter === 'vision' }"
                    @click="activeFilter = 'vision'"
                  >视觉模型</button>
                  <button
                    class="filter-btn"
                    :class="{ active: activeFilter === 'timeseries' }"
                    @click="activeFilter = 'timeseries'"
                  >时序模型</button>
                  <button
                    class="filter-btn"
                    :class="{ active: activeFilter === 'speech' }"
                    @click="activeFilter = 'speech'"
                  >语音模型</button>
                </div>
              </div>
              <ModelTable />
            </div>
          </div>
          <div class="center-column">
            <ServiceDetail />
          </div>
          <div class="right-column">
            <TaskPanel />
            <div class="quick-actions-card">
              <h3 class="card-title">快捷操作</h3>
              <div class="actions-grid">
                <button class="action-item">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                  </svg>
                  <span>新增服务</span>
                </button>
                <button class="action-item">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00ff88" stroke-width="2">
                    <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
                    <path d="M3 3v5h5"/>
                  </svg>
                  <span>重新部署</span>
                </button>
                <button class="action-item">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffaa00" stroke-width="2">
                    <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
                  </svg>
                  <span>配置编辑</span>
                </button>
                <router-link to="/" class="action-item">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ff5555" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>
                  <span>智能问答</span>
                </router-link>
              </div>
            </div>
          </div>
        </div>

        <div class="footer-bar">
          <span class="footer-text">统一封装、统一发布、统一监控，沉淀可复用模型服务资产</span>
          <div class="footer-actions">
            <router-link to="/" class="footer-btn secondary">返回工作台</router-link>
            <button class="footer-btn primary">发布新服务</button>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 12px 16px;
  min-height: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 320px;
  gap: 12px;
  margin-bottom: 10px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.left-column {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.center-column {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.right-column {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}

.model-workspace {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 12px;
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.workspace-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.workspace-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.workspace-filters {
  display: flex;
  gap: 6px;
  margin-left: auto;
}

.filter-btn {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.filter-btn:hover {
  background: rgba(0, 212, 255, 0.1);
  color: #00d4ff;
}

.filter-btn.active {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
  border-color: rgba(0, 212, 255, 0.4);
}

.quick-actions-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 14px;
  flex-shrink: 0;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 12px 0;
}

.actions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 8px;
  background: rgba(0, 212, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 11px;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.3s ease;
}

.action-item:hover {
  background: rgba(0, 212, 255, 0.12);
  border-color: rgba(0, 212, 255, 0.3);
  color: #00d4ff;
}

.footer-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(26, 35, 50, 0.9) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  flex-shrink: 0;
}

.footer-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

.footer-actions {
  display: flex;
  gap: 12px;
}

.footer-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  text-decoration: none;
}

.footer-btn.secondary {
  background: transparent;
  border: 1px solid rgba(0, 212, 255, 0.3);
  color: #00d4ff;
}

.footer-btn.secondary:hover {
  background: rgba(0, 212, 255, 0.1);
}

.footer-btn.primary {
  background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
  border: none;
  color: #fff;
}

.footer-btn.primary:hover {
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.4);
}
</style>