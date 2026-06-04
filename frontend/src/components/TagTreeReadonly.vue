<template>
  <div class="tag-tree-readonly">
    <div v-for="tag in tags" :key="tag.id" class="tro-node">
      <div class="tro-row" :style="{ paddingLeft: (depth - 1) * 14 + 'px' }">
        <span class="tro-bullet" :class="'bd-' + Math.min(depth, 4)"></span>
        <span class="tro-name">{{ tag.name }}</span>
      </div>
      <TagTreeReadonly v-if="tag.children?.length" :tags="tag.children" :depth="depth + 1" />
    </div>
  </div>
</template>

<script setup lang="ts">
interface TagItem {
  id: string
  name: string
  children?: TagItem[]
}

const props = withDefaults(defineProps<{
  tags: TagItem[]
  depth?: number
}>(), { depth: 1 })
</script>

<script lang="ts">
// Provide default depth
export default { inheritAttrs: true }
</script>

<style scoped>
.tag-tree-readonly { }
.tro-node { margin-bottom: 2px; }
.tro-row { display: flex; align-items: center; gap: 6px; }
.tro-bullet {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}
.tro-bullet.bd-1 { background: #00d4ff; }
.tro-bullet.bd-2 { background: #00ff88; }
.tro-bullet.bd-3 { background: #c084fc; }
.tro-bullet.bd-4 { background: #ffaa00; }
.tro-name { font-size: 12px; color: rgba(255,255,255,0.6); }
</style>
