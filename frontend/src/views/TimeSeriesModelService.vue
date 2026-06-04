<script setup lang="ts">
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import PredictView from '@/timeseries/views/PredictView.vue'
</script>

<template>
  <div class="app-layout">
    <Header title="模型服务 · 时序模型服务" subtitle="基于 Chronos-2 的时序数据预测服务" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area ts-content">
        <PredictView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: auto;
  padding: 12px 16px;
  min-height: 0;
}

.ts-content :deep(.predict-view) {
  max-width: none !important;
}
</style>
