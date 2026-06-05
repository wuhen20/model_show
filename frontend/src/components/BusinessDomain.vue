<template>
  <div class="business-domain">
    <el-row :gutter="16">
      <el-col :span="4" v-for="domain in domains" :key="domain.name">
        <div class="domain-card">
          <div class="domain-header">
            <div class="domain-icon" :style="{ backgroundColor: domain.color }">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2">
                <path :d="domain.iconPath"/>
              </svg>
            </div>
            <div class="domain-info">
              <div class="domain-name">{{ domain.name }}</div>
              <div class="domain-count">
                <span class="number">{{ domain.count.toLocaleString() }}</span>
                <span class="unit">份</span>
              </div>
            </div>
          </div>

          <div class="domain-tags">
            <span
              v-for="tag in domain.tags"
              :key="tag"
              class="domain-tag"
              :style="{ backgroundColor: domain.tagBg, color: domain.color }"
            >{{ tag }}</span>
          </div>

          <div class="domain-details">
            <div class="detail-item">
              <span class="label">核心知识</span>
              <span class="value">{{ domain.coreKnowledge.toLocaleString() }} 份</span>
            </div>
            <div class="detail-item">
              <span class="label">关键规则</span>
              <span class="value">{{ domain.keyRules }} 条</span>
            </div>
            <div class="detail-item">
              <span class="label">知识图谱实体</span>
              <span class="value">{{ domain.entities.toLocaleString() }} 个</span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
const domains = [
  {
    name: '计量领域',
    count: 3596,
    color: '#00d4ff',
    tagBg: 'rgba(0, 212, 255, 0.15)',
    tags: ['计量检测', '装表接电', '计量异常'],
    coreKnowledge: 1256,
    keyRules: 632,
    entities: 8652,
    iconPath: 'M3 3h18v18H3zM9 3v18M15 3v18M3 9h18M3 15h18'
  },
  {
    name: '采集运维领域',
    count: 2812,
    color: '#00ff88',
    tagBg: 'rgba(0, 255, 136, 0.15)',
    tags: ['采集运维', '通信网管', '数据治理'],
    coreKnowledge: 1032,
    keyRules: 512,
    entities: 6824,
    iconPath: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5'
  },
  {
    name: '用电管理领域',
    count: 2352,
    color: '#a855f7',
    tagBg: 'rgba(168, 85, 247, 0.15)',
    tags: ['用电分析', '线损管理', '电能质量'],
    coreKnowledge: 856,
    keyRules: 428,
    entities: 5632,
    iconPath: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8'
  },
  {
    name: '设备管理领域',
    count: 1570,
    color: '#ffaa00',
    tagBg: 'rgba(255, 170, 0, 0.15)',
    tags: ['设备运维', '故障诊断', '寿命管理'],
    coreKnowledge: 632,
    keyRules: 312,
    entities: 3856,
    iconPath: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm9.5-2.5a1.5 1.5 0 0 1-1.5-1.5v-1a1.5 1.5 0 0 1 3 0v1a1.5 1.5 0 0 1-1.5 1.5z'
  },
  {
    name: '市场与交易领域',
    count: 1230,
    color: '#ff5555',
    tagBg: 'rgba(255, 85, 85, 0.15)',
    tags: ['电力交易', '辅助服务', '市场监管'],
    coreKnowledge: 456,
    keyRules: 256,
    entities: 2682,
    iconPath: 'M18 20V10M12 20V4M6 20v-6'
  },
  {
    name: '其他领域',
    count: 1008,
    color: '#36a3f7',
    tagBg: 'rgba(54, 163, 247, 0.15)',
    tags: ['安全管理', '综合管理', '其他'],
    coreKnowledge: 200,
    keyRules: 128,
    entities: 1500,
    iconPath: 'M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z'
  }
]
</script>

<style scoped>
.business-domain {
  margin-bottom: 16px;
  clear: both;
}

.domain-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
  transition: all 0.3s;
  cursor: pointer;
}

.domain-card:hover {
  border-color: rgba(0, 212, 255, 0.4);
  box-shadow: 0 4px 20px rgba(0, 212, 255, 0.1);
  transform: translateY(-2px);
}

.domain-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.domain-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.domain-info {
  flex: 1;
}

.domain-name {
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 4px;
}

.domain-count {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.domain-count .number {
  font-size: 20px;
  font-weight: 600;
  color: #ffffff;
  line-height: 1;
}

.domain-count .unit {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.domain-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}

.domain-tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}

.domain-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid rgba(0, 212, 255, 0.08);
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-item .label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

.detail-item .value {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
}
</style>
