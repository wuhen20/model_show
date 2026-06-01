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
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
