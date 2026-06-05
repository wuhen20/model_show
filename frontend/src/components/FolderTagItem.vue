<template>
  <div class="ftag-item">
    <div
      class="ftag-row"
      :class="{ 'ftag-row-l1': depth === 1 }"
      :style="{ paddingLeft: (depth - 1) * 16 + 'px' }"
      @click="depth === 1 && tag.children?.length && (expanded = !expanded)"
    >
      <!-- Tree connector line -->
      <span v-if="depth > 1" class="ftag-line"></span>

      <!-- Expand/collapse toggle for L1 -->
      <span v-if="depth === 1 && tag.children?.length" class="ftag-toggle" :class="{ 'ftag-toggle-open': expanded }">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M9 18l6-6-6-6"/>
        </svg>
      </span>

      <!-- Depth dot indicator for L2+ -->
      <span v-if="depth > 1" class="ftag-dot" :class="'ftag-dot-d' + Math.min(depth, 4)"></span>

      <!-- Tag chip -->
      <span class="ftag-chip" :class="'ftag-depth-' + Math.min(depth, 4)">
        <span class="ftag-chip-name">{{ tag.name }}</span>
        <span class="ftag-chip-count" v-if="tag.children && tag.children.length">{{ tag.children.length }}</span>
      </span>
    </div>

    <!-- Children — always show for L2+, toggle for L1 -->
    <div v-if="depth === 1 ? expanded : true" class="ftag-children">
      <FolderTagItem
        v-for="c in (tag.children || [])"
        :key="c.name"
        :tag="c"
        :depth="depth + 1"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { FolderTagResponse } from '@/api/knowledge'

const props = defineProps<{
  tag: FolderTagResponse
  depth?: number
}>()

// L1 tags start expanded by default
const expanded = ref(true)
</script>

<style scoped>
.ftag-item { }

.ftag-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
  border-radius: 4px;
  transition: background 0.15s;
  cursor: default;
}
.ftag-row:hover {
  background: rgba(255, 255, 255, 0.03);
}

/* L1 rows are bolder — clickable to toggle */
.ftag-row-l1 {
  padding: 5px 4px;
  cursor: pointer;
  border-radius: 6px;
}
.ftag-row-l1:hover {
  background: rgba(0, 212, 255, 0.06);
}

/* Tree connector line (vertical) */
.ftag-line {
  position: relative;
  width: 1px;
  height: 16px;
  flex-shrink: 0;
  margin-right: 2px;
}
.ftag-line::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(255, 255, 255, 0.08);
}

/* Depth dot for L2+ */
.ftag-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-right: 2px;
}
.ftag-dot-d2 { background: #00ff88; box-shadow: 0 0 4px rgba(0, 255, 136, 0.4); }
.ftag-dot-d3 { background: #c084fc; box-shadow: 0 0 4px rgba(192, 132, 252, 0.4); }
.ftag-dot-d4 { background: #ffaa00; box-shadow: 0 0 4px rgba(255, 170, 0, 0.4); }

/* Expand/collapse toggle arrow */
.ftag-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 3px;
  flex-shrink: 0;
  transition: transform 0.2s, background 0.15s;
  color: rgba(0, 212, 255, 0.6);
}
.ftag-toggle:hover {
  background: rgba(0, 212, 255, 0.12);
  color: #00d4ff;
}
.ftag-toggle-open {
  transform: rotate(90deg);
}

/* Tag chip — pill/tag style */
.ftag-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 9px;
  border-radius: 4px;
  border: 1px solid;
  font-size: 11px;
  line-height: 20px;
  white-space: nowrap;
  max-width: 100%;
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.ftag-row-l1 .ftag-chip {
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 500;
  line-height: 22px;
  border-radius: 6px;
}

.ftag-row-l1:hover .ftag-chip {
  box-shadow: 0 0 8px rgba(0, 212, 255, 0.15);
}

/* Depth 1 — cyan */
.ftag-depth-1 {
  background: rgba(0, 212, 255, 0.10);
  border-color: rgba(0, 212, 255, 0.30);
  color: #00d4ff;
}
/* Depth 2 — green */
.ftag-depth-2 {
  background: rgba(0, 255, 136, 0.07);
  border-color: rgba(0, 255, 136, 0.22);
  color: #00ff88;
}
/* Depth 3 — purple */
.ftag-depth-3 {
  background: rgba(192, 132, 252, 0.07);
  border-color: rgba(192, 132, 252, 0.22);
  color: #c084fc;
}
/* Depth 4+ — amber */
.ftag-depth-4 {
  background: rgba(255, 170, 0, 0.07);
  border-color: rgba(255, 170, 0, 0.22);
  color: #ffaa00;
}

.ftag-chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
}

.ftag-chip-count {
  font-size: 9px;
  opacity: 0.45;
  margin-left: 1px;
  font-weight: 500;
}

/* Children section with left border for L1 groups */
.ftag-children {
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  margin-left: 12px;
  padding-left: 0;
}

.ftag-row-l1 + .ftag-children {
  border-left: 1px solid rgba(0, 212, 255, 0.12);
  margin-left: 11px;
}
</style>
