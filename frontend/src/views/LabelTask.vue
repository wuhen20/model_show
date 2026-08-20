<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getLabelTasks, createLabelTask, updateLabelTask, deleteLabelTask, importLabeledSamples, type LabelTask } from '@/api/label'
import { queryOriginalSampleSetOptions, getSampleSetOptions, type OriginalSampleSetOption, type SampleSetOption } from '@/api/clean'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

const taskList = ref<LabelTask[]>([])
const loading = ref(false)
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
    taskList.value = await getLabelTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '查询失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filterName.value = ''
}

// 新增/编辑任务弹框
const dialogVisible = ref(false)
const dialogSaving = ref(false)
const isEditMode = ref(false)
const editingTaskNo = ref('')
const labelsLocked = ref(false)
const originalSampleSetOptions = ref<OriginalSampleSetOption[]>([])

const dialogForm = ref({
  taskName: '',
  originalSampleSetNo: '',
  sampleLabels: ''
})

function openCreateDialog() {
  isEditMode.value = false
  editingTaskNo.value = ''
  labelsLocked.value = false
  dialogForm.value = { taskName: '', originalSampleSetNo: '', sampleLabels: '' }
  dialogVisible.value = true
}

async function openEditDialog(task: LabelTask) {
  isEditMode.value = true
  editingTaskNo.value = task.taskNo
  labelsLocked.value = task.labeledCount > 0
  dialogForm.value = {
    taskName: task.taskName,
    originalSampleSetNo: task.originalSampleSetNo,
    sampleLabels: task.sampleLabels || ''
  }
  dialogVisible.value = true
}

async function loadOriginalSampleSetOptions() {
  try {
    originalSampleSetOptions.value = await queryOriginalSampleSetOptions('05')
  } catch (e) {
    console.error('获取原始样本集选项失败:', e)
  }
}

async function handleConfirm() {
  if (!dialogForm.value.taskName.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }
  if (!isEditMode.value && !dialogForm.value.originalSampleSetNo) {
    ElMessage.warning('请选择原始样本集')
    return
  }
  if (!labelsLocked.value && !dialogForm.value.sampleLabels.trim()) {
    ElMessage.warning('请填写至少一个标签')
    return
  }

  dialogSaving.value = true
  try {
    if (isEditMode.value) {
      await updateLabelTask(editingTaskNo.value, dialogForm.value.taskName.trim(), dialogForm.value.sampleLabels)
      ElMessage.success('更新成功')
    } else {
      await createLabelTask(
        dialogForm.value.taskName.trim(),
        dialogForm.value.originalSampleSetNo,
        dialogForm.value.sampleLabels
      )
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    dialogSaving.value = false
  }
}

async function handleDelete(task: LabelTask) {
  try {
    await ElMessageBox.confirm(
      `确定删除任务"${task.taskName}"吗？该操作将删除任务及其所有标注明细，不可恢复。`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deleteLabelTask(task.taskNo)
    ElMessage.success('删除成功')
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

function handleTaskClick(task: LabelTask) {
  router.push({ path: '/label-workbench', query: { taskNo: task.taskNo } })
}

function statusColor(status: string): string {
  if (status === '02') return '#00ff88'
  if (status === '03') return '#00d4ff'
  if (status === '01') return '#ffaa00'
  return 'rgba(255, 255, 255, 0.5)'
}

// 入库按钮：标注进度完成即可，已入库后不屏蔽，允许重复操作
function canImport(task: LabelTask): boolean {
  return task.labeledCount >= task.totalCount && task.totalCount > 0
}

// ========== 入库弹框 ==========
const importVisible = ref(false)
const importSaving = ref(false)
const importTask = ref<LabelTask | null>(null)
const importSetNo = ref('')
const importMajorVersion = ref(false)
const importVersionRemark = ref('')
const sampleSetOptions = ref<SampleSetOption[]>([])

async function handleImport(task: LabelTask) {
  importTask.value = task
  importSetNo.value = ''
  importMajorVersion.value = false
  importVersionRemark.value = ''
  importVisible.value = true
  // 仅查询图像类型的高质量样本集
  try {
    sampleSetOptions.value = await getSampleSetOptions('05')
  } catch (e: any) {
    ElMessage.error(e.message || '加载样本集列表失败')
  }
}

async function confirmImport() {
  if (!importSetNo.value) {
    ElMessage.warning('请选择目标样本集')
    return
  }
  if (importVersionRemark.value.length > 150) {
    ElMessage.warning('变更说明不能超过 150 个字')
    return
  }
  if (!importTask.value) return
  importSaving.value = true
  try {
    const result = await importLabeledSamples(
      importTask.value.taskNo,
      importSetNo.value,
      importMajorVersion.value,
      importVersionRemark.value.trim()
    )
    let msg = `入库成功：新增 ${result.insertedCount} 张，更新 ${result.updatedCount} 张`
    if (result.errorCount > 0) {
      msg += `，失败 ${result.errorCount} 张`
    }
    if (result.preVersion && result.nextVersion) {
      msg += `，版本 ${result.preVersion} → ${result.nextVersion}`
    }
    ElMessage.success(msg)
    importVisible.value = false
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '入库失败')
  } finally {
    importSaving.value = false
  }
}

onMounted(() => {
  loadTasks()
  loadOriginalSampleSetOptions()
})
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="样本标注" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="page-header">
          <div class="page-title-row">
            <h2 class="page-title">标注任务管理</h2>
            <el-button type="primary" class="add-btn" @click="openCreateDialog">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px">
                <path d="M12 5v14M5 12h14" />
              </svg>
              新建任务
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

        <el-table :data="filteredList" v-loading="loading" style="width: 100%" class="label-task-table">
          <el-table-column prop="taskNo" label="任务编号" width="160">
            <template #default="{ row }">
              <span class="link-col" @click="handleTaskClick(row)">{{ row.taskNo }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="taskName" label="任务名称" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="link-col" @click="handleTaskClick(row)">{{ row.taskName }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="originalSampleSetName" label="原始样本集" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">{{ row.originalSampleSetName || '-' }}</template>
          </el-table-column>
          <el-table-column prop="sampleLabels" label="标签" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="labels-text">{{ row.sampleLabels ? row.sampleLabels.replace(/\n/g, '、') : '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="标注进度" width="120">
            <template #default="{ row }">
              <span class="progress-text">{{ row.labeledCount || 0 }} / {{ row.totalCount || 0 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="taskStatusName" label="状态" width="100">
            <template #default="{ row }">
              <span class="status-tag" :style="{ color: statusColor(row.taskStatus) }">
                {{ row.taskStatusName || '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="createTime" label="创建时间" width="160">
            <template #default="{ row }">{{ row.createTime || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="230">
            <template #default="{ row }">
              <el-button size="small" class="edit-btn" @click="openEditDialog(row)">编辑</el-button>
              <el-button size="small" type="primary" class="import-btn" :disabled="!canImport(row)" @click="handleImport(row)">入库</el-button>
              <el-button type="danger" size="small" class="delete-btn" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <div class="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1.5">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <p>暂无标注任务</p>
            </div>
          </template>
        </el-table>
      </main>
    </div>

    <!-- 新增/编辑任务弹框 -->
    <el-dialog v-model="dialogVisible" :title="isEditMode ? '编辑任务' : '新建标注任务'" width="520px" :close-on-click-modal="false" class="create-dialog">
      <el-form label-width="100px" label-position="right">
        <el-form-item label="任务名称" required>
          <el-input v-model="dialogForm.taskName" placeholder="请输入任务名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="原始样本集" required>
          <el-select
            v-model="dialogForm.originalSampleSetNo"
            placeholder="请选择原始样本集"
            filterable
            style="width: 100%"
            :disabled="isEditMode"
          >
            <el-option v-for="opt in originalSampleSetOptions" :key="opt.setNo" :label="opt.setName" :value="opt.setNo" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签" required>
          <el-input
            v-model="dialogForm.sampleLabels"
            type="textarea"
            :rows="6"
            placeholder="每行一个标签名，也可用逗号（中英文）、分号（中英文）、顿号分隔。例如：&#10;person&#10;car&#10;bike"
            :disabled="labelsLocked"
          />
          <div v-if="labelsLocked" class="lock-tip">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px">
              <rect x="3" y="11" width="18" height="11" rx="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            该任务已有标注数据，标签不可修改
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogSaving" @click="handleConfirm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 入库弹框 -->
    <el-dialog v-model="importVisible" title="已标注样本入库" width="520px" :close-on-click-modal="false" class="create-dialog">
      <el-form label-width="100px" label-position="right">
        <el-form-item label="目标样本集" required>
          <el-select
            v-model="importSetNo"
            placeholder="请选择高质量样本集"
            filterable
            style="width: 100%"
          >
            <el-option v-for="opt in sampleSetOptions" :key="opt.setNo" :label="`${opt.setName}（${opt.setNo}）`" :value="opt.setNo" />
          </el-select>
        </el-form-item>
        <el-form-item label="版本变更">
          <el-checkbox v-model="importMajorVersion">大版本变更</el-checkbox>
        </el-form-item>
        <el-form-item v-if="importMajorVersion" label="变更说明">
          <el-input
            v-model="importVersionRemark"
            type="textarea"
            :rows="3"
            placeholder="请输入变更说明（非必填，最多 150 字）"
            maxlength="150"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <div class="import-tip">
        <span class="import-tip-icon">!</span>
        同名文件将仅更新标注内容，不覆盖原文件。
      </div>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importSaving" @click="confirmImport">确认入库</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
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

.page-header { margin-bottom: 20px; }

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

.filter-bar { margin-bottom: 20px; }

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

.link-col {
  cursor: pointer;
  color: #00d4ff;
  transition: color 0.2s;

  &:hover {
    color: #33ddff !important;
    text-decoration: underline;
  }
}

.labels-text {
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
}

.progress-text {
  color: rgba(255, 255, 255, 0.8);
  font-size: 13px;
  font-weight: 500;
}

.status-tag {
  font-weight: 600;
  font-size: 13px;
}

.empty-state {
  padding: 60px 0;
  text-align: center;
  color: rgba(255, 255, 255, 0.3);

  p {
    margin-top: 12px;
    font-size: 14px;
  }
}

.lock-tip {
  display: flex;
  align-items: center;
  color: rgba(255, 170, 0, 0.7);
  font-size: 12px;
  margin-top: 4px;
}

.import-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 14px;
  background: rgba(255, 170, 0, 0.08);
  border: 1px solid rgba(255, 170, 0, 0.2);
  border-radius: 6px;
  color: rgba(255, 170, 0, 0.85);
  font-size: 13px;
}

.import-tip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 170, 0, 0.3);
  color: #ffaa00;
  font-weight: 700;
  font-size: 12px;
  flex-shrink: 0;
}

.import-btn {
  margin-left: 8px;
}
</style>

<style lang="scss">
/* Element Plus 暗色主题覆盖（与 DataCleanTask 一致） */
.label-task-table {
  background: transparent !important;

  .el-table__inner-wrapper {
    background: transparent !important;
  }

  th.el-table__cell {
    background: rgba(0, 212, 255, 0.08) !important;
    color: rgba(255, 255, 255, 0.7) !important;
    border-bottom: 1px solid rgba(0, 212, 255, 0.15) !important;
  }

  td.el-table__cell {
    background: transparent !important;
    color: rgba(255, 255, 255, 0.8) !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
  }

  .el-table__row:hover > td.el-table__cell {
    background: rgba(0, 212, 255, 0.05) !important;
  }

  .el-table__empty-block {
    background: transparent !important;
  }
}

.create-dialog {
  .el-dialog {
    background: #1a2332 !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
  }

  .el-dialog__header {
    .el-dialog__title {
      color: #fff !important;
    }
  }

  .el-dialog__body {
    color: rgba(255, 255, 255, 0.8) !important;
  }

  .el-form-item__label {
    color: rgba(255, 255, 255, 0.7) !important;
  }

  .el-input__wrapper,
  .el-textarea__inner {
    background: rgba(0, 0, 0, 0.3) !important;
    box-shadow: 0 0 0 1px rgba(0, 212, 255, 0.2) inset !important;
    color: #fff !important;

    &::placeholder {
      color: rgba(255, 255, 255, 0.3) !important;
    }
  }

  .el-select__wrapper {
    background: rgba(0, 0, 0, 0.3) !important;
    box-shadow: 0 0 0 1px rgba(0, 212, 255, 0.2) inset !important;
  }

  .el-checkbox__label {
    color: rgba(255, 255, 255, 0.85) !important;
  }

  .el-checkbox__input.is-checked .el-checkbox__inner {
    background: #00d4ff !important;
    border-color: #00d4ff !important;
  }

  .el-checkbox__input.is-checked + .el-checkbox__label {
    color: #00d4ff !important;
  }
}
</style>
