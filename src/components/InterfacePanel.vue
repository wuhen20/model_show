<script setup lang="ts">
import { invokeInfo } from '@/data/models'
</script>

<template>
  <div class="interface-panel">
    <div class="panel-header">
      <span class="panel-title">接口调试与调用信息</span>
    </div>
    <div class="endpoint-section">
      <div class="endpoint-header">
        <span class="method-badge">{{ invokeInfo.method }}</span>
        <span class="endpoint-url">{{ invokeInfo.endpoint }}</span>
        <span class="status-badge" :class="invokeInfo.status === '正常' ? 'success' : 'error'">
          {{ invokeInfo.status }}
        </span>
      </div>
    </div>
    <div class="stats-row">
      <div class="stat-item">
        <span class="stat-value">{{ invokeInfo.historyCalls }}</span>
        <span class="stat-label">历史调用</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ invokeInfo.todayCalls }}</span>
        <span class="stat-label">今日调用</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ invokeInfo.peakCalls }}</span>
        <span class="stat-label">峰值调用</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ invokeInfo.totalCalls }}</span>
        <span class="stat-label">累计调用</span>
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
</template>

<style scoped>
.interface-panel {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
}

.panel-header {
  margin-bottom: 16px;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.endpoint-section {
  margin-bottom: 16px;
}

.endpoint-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.method-badge {
  padding: 4px 10px;
  background: rgba(0, 255, 136, 0.2);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #00ff88;
}

.endpoint-url {
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 13px;
  color: #00d4ff;
}

.status-badge {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.success {
  background: rgba(0, 255, 136, 0.2);
  color: #00ff88;
}

.status-badge.error {
  background: rgba(255, 85, 85, 0.2);
  color: #ff5555;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-item {
  background: rgba(0, 212, 255, 0.05);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
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
  padding: 10px 12px;
  background: rgba(0, 212, 255, 0.1);
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
}

.code-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.copy-btn {
  padding: 4px 10px;
  background: rgba(0, 212, 255, 0.2);
  border: none;
  border-radius: 4px;
  color: #00d4ff;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.copy-btn:hover {
  background: rgba(0, 212, 255, 0.3);
}

.code-block {
  margin: 0;
  padding: 12px;
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  color: #00ff88;
  overflow-x: auto;
}

.code-block code {
  white-space: pre;
}
</style>
