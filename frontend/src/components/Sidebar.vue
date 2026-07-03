<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
const collapsed = ref(false)

interface MenuChild { id: string; name: string; path: string }
interface MenuItem { id: string; name: string; icon: string; path?: string; children?: MenuChild[] }

// 融合后的全平台导航（两级可展开）
const menuItems: MenuItem[] = [
  { id: 'home', name: '工作台首页', icon: 'home', path: '/' },
  { id: 'experience', name: '能力体验', icon: 'zap', path: '/ability-experience' },
  {
    id: 'service', name: '模型服务', icon: 'server', children: [
      { id: 'service-overview', name: '模型服务总览', path: '/model-service' },
      { id: 'service-mm', name: '多模态目标检测', path: '/multimodal-detection' },
      { id: 'service-ts', name: '时序模型服务', path: '/timeseries/model-service' }
    ]
  },
  {
    id: 'sm', name: '小模型平台', icon: 'cpu', children: [
      { id: 'sm-dash', name: '平台概览', path: '/sm' },
      { id: 'sm-models', name: '小模型管理', path: '/models' },
      { id: 'sm-training', name: '小模型训练', path: '/training' },
      { id: 'sm-exp', name: '小模型体验', path: '/experience' },
      { id: 'sm-ds', name: '训练数据集', path: '/datasets' },
      { id: 'sm-mcp', name: 'MCP 服务管理', path: '/mcp' },
      { id: 'sm-mcp-test', name: 'MCP 服务测试', path: '/mcp/test' }
    ]
  },
  { id: 'knowledge', name: '知识管理', icon: 'book', path: '/knowledge-management' },
  { id: 'center', name: '样本中心', icon: 'database', path: '/sample' },
  {
    id: 'sampleset', name: '样本集管理', icon: 'folder', children: [
      { id: 'sampleset-base', name: '样本集管理', path: '/sample-set' },
      { id: 'sampleset-ts', name: '时序样本集管理', path: '/timeseries/sample-set' },
      { id: 'sampleset-collect', name: '数据采集任务', path: '/collect-task' },
      { id: 'sampleset-clean', name: '样本数据清理', path: '/clean-task' }
    ]
  },
  {
    id: 'analysis', name: '评测分析', icon: 'bar-chart', children: [
      { id: 'analysis-ts', name: '时序模型分析', path: '/timeseries/analysis' }
    ]
  },
  { id: 'interface', name: '接口管理', icon: 'plug', path: '/interface' },
  { id: 'config', name: '场景配置', icon: 'settings', path: '/config' },
  { id: 'monitor', name: '运行监控', icon: 'monitor', path: '/monitor' },
  { id: 'log', name: '日志中心', icon: 'file-text', path: '/log' },
  { id: 'system', name: '系统设置', icon: 'cog', path: '/system' }
]

const isChildActive = (item: MenuItem) => !!item.children?.some(c => route.path === c.path)

// 展开状态：默认展开当前激活的父级
const expanded = reactive<Record<string, boolean>>({})
menuItems.forEach(i => { if (i.children) expanded[i.id] = isChildActive(i) })

const toggleGroup = (item: MenuItem) => {
  if (collapsed.value) collapsed.value = false
  expanded[item.id] = !expanded[item.id]
}

const getIconPath = (iconName: string) => {
  const icons: Record<string, string> = {
    home: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
    zap: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
    server: 'M22 12h-4l-3 9L9 3l-3 9H2',
    plug: 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z',
    settings: 'M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z',
    database: 'M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z',
    folder: 'M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z',
    'bar-chart': 'M18 20V10M12 20V4M6 20v-6',
    activity: 'M18 20V10M12 20V4M6 20v-6',
    monitor: 'M3 4h18v12H3zM8 21h8M12 17v4',
    'file-text': 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z',
    cpu: 'M4 4h16v16H4zM9 9h6v6H9zM9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3',
    book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z',
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
      <template v-for="item in menuItems" :key="item.id">
        <!-- 叶子菜单 -->
        <RouterLink
          v-if="!item.children"
          :to="item.path!"
          class="nav-item"
          :class="{ active: route.path === item.path }"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path :d="getIconPath(item.icon)"/>
          </svg>
          <span v-if="!collapsed">{{ item.name }}</span>
        </RouterLink>

        <!-- 含二级目录的父级 -->
        <div v-else class="nav-group">
          <div
            class="nav-item nav-parent"
            :class="{ active: isChildActive(item), open: expanded[item.id] }"
            @click="toggleGroup(item)"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path :d="getIconPath(item.icon)"/>
            </svg>
            <span v-if="!collapsed" class="nav-parent-label">{{ item.name }}</span>
            <svg
              v-if="!collapsed"
              class="chevron"
              :class="{ open: expanded[item.id] }"
              width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            >
              <path d="M6 9l6 6 6-6"/>
            </svg>
          </div>
          <div v-if="!collapsed && expanded[item.id]" class="submenu">
            <RouterLink
              v-for="child in item.children"
              :key="child.id"
              :to="child.path"
              class="subnav-item"
              :class="{ active: route.path === child.path }"
            >
              <span class="dot"></span>
              <span>{{ child.name }}</span>
            </RouterLink>
          </div>
        </div>
      </template>
    </nav>
    <div class="sidebar-footer">
      <button v-if="!collapsed" class="footer-btn">收起菜单</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 200px;
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
  z-index: 2;
}

.collapse-btn:hover {
  background: rgba(0, 212, 255, 0.3);
}

.sidebar-nav {
  padding: 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
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

/* 含子菜单的父级 */
.nav-group {
  display: flex;
  flex-direction: column;
}

.nav-parent {
  cursor: pointer;
  user-select: none;
}

.nav-parent .nav-parent-label {
  flex: 1;
}

.chevron {
  transition: transform 0.3s ease;
  opacity: 0.7;
}

.chevron.open {
  transform: rotate(180deg);
}

/* 二级菜单 */
.submenu {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 2px 0 4px 0;
  padding-left: 12px;
  border-left: 1px solid rgba(0, 212, 255, 0.15);
}

.subnav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
  font-size: 13px;
  transition: all 0.3s ease;
}

.subnav-item .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
  transition: all 0.3s ease;
}

.subnav-item:hover {
  background: rgba(0, 212, 255, 0.08);
  color: #00d4ff;
}

.subnav-item.active {
  background: rgba(0, 212, 255, 0.12);
  color: #00d4ff;
}

.subnav-item.active .dot {
  background: #00d4ff;
  box-shadow: 0 0 8px #00d4ff;
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
