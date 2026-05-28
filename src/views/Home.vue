<script setup lang="ts">
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import StatsCard from '@/components/StatsCard.vue'
import ModelTable from '@/components/ModelTable.vue'
import ServiceDetail from '@/components/ServiceDetail.vue'
import TaskPanel from '@/components/TaskPanel.vue'
import FlowChart from '@/components/FlowChart.vue'
import InvokeChart from '@/components/InvokeChart.vue'
import InterfacePanel from '@/components/InterfacePanel.vue'
import ServiceOverview from '@/components/ServiceOverview.vue'
import { statistics } from '@/data/models'
</script>

<template>
  <div class="app-layout">
    <Header title="人工智能分部 · 模型微调组" />
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
                  <button class="filter-btn active">全部</button>
                  <button class="filter-btn">语言模型</button>
                  <button class="filter-btn">视觉模型</button>
                  <button class="filter-btn">时序模型</button>
                  <button class="filter-btn">语音模型</button>
                </div>
                <div class="workspace-search">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="M21 21l-4.35-4.35"/>
                  </svg>
                  <input type="text" placeholder="搜索服务名称/模型/版本" class="search-input"/>
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
          </div>
        </div>
        <div class="bottom-grid">
          <div class="bottom-left">
            <FlowChart />
          </div>
          <div class="bottom-center">
            <div class="monitor-section">
              <div class="section-header">
                <span class="section-title">调用与资源监控</span>
                <span class="section-subtitle">近24小时</span>
              </div>
              <div class="monitor-grid">
                <div class="monitor-card">
                  <div class="monitor-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                      <path d="M18 20V10M12 20V4M6 20v-6"/>
                    </svg>
                  </div>
                  <div class="monitor-info">
                    <span class="monitor-value">{{ statistics.todayCalls.toLocaleString() }}</span>
                    <span class="monitor-label">调用总数</span>
                  </div>
                </div>
                <div class="monitor-card">
                  <div class="monitor-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00ff88" stroke-width="2">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    </svg>
                  </div>
                  <div class="monitor-info">
                    <span class="monitor-value">{{ statistics.successRate }}%</span>
                    <span class="monitor-label">成功率</span>
                  </div>
                </div>
                <div class="monitor-card">
                  <div class="monitor-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffaa00" stroke-width="2">
                      <path d="M12 12v-4l-3 3"/>
                    </svg>
                  </div>
                  <div class="monitor-info">
                    <span class="monitor-value">{{ statistics.avgLatency }}s</span>
                    <span class="monitor-label">平均响应</span>
                  </div>
                </div>
              </div>
              <div class="charts-row">
                <InvokeChart />
              </div>
            </div>
          </div>
          <div class="bottom-right">
            <InterfacePanel />
          </div>
        </div>
        <div class="footer-bar">
          <span class="footer-text">统一封装、统一发布、统一监控，沉淀可复用模型服务资产</span>
          <div class="footer-actions">
            <button class="footer-btn secondary">返回工作台</button>
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
  grid-template-columns: 1fr 1fr 360px;
  gap: 12px;
  margin-bottom: 10px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.left-column {
  grid-column: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.center-column {
  grid-column: 2;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.right-column {
  grid-column: 3;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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
  margin-bottom: 16px;
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

.workspace-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.5);
}

.search-input {
  background: transparent;
  border: none;
  outline: none;
  color: #fff;
  font-size: 12px;
  width: 200px;
}

.search-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.bottom-grid {
  display: grid;
  grid-template-columns: 350px 1fr 350px;
  gap: 12px;
  margin-bottom: 10px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.bottom-left {
  grid-column: 1;
  overflow: hidden;
  min-height: 0;
}

.bottom-center {
  grid-column: 2;
  overflow: hidden;
  min-height: 0;
}

.bottom-right {
  grid-column: 3;
  overflow: hidden;
  min-height: 0;
}

.monitor-section {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 12px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.section-subtitle {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.monitor-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.monitor-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(0, 212, 255, 0.05);
  border-radius: 8px;
}

.monitor-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 212, 255, 0.1);
  border-radius: 8px;
}

.monitor-info {
  display: flex;
  flex-direction: column;
}

.monitor-value {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.monitor-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.charts-row {
  flex: 1;
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
