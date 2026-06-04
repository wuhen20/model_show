<script setup lang="ts">
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import AnalysisView from '@/timeseries/views/AnalysisView.vue'
</script>

<template>
  <div class="app-layout">
    <Header title="评测分析 · 时序模型分析" subtitle="时序预测结果可视化与精度评估（R² / MAPE）" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area ts-content">
        <AnalysisView />
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

.ts-content :deep(.analysis-view) {
  max-width: none !important;
}
</style>
