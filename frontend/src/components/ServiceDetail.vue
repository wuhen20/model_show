<script setup lang="ts">
import { ref } from 'vue'

const activeTab = ref('basic')

const tabs = [
  { id: 'basic', name: '基本信息' },
  { id: 'config', name: '资源配置' },
  { id: 'publish', name: '发布参数' }
]

const basicInfo = {
  name: 'Qwen3-14B-sichuan-chat',
  model: 'Qwen3-14B',
  version: 'v1.6.2',
  serviceType: 'A100魔改',
  deployMode: '/h100/model-completions',
  authMode: 'Token',
  status: '运行中',
  updateTime: '2025-10-19 09:30'
}

const resourceConfig = {
  gpu: { used: 4, total: 4, percent: 72 },
  memory: { used: 38, total: 64, percent: 59 },
  storage: { used: 64, total: 128, percent: 50 }
}

const publishParams = [
  { key: 'model', value: 'Qwen3-14B-sichuan-chat' },
  { key: 'temperature', value: '0.7' },
  { key: 'max_tokens', value: '1024' },
  { key: 'top_p', value: '0.9' },
  { key: 'frequency_penalty', value: '0.0' },
  { key: 'presence_penalty', value: '0.0' },
  { key: 'stop', value: '["</s>"]' },
  { key: 'tool_calls', value: 'null' }
]
</script>

<template>
  <div class="service-detail">
    <div class="detail-header">
      <div class="header-info">
        <h3 class="detail-title">{{ basicInfo.name }}</h3>
        <span class="detail-tag">A100魔改</span>
      </div>
      <div class="header-actions">
        <button class="action-btn secondary">发布新版本</button>
        <button class="action-btn secondary">编辑配置</button>
        <button class="action-btn secondary">查看日志</button>
      </div>
    </div>
    <div class="tabs-wrapper">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.name }}
      </button>
    </div>
    <div class="tab-content">
      <div v-if="activeTab === 'basic'" class="basic-info">
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">服务名称</span>
            <span class="info-value">{{ basicInfo.name }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">基础模型</span>
            <span class="info-value">{{ basicInfo.model }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">版本号</span>
            <span class="info-value">{{ basicInfo.version }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">服务类型</span>
            <span class="info-value">{{ basicInfo.serviceType }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">部署方式</span>
            <span class="info-value">{{ basicInfo.deployMode }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">认证方式</span>
            <span class="info-value">{{ basicInfo.authMode }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">服务状态</span>
            <span class="info-value status-success">{{ basicInfo.status }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">最近更新</span>
            <span class="info-value">{{ basicInfo.updateTime }}</span>
          </div>
        </div>
      </div>
      <div v-if="activeTab === 'config'" class="config-info">
        <div class="config-section">
          <h4 class="config-title">资源配置</h4>
          <div class="config-grid">
            <div class="config-card">
              <div class="config-header">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                  <path d="M7 6h10M7 12h10M7 18h10"/>
                </svg>
                <span>GPU</span>
              </div>
              <div class="config-value">
                <span class="value-num">{{ resourceConfig.gpu.used }}</span>
                <span class="value-unit">/{{ resourceConfig.gpu.total }} 卡</span>
              </div>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: resourceConfig.gpu.percent + '%' }"></div>
              </div>
              <span class="progress-percent">{{ resourceConfig.gpu.percent }}%</span>
            </div>
            <div class="config-card">
              <div class="config-header">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00ff88" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <polyline points="12 6 12 12 16 14"/>
                </svg>
                <span>显存</span>
              </div>
              <div class="config-value">
                <span class="value-num">{{ resourceConfig.memory.used }}</span>
                <span class="value-unit">/{{ resourceConfig.memory.total }} GB</span>
              </div>
              <div class="progress-bar">
                <div class="progress-fill memory" :style="{ width: resourceConfig.memory.percent + '%' }"></div>
              </div>
              <span class="progress-percent">{{ resourceConfig.memory.percent }}%</span>
            </div>
            <div class="config-card">
              <div class="config-header">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffaa00" stroke-width="2">
                  <path d="M4 20h16a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z"/>
                </svg>
                <span>存储</span>
              </div>
              <div class="config-value">
                <span class="value-num">{{ resourceConfig.storage.used }}</span>
                <span class="value-unit">/{{ resourceConfig.storage.total }} GB</span>
              </div>
              <div class="progress-bar">
                <div class="progress-fill storage" :style="{ width: resourceConfig.storage.percent + '%' }"></div>
              </div>
              <span class="progress-percent">{{ resourceConfig.storage.percent }}%</span>
            </div>
          </div>
        </div>
      </div>
      <div v-if="activeTab === 'publish'" class="publish-info">
        <div class="publish-section">
          <h4 class="publish-title">发布参数</h4>
          <div class="params-list">
            <div v-for="param in publishParams" :key="param.key" class="param-item">
              <span class="param-key">{{ param.key }}</span>
              <span class="param-value">{{ param.value }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.service-detail {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
}

.header-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.detail-tag {
  padding: 4px 10px;
  background: rgba(0, 212, 255, 0.2);
  border-radius: 4px;
  font-size: 12px;
  color: #00d4ff;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-btn.secondary {
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.3);
  color: #00d4ff;
}

.action-btn.secondary:hover {
  background: rgba(0, 212, 255, 0.2);
}

.tabs-wrapper {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.tab-btn {
  padding: 10px 20px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.tab-btn:hover {
  background: rgba(0, 212, 255, 0.1);
}

.tab-btn.active {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.info-value {
  font-size: 14px;
  color: #fff;
}

.info-value.status-success {
  color: #00ff88;
}

.config-section {
  margin-bottom: 20px;
}

.config-title {
  margin: 0 0 16px 0;
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.config-card {
  background: rgba(0, 212, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.1);
  border-radius: 10px;
  padding: 16px;
}

.config-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.config-header span {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
}

.config-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 12px;
}

.value-num {
  font-size: 28px;
  font-weight: 600;
  color: #fff;
}

.value-unit {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #00d4ff 0%, #0099cc 100%);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-fill.memory {
  background: linear-gradient(90deg, #00ff88 0%, #00cc6a 100%);
}

.progress-fill.storage {
  background: linear-gradient(90deg, #ffaa00 0%, #cc8800 100%);
}

.progress-percent {
  display: block;
  text-align: right;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 4px;
}

.publish-section {
  margin-bottom: 20px;
}

.publish-title {
  margin: 0 0 16px 0;
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.params-list {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 8px;
  font-family: 'Monaco', 'Consolas', monospace;
}

.param-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.param-item:last-child {
  border-bottom: none;
}

.param-key {
  color: #ffaa00;
  font-size: 12px;
}

.param-value {
  color: #00ff88;
  font-size: 12px;
}
</style>
