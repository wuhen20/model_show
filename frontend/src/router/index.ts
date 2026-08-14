import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import ModelService from '@/views/ModelService.vue'
import AbilityExperience from '@/views/AbilityExperience.vue'
import SmLayout from '@/layouts/SmLayout.vue'

const routes = [
  // ===== 原系统（视图自带 Header + Sidebar 布局）=====
  { path: '/', name: 'Home', component: Home, meta: { title: '工作台首页' } },
  { path: '/model-service', name: 'ModelService', component: ModelService, meta: { title: '模型服务' } },
  { path: '/ability-experience', name: 'AbilityExperience', component: AbilityExperience, meta: { title: '能力体验' } },

  // ===== 多模态目标检测（multimodal-llm）=====
  { path: '/multimodal-detection', name: 'MultimodalDetection', component: () => import('@/views/MultimodalDetection.vue'), meta: { title: '多模态目标检测' } },

  // ===== 样本中心（sxy-sample-center）=====
  { path: '/sample', name: 'SampleCenter', component: () => import('@/views/SampleCenter.vue'), meta: { title: '样本中心' } },
  { path: '/sample-set', name: 'SampleSetManagement', component: () => import('@/views/SampleSetManagement.vue'), meta: { title: '高质量样本管理' } },
  { path: '/sample-detail', name: 'SampleDetail', component: () => import('@/views/SampleDetail.vue'), meta: { title: '样本详情' } },
  { path: '/original-sample-set', name: 'OriginalSampleSetManagement', component: () => import('@/views/OriginalSampleSetManagement.vue'), meta: { title: '原始样本集管理' } },
  { path: '/original-sample-detail', name: 'OriginalSampleDetail', component: () => import('@/views/OriginalSampleDetail.vue'), meta: { title: '原始样本详情' } },
  { path: '/collect-task', name: 'SampleCollectTask', component: () => import('@/views/SampleCollectTask.vue'), meta: { title: '数据采集任务管理' } },
  { path: '/collect-task-detail', name: 'SampleCollectTaskDet', component: () => import('@/views/SampleCollectTaskDet.vue'), meta: { title: '采集任务明细' } },
  { path: '/clean-task', name: 'DataCleanTask', component: () => import('@/views/DataCleanTask.vue'), meta: { title: '样本数据清洗' } },
  { path: '/clean-task-edit', name: 'DataCleanTaskEdit', component: () => import('@/views/DataCleanTaskEdit.vue'), meta: { title: '清洗任务编排' } },
  { path: '/clean-result', name: 'DataCleanResult', component: () => import('@/views/DataCleanResult.vue'), meta: { title: '数据清洗结果' } },
  { path: '/label-task', name: 'LabelTask', component: () => import('@/views/LabelTask.vue'), meta: { title: '标注任务管理' } },
  { path: '/label-workbench', name: 'LabelWorkbench', component: () => import('@/views/LabelWorkbench.vue'), meta: { title: '标注工作台' } },

  // ===== 知识管理（liuqi-knowledgebase）=====
  { path: '/knowledge-management', name: 'KnowledgeManagement', component: () => import('@/views/KnowledgeManagement.vue'), meta: { title: '知识管理' } },
  { path: '/knowledge-detail/:id', name: 'KnowledgeDetail', component: () => import('@/views/KnowledgeDetail.vue'), meta: { title: '知识详情' } },
  { path: '/knowledge-create', name: 'KnowledgeCreate', component: () => import('@/views/KnowledgeCreate.vue'), meta: { title: '创建知识库' } },
  { path: '/knowledge-base/:id', name: 'KnowledgeBaseDetail', component: () => import('@/views/KnowledgeBaseDetail.vue'), meta: { title: '知识库详情' } },
  { path: '/folder-kb/:name', name: 'FolderKBDetail', component: () => import('@/views/FolderKBDetail.vue'), meta: { title: '文件夹知识库' } },

  // ===== 时序功能（time-series-large-model）=====
  { path: '/timeseries/sample-set', name: 'TimeSeriesSampleSet', component: () => import('@/views/TimeSeriesSampleSet.vue'), meta: { title: '时序样本集管理' } },
  { path: '/timeseries/model-service', name: 'TimeSeriesModelService', component: () => import('@/views/TimeSeriesModelService.vue'), meta: { title: '时序模型服务' } },
  { path: '/timeseries/analysis', name: 'TimeSeriesAnalysis', component: () => import('@/views/TimeSeriesAnalysis.vue'), meta: { title: '时序模型分析' } },

  // ===== 小模型平台（dev-algomodel，内容型视图统一包裹 SmLayout 外壳）=====
  {
    path: '/sm-platform',
    component: SmLayout,
    children: [
      { path: '/sm', name: 'SmDashboard', component: () => import('@/views/SmDashboard.vue'), meta: { title: '小模型平台 · 概览' } },
      { path: '/models', name: 'ModelsList', component: () => import('@/views/ModelsList.vue'), meta: { title: '小模型管理' } },
      { path: '/models/:code', name: 'ModelDetail', component: () => import('@/views/ModelDetail.vue'), meta: { title: '小模型详情' } },
      { path: '/training', name: 'TrainingList', component: () => import('@/views/TrainingList.vue'), meta: { title: '小模型训练' } },
      { path: '/experience', name: 'ExperienceHub', component: () => import('@/views/ExperienceHub.vue'), meta: { title: '小模型体验' } },
      { path: '/experience/:code', name: 'ExperienceDetail', component: () => import('@/views/ExperienceDetail.vue'), meta: { title: '小模型体验详情' } },
      { path: '/datasets', name: 'DatasetsList', component: () => import('@/views/DatasetsList.vue'), meta: { title: '训练数据集' } },
      { path: '/mcp', name: 'McpServiceList', component: () => import('@/views/McpServiceList.vue'), meta: { title: 'MCP 服务管理' } },
      { path: '/mcp/test', name: 'McpTest', component: () => import('@/views/McpTest.vue'), meta: { title: 'MCP 服务测试' } }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
