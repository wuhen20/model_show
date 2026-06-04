import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import ModelService from '@/views/ModelService.vue'
import AbilityExperience from '@/views/AbilityExperience.vue'
import KnowledgeManagement from '@/views/KnowledgeManagement.vue'
import KnowledgeDetail from '@/views/KnowledgeDetail.vue'

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
  {
    path: '/knowledge-management',
    name: 'KnowledgeManagement',
    component: KnowledgeManagement
  },
  {
    path: '/knowledge-detail/:id',
    name: 'KnowledgeDetail',
    component: KnowledgeDetail
  },
  {
    path: '/knowledge-create',
    name: 'KnowledgeCreate',
    component: () => import('@/views/KnowledgeCreate.vue')
  },
  {
    path: '/knowledge-base/:id',
    name: 'KnowledgeBaseDetail',
    component: () => import('@/views/KnowledgeBaseDetail.vue')
  },
  {
    path: '/folder-kb/:name',
    name: 'FolderKBDetail',
    component: () => import('@/views/FolderKBDetail.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
