<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  unit?: string
  change?: {
    value: string
    type: 'up' | 'down'
  }
  icon: string
}>()

const getIconPath = (iconName: string) => {
  const icons: Record<string, string> = {
    'online-models': 'M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z',
    'deployed-models': 'M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z',
    'today-calls': 'M12 8v4l3 3',
    'avg-latency': 'M12 12v-4l-3 3',
    'success-rate': 'M22 11.08V12a10 10 0 1 1-5.93-9.14',
    'total-interfaces': 'M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z'
  }
  return icons[iconName] || icons['online-models']
}
</script>

<template>
  <div class="stats-card">
    <div class="card-icon">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path :d="getIconPath(icon)"/>
      </svg>
    </div>
    <div class="card-content">
      <div class="card-title">{{ title }}</div>
      <div class="card-value">
        <span>{{ value }}</span>
        <span v-if="unit" class="card-unit">{{ unit }}</span>
      </div>
      <div v-if="change" class="card-change" :class="change.type">
        <svg v-if="change.type === 'up'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M5 10l7-7 7 7"/>
        </svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 14l-7 7-7-7"/>
        </svg>
        <span>{{ change.value }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  backdrop-filter: blur(10px);
  transition: all 0.3s ease;
}

.stats-card:hover {
  border-color: rgba(0, 212, 255, 0.4);
  box-shadow: 0 4px 20px rgba(0, 212, 255, 0.1);
}

.card-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.2) 0%, rgba(0, 255, 136, 0.1) 100%);
  border-radius: 12px;
  color: #00d4ff;
}

.card-content {
  flex: 1;
}

.card-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 4px;
}

.card-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
  font-size: 24px;
  font-weight: 600;
  color: #fff;
}

.card-unit {
  font-size: 14px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.5);
}

.card-change {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  margin-top: 4px;
}

.card-change.up {
  color: #00ff88;
}

.card-change.down {
  color: #ff5555;
}
</style>
