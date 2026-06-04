<template>
  <div class="color-selector">
    <div
      v-for="c in colors"
      :key="c"
      class="color-option"
      :class="{ selected: modelValue === c }"
      :style="{ backgroundColor: c }"
      @click="$emit('update:modelValue', c)"
    >
      <svg v-if="modelValue === c" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ modelValue: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()

const colors = ['#00d4ff', '#00ff88', '#a855f7', '#ffaa00', '#ff5555', '#36a3f7']
</script>

<style scoped>
.color-selector { display: flex; gap: 10px; flex-wrap: wrap; }
.color-option {
  width: 32px; height: 32px;
  border-radius: 50%;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  border: 2px solid transparent;
  transition: all 0.2s;
}
.color-option:hover { transform: scale(1.15); }
.color-option.selected { border-color: #fff; transform: scale(1.15); }
</style>
