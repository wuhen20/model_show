import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import ModelService from '@/views/ModelService.vue'
import AbilityExperience from '@/views/AbilityExperience.vue'

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
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
