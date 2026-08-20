<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getCleanResults, viewCleanResult, getDownloadCleanResultUrl, getSampleSetOptions, importToSample, queryCleanPics, getCleanPicImageUrl, rollbackCleanPics, deleteCleanResultFile, type CleanResult, type CleanResultData, type SampleSetOption, type CleanPicRecord } from '@/api/clean'
import { getCodeDict } from '@/api/sample'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'

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
// 当前查看的记录ID，翻页时复用
const viewCurrentRecordId = ref<number>(0)
// 总条数（来自后端，避免依赖 viewData.rows.length）
const viewTotal = ref(0)

// 翻页时请求后端对应页数据
async function handleViewPageChange(page: number) {
  if (!viewCurrentRecordId.value || page === viewCurrentPage.value) return
  viewCurrentPage.value = page
  viewLoading.value = true
  try {
    viewData.value = await viewCleanResult(viewCurrentRecordId.value, page, viewPageSize)
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    viewLoading.value = false
  }
}

async function handleView(item: CleanResult) {
  // 图片类型清洗结果：查询被清洗的图片记录并展示
  if (item.sampleTypeCode === '05') {
    await handleViewImageResult(item)
    return
  }
  // 时序/结构化类型：查看 JSON 结果文件（服务端分页）
  viewVisible.value = true
  viewLoading.value = true
  viewData.value = null
  viewCurrentPage.value = 1
  viewCurrentRecordId.value = item.recordId
  viewTotal.value = 0
  try {
    const res = await viewCleanResult(item.recordId, 1, viewPageSize)
    viewData.value = res
    viewTotal.value = res.total || 0
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
    imageResultList.value = await queryCleanPics(item.recordId, item.taskNo)
  } catch (e: any) {
    ElMessage.error(e.message || '查看失败')
  } finally {
    imageResultLoading.value = false
  }
}

// ========== 清洗标签解析与颜色 ==========
const TAG_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  '模糊':   { bg: 'rgba(255, 82, 82, 0.12)',  border: 'rgba(255, 82, 82, 0.35)',  text: '#ff5252' },
  '过暗':   { bg: 'rgba(100, 100, 255, 0.12)', border: 'rgba(100, 100, 255, 0.35)', text: '#6464ff' },
  '过亮':   { bg: 'rgba(255, 215, 0, 0.12)',   border: 'rgba(255, 215, 0, 0.35)',   text: '#ffd700' },
  '信息量低': { bg: 'rgba(160, 120, 255, 0.12)', border: 'rgba(160, 120, 255, 0.35)', text: '#a078ff' },
  '宽高比异常': { bg: 'rgba(0, 200, 200, 0.12)',  border: 'rgba(0, 200, 200, 0.35)',  text: '#00c8c8' },
  '灰度图像': { bg: 'rgba(180, 180, 180, 0.12)', border: 'rgba(180, 180, 180, 0.35)', text: '#b4b4b4' },
  '完全重复': { bg: 'rgba(255, 100, 200, 0.12)', border: 'rgba(255, 100, 200, 0.35)', text: '#ff64c8' },
  '近似重复': { bg: 'rgba(255, 150, 50, 0.12)',  border: 'rgba(255, 150, 50, 0.35)',  text: '#ff9632' },
  '异常大小': { bg: 'rgba(50, 200, 100, 0.12)',  border: 'rgba(50, 200, 100, 0.35)',  text: '#32c864' },
}

const DEFAULT_TAG_COLOR = { bg: 'rgba(255, 170, 0, 0.1)', border: 'rgba(255, 170, 0, 0.25)', text: '#ffaa00' }

function parseCleanTags(cleanTypeName: string): string[] {
  if (!cleanTypeName) return []
  return cleanTypeName.split(/[,，]/).map(s => s.trim()).filter(Boolean)
}

function tagColor(tag: string) {
  return TAG_COLORS[tag] || DEFAULT_TAG_COLOR
}

// ========== 图片预览弹框 ==========
const imagePreviewVisible = ref(false)
const imagePreviewUrl = ref('')
const imagePreviewTitle = ref('')
const imagePreviewTags = ref<string[]>([])
const imagePreviewRepeatUrl = ref('')     // 对比图 URL，仅重复类型有值
const imagePreviewRepeatName = ref('')    // 对比图文件名
const imagePreviewIsDuplicate = ref(false) // 是否为重复类型（控制分左右展示）

// 重复检测中文名集合
const DUPLICATE_TAGS = new Set(['完全重复', '近似重复'])

function openImagePreview(pic: CleanPicRecord) {
  const tags = parseCleanTags(pic.cleanTypeName)
  const isDuplicate = tags.some(t => DUPLICATE_TAGS.has(t))

  imagePreviewUrl.value = getCleanPicImageUrl(pic.filePath)
  imagePreviewTitle.value = pic.fileName || '图片预览'
  imagePreviewTags.value = tags
  imagePreviewIsDuplicate.value = isDuplicate

  if (isDuplicate && pic.repeatFilePath) {
    imagePreviewRepeatUrl.value = getCleanPicImageUrl(pic.repeatFilePath)
    imagePreviewRepeatName.value = pic.repeatFileName || '对比图'
  } else {
    imagePreviewRepeatUrl.value = ''
    imagePreviewRepeatName.value = ''
  }
  imagePreviewVisible.value = true
}

// ========== 回滚 ==========
const rollbackSet = ref<Set<number>>(new Set())

async function handleRollback(item: CleanResult) {
  try {
    await ElMessageBox.confirm(
      `确认回滚清洗任务「${item.taskName || item.taskNo}」？\n已标记的问题图片将取消清洗标记，恢复为未清洗状态。`,
      '回滚确认',
      { type: 'warning', confirmButtonText: '回滚', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  rollbackSet.value.add(item.recordId)
  try {
    const result = await rollbackCleanPics(item.taskNo, item.recordId)
    ElMessage.success(`回滚成功，恢复 ${result.restoredCount} 张图片${result.skippedCount ? `，跳过 ${result.skippedCount} 张` : ''}`)
    await loadResults()
  } catch (e: any) {
    ElMessage.error(e.message || '回滚失败')
  } finally {
    rollbackSet.value.delete(item.recordId)
  }
}

// ========== 删除结果文件 ==========
const deleteSet = ref<Set<number>>(new Set())

async function handleDeleteFile(item: CleanResult) {
  try {
    await ElMessageBox.confirm(
      `确认删除清洗结果文件「${item.fileName || item.taskNo}」？\n删除后该结果将无法查看和下载（状态变为"文件已删除"）。`,
      '删除文件确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  deleteSet.value.add(item.recordId)
  try {
    await deleteCleanResultFile(item.recordId)
    ElMessage.success('文件已删除')
    await loadResults()
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  } finally {
    deleteSet.value.delete(item.recordId)
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

async function confirmDownload() {
  if (!downloadItem.value) return
  const url = getDownloadCleanResultUrl(downloadItem.value.recordId, downloadFormat.value)
  downloadVisible.value = false
  const loadingInstance = ElLoading.service({ lock: true, text: '正在下载文件...', background: 'rgba(0,0,0,0.7)' })
  try {
    const res = await fetch(url)
    if (!res.ok) {
      const errData = await res.json().catch(() => null)
      throw new Error(errData?.message || '下载失败')
    }
    const blob = await res.blob()
    // 从响应头获取文件名
    let fileName = `${downloadItem.value.taskNo || '清洗结果'}_${downloadFormat.value === 'excel' ? 'xlsx' : 'json'}`
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename\*?=([^;]+)/i)
    if (match) {
      fileName = decodeURIComponent(match[1].replace(/^UTF-8''/i, '').replace(/^"/, '').replace(/"$/, '').trim())
    }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = fileName
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success('下载成功')
  } catch (e: any) {
    console.error('下载失败:', e)
    ElMessage.error(e.message || '下载出错')
  } finally {
    loadingInstance.close()
  }
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

        <el-table :data="filteredList" v-loading="loading" style="width: 100%" class="clean-result-table">
          <el-table-column prop="taskNo" label="任务编号" width="150" />
          <el-table-column prop="taskName" label="任务名称" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">{{ row.taskName || '-' }}</template>
          </el-table-column>
          <el-table-column prop="sampleTypeCode" label="数据类型" width="100">
            <template #default="{ row }">{{ getSampleTypeName(row.sampleTypeCode) }}</template>
          </el-table-column>
          <el-table-column prop="startTime" label="执行开始时间" width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ row.startTime || '-' }}</template>
          </el-table-column>
          <el-table-column prop="endTime" label="执行结束时间" width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ row.endTime || '-' }}</template>
          </el-table-column>
          <el-table-column label="结果数据数" width="100">
            <template #default="{ row }">{{ row.sampleTypeCode === '05' ? row.removedCount : row.resultCount }}</template>
          </el-table-column>
          <el-table-column prop="fileName" label="文件名" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.fileName || '-' }}</template>
          </el-table-column>
          <el-table-column prop="filePath" label="文件路径" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.filePath || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="280">
            <template #default="{ row }">
              <template v-if="row.executeStatus === '05'">
                <span class="rollback-status-text">已回滚</span>
              </template>
              <template v-else-if="row.executeStatus === '06'">
                <span class="rollback-status-text">文件已删除</span>
              </template>
              <template v-else>
                <el-button size="small" @click="handleView(row)">查看</el-button>
                <el-button v-if="row.sampleTypeCode !== '05'" size="small" @click="handleDownload(row)">下载</el-button>
                <el-button
                  v-if="row.sampleTypeCode !== '05'"
                  size="small"
                  type="danger"
                  :loading="deleteSet.has(row.recordId)"
                  @click="handleDeleteFile(row)"
                >删除文件</el-button>
                <el-button v-if="row.sampleTypeCode !== '05' && row.executeStatus !== '07'" size="small" type="primary" @click="handleImport(row)">入库</el-button>
                <el-button
                  v-if="row.sampleTypeCode === '05'"
                  size="small"
                  type="warning"
                  :loading="rollbackSet.has(row.recordId)"
                  @click="handleRollback(row)"
                >回滚</el-button>
              </template>
            </template>
          </el-table-column>
          <template #empty>
            <div class="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1.5">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <p>暂无清洗结果</p>
            </div>
          </template>
        </el-table>
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
          <el-table :data="viewData.rows" style="width: 100%" max-height="500" class="view-table">
            <el-table-column type="index" label="#" width="50" :index="(i: number) => (viewCurrentPage - 1) * viewPageSize + i + 1" />
            <el-table-column
              v-for="col in viewData.columns"
              :key="col"
              :prop="col"
              :label="col"
              min-width="120"
              show-overflow-tooltip
            >
              <template #default="{ row }">{{ row[col] ?? '' }}</template>
            </el-table-column>
            <template #empty>
              <div class="td-empty">暂无数据</div>
            </template>
          </el-table>
        </div>
        <div class="view-pagination" v-if="viewTotal > viewPageSize">
          <el-pagination
            v-model:current-page="viewCurrentPage"
            :page-size="viewPageSize"
            :total="viewTotal"
            layout="prev, pager, next, total"
            background
            @current-change="handleViewPageChange"
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
          <div v-for="pic in imageFilteredResult" :key="pic.recordId" class="image-card" @click="openImagePreview(pic)">
            <div class="image-thumb">
              <img :src="getCleanPicImageUrl(pic.filePath)" :alt="pic.fileName" loading="lazy" />
            </div>
            <div class="image-info">
              <div class="image-name" :title="pic.fileName">{{ pic.fileName }}</div>
              <div class="image-reasons">
                <span
                  v-for="(tag, idx) in parseCleanTags(pic.cleanTypeName)"
                  :key="idx"
                  class="image-tag"
                  :style="{ background: tagColor(tag).bg, borderColor: tagColor(tag).border, color: tagColor(tag).text }"
                >{{ tag }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="imageResultVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 图片预览弹框 -->
    <el-dialog
      v-model="imagePreviewVisible"
      width="auto"
      top="5vh"
      :close-on-click-modal="true"
      class="image-preview-dialog"
      destroy-on-close
      append-to-body
    >
      <template #header>
        <div class="preview-header">
          <span class="preview-name">{{ imagePreviewTitle }}</span>
          <span
            v-for="(tag, idx) in imagePreviewTags"
            :key="idx"
            class="image-tag"
            :style="{ background: tagColor(tag).bg, borderColor: tagColor(tag).border, color: tagColor(tag).text }"
          >{{ tag }}</span>
        </div>
      </template>
      <!-- 重复图: 左右分栏对比 -->
      <div v-if="imagePreviewIsDuplicate" class="image-preview-dual">
        <div class="image-preview-side">
          <div class="image-preview-label image-preview-label-b">被清洗图片</div>
          <div class="image-preview-wrap">
            <img :src="imagePreviewUrl" :alt="imagePreviewTitle" class="image-preview-img" />
          </div>
          <div class="image-preview-filename" :title="imagePreviewTitle">{{ imagePreviewTitle }}</div>
        </div>
        <div class="image-preview-divider"></div>
        <div class="image-preview-side">
          <div class="image-preview-label image-preview-label-a">对比图（保留）</div>
          <div v-if="imagePreviewRepeatUrl" class="image-preview-wrap">
            <img :src="imagePreviewRepeatUrl" :alt="imagePreviewRepeatName" class="image-preview-img" />
          </div>
          <div v-else class="image-preview-empty">对比图缺失</div>
          <div class="image-preview-filename" :title="imagePreviewRepeatName">{{ imagePreviewRepeatName }}</div>
        </div>
      </div>
      <!-- 非重复: 单图展示（保持原逻辑） -->
      <div v-else class="image-preview-wrap">
        <img :src="imagePreviewUrl" :alt="imagePreviewTitle" class="image-preview-img" />
      </div>
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

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 14px;
  gap: 12px;
}

.rollback-status-text {
  color: rgba(255, 170, 0, 0.8);
  font-size: 13px;
  font-weight: 500;
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
    width: 10px;
    height: 10px;
  }

  &::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(0, 212, 255, 0.5);
    border-radius: 5px;

    &:hover {
      background: rgba(0, 212, 255, 0.7);
    }
  }
}

.view-table {
  font-size: 13px;
}

.td-empty {
  text-align: center;
  padding: 40px 0;
  color: rgba(255, 255, 255, 0.3);
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
  height: 65vh; // 固定高度，确保内容超出时可滚动
  max-height: calc(90vh - 150px); // 最大高度限制
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
  margin-bottom: 12px;
  flex-shrink: 0;

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
  overflow-x: hidden;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  align-content: start;
  padding: 4px;
  min-height: 0; // 重要：让 flex 子项可以收缩并显示滚动条

  &::-webkit-scrollbar {
    width: 10px;
    height: 12px;
  }

  &::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 5px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(0, 212, 255, 0.5);
    border-radius: 5px;

    &:hover {
      background: rgba(0, 212, 255, 0.7);
    }
  }
}

.image-card {
  background: rgba(0, 212, 255, 0.04);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s, transform 0.2s;
  display: flex;
  flex-direction: column;
  height: 240px; // 卡片高度调大
  cursor: pointer;

  &:hover {
    border-color: rgba(0, 212, 255, 0.5);
    transform: translateY(-2px);
  }
}

.image-thumb {
  width: 100%;
  height: 165px; // 图片区域调大
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
}

.image-info {
  padding: 10px;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 0;
  overflow: hidden;
}

.image-name {
  font-size: 13px; // 字体调大
  color: rgba(255, 255, 255, 0.8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 6px;
  flex-shrink: 0;
}

.image-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  overflow: hidden;
}

.image-tag {
  font-size: 12px; // 标签字体调大
  line-height: 1.5;
  padding: 2px 8px;
  border: 1px solid;
  border-radius: 3px;
  white-space: nowrap;
  flex-shrink: 0;
}

// ========== 图片预览弹框 ==========
.image-preview-dialog {
  :deep(.el-dialog) {
    max-width: 90vw;
    max-height: 90vh;
    background: rgba(0, 0, 0, 0.92);
    border-color: rgba(0, 212, 255, 0.3);
  }
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-right: 30px; // 给关闭按钮留空间

  .preview-name {
    font-size: 14px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.9);
  }

  .image-tag {
    font-size: 12px;
  }
}

.image-preview-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: 85vw;
  max-height: 80vh;
  overflow: hidden;
}

.image-preview-img {
  max-width: 85vw;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 4px;
}

// ========== 重复图对比展示（左右分栏） ==========
.image-preview-dual {
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: 16px;
  max-width: 90vw;
  max-height: 80vh;
}

.image-preview-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.image-preview-label {
  font-size: 13px;
  padding: 4px 14px;
  border-radius: 4px;
  margin-bottom: 10px;
  border: 1px solid;
  white-space: nowrap;
}

.image-preview-label-b {
  color: #ff9632;
  background: rgba(255, 150, 50, 0.12);
  border-color: rgba(255, 150, 50, 0.35);
}

.image-preview-label-a {
  color: #00d4ff;
  background: rgba(0, 212, 255, 0.12);
  border-color: rgba(0, 212, 255, 0.35);
}

.image-preview-divider {
  width: 1px;
  background: rgba(0, 212, 255, 0.2);
  align-self: stretch;
}

.image-preview-filename {
  margin-top: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.image-preview-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 200px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 13px;
  border: 1px dashed rgba(255, 255, 255, 0.15);
  border-radius: 4px;
}

// 双图模式下约束单图尺寸，不影响单图模式
.image-preview-dual .image-preview-wrap {
  max-width: 42vw;
  max-height: 70vh;
}

.image-preview-dual .image-preview-img {
  max-width: 42vw;
  max-height: 70vh;
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
