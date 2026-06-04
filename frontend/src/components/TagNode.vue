<template>
  <div class="tag-node">
    <div class="tag-row" :style="{ paddingLeft: (depth - 1) * 28 + 'px' }">
      <span class="tag-level-badge" :class="'depth-' + Math.min(depth, 4)">
        {{ depth }}级
      </span>
      <el-input
        v-model="tag.name"
        :placeholder="`请输入${depth}级标签名`"
        size="small"
        class="tag-input"
      />
      <el-button
        size="small"
        circle
        @click="$emit('add-child', tag)"
        :disabled="!tag.name"
        title="添加子标签"
      >+</el-button>
      <el-button
        size="small"
        circle
        type="danger"
        plain
        @click="$emit('remove')"
        title="删除标签"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </el-button>
    </div>
    <div v-if="tag.children.length" class="tag-children">
      <TagNode
        v-for="(child, idx) in tag.children"
        :key="idx"
        :tag="child"
        :depth="depth + 1"
        @remove="removeChild(idx)"
        @add-child="$emit('add-child', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
interface TagFormNode {
  name: string
  children: TagFormNode[]
}

const props = defineProps<{
  tag: TagFormNode
  depth: number
}>()

const emit = defineEmits<{
  remove: []
  'add-child': [tag: TagFormNode]
}>()

function removeChild(idx: number) {
  props.tag.children.splice(idx, 1)
}
</script>

<style scoped>
.tag-node { margin-bottom: 4px; }
.tag-row {
  display: flex; align-items: center; gap: 8px; margin-bottom: 4px;
}
.tag-level-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  white-space: nowrap; min-width: 36px; text-align: center;
  font-weight: 500;
}
.tag-level-badge.depth-1 { background: rgba(0,212,255,0.2); color: #00d4ff; }
.tag-level-badge.depth-2 { background: rgba(0,255,136,0.2); color: #00ff88; }
.tag-level-badge.depth-3 { background: rgba(168,85,247,0.2); color: #c084fc; }
.tag-level-badge.depth-4 { background: rgba(255,170,0,0.2); color: #ffaa00; }
.tag-input { flex: 1; }
.tag-children {
  border-left: 2px solid rgba(0,212,255,0.15);
  margin-left: 18px;
  padding-left: 4px;
}
</style>
