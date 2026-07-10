<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getCollectTasks, saveCollectTask, executeCollectTask, stopCollectTask, deleteCollectTask, getCollectLogs, getCodeDict, querySampleSetByType, type CollectTask, type CollectLog, type SampleSetOption } from '@/api/sample'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

const taskList = ref<CollectTask[]>([])
const loading = ref(false)
const executingSet = ref<Set<string>>(new Set())

// 数据类型选项
const sampleTypeOptions = ref<{ value: string; label: string }[]>([])
// 原始样本集选项（根据数据类型动态加载）
const sampleSetOptions = ref<SampleSetOption[]>([])
const sampleSetLoading = ref(false)

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
const dialogForm = ref({ taskName: '', remark: '', executeType: '01', cronFormula: '', sampleType: '', sampleSetNo: '' })

function openCreateDialog() {
  dialogForm.value = { taskName: '', remark: '', executeType: '01', cronFormula: '', sampleType: '', sampleSetNo: '' }
  sampleSetOptions.value = []
  dialogVisible.value = true
}

// 数据类型变化时，清空已选样本集并重新加载
async function onSampleTypeChange(val: string) {
  dialogForm.value.sampleSetNo = ''
  sampleSetOptions.value = []
  if (!val) return
  sampleSetLoading.value = true
  try {
    sampleSetOptions.value = await querySampleSetByType(val)
  } catch (e: any) {
    ElMessage.error(e.message || '查询原始样本集失败')
  } finally {
    sampleSetLoading.value = false
  }
}

async function handleCreateConfirm() {
  if (!dialogForm.value.taskName.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }
  if (!dialogForm.value.sampleType) {
    ElMessage.warning('请选择数据类型')
    return
  }
  if (!dialogForm.value.sampleSetNo) {
    ElMessage.warning('请选择原始样本集')
    return
  }
  if (dialogForm.value.executeType === '02' && !dialogForm.value.cronFormula.trim()) {
    ElMessage.warning('执行方式为定时时，请输入 cron 表达式')
    return
  }
  dialogSaving.value = true
  try {
    const taskNo = await saveCollectTask(
      dialogForm.value.taskName.trim(),
      dialogForm.value.remark.trim(),
      dialogForm.value.executeType,
      dialogForm.value.cronFormula.trim(),
      dialogForm.value.sampleType,
      dialogForm.value.sampleSetNo
    )
    ElMessage.success('新建任务成功')
    dialogVisible.value = false
    // 跳转到任务明细页面，传递 sampleType 用于判断图像/时序类型
    router.push({ path: '/collect-task-detail', query: { taskNo, sampleType: dialogForm.value.sampleType } })
  } catch (e: any) {
    ElMessage.error(e.message || '新建失败')
  } finally {
    dialogSaving.value = false
  }
}

// ========== 执行记录弹框 ==========
const logDialogVisible = ref(false)
const logLoading = ref(false)
const logList = ref<CollectLog[]>([])
const logDialogTitle = ref('执行记录')

function logStatusColor(statusName: string): string {
  if (statusName === '成功') return '#00ff88'
  if (statusName === '失败') return '#ff5555'
  return '#ffaa00' // 执行中
}

async function openLogDialog(task: CollectTask) {
  logDialogTitle.value = `执行记录 - ${task.taskName}`
  logDialogVisible.value = true
  logLoading.value = true
  logList.value = []
  try {
    logList.value = await getCollectLogs(task.taskNo)
  } catch (e: any) {
    ElMessage.error(e.message || '查询执行记录失败')
  } finally {
    logLoading.value = false
  }
}

// 执行结果颜色
function resultColor(flagName: string): string {
  if (flagName === '成功') return '#00ff88'
  if (flagName === '失败') return '#ff5555'
  return 'rgba(255, 255, 255, 0.5)' // 未执行
}

// 执行状态颜色
function statusColor(statusCode: string): string {
  if (statusCode === '02') return '#ffaa00'   // 执行中
  if (statusCode === '03') return '#00ff88'   // 已完成
  if (statusCode === '04') return '#ff5555'   // 已停止
  return 'rgba(255, 255, 255, 0.5)'           // 未执行
}

// 执行任务
async function handleExecute(taskNo: string) {
  try {
    await ElMessageBox.confirm('确认执行该采集任务？', '提示', { type: 'warning' })
  } catch {
    return
  }
  executingSet.value.add(taskNo)
  try {
    const msg = await executeCollectTask(taskNo)
    ElMessage.success(msg)
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '执行失败')
    await loadTasks()
  } finally {
    executingSet.value.delete(taskNo)
  }
}

// 停止任务
async function handleStop(taskNo: string) {
  try {
    await ElMessageBox.confirm('确认停止该采集任务？', '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await stopCollectTask(taskNo)
    ElMessage.success('已停止')
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '停止失败')
  }
}

// 删除任务
async function handleDelete(task: CollectTask) {
  try {
    await ElMessageBox.confirm(
      `确认删除任务「${task.taskName}」？\n将同时删除任务的明细配置、字段映射和执行记录，且不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteCollectTask(task.taskNo)
    ElMessage.success('删除成功')
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

function goToDetail(task: CollectTask) {
  router.push({ path: '/collect-task-detail', query: { taskNo: task.taskNo, sampleType: task.sampleTypeCode || '' } })
}

onMounted(() => {
  loadTasks()
  loadCodeDict()
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
              <span class="col col-remark">任务说明</span>
              <span class="col col-create">创建时间</span>
              <span class="col col-exec">最近执行时间</span>
              <span class="col col-result">执行结果</span>
              <span class="col col-status">执行状态</span>
              <span class="col col-sample-type">数据类型</span>
              <span class="col col-exec-type">执行方式</span>
              <span class="col col-action">操作</span>
            </div>
            <div v-if="loading" class="loading-state">
              <span>加载中...</span>
            </div>
            <div v-else-if="filteredList.length === 0" class="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1.5">
                <path d="M22 19a2 2 0 1-2 2H4a2 2 0 1-2-2V5a2 2 0 1 2-2h5l2 3h9a2 2 0 1 2 2z" />
              </svg>
              <p>暂无采集任务</p>
            </div>
            <div v-else>
            <div class="list-row" v-for="item in filteredList" :key="item.taskNo">
              <span class="col col-no link-col" @click="goToDetail(item)">{{ item.taskNo }}</span>
              <span class="col col-name link-col" @click="goToDetail(item)">{{ item.taskName }}</span>
              <span class="col col-remark">{{ item.remark || '-' }}</span>
              <span class="col col-create">{{ item.createTime || '-' }}</span>
              <span class="col col-exec">{{ item.lastExecuteTime || '-' }}</span>
              <span class="col col-result">
                <span class="result-tag" :style="{ color: resultColor(item.lastExecuteFlagName) }">
                  {{ item.lastExecuteFlagName || '未执行' }}
                </span>
              </span>
              <span class="col col-status">
                <span class="status-tag" :style="{ color: statusColor(item.taskStatusCode) }">
                  {{ item.taskStatusName || '未执行' }}
                </span>
              </span>
              <span class="col col-sample-type">
                {{ sampleTypeOptions.find(o => o.value === item.sampleTypeCode)?.label || item.sampleTypeCode || '-' }}
              </span>
              <span class="col col-exec-type">
                <span class="exec-type-tag">{{ item.executeTypeName || '手动' }}</span>
                <span v-if="item.executeTypeCode === '02' && item.cronFormula" class="cron-text" :title="item.cronFormula">
                  {{ item.cronFormula }}
                </span>
              </span>
              <span class="col col-action">
                <el-button
                  type="primary"
                  size="small"
                  :loading="executingSet.has(item.taskNo)"
                  :disabled="item.taskStatusCode === '02'"
                  @click="handleExecute(item.taskNo)"
                >执行</el-button>
                <el-button
                  type="danger"
                  size="small"
                  :disabled="item.taskStatusCode !== '02'"
                  @click="handleStop(item.taskNo)"
                >停止</el-button>
                <el-button
                  size="small"
                  class="log-btn"
                  @click="openLogDialog(item)"
                >执行记录</el-button>
                <el-button
                  type="danger"
                  size="small"
                  class="delete-btn"
                  :disabled="item.taskStatusCode === '02'"
                  @click="handleDelete(item)"
                >删除</el-button>
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- 新增任务弹框 -->
    <el-dialog v-model="dialogVisible" title="新增采集任务" width="680px" :close-on-click-modal="false" class="create-dialog">
      <el-form label-width="100px" label-position="right">
        <el-form-item label="任务名称" required>
          <el-input v-model="dialogForm.taskName" placeholder="请输入任务名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="数据类型" required>
          <el-select v-model="dialogForm.sampleType" placeholder="请选择数据类型" style="width: 100%" @change="onSampleTypeChange">
            <el-option v-for="opt in sampleTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="原始样本集" required>
          <el-select v-model="dialogForm.sampleSetNo" placeholder="请先选择数据类型" :loading="sampleSetLoading" :disabled="!dialogForm.sampleType" style="width: 100%">
            <el-option v-for="opt in sampleSetOptions" :key="opt.setNo" :label="opt.setName" :value="opt.setNo" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行方式" required>
          <el-radio-group v-model="dialogForm.executeType">
            <el-radio value="01">手动</el-radio>
            <el-radio value="02">定时</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="dialogForm.executeType === '02'" label="cron表达式" required>
          <el-input v-model="dialogForm.cronFormula" placeholder="请输入cron表达式，如：0 0 2 * * ?" maxlength="200" />
          <div class="cron-tip">示例：0 0 2 * * ? 表示每天凌晨2点执行；0 */5 * * * ? 表示每5分钟执行一次</div>
        </el-form-item>
        <el-form-item label="任务说明">
          <el-input v-model="dialogForm.remark" type="textarea" :rows="3" placeholder="请输入任务说明（选填）" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogSaving" @click="handleCreateConfirm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 执行记录弹框 -->
    <el-dialog v-model="logDialogVisible" :title="logDialogTitle" width="780px" :close-on-click-modal="false" class="log-dialog">
      <div v-if="logLoading" class="log-loading">加载中...</div>
      <div v-else-if="logList.length === 0" class="log-empty">暂无执行记录</div>
      <div v-else class="log-list">
        <div class="log-item" v-for="log in logList" :key="log.recordId">
          <div class="log-item-header">
            <span class="log-status" :style="{ color: logStatusColor(log.executeStatusName) }">
              {{ log.executeStatusName }}
            </span>
            <span class="log-time">开始：{{ log.startTime || '-' }}</span>
            <span class="log-time">结束：{{ log.endTime || '-' }}</span>
          </div>
          <pre class="log-content">{{ log.executeLog || '（无日志内容）' }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="logDialogVisible = false">关闭</el-button>
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
  padding: 24px 16px;
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
  overflow-x: auto;

  &::-webkit-scrollbar {
    height: 8px;
  }

  &::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(0, 212, 255, 0.3);
    border-radius: 4px;

    &:hover {
      background: rgba(0, 212, 255, 0.5);
    }
  }
}

.list-header,
.list-row {
  display: flex;
  align-items: center;
  padding: 0 12px;
  min-height: 52px;
  box-sizing: border-box;
  width: max-content;
  min-width: 100%;
}

.list-header {
  background: rgba(0, 212, 255, 0.15);
  border-bottom: 1px solid rgba(0, 212, 255, 0.3);
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
    background: rgba(0, 212, 255, 0.08);
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
.col-name { width: 200px; flex-shrink: 0; }
.col-remark { width: 150px; flex-shrink: 0; color: rgba(255, 255, 255, 0.6); }
.col-create { width: 160px; flex-shrink: 0; color: rgba(255, 255, 255, 0.6); }
.col-exec { width: 160px; flex-shrink: 0; color: rgba(255, 255, 255, 0.6); }
.col-result { width: 90px; flex-shrink: 0; text-align: center; }
.col-status { width: 90px; flex-shrink: 0; text-align: center; }
.col-sample-type { width: 90px; flex-shrink: 0; text-align: center; color: rgba(255, 255, 255, 0.7); }
.col-exec-type { width: 150px; flex-shrink: 0; display: flex; flex-direction: column; gap: 2px; }
.col-action { width: 320px; flex-grow: 1; flex-shrink: 0; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }

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

.status-tag {
  font-weight: 600;
  font-size: 13px;
}

.exec-type-tag {
  font-size: 13px;
  color: #00d4ff;
  font-weight: 600;
}

.cron-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cron-tip {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 4px;
  line-height: 1.5;
}

.log-btn {
  background: rgba(0, 212, 255, 0.1) !important;
  border: 1px solid rgba(0, 212, 255, 0.3) !important;
  color: #00d4ff !important;

  &:hover {
    background: rgba(0, 212, 255, 0.2) !important;
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

.log-loading,
.log-empty {
  text-align: center;
  padding: 60px 20px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 14px;
}

.log-list {
  max-height: 60vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.log-item {
  background: rgba(0, 212, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  padding: 12px 16px;
}

.log-item-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.log-status {
  font-weight: 600;
  font-size: 14px;
  min-width: 50px;
}

.log-time {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.log-content {
  margin: 0;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.8);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}
</style>

<style lang="scss">
.el-dialog.create-dialog,
.el-dialog.log-dialog {
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

  .el-radio__label {
    color: rgba(255, 255, 255, 0.85) !important;
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
