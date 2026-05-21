<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
const collapsed = ref(false)

const menuItems = [
  { id: 'home', name: '工作台首页', icon: 'home', path: '/' },
  { id: 'experience', name: '能力体验', icon: 'zap', path: '/ability-experience' },
  { id: 'service', name: '模型服务', icon: 'server', path: '/model-service' },
  { id: 'interface', name: '接口管理', icon: 'plug', path: '/interface' },
  { id: 'config', name: '场景配置', icon: 'settings', path: '/config' },
  { id: 'center', name: '样本中心', icon: 'database', path: '/sample' },
  { id: 'analysis', name: '评测分析', icon: 'bar-chart', path: '/analysis' },
  { id: 'monitor', name: '运行监控', icon: 'activity', path: '/monitor' },
  { id: 'log', name: '日志中心', icon: 'file-text', path: '/log' },
  { id: 'system', name: '系统设置', icon: 'cog', path: '/system' }
]

const getIconPath = (iconName: string) => {
  const icons: Record<string, string> = {
    home: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
    zap: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
    server: 'M22 12h-4l-3 9L9 3l-3 9H2',
    plug: 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z',
    settings: 'M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z',
    database: 'M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z',
    'bar-chart': 'M18 20V10M12 20V4M6 20v-6',
    activity: 'M18 20V10M12 20V4M6 20v-6',
    'file-text': 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z',
    cog: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm9.5-2.5a1.5 1.5 0 0 1-1.5-1.5v-1a1.5 1.5 0 0 1 3 0v1a1.5 1.5 0 0 1-1.5 1.5zm-19 0a1.5 1.5 0 0 1-1.5-1.5v-1a1.5 1.5 0 0 1 3 0v1a1.5 1.5 0 0 1-1.5 1.5zM12 4.5a1.5 1.5 0 0 1-1.5-1.5v-1a1.5 1.5 0 0 1 3 0v1A1.5 1.5 0 0 1 12 4.5zm0 19a1.5 1.5 0 0 1-1.5-1.5v-1a1.5 1.5 0 0 1 3 0v1a1.5 1.5 0 0 1-1.5 1.5zM5.5 9a1.5 1.5 0 0 1-1.5-1.5V6a1.5 1.5 0 0 1 3 0v1.5A1.5 1.5 0 0 1 5.5 9zm13 0a1.5 1.5 0 0 1-1.5-1.5V6a1.5 1.5 0 0 1 3 0v1.5a1.5 1.5 0 0 1-1.5 1.5z'
  }
  return icons[iconName] || icons.home
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="collapse-btn" @click="collapsed = !collapsed">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path :d="collapsed ? 'M9 18l6-6-6-6' : 'M15 18l-6-6 6-6'"/>
      </svg>
    </div>
    <nav class="sidebar-nav">
      <RouterLink
        v-for="item in menuItems"
        :key="item.id"
        :to="item.path"
        class="nav-item"
        :class="{ active: route.path === item.path }"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path :d="getIconPath(item.icon)"/>
        </svg>
        <span v-if="!collapsed">{{ item.name }}</span>
      </RouterLink>
    </nav>
    <div class="sidebar-footer">
      <button v-if="!collapsed" class="footer-btn">收起菜单</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 200px;
  height: calc(100vh - 65px);
  background: linear-gradient(180deg, rgba(17, 24, 39, 0.95) 0%, rgba(13, 17, 23, 0.98) 100%);
  border-right: 1px solid rgba(0, 212, 255, 0.15);
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.3s ease;
}

.sidebar.collapsed {
  width: 64px;
}

.collapse-btn {
  position: absolute;
  right: -8px;
  top: 20px;
  width: 16px;
  height: 16px;
  background: rgba(0, 212, 255, 0.2);
  border: 1px solid rgba(0, 212, 255, 0.3);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #00d4ff;
  transition: all 0.3s ease;
}

.collapse-btn:hover {
  background: rgba(0, 212, 255, 0.3);
}

.sidebar-nav {
  padding: 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  transition: all 0.3s ease;
}

.nav-item:hover {
  background: rgba(0, 212, 255, 0.1);
  color: #00d4ff;
}

.nav-item.active {
  background: rgba(0, 212, 255, 0.15);
  color: #00d4ff;
  border-left: 2px solid #00d4ff;
}

.nav-item svg {
  flex-shrink: 0;
}

.sidebar-footer {
  margin-top: auto;
  padding: 16px;
}

.footer-btn {
  width: 100%;
  padding: 8px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.footer-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.7);
}
</style>
