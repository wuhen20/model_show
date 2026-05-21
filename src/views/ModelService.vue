<script setup lang="ts">
import { ref } from 'vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import StatsCard from '@/components/StatsCard.vue'
import TaskPanel from '@/components/TaskPanel.vue'
import ServiceOverview from '@/components/ServiceOverview.vue'
import { statistics, mockOutput, sceneTemplates, invokeInfo } from '@/data/models'

const activeModel = ref('Qwen3-14B-sichuan')
const inputContent = ref('请结合台区电压变化、采集成功率、线损率和档案变更等信息，对本月线损异常进行分析并给出处置建议。')
const selectedTemplate = ref('')

const modelOptions = [
  { id: 'Qwen3-14B-sichuan', name: 'Qwen3-14B-sichuan', type: '语言模型' },
  { id: 'Qwen3-VL', name: 'Qwen3-VL', type: '视觉模型' },
  { id: 'Chroma2', name: 'Chroma2', type: '时序模型' },
  { id: 'Qwen-ASR', name: 'Qwen-ASR', type: '语音模型' }
]

const getAnomalyLevelClass = (level: string) => {
  if (level === '正常') return 'normal'
  if (level === '低风险') return 'low'
  if (level === '中风险') return 'medium'
  return 'high'
}
</script>

<template>
  <div class="app-layout">
    <Header title="人工智能分部 · 模型微调组" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="stats-grid">
          <StatsCard
            title="在线模型"
            :value="statistics.onlineModels"
            icon="online-models"
          />
          <StatsCard
            title="接口总数"
            :value="statistics.totalInterfaces"
            icon="total-interfaces"
          />
          <StatsCard
            title="今日调用"
            :value="statistics.todayCalls.toLocaleString()"
            unit="次"
            icon="today-calls"
          />
          <StatsCard
            title="平均响应"
            :value="statistics.avgLatency"
            unit="s"
            icon="avg-latency"
          />
          <StatsCard
            title="成功率"
            :value="statistics.successRate"
            unit="%"
            icon="success-rate"
          />
        </div>
        <div class="main-grid">
          <div class="left-column">
            <div class="experience-panel">
              <div class="panel-header">
                <span class="panel-title">模型能力体验区</span>
              </div>
              <div class="model-selector">
                <div class="selector-tabs">
                  <button
                    v-for="option in modelOptions"
                    :key="option.id"
                    class="selector-tab"
                    :class="{ active: activeModel === option.id }"
                    @click="activeModel = option.id"
                  >
                    <span class="tab-name">{{ option.name }}</span>
                    <span class="tab-type">{{ option.type }}</span>
                  </button>
                </div>
              </div>
              <div class="input-section">
                <div class="section-header">
                  <span class="section-title">输入内容</span>
                  <span class="char-count">{{ inputContent.length }}/500</span>
                </div>
                <textarea
                  v-model="inputContent"
                  class="input-textarea"
                  placeholder="请输入您的问题或分析需求..."
                  rows="6"
                ></textarea>
              </div>
              <div class="quick-actions">
                <span class="actions-label">快捷操作</span>
                <div class="action-buttons">
                  <button class="action-btn">运行体验</button>
                  <button class="action-btn secondary">保存场景</button>
                  <button class="action-btn secondary">加载样例</button>
                  <button class="action-btn secondary">导出结果</button>
                </div>
              </div>
            </div>
            <div class="templates-panel">
              <div class="panel-header">
                <span class="panel-title">场景模板库</span>
                <button class="more-btn">全部模板</button>
              </div>
              <div class="templates-grid">
                <button
                  v-for="template in sceneTemplates"
                  :key="template.id"
                  class="template-btn"
                  :class="{ active: selectedTemplate === template.id }"
                  @click="selectedTemplate = template.id"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                    <path v-if="template.icon === 'trending-up'" d="M18 20V10M12 20V4M6 20v-6"/>
                    <path v-else-if="template.icon === 'wrench'" d="M12 20V10M16 16l4-4-4-4M8 8l-4 4 4 4"/>
                    <path v-else-if="template.icon === 'zap'" d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                    <path v-else-if="template.icon === 'image'" d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                    <path v-else d="M18 20V10M12 20V4M6 20v-6"/>
                  </svg>
                  <span>{{ template.name }}</span>
                </button>
              </div>
            </div>
            <div class="invoke-panel">
              <div class="panel-header">
                <span class="panel-title">接口调试与调用信息</span>
              </div>
              <div class="invoke-info">
                <div class="info-row">
                  <span class="info-label">接口地址</span>
                  <span class="info-value">{{ invokeInfo.endpoint }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">方法</span>
                  <span class="info-value method">{{ invokeInfo.method }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">状态</span>
                  <span class="info-value status success">{{ invokeInfo.status }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">历史调用</span>
                  <span class="info-value">{{ invokeInfo.historyCalls }}</span>
                </div>
              </div>
              <div class="code-section">
                <div class="code-header">
                  <span class="code-title">示例请求</span>
                  <button class="copy-btn">复制</button>
                </div>
                <pre class="code-block"><code>{
  "model": "Qwen3-14B-sichuan-chat",
  "messages": [
    {
      "role": "user",
      "content": "请结合台区电压变化、采集成功率、线损率和档案变更等信息，对本月线损异常进行分析并给出处置建议。"
    }
  ],
  "temperature": 0.7
}</code></pre>
              </div>
            </div>
          </div>
          <div class="center-column">
            <div class="output-panel">
              <div class="panel-header">
                <span class="panel-title">模型输出结果</span>
                <div class="panel-tabs">
                  <button class="tab-btn active">结果展示</button>
                  <button class="tab-btn">JSON</button>
                  <button class="tab-btn">耗时信息</button>
                </div>
              </div>
              <div class="output-content">
                <div class="anomaly-header">
                  <span class="anomaly-label">异常等级</span>
                  <span class="anomaly-value" :class="getAnomalyLevelClass(mockOutput.anomalyLevel)">
                    {{ mockOutput.anomalyLevel }}
                  </span>
                </div>
                <div class="result-section">
                  <h4 class="section-title">异常描述</h4>
                  <p class="result-text">{{ mockOutput.cause }}</p>
                </div>
                <div class="result-section">
                  <h4 class="section-title">处置建议</h4>
                  <ul class="suggestions-list">
                    <li v-for="(suggestion, index) in mockOutput.suggestions" :key="index" class="suggestion-item">
                      <span class="suggestion-num">{{ index + 1 }}</span>
                      <span class="suggestion-text">{{ suggestion }}</span>
                    </li>
                  </ul>
                </div>
                <div class="result-footer">
                  <span class="result-time">输出时间: {{ mockOutput.timestamp }}</span>
                  <span class="token-count">Tokens: 2,164</span>
                </div>
              </div>
            </div>
            <div class="monitor-panel">
              <div class="panel-header">
                <span class="panel-title">运行监控</span>
                <div class="monitor-tabs">
                  <button class="tab-btn active">调用概览</button>
                  <button class="tab-btn">性能指标</button>
                </div>
              </div>
              <div class="monitor-stats">
                <div class="monitor-item">
                  <span class="monitor-value">{{ statistics.todayCalls.toLocaleString() }}</span>
                  <span class="monitor-label">调用总数</span>
                </div>
                <div class="monitor-item">
                  <span class="monitor-value">{{ statistics.successRate }}%</span>
                  <span class="monitor-label">成功率</span>
                </div>
                <div class="monitor-item">
                  <span class="monitor-value">{{ statistics.avgLatency }}s</span>
                  <span class="monitor-label">平均响应时间</span>
                </div>
              </div>
              <div class="charts-container">
                <div class="chart-item">
                  <div class="chart-header">
                    <span class="chart-title">调用趋势</span>
                    <span class="chart-time">近24小时</span>
                  </div>
                  <div class="mini-chart">
                    <svg width="100%" height="60" viewBox="0 0 200 60">
                      <defs>
                        <linearGradient id="lineGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                          <stop offset="0%" style="stop-color:#00d4ff;stop-opacity:0.4"/>
                          <stop offset="100%" style="stop-color:#00d4ff;stop-opacity:0"/>
                        </linearGradient>
                      </defs>
                      <path d="M0 50 Q25 45 50 35 T100 25 T150 40 T200 20" fill="none" stroke="#00d4ff" stroke-width="2"/>
                      <path d="M0 50 Q25 45 50 35 T100 25 T150 40 T200 20 L200 60 L0 60 Z" fill="url(#lineGradient)"/>
                    </svg>
                  </div>
                </div>
                <div class="chart-item">
                  <div class="chart-header">
                    <span class="chart-title">GPU使用率</span>
                    <span class="chart-time">实时</span>
                  </div>
                  <div class="mini-chart">
                    <svg width="100%" height="60" viewBox="0 0 200 60">
                      <defs>
                        <linearGradient id="barGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                          <stop offset="0%" style="stop-color:#00ff88;stop-opacity:0.6"/>
                          <stop offset="100%" style="stop-color:#00ff88;stop-opacity:0.2"/>
                        </linearGradient>
                      </defs>
                      <rect x="10" y="10" width="15" height="40" fill="url(#barGradient)" rx="3"/>
                      <rect x="35" y="5" width="15" height="45" fill="url(#barGradient)" rx="3"/>
                      <rect x="60" y="15" width="15" height="35" fill="url(#barGradient)" rx="3"/>
                      <rect x="85" y="8" width="15" height="42" fill="url(#barGradient)" rx="3"/>
                      <rect x="110" y="12" width="15" height="38" fill="url(#barGradient)" rx="3"/>
                      <rect x="135" y="6" width="15" height="44" fill="url(#barGradient)" rx="3"/>
                      <rect x="160" y="18" width="15" height="32" fill="url(#barGradient)" rx="3"/>
                      <rect x="185" y="10" width="15" height="40" fill="url(#barGradient)" rx="3"/>
                    </svg>
                  </div>
                </div>
                <div class="chart-item">
                  <div class="chart-header">
                    <span class="chart-title">平均响应时间</span>
                    <span class="chart-time">近24小时</span>
                  </div>
                  <div class="mini-chart">
                    <svg width="100%" height="60" viewBox="0 0 200 60">
                      <defs>
                        <linearGradient id="timeGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                          <stop offset="0%" style="stop-color:#ffaa00;stop-opacity:0.4"/>
                          <stop offset="100%" style="stop-color:#ffaa00;stop-opacity:0"/>
                        </linearGradient>
                      </defs>
                      <path d="M0 30 Q25 25 50 35 T100 28 T150 32 T200 25" fill="none" stroke="#ffaa00" stroke-width="2"/>
                      <path d="M0 30 Q25 25 50 35 T100 28 T150 32 T200 25 L200 60 L0 60 Z" fill="url(#timeGradient)"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="right-column">
            <ServiceOverview />
            <div class="quick-panel">
              <div class="panel-header">
                <span class="panel-title">待办事项</span>
              </div>
              <div class="task-list">
                <div class="task-item">
                  <span class="task-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                      <circle cx="12" cy="12" r="10"/>
                      <polyline points="12 6 12 12 16 14"/>
                    </svg>
                  </span>
                  <span class="task-text">新增模型样本（设备缺陷）</span>
                  <span class="task-status processing">进行中</span>
                </div>
                <div class="task-item">
                  <span class="task-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                      <circle cx="12" cy="12" r="10"/>
                      <polyline points="12 6 12 12 16 14"/>
                    </svg>
                  </span>
                  <span class="task-text">完成时序模型训练（负荷预测）</span>
                  <span class="task-status pending">待处理</span>
                </div>
                <div class="task-item">
                  <span class="task-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                      <circle cx="12" cy="12" r="10"/>
                      <polyline points="12 6 12 12 16 14"/>
                    </svg>
                  </span>
                  <span class="task-text">更新模型服务（线损分析 v2.0）</span>
                  <span class="task-status pending">待处理</span>
                </div>
              </div>
            </div>
            <div class="logs-panel">
              <div class="panel-header">
                <span class="panel-title">最近操作日志</span>
              </div>
              <div class="logs-list">
                <div class="log-item">
                  <span class="log-time">10:24:45</span>
                  <span class="log-action">调用模型: Qwen3-14B-sichuan-chat</span>
                </div>
                <div class="log-item">
                  <span class="log-time">10:23:15</span>
                  <span class="log-action">调用模型: Qwen3-VL-visual</span>
                </div>
                <div class="log-item">
                  <span class="log-time">10:21:30</span>
                  <span class="log-action">保存场景: 台区线损分析 v2.0</span>
                </div>
                <div class="log-item">
                  <span class="log-time">10:18:00</span>
                  <span class="log-action">用户登录: zhanggong</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="footer-bar">
          <span class="footer-text">统一封装、统一体验、统一评估，沉淀可复用模型能力资产</span>
          <div class="footer-actions">
            <button class="footer-btn secondary">返回总览</button>
            <button class="footer-btn primary">发布服务</button>
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
  min-height: 100vh;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.main-grid {
  display: grid;
  grid-template-columns: 400px 1fr 320px;
  gap: 20px;
  margin-bottom: 20px;
}

.left-column {
  grid-column: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.center-column {
  grid-column: 2;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.right-column {
  grid-column: 3;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.experience-panel, .templates-panel, .invoke-panel {
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
}

.more-btn:hover {
  background: rgba(0, 212, 255, 0.1);
  color: #00d4ff;
}

.model-selector {
  margin-bottom: 16px;
}

.selector-tabs {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.selector-tab {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(0, 212, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.selector-tab:hover {
  border-color: rgba(0, 212, 255, 0.3);
}

.selector-tab.active {
  background: rgba(0, 212, 255, 0.2);
  border-color: rgba(0, 212, 255, 0.4);
}

.tab-name {
  font-size: 12px;
  color: #fff;
}

.tab-type {
  padding: 2px 6px;
  background: rgba(0, 212, 255, 0.15);
  border-radius: 3px;
  font-size: 10px;
  color: #00d4ff;
}

.input-section {
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.section-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.char-count {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.input-textarea {
  width: 100%;
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 8px;
  color: #fff;
  font-size: 12px;
  resize: none;
  outline: none;
  box-sizing: border-box;
}

.input-textarea::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.quick-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.actions-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 8px 14px;
  background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-btn:hover {
  box-shadow: 0 0 15px rgba(0, 212, 255, 0.4);
}

.action-btn.secondary {
  background: transparent;
  border: 1px solid rgba(0, 212, 255, 0.3);
  color: #00d4ff;
}

.action-btn.secondary:hover {
  background: rgba(0, 212, 255, 0.1);
}

.templates-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.template-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: rgba(0, 212, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.template-btn:hover {
  border-color: rgba(0, 212, 255, 0.3);
}

.template-btn.active {
  background: rgba(0, 212, 255, 0.2);
  border-color: rgba(0, 212, 255, 0.4);
}

.invoke-info {
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
}

.info-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.info-value {
  font-size: 12px;
  color: #fff;
}

.info-value.method {
  padding: 2px 8px;
  background: rgba(0, 255, 136, 0.2);
  border-radius: 4px;
  color: #00ff88;
}

.info-value.status.success {
  color: #00ff88;
}

.code-section {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  overflow: hidden;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: rgba(0, 212, 255, 0.1);
}

.code-title {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
}

.copy-btn {
  padding: 3px 8px;
  background: rgba(0, 212, 255, 0.2);
  border: none;
  border-radius: 3px;
  color: #00d4ff;
  font-size: 10px;
  cursor: pointer;
}

.code-block {
  margin: 0;
  padding: 10px;
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 10px;
  color: #00ff88;
  overflow-x: auto;
}

.output-panel, .monitor-panel {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 16px;
}

.panel-tabs {
  display: flex;
  gap: 8px;
}

.tab-btn {
  padding: 6px 12px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 11px;
  cursor: pointer;
}

.tab-btn.active {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.output-content {
  padding: 16px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 10px;
}

.anomaly-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
}

.anomaly-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
}

.anomaly-value {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
}

.anomaly-value.normal {
  background: rgba(0, 255, 136, 0.2);
  color: #00ff88;
}

.anomaly-value.low {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.anomaly-value.medium {
  background: rgba(255, 170, 0, 0.2);
  color: #ffaa00;
}

.anomaly-value.high {
  background: rgba(255, 85, 85, 0.2);
  color: #ff5555;
}

.result-section {
  margin-bottom: 16px;
}

.result-section .section-title {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 8px;
}

.result-text {
  margin: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.6;
}

.suggestions-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.suggestion-item {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
}

.suggestion-item:last-child {
  border-bottom: none;
}

.suggestion-num {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 212, 255, 0.2);
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  color: #00d4ff;
  flex-shrink: 0;
}

.suggestion-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.5;
}

.result-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(0, 212, 255, 0.15);
}

.result-time, .token-count {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.monitor-stats {
  display: flex;
  justify-content: space-around;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
}

.monitor-item {
  text-align: center;
}

.monitor-value {
  display: block;
  font-size: 24px;
  font-weight: 600;
  color: #fff;
}

.monitor-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.charts-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chart-item {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  padding: 12px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.chart-title {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
}

.chart-time {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
}

.mini-chart {
  width: 100%;
  height: 60px;
}

.quick-panel, .logs-panel {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 16px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: rgba(0, 212, 255, 0.05);
  border-radius: 8px;
}

.task-icon {
  color: #00d4ff;
}

.task-text {
  flex: 1;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.9);
}

.task-status {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
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

.logs-list {
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
  min-width: 70px;
}

.log-action {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
}

.footer-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(26, 35, 50, 0.9) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
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
