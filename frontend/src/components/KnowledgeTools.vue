<template>
  <div class="knowledge-tools">
    <div class="tools-header">
      <h3 class="tools-title">知识能力工具</h3>
    </div>

    <div class="tools-grid">
      <div class="tool-item" v-for="tool in tools" :key="tool.name">
        <div class="tool-icon" :style="{ backgroundColor: tool.bgColor }">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" :stroke="tool.color" stroke-width="2">
            <path :d="tool.iconPath"/>
          </svg>
        </div>
        <div class="tool-info">
          <div class="tool-name">{{ tool.name }}</div>
          <div class="tool-desc">{{ tool.desc }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const tools = [
  {
    name: '知识检索',
    desc: '精准检索知识内容',
    color: '#00d4ff',
    bgColor: 'rgba(0, 212, 255, 0.15)',
    iconPath: 'M11 17.25a6.25 6.25 0 1 1 0-12.5 6.25 6.25 0 0 1 0 12.5zM16 16l4.5 4.5'
  },
  {
    name: '智能问答',
    desc: '基于知识的智能问答',
    color: '#00ff88',
    bgColor: 'rgba(0, 255, 136, 0.15)',
    iconPath: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'
  },
  {
    name: '知识摘要',
    desc: '自动提炼知识要点',
    color: '#a855f7',
    bgColor: 'rgba(168, 85, 247, 0.15)',
    iconPath: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8'
  },
  {
    name: '知识关联分析',
    desc: '发现知识间关联关系',
    color: '#ffaa00',
    bgColor: 'rgba(255, 170, 0, 0.15)',
    iconPath: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71'
  },
  {
    name: '知识推荐',
    desc: '个性化知识推荐',
    color: '#ff5555',
    bgColor: 'rgba(255, 85, 85, 0.15)',
    iconPath: 'M12 2L15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'
  },
  {
    name: '知识对比',
    desc: '多版本差异对比',
    color: '#36a3f7',
    bgColor: 'rgba(54, 163, 247, 0.15)',
    iconPath: 'M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M12 20V4'
  },
  {
    name: '知识导出',
    desc: '导出知识内容与结构',
    color: '#ffaa00',
    bgColor: 'rgba(255, 170, 0, 0.15)',
    iconPath: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3'
  },
  {
    name: '知识订阅',
    desc: '订阅关注知识动态',
    color: '#eb2f96',
    bgColor: 'rgba(235, 47, 150, 0.15)',
    iconPath: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0'
  }
]
</script>

<style scoped>
.knowledge-tools {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
}

.tools-header {
  margin-bottom: 20px;
}

.tools-title {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 16px;
}

.tool-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.tool-item:hover {
  background-color: rgba(0, 212, 255, 0.08);
  transform: translateY(-2px);
}

.tool-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tool-info {
  text-align: center;
}

.tool-name {
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 4px;
}

.tool-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.4;
}
</style>
