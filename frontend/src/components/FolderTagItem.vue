<template>
  <div class="ftag-item">
    <div class="ftag-row" :style="{ paddingLeft: (depth - 1) * 14 + 'px' }">
      <span class="ftag-chip" :class="'ftag-depth-' + Math.min(depth, 4)">
        <span class="ftag-chip-name">{{ tag.name }}</span>
        <span class="ftag-chip-count" v-if="tag.children && tag.children.length">{{ tag.children.length }}</span>
      </span>
    </div>
    <FolderTagItem
      v-for="c in (tag.children || [])"
      :key="c.name"
      :tag="c"
      :depth="depth + 1"
    />
  </div>
</template>

<script setup lang="ts">
import type { FolderTagResponse } from '@/api/knowledge'

defineProps<{
  tag: FolderTagResponse
  depth?: number
}>()
</script>

<style scoped>
.ftag-item { }
.ftag-row {
  padding: 3px 0;
}

/* Tag chip — pill/tag style matching the file-list tag look, depth-colored */
.ftag-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid;
  font-size: 11px;
  line-height: 18px;
  white-space: nowrap;
  max-width: 100%;
}

/* Depth 1 — cyan */
.ftag-depth-1 {
  background: rgba(0, 212, 255, 0.08);
  border-color: rgba(0, 212, 255, 0.25);
  color: #00d4ff;
}
/* Depth 2 — green */
.ftag-depth-2 {
  background: rgba(0, 255, 136, 0.06);
  border-color: rgba(0, 255, 136, 0.2);
  color: #00ff88;
}
/* Depth 3 — purple */
.ftag-depth-3 {
  background: rgba(192, 132, 252, 0.06);
  border-color: rgba(192, 132, 252, 0.2);
  color: #c084fc;
}
/* Depth 4+ — amber */
.ftag-depth-4 {
  background: rgba(255, 170, 0, 0.06);
  border-color: rgba(255, 170, 0, 0.2);
  color: #ffaa00;
}

.ftag-chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
}

.ftag-chip-count {
  font-size: 9px;
  opacity: 0.5;
  margin-left: 2px;
}
</style>
