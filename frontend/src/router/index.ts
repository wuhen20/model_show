import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import ModelService from '@/views/ModelService.vue'
import AbilityExperience from '@/views/AbilityExperience.vue'
import TimeSeriesSampleSet from '@/views/TimeSeriesSampleSet.vue'
import TimeSeriesModelService from '@/views/TimeSeriesModelService.vue'
import TimeSeriesAnalysis from '@/views/TimeSeriesAnalysis.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/model-service',
    name: 'ModelService',
    component: ModelService
  },
  {
    path: '/ability-experience',
    name: 'AbilityExperience',
    component: AbilityExperience
  },
  // 样本集管理 · 时序样本集管理（上传/预处理/整合/下载）
  {
    path: '/timeseries/sample-set',
    name: 'TimeSeriesSampleSet',
    component: TimeSeriesSampleSet
  },
  // 模型服务 · 时序模型服务（数据预测）
  {
    path: '/timeseries/model-service',
    name: 'TimeSeriesModelService',
    component: TimeSeriesModelService
  },
  // 评测分析 · 时序模型分析（数据分析）
  {
    path: '/timeseries/analysis',
    name: 'TimeSeriesAnalysis',
    component: TimeSeriesAnalysis
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
