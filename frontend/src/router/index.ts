import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import ModelService from '@/views/ModelService.vue'
import AbilityExperience from '@/views/AbilityExperience.vue'
import SampleCenter from '@/views/SampleCenter.vue'
import SampleSetManagement from '@/views/SampleSetManagement.vue'
import SampleDetail from '@/views/SampleDetail.vue'

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
    path: '/sample',
    name: 'SampleCenter',
    component: SampleCenter
  },
  {
    path: '/sample-set',
    name: 'SampleSetManagement',
    component: SampleSetManagement
  },
  {
    path: '/sample-detail',
    name: 'SampleDetail',
    component: SampleDetail
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
