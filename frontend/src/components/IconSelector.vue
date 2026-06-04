<template>
  <div class="icon-selector">
    <div
      v-for="item in icons"
      :key="item.key"
      class="icon-option"
      :class="{ selected: modelValue === item.key }"
      @click="$emit('update:modelValue', item.key)"
    >
      <div class="icon-box" :style="{ backgroundColor: modelValue === item.key ? color : 'rgba(255,255,255,0.08)' }">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2">
          <path :d="item.path"/>
        </svg>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ modelValue: string; color?: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()

const icons = [
  { key: 'brain', path: 'M12 2a8 8 0 0 0-8 8c0 3.4 2.1 6.3 5 7.5V20h6v-2.5c2.9-1.2 5-4.1 5-7.5a8 8 0 0 0-8-8z' },
  { key: 'plug', path: 'M12 22V8M5 12H2a10 10 0 0 0 20 0h-3' },
  { key: 'database', path: 'M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z' },
  { key: 'scale', path: 'M12 3v18M3 12h18M5.5 5.5l13 13M18.5 5.5l-13 13' },
  { key: 'trending-down', path: 'M23 18l-9.5-9.5-5 5L1 6' },
  { key: 'shield', path: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' },
  { key: 'book', path: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z' },
  { key: 'file-text', path: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8' },
  { key: 'layers', path: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
  { key: 'cpu', path: 'M6 3v3M10 3v3M14 3v3M18 3v3M6 21v-3M10 21v-3M14 21v-3M18 21v-3M3 6h3M3 10h3M3 14h3M3 18h3M21 6h-3M21 10h-3M21 14h-3M21 18h-3M6 6h12v12H6z' },
  { key: 'globe', path: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z' },
  { key: 'zap', path: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z' },
  { key: 'target', path: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 6v6l4 2' },
  { key: 'search', path: 'M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM21 21l-4.35-4.35' },
  { key: 'code', path: 'M16 18l6-6-6-6M8 6l-6 6 6 6' },
  { key: 'box', path: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zM3.27 6.96L12 12.01l8.73-5.05M12 22.08V12' },
  { key: 'share', path: 'M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8M16 6l-4-4-4 4M12 2v13' },
  { key: 'cog', path: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z' },
  { key: 'link', path: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71' },
  { key: 'feather', path: 'M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5zM16 8L2 22M17.5 15H9' },
  { key: 'git-branch', path: 'M6 3v6M6 21v-4a2 2 0 0 1 2-2h4M18 3a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM6 9a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM18 7v4a2 2 0 0 1-2 2H10' },
]
</script>

<style scoped>
.icon-selector {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.icon-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 6px;
  border-radius: 8px;
  border: 2px solid transparent;
  transition: all 0.2s;
}
.icon-option:hover { background: rgba(0,212,255,0.08); }
.icon-option.selected { border-color: var(--accent, #00d4ff); background: rgba(0,212,255,0.1); }
.icon-box {
  width: 36px; height: 36px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s;
}
</style>
