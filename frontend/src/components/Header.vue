<script setup lang="ts">
import { RouterLink } from 'vue-router'

defineProps<{
  title: string
  subtitle?: string
}>()
</script>

<template>
  <header class="header">
    <div class="header-left">
      <div class="title-section">
        <h1 class="main-title">样本管理平台</h1>
        <span v-if="subtitle" class="main-subtitle">{{ subtitle }}</span>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(26, 35, 50, 0.9) 100%);
  border-bottom: 1px solid rgba(0, 212, 255, 0.2);
  backdrop-filter: blur(10px);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 24px;
}

.title-section {
  display: flex;
  flex-direction: column;
}

.main-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

.main-subtitle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}
</style>
