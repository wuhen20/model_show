<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getCleanTasks, saveCleanTask, executeCleanTask, deleteCleanTask, getCleanLogs, getCleanTaskDetail, saveCleanTaskNodes, queryPicCleanTypes, queryOriginalSampleSetOptions, type CleanTask, type CleanLog, type PicCleanType, type OriginalSampleSetOption } from '@/api/clean'
import { getCodeDict } from '@/api/sample'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

const taskList = ref<CleanTask[]>([])
const loading = ref(false)
const executingSet = ref<Set<string>>(new Set())

// 数据类型选项
const sampleTypeOptions = ref<{ value: string; label: string }[]>([])

// 图片清洗相关
const picCleanTypes = ref<PicCleanType[]>([])
const originalSampleSetOptions = ref<OriginalSampleSetOption[]>([])

// 清洗类型全选相关
const isAllCleanTypesSelected = computed({
  get: () => picCleanTypes.value.length > 0 && dialogForm.value.cleanTypes.length === picCleanTypes.value.length,
  set: (val: boolean) => {
    dialogForm.value.cleanTypes = val ? picCleanTypes.value.map(ct => ct.codeValue) : []
  }
})
const isCleanTypesIndeterminate = computed(() => {
  const len = dialogForm.value.cleanTypes.length
  return len > 0 && len < picCleanTypes.value.length
})
function handleAllCleanTypesChange(val: boolean) {
  dialogForm.value.cleanTypes = val ? picCleanTypes.value.map(ct => ct.codeValue) : []
}

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
    taskList.value = await getCleanTasks()
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
const dialogForm = ref({ taskName: '', remark: '', sampleType: '', originalSampleSetNo: '', cleanTypes: [] as string[] })
const isEditMode = ref(false)
const editingTaskNo = ref('')

function openCreateDialog() {
  isEditMode.value = false
  editingTaskNo.value = ''
  dialogForm.value = { taskName: '', remark: '', sampleType: '', originalSampleSetNo: '', cleanTypes: [] }
  dialogVisible.value = true
}

async function openEditConfigDialog(task: CleanTask) {
  isEditMode.value = true
  editingTaskNo.value = task.taskNo
  dialogForm.value = { taskName: task.taskName, remark: task.remark || '', sampleType: task.sampleType || '', originalSampleSetNo: '', cleanTypes: [] }
  dialogVisible.value = true

  // 加载已有配置
  try {
    const detail = await getCleanTaskDetail(task.taskNo)
    if (detail.nodes && detail.nodes.length > 0) {
      const node = detail.nodes[0]
      dialogForm.value.originalSampleSetNo = node.nodeId || ''
      // nodeConfig 可能是逗号分隔字符串(image_clean)或对象(时序节点)
      const config = node.nodeConfig as any
      if (typeof config === 'string') {
        dialogForm.value.cleanTypes = config.split(',').map((s: string) => s.trim()).filter(Boolean)
      } else if (Array.isArray(config)) {
        dialogForm.value.cleanTypes = config
      }
    }
  } catch (e: any) {
    ElMessage.error('加载配置失败：' + (e.message || ''))
  }
}

async function handleCreateConfirm() {
  if (!dialogForm.value.taskName.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }

  // 图片类型校验
  if (dialogForm.value.sampleType === '05') {
    if (!dialogForm.value.originalSampleSetNo) {
      ElMessage.warning('请选择原始样本集')
      return
    }
    if (dialogForm.value.cleanTypes.length === 0) {
      ElMessage.warning('请选择清洗类型')
      return
    }
  }

  dialogSaving.value = true
  try {
    if (isEditMode.value) {
      // 编辑模式：更新图片清洗配置
      const cleanTypesStr = dialogForm.value.cleanTypes.join(',')
      // 查找原始样本集名称
      const setName = originalSampleSetOptions.value.find(o => o.setNo === dialogForm.value.originalSampleSetNo)?.setName || dialogForm.value.originalSampleSetNo
      await saveCleanTaskNodes(editingTaskNo.value, [{
        nodeId: dialogForm.value.originalSampleSetNo,
        nodeType: 'image_clean',
        nodeName: setName,
        nodeConfig: cleanTypesStr,
        posX: 0,
        posY: 0,
        prevNodeId: null,
      }])
      ElMessage.success('配置保存成功')
      dialogVisible.value = false
      await loadTasks()
    } else if (dialogForm.value.sampleType === '05') {
      // 新建图片类型任务
      const cleanTypesStr = dialogForm.value.cleanTypes.join(',')
      await saveCleanTask(
        dialogForm.value.taskName.trim(),
        dialogForm.value.remark.trim(),
        '05',
        dialogForm.value.originalSampleSetNo,
        cleanTypesStr
      )
      ElMessage.success('新建任务成功')
      dialogVisible.value = false
      await loadTasks()
    } else {
      // 新建时序类型任务
      const taskNo = await saveCleanTask(
        dialogForm.value.taskName.trim(),
        dialogForm.value.remark.trim(),
        dialogForm.value.sampleType
      )
      ElMessage.success('新建任务成功')
      dialogVisible.value = false
      router.push({ path: '/clean-task-edit', query: { taskNo } })
    }
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    dialogSaving.value = false
  }
}

function resultColor(flagName: string): string {
  if (flagName === '成功') return '#00ff88'
  if (flagName === '失败') return '#ff5555'
  return 'rgba(255, 255, 255, 0.5)'
}

function statusColor(statusCode: string): string {
  if (statusCode === '02') return '#ffaa00'
  if (statusCode === '03') return '#00ff88'
  if (statusCode === '04') return '#ff5555'
  return 'rgba(255, 255, 255, 0.5)'
}

// 执行任务
async function handleExecute(task: CleanTask) {
  const isImage = task.sampleType === '05'
  const confirmMsg = isImage
    ? '确认执行该清洗任务？执行后将检测并标记问题图片（文件不会移动，仍在原位置）。'
    : '确认执行该清洗任务？执行后清洗结果将以 JSON 文件保存到服务器。'
  try {
    await ElMessageBox.confirm(confirmMsg, '提示', { type: 'warning' })
  } catch {
    return
  }
  executingSet.value.add(task.taskNo)
  let isAsync = false
  try {
    const result = await executeCleanTask(task.taskNo)
    // 图片类型和时序类型均为异步执行：启动轮询监控任务状态
    isAsync = !!result.async

    if (isAsync) {
      ElMessage.success('任务已启动，正在后台执行，请通过执行记录查看进度')
      startTaskPolling(task.taskNo)
      await loadTasks()
      return
    }

    // 同步执行结果（兼容旧逻辑）
    if (isImage) {
      ElMessage.success(`执行成功，共检测 ${result.resultCount} 张正常图片，问题图片已标记`)
    } else {
      ElMessage.success(`执行成功，清洗结果已保存（共 ${result.resultCount} 条），文件：${result.fileName}`)
    }
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '执行失败')
    await loadTasks()
  } finally {
    // 异步任务不在此处移除 executingSet，由轮询结束时机移除
    if (!isAsync) {
      executingSet.value.delete(task.taskNo)
    }
  }
}

// ========== 异步任务轮询 ==========
// {taskNo: number} 保存定时器ID
const pollingTimers: Record<string, ReturnType<typeof setInterval>> = {}
const POLLING_INTERVAL = 2000 // 轮询间隔 2 秒
const POLLING_TIMEOUT = 30 * 60 * 1000 // 最大轮询时长 30 分钟

function startTaskPolling(taskNo: string) {
  // 避免重复启动
  if (pollingTimers[taskNo]) {
    clearInterval(pollingTimers[taskNo])
  }

  const startTime = Date.now()

  const poll = async () => {
    // 超时保护
    if (Date.now() - startTime > POLLING_TIMEOUT) {
      ElMessage.warning(`任务 ${taskNo} 轮询超时，请手动刷新查看结果`)
      stopTaskPolling(taskNo)
      return
    }

    try {
      const logs = await getCleanLogs(taskNo)
      if (!logs || logs.length === 0) return

      // 取最新一条日志
      const latestLog = logs[0]
      const status = String(latestLog.executeStatusCode || '')

      if (status === '03') {
        // 执行成功
        ElMessage.success(`任务执行成功，共检测 ${latestLog.totalCount} 张图片，标记 ${latestLog.removedCount} 张问题图片`)
        stopTaskPolling(taskNo)
        await loadTasks()
      } else if (status === '04') {
        // 执行失败
        ElMessage.error(`任务执行失败：${latestLog.executeLog || '未知错误'}`)
        stopTaskPolling(taskNo)
        await loadTasks()
      }
      // status === '02' 执行中，继续轮询
    } catch (e) {
      console.error('轮询任务状态失败:', e)
    }
  }

  // 立即执行一次，然后定时执行
  poll()
  pollingTimers[taskNo] = setInterval(poll, POLLING_INTERVAL)
}

function stopTaskPolling(taskNo: string) {
  if (pollingTimers[taskNo]) {
    clearInterval(pollingTimers[taskNo])
    delete pollingTimers[taskNo]
  }
  executingSet.value.delete(taskNo)
}

// 删除任务
async function handleDelete(task: CleanTask) {
  try {
    await ElMessageBox.confirm(
      `确认删除清洗任务「${task.taskName}」？\n将同时删除流程配置，且不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteCleanTask(task.taskNo)
    ElMessage.success('删除成功')
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

function goToEdit(taskNo: string) {
  router.push({ path: '/clean-task-edit', query: { taskNo } })
}

function handleTaskClick(task: CleanTask) {
  if (task.sampleType === '05') {
    openEditConfigDialog(task)
  } else {
    goToEdit(task.taskNo)
  }
}

// ========== 执行记录弹窗 ==========
const logDialogVisible = ref(false)
const logDialogLoading = ref(false)
const logList = ref<CleanLog[]>([])
const currentLogTask = ref<CleanTask | null>(null)

async function openLogDialog(task: CleanTask) {
  currentLogTask.value = task
  logDialogVisible.value = true
  logDialogLoading.value = true
  logList.value = []
  try {
    logList.value = await getCleanLogs(task.taskNo)
  } catch (e: any) {
    ElMessage.error(e.message || '查询执行记录失败')
  } finally {
    logDialogLoading.value = false
  }
}

function logStatusColor(statusCode: string): string {
  if (statusCode === '03') return '#00ff88'
  if (statusCode === '04') return '#ff5555'
  if (statusCode === '02') return '#ffaa00'
  return 'rgba(255, 255, 255, 0.5)'
}

// ========== 日志详情弹窗 ==========
const logDetailDialogVisible = ref(false)
const currentLogDetail = ref<CleanLog | null>(null)

function openLogDetailDialog(log: CleanLog) {
  currentLogDetail.value = log
  logDetailDialogVisible.value = true
}

onMounted(() => {
  loadTasks()
  loadCodeDict()
  loadPicCleanTypes()
  loadOriginalSampleSetOptions()
})

async function loadCodeDict() {
  try {
    const data = await getCodeDict()
    if (data.SAMPLE_TYPE && data.SAMPLE_TYPE.length > 0) {
      sampleTypeOptions.value = data.SAMPLE_TYPE.map((item: any) => ({
        value: item.codeValue,
        label: item.codeName
      }))
    }
  } catch (e) {
    console.error('获取数据类型字典失败:', e)
  }
}

async function loadPicCleanTypes() {
  try {
    picCleanTypes.value = await queryPicCleanTypes()
  } catch (e) {
    console.error('获取图像清洗类型失败:', e)
  }
}

async function loadOriginalSampleSetOptions() {
  try {
    originalSampleSetOptions.value = await queryOriginalSampleSetOptions('05')
  } catch (e) {
    console.error('获取原始样本集选项失败:', e)
  }
}
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="样本数据清洗" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="page-header">
          <div class="page-title-row">
            <h2 class="page-title">样本数据清理任务管理</h2>
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

        <el-table :data="filteredList" v-loading="loading" style="width: 100%" class="clean-task-table">
          <el-table-column prop="taskNo" label="任务编号" width="150">
            <template #default="{ row }">
              <span class="link-col" @click="handleTaskClick(row)">{{ row.taskNo }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="taskName" label="任务名称" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="link-col" @click="handleTaskClick(row)">{{ row.taskName }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="任务说明" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">{{ row.remark || '-' }}</template>
          </el-table-column>
          <el-table-column prop="createTime" label="创建时间" width="160">
            <template #default="{ row }">{{ row.createTime || '-' }}</template>
          </el-table-column>
          <el-table-column prop="lastExecuteTime" label="最近执行时间" width="160">
            <template #default="{ row }">{{ row.lastExecuteTime || '-' }}</template>
          </el-table-column>
          <el-table-column prop="lastExecuteFlagName" label="执行结果" width="100">
            <template #default="{ row }">
              <span class="result-tag" :style="{ color: resultColor(row.lastExecuteFlagName) }">
                {{ row.lastExecuteFlagName || '未执行' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="taskStatusName" label="状态" width="100">
            <template #default="{ row }">
              <span class="status-tag" :style="{ color: statusColor(row.taskStatusCode) }">
                {{ row.taskStatusName || '未执行' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="320">
            <template #default="{ row }">
              <el-button
                type="primary"
                size="small"
                :loading="executingSet.has(row.taskNo)"
                :disabled="row.taskStatusCode === '02'"
                @click="handleExecute(row)"
              >执行</el-button>
              <el-button
                v-if="row.sampleType === '05'"
                size="small"
                class="edit-btn"
                @click="openEditConfigDialog(row)"
              >配置</el-button>
              <el-button
                v-else
                size="small"
                class="edit-btn"
                @click="goToEdit(row.taskNo)"
              >编排</el-button>
              <el-button
                size="small"
                class="log-btn"
                @click="openLogDialog(row)"
              >执行记录</el-button>
              <el-button
                type="danger"
                size="small"
                class="delete-btn"
                :disabled="row.taskStatusCode === '02'"
                @click="handleDelete(row)"
              >删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <div class="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1.5">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <p>暂无清洗任务</p>
            </div>
          </template>
        </el-table>
      </main>
    </div>

    <!-- 新增/编辑任务弹框 -->
    <el-dialog v-model="dialogVisible" :title="isEditMode ? '编辑清洗配置' : '新增清洗任务'" width="520px" :close-on-click-modal="false" class="create-dialog">
      <el-form label-width="100px" label-position="right">
        <el-form-item label="任务名称" required>
          <el-input v-model="dialogForm.taskName" placeholder="请输入任务名称" maxlength="100" :disabled="isEditMode" />
        </el-form-item>
        <el-form-item label="数据类型">
          <el-select v-model="dialogForm.sampleType" placeholder="请选择数据类型" clearable style="width: 100%" :disabled="isEditMode">
            <el-option v-for="opt in sampleTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <!-- 图片类型：显示原始样本集和清洗类型 -->
        <template v-if="dialogForm.sampleType === '05'">
          <el-form-item label="原始样本集" required>
            <el-select v-model="dialogForm.originalSampleSetNo" placeholder="请选择原始样本集" filterable style="width: 100%">
              <el-option v-for="opt in originalSampleSetOptions" :key="opt.setNo" :label="opt.setName" :value="opt.setNo" />
            </el-select>
          </el-form-item>
          <el-form-item label="清洗类型" required>
            <div class="clean-type-checkbox-group">
              <el-checkbox
                v-model="isAllCleanTypesSelected"
                :indeterminate="isCleanTypesIndeterminate"
                @change="handleAllCleanTypesChange"
              >全选</el-checkbox>
              <el-checkbox-group v-model="dialogForm.cleanTypes">
                <el-checkbox v-for="ct in picCleanTypes" :key="ct.codeValue" :label="ct.codeValue">{{ ct.codeName }}</el-checkbox>
              </el-checkbox-group>
            </div>
          </el-form-item>
        </template>
        <el-form-item label="任务说明">
          <el-input v-model="dialogForm.remark" type="textarea" :rows="3" placeholder="请输入任务说明（选填）" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogSaving" @click="handleCreateConfirm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 执行记录弹窗 -->
    <el-dialog
      v-model="logDialogVisible"
      :title="`执行记录 - ${currentLogTask?.taskName || ''}`"
      width="900px"
      :close-on-click-modal="false"
      class="log-dialog"
    >
      <div v-if="logDialogLoading" class="log-loading">加载中...</div>
      <div v-else-if="logList.length === 0" class="log-empty">
        <p>暂无执行记录</p>
      </div>
      <div v-else class="log-list">
        <div v-for="log in logList" :key="log.recordId" class="log-item">
          <div class="log-item-header">
            <div class="log-item-info">
              <span class="log-status" :style="{ color: logStatusColor(log.executeStatusCode) }">
                {{ log.executeStatusName }}
              </span>
              <span class="log-time">开始：{{ log.startTime || '-' }}</span>
              <span class="log-time">结束：{{ log.endTime || '-' }}</span>
            </div>
            <div class="log-stats">
              <span class="stat-item">总数：<b>{{ log.totalCount }}</b></span>
              <span class="stat-item removed">移除：<b>{{ log.removedCount }}</b></span>
              <span class="stat-item result">结果：<b>{{ currentLogTask?.sampleType === '05' ? log.removedCount : log.resultCount }}</b></span>
            </div>
            <el-button size="small" class="log-btn" @click="openLogDetailDialog(log)">
              日志
            </el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="logDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 日志详情弹窗 -->
    <el-dialog
      v-model="logDetailDialogVisible"
      title="执行日志详情"
      width="700px"
      :close-on-click-modal="false"
      class="log-detail-dialog"
    >
      <div v-if="currentLogDetail" class="log-detail-header">
        <span class="log-status" :style="{ color: logStatusColor(currentLogDetail.executeStatusCode) }">
          {{ currentLogDetail.executeStatusName }}
        </span>
        <span class="log-time">开始：{{ currentLogDetail.startTime || '-' }}</span>
        <span class="log-time">结束：{{ currentLogDetail.endTime || '-' }}</span>
      </div>
      <div v-if="currentLogDetail?.executeLog" class="log-detail-content">
        <pre>{{ currentLogDetail.executeLog }}</pre>
      </div>
      <div v-else class="log-detail-empty">
        <p>无日志内容</p>
      </div>
      <template #footer>
        <el-button @click="logDetailDialogVisible = false">关闭</el-button>
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
  transition: color 0.2s;

  &:hover {
    color: #33ddff !important;
    text-decoration: underline;
  }
}

.result-tag, .status-tag {
  font-weight: 600;
  font-size: 13px;
}

.edit-btn {
  background: rgba(0, 212, 255, 0.1) !important;
  border: 1px solid rgba(0, 212, 255, 0.3) !important;
  color: #00d4ff !important;

  &:hover {
    background: rgba(0, 212, 255, 0.2) !important;
  }
}

.log-btn {
  background: rgba(255, 170, 0, 0.1) !important;
  border: 1px solid rgba(255, 170, 0, 0.3) !important;
  color: #ffaa00 !important;

  &:hover {
    background: rgba(255, 170, 0, 0.2) !important;
  }
}

.delete-btn {
  background: rgba(255, 85, 85, 0.1) !important;
  border: 1px solid rgba(255, 85, 85, 0.3) !important;
  color: #ff5555 !important;

  &:hover {
    background: rgba(255, 85, 85, 0.2) !important;
  }

  &.is-disabled,
  &.is-disabled:hover {
    background: rgba(255, 255, 255, 0.05) !important;
    border-color: rgba(255, 255, 255, 0.1) !important;
    color: rgba(255, 255, 255, 0.3) !important;
  }
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

.log-loading, .log-empty {
  padding: 40px;
  text-align: center;
  color: rgba(255, 255, 255, 0.4);
  font-size: 14px;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 60vh;
  overflow-y: auto;
}

.log-item {
  background: rgba(0, 212, 255, 0.04);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  overflow: hidden;
}

.log-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: rgba(0, 212, 255, 0.06);
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
  flex-wrap: wrap;
  gap: 8px;
}

.log-item-info {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.log-status {
  font-weight: 600;
  font-size: 13px;
}

.log-time {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.log-stats {
  display: flex;
  gap: 14px;
}

.stat-item {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);

  b {
    color: #fff;
    font-weight: 600;
    margin-left: 2px;
  }

  &.removed b { color: #ff5555; }
  &.result b { color: #00ff88; }
}

.log-content {
  padding: 10px 14px;

  pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
    line-height: 1.6;
    color: rgba(255, 255, 255, 0.75);
  }
}

.log-btn {
  background: rgba(0, 212, 255, 0.15) !important;
  border: 1px solid rgba(0, 212, 255, 0.3) !important;
  color: #00d4ff !important;
  font-size: 12px;
  padding: 4px 12px;
  margin-left: 10px;

  &:hover {
    background: rgba(0, 212, 255, 0.25) !important;
  }
}

.clean-type-checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;

  .el-checkbox-group {
    display: flex;
    flex-wrap: wrap;
    gap: 12px 20px;
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
  --el-fill-color-blank: transparent;
  --el-border-color: rgba(0, 212, 255, 0.2);
  --el-bg-color: transparent;
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

.el-dialog.log-dialog {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.98) 0%, rgba(26, 35, 50, 0.95) 100%) !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;
  border-radius: 12px !important;

  --el-text-color-regular: rgba(255, 255, 255, 0.85);
  --el-text-color-primary: #fff;

  .el-dialog__header {
    border-bottom: 1px solid rgba(0, 212, 255, 0.15);
  }

  .el-dialog__title {
    color: #fff !important;
  }

  .el-dialog__body {
    padding: 20px;
  }

  .el-button:not(.el-button--primary) {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
    color: rgba(255, 255, 255, 0.7) !important;
  }
}

.el-dialog.log-detail-dialog {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.98) 0%, rgba(26, 35, 50, 0.95) 100%) !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;
  border-radius: 12px !important;

  --el-text-color-regular: rgba(255, 255, 255, 0.85);
  --el-text-color-primary: #fff;

  .el-dialog__header {
    border-bottom: 1px solid rgba(0, 212, 255, 0.15);
  }

  .el-dialog__title {
    color: #fff !important;
  }

  .el-dialog__body {
    padding: 16px 20px;
    max-height: 500px;
    overflow-y: auto;
  }

  .log-detail-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(0, 212, 255, 0.1);
  }

  .log-detail-content {
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-all;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 13px;
      line-height: 1.7;
      color: rgba(255, 255, 255, 0.8);
      background: rgba(0, 0, 0, 0.2);
      padding: 12px;
      border-radius: 6px;
    }
  }

  .log-detail-empty {
    text-align: center;
    padding: 40px;
    color: rgba(255, 255, 255, 0.5);
  }

  .el-button:not(.el-button--primary) {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
    color: rgba(255, 255, 255, 0.7) !important;
  }
}
</style>
