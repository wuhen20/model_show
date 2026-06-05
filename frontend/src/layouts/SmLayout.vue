<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterView } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'

const route = useRoute()
const pageTitle = computed(() => (route.meta.title as string) || '小模型平台')
</script>

<template>
  <div class="app-shell">
    <Header :title="pageTitle" subtitle="国家电网 · 小模型展示平台" />
    <div class="app-body">
      <Sidebar />
      <main class="app-main">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.app-main {
  flex: 1;
  overflow: auto;
  padding: 16px 20px;
}
</style>
