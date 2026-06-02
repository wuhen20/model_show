import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { title: '工作台首页' }
  },
  // 小模型管理
  {
    path: '/models',
    name: 'ModelsList',
    component: () => import('@/views/ModelsList.vue'),
    meta: { title: '小模型管理' }
  },
  {
    path: '/models/:code',
    name: 'ModelDetail',
    component: () => import('@/views/ModelDetail.vue'),
    meta: { title: '小模型详情' }
  },
  // 小模型训练
  {
    path: '/training',
    name: 'TrainingList',
    component: () => import('@/views/TrainingList.vue'),
    meta: { title: '小模型训练' }
  },
  // 小模型展示及体验
  {
    path: '/experience',
    name: 'ExperienceHub',
    component: () => import('@/views/ExperienceHub.vue'),
    meta: { title: '小模型体验' }
  },
  {
    path: '/experience/:code',
    name: 'ExperienceDetail',
    component: () => import('@/views/ExperienceDetail.vue'),
    meta: { title: '小模型体验详情' }
  },
  // 训练数据集管理
  {
    path: '/datasets',
    name: 'DatasetsList',
    component: () => import('@/views/DatasetsList.vue'),
    meta: { title: '训练数据集' }
  },
  // 小模型 MCP 服务管理
  {
    path: '/mcp',
    name: 'McpServiceList',
    component: () => import('@/views/McpServiceList.vue'),
    meta: { title: 'MCP 服务管理' }
  },
  // 小模型 MCP 服务测试
  {
    path: '/mcp/test',
    name: 'McpTest',
    component: () => import('@/views/McpTest.vue'),
    meta: { title: 'MCP 服务测试' }
  },
  // 兼容旧路由（重定向）
  { path: '/model-service', redirect: '/models' },
  { path: '/ability-experience', redirect: '/experience' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
