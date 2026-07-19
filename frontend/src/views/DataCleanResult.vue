<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getCleanResults, viewCleanResult, getDownloadCleanResultUrl, getSampleSetOptions, importToSample, queryCleanPics, getCleanPicImageUrl, rollbackCleanPics, type CleanResult, type CleanResultData, type SampleSetOption, type CleanPicRecord } from '@/api/clean'
import { getCodeDict } from '@/api/sample'
import { ElMessage, ElMessageBox } from 'element-plus'

const resultList = ref<CleanResult[]>([])
const loading = ref(false)

// 数据类型选项
const sampleTypeMap = ref<Record<string, string>>({})

// 筛选
const filterName = ref('')
const filterType = ref('')

const filteredList = computed(() => {
  let list = resultList.value
  if (filterName.value.trim()) {
    const kw = filterName.value.trim().toLowerCase()
    list = list.filter(r =>
      r.taskName.toLowerCase().includes(kw) || r.taskNo.toLowerCase().includes(kw)
    )
  }
  if (filterType.value) {
    list = list.filter(r => r.sampleTypeCode === filterType.value)
  }
  return list
})

async function loadResults() {
  loading.value = true
  try {
    resultList.value = await getCleanResults()
  } catch (e: any) {
    ElMessage.error(e.message || '查询失败')
  } finally {
    loading.value = false
  }
}

async function loadCodeDict() {
  try {
    const data = await getCodeDict()
    if (data.SAMPLE_TYPE && data.SAMPLE_TYPE.length > 0) {
      const map: Record<string, string> = {}
      data.SAMPLE_TYPE.forEach((item: any) => {
        map[item.codeValue] = item.codeName
      })
      sampleTypeMap.value = map
    }
  } catch (e) {
    console.error('获取数据类型字典失败:', e)
  }
}

function getSampleTypeName(code: string): string {
  if (!code) return '-'
  return sampleTypeMap.value[code] || code
}

function resetFilters() {
  filterName.value = ''
  filterType.value = ''
}

// ========== 查看弹框 ==========
const viewVisible = ref(false)
const viewLoading = ref(false)
const viewData = ref<CleanResultData | null>(null)
const viewCurrentPage = ref(1)
const viewPageSize = 20

const viewPagedRows = computed(() => {
  if (!viewData.value?.rows) return []
  const start = (viewCurrentPage.value - 1) * viewPageSize
  return viewData.value.rows.slice(start, start + viewPageSize)
})

const viewTotalPages = computed(() => {
  if (!viewData.value?.rows) return 0
  return Math.ceil(viewData.value.rows.length / viewPageSize)
})

async function handleView(item: CleanResult) {
  // 图片类型清洗结果：查询被清洗的图片记录并展示
  if (item.sampleTypeCode === '05') {
    await handleViewImageResult(item)
    return
  }
  // 时序/结构化类型：查看 JSON 结果文件
  viewVisible.value = true
  viewLoading.value = true
  viewData.value = null
  viewCurrentPage.value = 1
  try {
    viewData.value = await viewCleanResult(item.recordId)
  } catch (e: any) {
    ElMessage.error(e.message || '查看失败')
  } finally {
    viewLoading.value = false
  }
}

// ========== 图像清洗结果查看弹框 ==========
const imageResultVisible = ref(false)
const imageResultLoading = ref(false)
const imageResultList = ref<CleanPicRecord[]>([])
const imageResultTaskName = ref('')
const imageFilterType = ref('')

const imageFilteredResult = computed(() => {
  if (!imageFilterType.value) return imageResultList.value
  return imageResultList.value.filter(p => p.cleanType === imageFilterType.value)
})

const imageCleanTypeOptions = computed(() => {
  const map = new Map<string, string>()
  for (const p of imageResultList.value) {
    if (!map.has(p.cleanType)) {
      map.set(p.cleanType, p.cleanTypeName)
    }
  }
  return Array.from(map.entries()).map(([value, label]) => ({ value, label }))
})

async function handleViewImageResult(item: CleanResult) {
  imageResultVisible.value = true
  imageResultLoading.value = true
  imageResultList.value = []
  imageResultTaskName.value = item.taskName || item.taskNo
  imageFilterType.value = ''
  try {
    imageResultList.value = await queryCleanPics(item.taskNo)
  } catch (e: any) {
    ElMessage.error(e.message || '查看失败')
  } finally {
    imageResultLoading.value = false
  }
}

// ========== 回滚 ==========
const rollbackSet = ref<Set<string>>(new Set())

async function handleRollback(item: CleanResult) {
  try {
    await ElMessageBox.confirm(
      `确认回滚清洗任务「${item.taskName || item.taskNo}」？\n被隔离的图片将移回原始样本集目录，并恢复原始样本记录。`,
      '回滚确认',
      { type: 'warning', confirmButtonText: '回滚', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  rollbackSet.value.add(item.taskNo)
  try {
    const result = await rollbackCleanPics(item.taskNo)
    ElMessage.success(`回滚成功，恢复 ${result.restoredCount} 张图片${result.skippedCount ? `，跳过 ${result.skippedCount} 张` : ''}`)
    await loadResults()
  } catch (e: any) {
    ElMessage.error(e.message || '回滚失败')
  } finally {
    rollbackSet.value.delete(item.taskNo)
  }
}

// ========== 下载弹框 ==========
const downloadVisible = ref(false)
const downloadItem = ref<CleanResult | null>(null)
const downloadFormat = ref<'json' | 'excel'>('json')

function handleDownload(item: CleanResult) {
  downloadItem.value = item
  downloadFormat.value = 'json'
  downloadVisible.value = true
}

function confirmDownload() {
  if (!downloadItem.value) return
  const url = getDownloadCleanResultUrl(downloadItem.value.recordId, downloadFormat.value)
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  downloadVisible.value = false
  ElMessage.success('开始下载')
}

// ========== 入库弹框 ==========
const importVisible = ref(false)
const importItem = ref<CleanResult | null>(null)
const importSetNo = ref('')
const importSampleName = ref('')
const importMajorVersion = ref(false)
const importVersionRemark = ref('')
const importSaving = ref(false)
const sampleSetOptions = ref<SampleSetOption[]>([])

async function handleImport(item: CleanResult) {
  importItem.value = item
  importSetNo.value = ''
  // 默认样本名称为文件名（去掉.json后缀）
  const fileName = item.fileName || ''
  importSampleName.value = fileName.endsWith('.json') ? fileName.replace('.json', '') : fileName
  importMajorVersion.value = false
  importVersionRemark.value = ''
  importVisible.value = true
  // 加载样本集选项，按当前数据的类型过滤
  try {
    sampleSetOptions.value = await getSampleSetOptions(item.sampleTypeCode || '')
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
  if (!importItem.value) return
  importSaving.value = true
  try {
    const result = await importToSample(
      importItem.value.recordId,
      importSetNo.value,
      importSampleName.value,
      importMajorVersion.value,
      importVersionRemark.value.trim()
    )
    let msg = '入库成功'
    if (result?.preVersion && result?.nextVersion) {
      msg += `，版本 ${result.preVersion} → ${result.nextVersion}`
    }
    ElMessage.success(msg)
    importVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.message || '入库失败')
  } finally {
    importSaving.value = false
  }
}

onMounted(() => {
  loadResults()
  loadCodeDict()
})
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="数据清洗结果" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="page-header">
          <div class="page-title-row">
            <h2 class="page-title">数据清洗结果</h2>
          </div>
        </div>

        <div class="filter-bar">
          <div class="filter-row">
            <div class="filter-item filter-name">
              <label>名称</label>
              <el-input v-model="filterName" placeholder="搜索任务名称或编号" clearable size="default" />
            </div>
            <div class="filter-item filter-type">
              <label>数据类型</label>
              <el-select v-model="filterType" placeholder="全部" clearable size="default">
                <el-option v-for="(name, code) in sampleTypeMap" :key="code" :label="name" :value="code" />
              </el-select>
            </div>
            <el-button class="reset-btn" @click="resetFilters">重置</el-button>
          </div>
        </div>

        <div class="table-container">
          <div class="list-header">
            <span class="col col-no">任务编号</span>
            <span class="col col-name">任务名称</span>
            <span class="col col-type">数据类型</span>
            <span class="col col-start">执行开始时间</span>
            <span class="col col-end">执行结束时间</span>
            <span class="col col-count">结果数据数</span>
            <span class="col col-file">文件名</span>
            <span class="col col-path">文件路径</span>
            <span class="col col-action">操作</span>
          </div>
          <div v-if="loading" class="loading-state">
            <span>加载中...</span>
          </div>
          <div v-else-if="filteredList.length === 0" class="empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1.5">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            <p>暂无清洗结果</p>
          </div>
          <div v-else>
            <div class="list-row" v-for="item in filteredList" :key="item.recordId">
              <span class="col col-no">{{ item.taskNo }}</span>
              <span class="col col-name">{{ item.taskName || '-' }}</span>
              <span class="col col-type">{{ getSampleTypeName(item.sampleTypeCode) }}</span>
              <span class="col col-start">{{ item.startTime || '-' }}</span>
              <span class="col col-end">{{ item.endTime || '-' }}</span>
              <span class="col col-count">{{ item.resultCount }}</span>
              <span class="col col-file" :title="item.fileName">{{ item.fileName || '-' }}</span>
              <span class="col col-path" :title="item.filePath">{{ item.filePath || '-' }}</span>
              <span class="col col-action">
                <el-button size="small" @click="handleView(item)">查看</el-button>
                <el-button v-if="item.sampleTypeCode !== '05'" size="small" @click="handleDownload(item)">下载</el-button>
                <el-button v-if="item.sampleTypeCode !== '05'" size="small" type="primary" @click="handleImport(item)">入库</el-button>
                <el-button
                  v-if="item.sampleTypeCode === '05'"
                  size="small"
                  type="warning"
                  :loading="rollbackSet.has(item.taskNo)"
                  @click="handleRollback(item)"
                >回滚</el-button>
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- 查看弹框 -->
    <el-dialog v-model="viewVisible" :title="`清洗结果查看 - ${viewData?.taskName || ''}`" width="90%" top="5vh" :close-on-click-modal="false" class="view-dialog" destroy-on-close>
      <div v-if="viewLoading" class="view-loading">加载中...</div>
      <div v-else-if="viewData" class="view-content">
        <div class="view-summary">
          <span>任务编号：<b>{{ viewData.taskNo }}</b></span>
          <span>执行时间：<b>{{ viewData.executeTime }}</b></span>
          <span>原始数据：<b>{{ viewData.totalCount }}</b> 条</span>
          <span>移除重复：<b>{{ viewData.removedCount }}</b> 条</span>
          <span>结果数据：<b style="color:#00ff88">{{ viewData.resultCount }}</b> 条</span>
        </div>
        <div class="view-table-wrap">
          <table class="view-table">
            <thead>
              <tr>
                <th class="th-index">#</th>
                <th v-for="col in viewData.columns" :key="col">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in viewPagedRows" :key="idx">
                <td class="td-index">{{ (viewCurrentPage - 1) * viewPageSize + idx + 1 }}</td>
                <td v-for="col in viewData.columns" :key="col" :title="String(row[col] ?? '')">{{ row[col] ?? '' }}</td>
              </tr>
              <tr v-if="viewPagedRows.length === 0">
                <td :colspan="viewData.columns.length + 1" class="td-empty">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="view-pagination" v-if="viewData.rows.length > viewPageSize">
          <el-pagination
            v-model:current-page="viewCurrentPage"
            :page-size="viewPageSize"
            :total="viewData.rows.length"
            layout="prev, pager, next"
            background
          />
        </div>
      </div>
    </el-dialog>

    <!-- 图像清洗结果查看弹框 -->
    <el-dialog
      v-model="imageResultVisible"
      :title="`被清洗图片 - ${imageResultTaskName}`"
      width="90%"
      top="5vh"
      :close-on-click-modal="false"
      class="image-result-dialog"
      destroy-on-close
    >
      <div v-if="imageResultLoading" class="view-loading">加载中...</div>
      <div v-else-if="imageResultList.length === 0" class="view-loading">暂无被清洗图片记录</div>
      <div v-else class="image-result-content">
        <div class="image-result-toolbar">
          <span class="image-result-summary">
            共 <b>{{ imageResultList.length }}</b> 张被清洗图片
          </span>
          <el-select v-model="imageFilterType" placeholder="按清洗原因筛选" clearable size="default" style="width: 220px">
            <el-option v-for="opt in imageCleanTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </div>
        <div class="image-grid">
          <div v-for="pic in imageFilteredResult" :key="pic.recordId" class="image-card">
            <div class="image-thumb">
              <img :src="getCleanPicImageUrl(pic.filePath)" :alt="pic.fileName" loading="lazy" />
            </div>
            <div class="image-info">
              <div class="image-name" :title="pic.fileName">{{ pic.fileName }}</div>
              <div class="image-reason">{{ pic.cleanTypeName }}</div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="imageResultVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 下载弹框 -->
    <el-dialog v-model="downloadVisible" title="下载清洗结果" width="400px" :close-on-click-modal="false" class="download-dialog">
      <div class="download-form">
        <div class="download-label">选择下载格式：</div>
        <el-radio-group v-model="downloadFormat" class="download-radios">
          <el-radio value="json">JSON 文件</el-radio>
          <el-radio value="excel">Excel 文件</el-radio>
        </el-radio-group>
      </div>
      <template #footer>
        <el-button @click="downloadVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmDownload">确认下载</el-button>
      </template>
    </el-dialog>

    <!-- 入库弹框 -->
    <el-dialog v-model="importVisible" title="清洗结果入库" width="520px" :close-on-click-modal="false" class="download-dialog">
      <div class="download-form">
        <div class="download-label">样本名称：</div>
        <el-input v-model="importSampleName" placeholder="请输入样本名称" style="width: 100%" size="default" />
        <div class="download-label" style="margin-top: 16px;">选择目标样本集：</div>
        <el-select v-model="importSetNo" placeholder="请选择样本集" filterable style="width: 100%" size="default">
          <el-option v-for="opt in sampleSetOptions" :key="opt.setNo" :label="`${opt.setName}（${opt.setNo}）`" :value="opt.setNo" />
        </el-select>
        <div class="import-hint" v-if="importItem">将清洗结果文件 <b>{{ importItem.fileName }}</b> 入库到所选样本集</div>
        <div class="import-version-row">
          <el-checkbox v-model="importMajorVersion">大版本变更</el-checkbox>
        </div>
        <div v-if="importMajorVersion" class="import-remark-row">
          <div class="download-label" style="margin-bottom: 6px;">变更说明<span class="import-remark-tip">（非必填，最多 150 字）</span></div>
          <el-input
            v-model="importVersionRemark"
            type="textarea"
            :rows="3"
            placeholder="请输入变更说明，留空则自动生成"
            maxlength="150"
            show-word-limit
          />
        </div>
        <div class="import-version-tip">
          <span v-if="!importMajorVersion">未勾选：入库后小版本号 +1</span>
          <span v-else>已勾选：入库后大版本号 +1，小版本号归 0</span>
        </div>
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
  background: #0d1117;
  color: #e6edf3;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px 32px;
  overflow: hidden;
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
  font-size: 20px;
  font-weight: 600;
  color: #e6edf3;
  margin: 0;
}

.filter-bar {
  margin-bottom: 16px;
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
    font-size: 13px;
    color: rgba(255, 255, 255, 0.6);
    white-space: nowrap;
  }
}

.filter-name {
  width: 260px;
}

.filter-type {
  width: 180px;
}

.reset-btn {
  margin-left: auto;
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
.col-name { width: 150px; flex-shrink: 0; }
.col-type { width: 100px; flex-shrink: 0; text-align: center; }
.col-start { width: 170px; flex-shrink: 0; color: rgba(255, 255, 255, 0.6); }
.col-end { width: 170px; flex-shrink: 0; color: rgba(255, 255, 255, 0.6); }
.col-count { width: 100px; flex-shrink: 0; text-align: center; color: #00ff88; }
.col-file { width: 240px; flex-shrink: 0; color: rgba(255, 255, 255, 0.6); }
.col-path { width: 280px; flex-shrink: 0; color: rgba(255, 255, 255, 0.4); font-size: 12px; }
.col-action { width: 220px; flex-grow: 1; flex-shrink: 0; display: flex; align-items: center; gap: 6px; }

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 14px;
  gap: 12px;
  min-height: 200px;
}

// ========== 查看弹框 ==========
.view-loading {
  text-align: center;
  padding: 60px 0;
  color: rgba(255, 255, 255, 0.5);
}

.view-content {
  display: flex;
  flex-direction: column;
  height: 70vh;
}

.view-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  padding: 12px 16px;
  background: rgba(0, 212, 255, 0.08);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);

  b {
    color: #e6edf3;
  }
}

.view-table-wrap {
  flex: 1;
  overflow: auto;
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;

  &::-webkit-scrollbar {
    width: 8px;
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

.view-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: max-content;

  th, td {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    text-align: left;
    white-space: nowrap;
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  th {
    background: #172638;
    color: rgba(255, 255, 255, 0.7);
    font-weight: 600;
    position: sticky;
    top: 0;
    z-index: 1;
  }

  td {
    color: rgba(255, 255, 255, 0.85);
  }

  tbody tr:hover {
    background: rgba(0, 212, 255, 0.06);
  }

  .th-index, .td-index {
    width: 50px;
    text-align: center;
    color: rgba(255, 255, 255, 0.4);
  }

  .td-empty {
    text-align: center;
    padding: 40px 0;
    color: rgba(255, 255, 255, 0.3);
  }
}

.view-pagination {
  display: flex;
  justify-content: center;
  padding-top: 16px;
}

// ========== 图像清洗结果弹框 ==========
.image-result-content {
  display: flex;
  flex-direction: column;
  height: 70vh;
}

.image-result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 16px;
  background: rgba(0, 212, 255, 0.08);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  margin-bottom: 16px;

  .image-result-summary {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.7);

    b {
      color: #ff5555;
      font-weight: 600;
    }
  }
}

.image-grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  align-content: start;
  padding: 4px;

  &::-webkit-scrollbar {
    width: 8px;
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

.image-card {
  background: rgba(0, 212, 255, 0.04);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s, transform 0.2s;

  &:hover {
    border-color: rgba(0, 212, 255, 0.5);
    transform: translateY(-2px);
  }
}

.image-thumb {
  width: 100%;
  height: 160px;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
}

.image-info {
  padding: 8px 10px;
  min-height: 50px;
}

.image-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.image-reason {
  font-size: 11px;
  color: #ffaa00;
  background: rgba(255, 170, 0, 0.1);
  border: 1px solid rgba(255, 170, 0, 0.2);
  border-radius: 4px;
  padding: 2px 6px;
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  box-sizing: border-box;
}

// ========== 下载弹框 ==========
.download-form {
  padding: 16px 0;
}

.download-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 16px;
}

.download-radios {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.import-hint {
  margin-top: 16px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);

  b {
    color: #00ff88;
  }
}

.import-version-row {
  margin-top: 16px;

  :deep(.el-checkbox__label) {
    color: rgba(255, 255, 255, 0.85);
  }
}

.import-remark-row {
  margin-top: 10px;
}

.import-remark-tip {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
  margin-left: 4px;
}

.import-version-tip {
  margin-top: 12px;
  font-size: 12px;
  color: rgba(0, 212, 255, 0.7);
}

// ========== Element Plus 深色主题覆盖 ==========
:deep(.el-input__wrapper) {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 212, 255, 0.2);
  box-shadow: none;
}

:deep(.el-input__wrapper:hover),
:deep(.el-input__wrapper.is-focus) {
  border-color: rgba(0, 212, 255, 0.5);
}

:deep(.el-input__inner) {
  color: #e6edf3;
}

:deep(.el-input__inner::placeholder) {
  color: rgba(255, 255, 255, 0.3);
}

:deep(.el-select .el-input__wrapper) {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 212, 255, 0.2);
}

:deep(.el-select__placeholder) {
  color: rgba(255, 255, 255, 0.3);
}

:deep(.el-select .el-input__inner) {
  color: #e6edf3 !important;
}

:deep(.el-button) {
  --el-button-bg-color: rgba(0, 212, 255, 0.1);
  --el-button-border-color: rgba(0, 212, 255, 0.3);
  --el-button-text-color: #00d4ff;
  --el-button-hover-bg-color: rgba(0, 212, 255, 0.2);
  --el-button-hover-border-color: rgba(0, 212, 255, 0.5);
  --el-button-hover-text-color: #00d4ff;
}

:deep(.el-dialog) {
  background: #1a2332;
  border: 1px solid rgba(0, 212, 255, 0.25);
  border-radius: 12px;
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
  padding: 16px 20px;
}

:deep(.el-dialog__title) {
  color: #e6edf3;
  font-size: 16px;
}

:deep(.el-dialog__body) {
  padding: 20px;
  color: #e6edf3;
}

:deep(.el-dialog__headerbtn .el-dialog__close) {
  color: rgba(255, 255, 255, 0.5);
}

:deep(.el-radio__label) {
  color: #e6edf3;
}

:deep(.el-radio__input.is-checked .el-radio__inner) {
  background: #00d4ff;
  border-color: #00d4ff;
}

:deep(.el-radio__input.is-checked + .el-radio__label) {
  color: #00d4ff;
}

:deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background: #00d4ff;
  border-color: #00d4ff;
}

:deep(.el-checkbox__input.is-checked + .el-checkbox__label) {
  color: #00d4ff;
}

:deep(.el-textarea__inner) {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 212, 255, 0.2);
  box-shadow: none;
  color: #e6edf3;

  &:hover,
  &:focus {
    border-color: rgba(0, 212, 255, 0.5);
  }

  &::placeholder {
    color: rgba(255, 255, 255, 0.3);
  }
}

:deep(.el-input__count) {
  background: transparent;
  color: rgba(255, 255, 255, 0.4);
}

:deep(.el-pager li) {
  background: rgba(0, 0, 0, 0.3);
  color: rgba(255, 255, 255, 0.6);

  &.is-active {
    background: rgba(0, 212, 255, 0.3);
    color: #00d4ff;
  }
}

:deep(.el-pagination button) {
  background: rgba(0, 0, 0, 0.3);
  color: rgba(255, 255, 255, 0.6);
}
</style>
