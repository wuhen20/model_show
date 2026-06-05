<template>
  <div class="tag-checkbox-group">
    <div class="tag-checkbox-row" :style="{ paddingLeft: (depth - 1) * 20 + 'px' }">
      <el-checkbox
        v-model="tag._selected"
        :label="tag.name"
        size="small"
        :indeterminate="indeterminate"
        @change="onSelfChange"
      />
    </div>
    <div v-if="tag.children?.length" class="tag-checkbox-children">
      <TagCheckbox
        v-for="child in tag.children"
        :key="child.id"
        :tag="child"
        :depth="depth + 1"
        :all-tags="allTags"
        @check-change="onChildChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface TagWithSelected {
  id: string
  name: string
  children?: TagWithSelected[]
  _selected?: boolean
  parent_tag_id?: string | null
}

const props = defineProps<{
  tag: TagWithSelected
  depth: number
  allTags: TagWithSelected[]
}>()

const emit = defineEmits<{
  'check-change': []
}>()

const indeterminate = computed(() => {
  if (!props.tag.children?.length) return false
  const some = props.tag.children.some(c => c._selected)
  const all = props.tag.children.every(c => c._selected)
  return some && !all
})

function onSelfChange(val: boolean) {
  // Toggle all descendants
  setDescendants(props.tag, val)
  // Ensure parent chain is selected if self is selected
  if (val) {
    selectParentChain(props.tag)
  }
  emit('check-change')
}

function onChildChange() {
  // If any child is selected, ensure parent is selected too
  const anyChildSelected = props.tag.children?.some(c => c._selected)
  if (anyChildSelected && !props.tag._selected) {
    props.tag._selected = true
    selectParentChain(props.tag)
  }
  // If all children deselected, deselect parent
  if (!anyChildSelected && props.tag._selected) {
    // Only auto-deselect if we have children and none are selected
    const allDeselected = props.tag.children?.every(c => !c._selected)
    if (allDeselected) {
      props.tag._selected = false
    }
  }
  emit('check-change')
}

function setDescendants(node: TagWithSelected, val: boolean) {
  node._selected = val
  if (node.children?.length) {
    for (const child of node.children) {
      setDescendants(child, val)
    }
  }
}

function selectParentChain(node: TagWithSelected) {
  // Walk up the allTags tree to find and select parents
  const parentId = node.parent_tag_id
  if (!parentId) return
  const parent = findTagById(props.allTags, parentId)
  if (parent && !parent._selected) {
    parent._selected = true
    selectParentChain(parent)
  }
}

function findTagById(tags: TagWithSelected[], id: string): TagWithSelected | null {
  for (const t of tags) {
    if (t.id === id) return t
    if (t.children?.length) {
      const found = findTagById(t.children, id)
      if (found) return found
    }
  }
  return null
}
</script>

<style scoped>
.tag-checkbox-group { margin-bottom: 2px; }
.tag-checkbox-row { display: flex; align-items: center; }
.tag-checkbox-children {
  border-left: 2px solid rgba(0,212,255,0.12);
  margin-left: 10px;
  padding-left: 4px;
}
</style>
