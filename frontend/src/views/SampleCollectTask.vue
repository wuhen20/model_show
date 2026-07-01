<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getCollectTasks, saveCollectTask, type CollectTask } from '@/api/sample'
import { ElMessage } from 'element-plus'

const router = useRouter()

const taskList = ref<CollectTask[]>([])
const loading = ref(false)

// 筛选
const filterName = ref('')

const filteredList = computed(() => {
  if (!filterName.value.trim()) return taskList.value
  const kw = filterName.value.trim().toLowerCase()
  return taskList.value.filter(t =>
    t.taskName.toLowerCase().includes(kw) || t.taskNo.toLowerCase().includes(kw)
  )
})

async function loadTasks() {
  loading.value = true
  try {
    taskList.value = await getCollectTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '查询失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filterName.value = ''
}

// ========== 新增任务弹框 ==========
const dialogVisible = ref(false)
const dialogSaving = ref(false)
const dialogForm = ref({ taskName: '', remark: '' })

function openCreateDialog() {
  dialogForm.value = { taskName: '', remark: '' }
  dialogVisible.value = true
}

async function handleCreateConfirm() {
  if (!dialogForm.value.taskName.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }
  dialogSaving.value = true
  try {
    const taskNo = await saveCollectTask(
      dialogForm.value.taskName.trim(),
      dialogForm.value.remark.trim()
    )
    ElMessage.success('新建任务成功')
    dialogVisible.value = false
    // 跳转到任务明细页面
    router.push({ path: '/collect-task-detail', query: { taskNo } })
  } catch (e: any) {
    ElMessage.error(e.message || '新建失败')
  } finally {
    dialogSaving.value = false
  }
}

// 执行结果颜色
function resultColor(flagName: string): string {
  if (flagName === '成功') return '#00ff88'
  if (flagName === '失败') return '#ff5555'
  return 'rgba(255, 255, 255, 0.5)' // 未执行
}

function goToDetail(taskNo: string) {
  router.push({ path: '/collect-task-detail', query: { taskNo } })
}

onMounted(() => {
  loadTasks()
})
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="数据采集任务管理" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="page-header">
          <div class="page-title-row">
            <h2 class="page-title">数据采集任务管理</h2>
            <el-button type="primary" class="add-btn" @click="openCreateDialog">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px">
                <path d="M12 5v14M5 12h14" />
              </svg>
              新增任务
            </el-button>
          </div>
        </div>

        <div class="filter-bar">
          <div class="filter-row">
            <div class="filter-item filter-name">
              <label>名称</label>
              <el-input v-model="filterName" placeholder="搜索任务名称或编号" clearable size="default" />
            </div>
            <el-button class="reset-btn" @click="resetFilters">重置</el-button>
          </div>
        </div>

        <div class="table-container">
          <div class="list-header">
            <span class="col col-no">任务编号</span>
            <span class="col col-name">任务名称</span>
            <span class="col col-remark">备注信息</span>
            <span class="col col-create">创建时间</span>
            <span class="col col-exec">最近执行时间</span>
            <span class="col col-result">执行结果</span>
          </div>
          <div v-if="loading" class="loading-state">
            <span>加载中...</span>
          </div>
          <div v-else-if="filteredList.length === 0" class="empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1.5">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            <p>暂无采集任务</p>
          </div>
          <div v-else>
            <div class="list-row" v-for="item in filteredList" :key="item.taskNo">
              <span class="col col-no link-col" @click="goToDetail(item.taskNo)">{{ item.taskNo }}</span>
              <span class="col col-name link-col" @click="goToDetail(item.taskNo)">{{ item.taskName }}</span>
              <span class="col col-remark">{{ item.remark || '-' }}</span>
              <span class="col col-create">{{ item.createTime || '-' }}</span>
              <span class="col col-exec">{{ item.lastExecuteTime || '-' }}</span>
              <span class="col col-result">
                <span class="result-tag" :style="{ color: resultColor(item.lastExecuteFlagName) }">
                  {{ item.lastExecuteFlagName || '未执行' }}
                </span>
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- 新增任务弹框 -->
    <el-dialog v-model="dialogVisible" title="新增采集任务" width="520px" :close-on-click-modal="false" class="create-dialog">
      <el-form label-width="80px" label-position="right">
        <el-form-item label="任务名称" required>
          <el-input v-model="dialogForm.taskName" placeholder="请输入任务名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="备注信息">
          <el-input v-model="dialogForm.remark" type="textarea" :rows="3" placeholder="请输入备注信息（选填）" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogSaving" @click="handleCreateConfirm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0d1117;
  overflow: hidden;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.content-area {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.page-header {
  margin-bottom: 20px;
}

.page-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #fff;
  margin: 0;
}

.add-btn {
  background: linear-gradient(135deg, #00d4ff, #0099cc) !important;
  border: none !important;
  color: #0d1117 !important;
  font-weight: 600;
  display: flex;
  align-items: center;

  &:hover {
    background: linear-gradient(135deg, #33ddff, #00aadd) !important;
  }
}

.filter-bar {
  margin-bottom: 20px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;

  label {
    color: rgba(255, 255, 255, 0.5);
    font-size: 13px;
    white-space: nowrap;
  }

  &.filter-name {
    flex: 1;
    max-width: 360px;
  }
}

.reset-btn {
  background: rgba(0, 212, 255, 0.1) !important;
  border: 1px solid rgba(0, 212, 255, 0.3) !important;
  color: rgba(255, 255, 255, 0.7) !important;

  &:hover {
    background: rgba(0, 212, 255, 0.2) !important;
    color: #00d4ff !important;
  }
}

.table-container {
  flex: 1;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  overflow: hidden;
}

.list-header,
.list-row {
  display: flex;
  align-items: center;
  padding: 0 20px;
  min-height: 52px;
}

.list-header {
  background: rgba(0, 212, 255, 0.08);
  border-bottom: 1px solid rgba(0, 212, 255, 0.2);
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
}

.list-row {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  transition: background 0.2s;

  &:hover {
    background: rgba(0, 212, 255, 0.05);
  }

  &:last-child {
    border-bottom: none;
  }
}

.col {
  padding: 0 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-no { width: 130px; flex-shrink: 0; color: #00d4ff; }
.col-name { flex: 1; min-width: 0; }
.col-remark { width: 200px; flex-shrink: 0; color: rgba(255, 255, 255, 0.6); }
.col-create { width: 170px; flex-shrink: 0; color: rgba(255, 255, 255, 0.6); }
.col-exec { width: 170px; flex-shrink: 0; color: rgba(255, 255, 255, 0.6); }
.col-result { width: 100px; flex-shrink: 0; text-align: center; }

.link-col {
  cursor: pointer;
  transition: color 0.2s;

  &:hover {
    color: #33ddff !important;
    text-decoration: underline;
  }
}

.result-tag {
  font-weight: 600;
  font-size: 13px;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 12px;

  span, p {
    color: rgba(255, 255, 255, 0.4);
    font-size: 14px;
  }
}
</style>

<style lang="scss">
.el-dialog.create-dialog {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.98) 0%, rgba(26, 35, 50, 0.95) 100%) !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;
  border-radius: 12px !important;

  --el-text-color-regular: rgba(255, 255, 255, 0.85);
  --el-text-color-primary: #fff;
  --el-text-color-placeholder: rgba(255, 255, 255, 0.3);
  --el-fill-color-blank: rgba(255, 255, 255, 0.05);
  --el-border-color: rgba(0, 212, 255, 0.2);
  --el-bg-color: rgba(17, 24, 39, 0.98);
  --el-bg-color-overlay: rgba(17, 24, 39, 0.98);
  --el-color-primary: #00d4ff;

  .el-dialog__header {
    border-bottom: 1px solid rgba(0, 212, 255, 0.15);
  }

  .el-dialog__title {
    color: #fff !important;
  }

  .el-dialog__body {
    padding: 24px 20px;
  }

  .el-form-item__label {
    color: rgba(255, 255, 255, 0.7) !important;
  }

  .el-input__wrapper,
  .el-textarea__inner {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
    box-shadow: none !important;
    color: rgba(255, 255, 255, 0.85) !important;
  }

  .el-input__inner {
    color: rgba(255, 255, 255, 0.85) !important;

    &::placeholder {
      color: rgba(255, 255, 255, 0.3) !important;
    }
  }

  .el-textarea__inner {
    color: rgba(255, 255, 255, 0.85) !important;

    &::placeholder {
      color: rgba(255, 255, 255, 0.3) !important;
    }
  }

  .el-button--primary {
    background: linear-gradient(135deg, #00d4ff, #0099cc) !important;
    border: none !important;
    color: #0d1117 !important;
    font-weight: 600;
  }

  .el-button:not(.el-button--primary) {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
    color: rgba(255, 255, 255, 0.7) !important;
  }
}
</style>
