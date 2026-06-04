<template>
  <div class="knowledge-table-card">
    <div class="card-header">
      <div class="header-left">
        <h3 class="card-title">
          <template v-if="categoryId">{{ categoryId }}</template>
          <template v-else>知识资产库</template>
          <span v-if="totalItems" class="card-total">（{{ totalItems }}条）</span>
        </h3>
      </div>
      <el-button v-if="categoryId" text size="small" class="back-btn" @click="handleBack">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6"/>
        </svg>
        返回全部
      </el-button>
    </div>

    <el-tabs v-model="activeTab" class="knowledge-tabs">
      <el-tab-pane label="最新知识" name="latest"></el-tab-pane>
      <el-tab-pane label="热门知识" name="popular"></el-tab-pane>
      <el-tab-pane label="高价值知识" name="valuable"></el-tab-pane>
      <el-tab-pane label="待审核知识" name="pending"></el-tab-pane>
    </el-tabs>

    <el-table :data="tableData" style="width: 100%" :header-cell-style="headerCellStyle">
      <el-table-column prop="title" label="知识标题" min-width="200">
        <template #default="{ row }">
          <span class="knowledge-title-readonly">{{ row.title }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="category_name" label="所属类目" width="120">
        <template #default="{ row }">
          <span class="domain-tag">{{ row.category_name }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="knowledge_type" label="知识类型" width="100" />

      <el-table-column prop="source" label="知识来源" width="100" />

      <el-table-column prop="score" label="质量评分" width="120">
        <template #default="{ row }">
          <div class="score-stars">
            <svg
              v-for="i in 5"
              :key="i"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              :stroke="i <= row.score ? '#ffaa00' : 'rgba(255,255,255,0.2)'"
              stroke-width="2"
            >
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="update_time" label="更新时间" width="120" />
    </el-table>

    <div class="table-footer">
      <span class="view-all-text">共 {{ totalItems }} 条知识</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { fetchKnowledgeList, fetchFolderKBFileList, type KnowledgeItem } from '@/api/knowledge'

const props = defineProps<{
  categoryId?: string
  workspace?: string
}>()

const emit = defineEmits<{
  (e: 'back'): void
}>()

const activeTab = ref('latest')
const tableData = ref<KnowledgeItem[]>([])
const totalItems = ref(0)

const headerCellStyle = {
  background: 'rgba(0, 212, 255, 0.1)',
  color: 'rgba(255, 255, 255, 0.7)',
  fontWeight: 500,
  fontSize: '13px'
}

/** Map LightRAG / legacy status strings to el-tag type */
function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  switch (status) {
    case 'PROCESSED':
    case '已发布':
      return 'success'
    case 'PROCESSING':
      return 'primary'
    case 'PENDING':
    case '待审核':
      return 'info'
    case 'FAILED':
      return 'danger'
    default:
      return 'warning'
  }
}

/** Friendly status label in Chinese */
function statusLabel(status: string): string {
  switch (status) {
    case 'PROCESSED':
      return '已处理'
    case 'PROCESSING':
      return '处理中'
    case 'PENDING':
      return '待处理'
    case 'FAILED':
      return '处理失败'
    case '已发布':
      return '已发布'
    case '待审核':
      return '待审核'
    default:
      return status
  }
}

async function loadData() {
  // If a specific LightRAG workspace is selected, use the legacy API
  if (props.workspace) {
    try {
      const result = await fetchKnowledgeList({
        tab: activeTab.value,
        page: 1,
        page_size: 10,
        workspace: props.workspace,
      })
      tableData.value = result.items
      totalItems.value = result.total
    } catch {
      tableData.value = []
      totalItems.value = 0
    }
    return
  }

  // Otherwise, use the folder-based KB API (reads from real filesystem)
  try {
    const result = await fetchFolderKBFileList({
      tab: activeTab.value,
      page: 1,
      page_size: 10,
      category_id: props.categoryId || undefined,
    })
    tableData.value = result.items
    totalItems.value = result.total
  } catch {
    // Fallback to legacy API if folder API fails
    try {
      const result = await fetchKnowledgeList({
        tab: activeTab.value,
        page: 1,
        page_size: 10,
        category_id: props.categoryId || undefined,
      })
      tableData.value = result.items
      totalItems.value = result.total
    } catch {
      tableData.value = []
      totalItems.value = 0
    }
  }
}

onMounted(() => {
  loadData()
})

watch(() => props.categoryId, () => {
  loadData()
})

watch(() => props.workspace, () => {
  loadData()
})

// Reload data when tab changes
watch(activeTab, () => {
  loadData()
})

function handleBack() {
  emit('back')
}
</script>

<style scoped>
.knowledge-table-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
}

.card-header {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  min-width: 0;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
}

.card-total {
  font-size: 13px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.45);
}

.back-btn {
  color: #00d4ff !important;
  font-size: 12px;
  padding: 4px 8px;
  flex-shrink: 0;
}

.knowledge-tabs {
  margin-bottom: 16px;
}

.knowledge-title-readonly {
  color: rgba(255, 255, 255, 0.9);
  cursor: default;
}

.domain-tag {
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
}

.score-stars {
  display: flex;
  gap: 2px;
}

:deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-row-hover-bg-color: rgba(0, 212, 255, 0.08);
  --el-table-header-bg-color: rgba(0, 212, 255, 0.1);
  --el-table-border-color: rgba(0, 212, 255, 0.1);
  --el-table-text-color: rgba(255, 255, 255, 0.9);
  --el-table-header-text-color: rgba(255, 255, 255, 0.7);
  --el-table-current-row-bg-color: rgba(0, 212, 255, 0.1);
  background: transparent;
}

:deep(.el-table__inner-wrapper) { background: transparent; }
:deep(.el-table__body-wrapper) { background: transparent; }
:deep(.el-table__header-wrapper) { background: transparent; }
:deep(.el-table__body tr) { background: transparent; cursor: default; }
:deep(.el-table__body tr:hover > td) { background: rgba(0, 212, 255, 0.08) !important; }
:deep(.el-table__empty-block) { background: transparent; }
:deep(.el-table th.el-table__cell) { background: rgba(0, 212, 255, 0.1); }

:deep(.el-tabs__item) { color: rgba(255, 255, 255, 0.7); }
:deep(.el-tabs__item.is-active) { color: #00d4ff; }
:deep(.el-tabs__active-bar) { background: #00d4ff; }
:deep(.el-tabs__nav-wrap::after) { background: rgba(0, 212, 255, 0.15); }

.table-footer {
  display: flex;
  justify-content: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(0, 212, 255, 0.1);
}

.view-all-text {
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
}
</style>
