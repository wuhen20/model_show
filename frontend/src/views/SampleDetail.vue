<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getSamples, getImageUrl, getAnnotations, getAudioText, updateSampleScore, uploadSamples, uploadSamplesBatch, saveLabelThink, getClasses, getSamplesByLabels, type SampleInfoRow, type AnnotationData, type AnnotationBox } from '@/api/sample'
import ChunkUploadDialog from '@/components/ChunkUploadDialog.vue'
import { ElMessage, ElLoading } from 'element-plus'

const route = useRoute()
const router = useRouter()

const setNo = ref(typeof route.query.setNo === 'string' ? route.query.setNo : '')
const setName = ref(typeof route.query.setName === 'string' ? route.query.setName : '')
const typeCode = ref(typeof route.query.typeCode === 'string' ? route.query.typeCode : '')

const loading = ref(false)
const sampleList = ref<SampleInfoRow[]>([])
const columns = ref<{ key: string; label: string }[]>([])

// 判断是否为图片样本集
const isImageSet = computed(() => typeCode.value === '05')

// 判断是否为时序样本集
const isTimeSeriesSet = computed(() => typeCode.value === '02')

// 视图模式：缩略图 / 列表
const viewMode = ref<'thumbnail' | 'list'>('list')

// ========== 上传样本弹框 ==========
const uploadDialogVisible = ref(false)
const uploadSaving = ref(false)
const uploadFileList = ref<File[]>([])
const uploadDisplayList = ref<any[]>([]) // el-upload 显示的文件列表

// 样本类型编码 → 允许的文件扩展名
const typeCodeToExtensions: Record<string, string[]> = {
  '05': ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tif', '.tiff'],
  '02': ['.txt', '.csv', '.json', '.xml', '.doc', '.docx', '.pdf'],
  '03': ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.wma', '.m4a'],
  '04': ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'],
}

// 样本类型编码 → 允许的 accept 值
const typeCodeToAccept: Record<string, string> = {
  '05': 'image/*,.txt',
  '02': '.txt,.csv,.json,.xml,.doc,.docx,.pdf',
  '03': 'audio/*',
  '04': 'video/*',
}

function openUploadDialog() {
  uploadFileList.value = []
  uploadDisplayList.value = []
  uploadDialogVisible.value = true
}

// 导出相关
const exportDialogVisible = ref(false)
const exportFormat = ref<'original' | 'json'>('original')
const exportLoading = ref(false)

function openExportDialog() {
  exportFormat.value = 'original'
  exportDialogVisible.value = true
}

async function confirmExport() {
  if (!setNo.value) {
    ElMessage.warning('样本集编号为空')
    return
  }
  exportLoading.value = true
  try {
    const fileName = (setName.value || setNo.value).replace(/\s+/g, '_')
    let url = ''
    if (exportFormat.value === 'original') {
      url = `/api/sample/download-sample-set?setNo=${encodeURIComponent(setNo.value)}&fileName=${encodeURIComponent(fileName)}`
    } else {
      url = `/api/sample/export-sample-set-json?setNo=${encodeURIComponent(setNo.value)}&fileName=${encodeURIComponent(fileName)}`
    }
    // 触发下载
    const a = document.createElement('a')
    a.href = url
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    exportDialogVisible.value = false
    ElMessage.success('导出任务已开始，请等待浏览器下载')
  } catch (e: any) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exportLoading.value = false
  }
}

function handleUploadFileChange(_file: any, fileList: any[]) {
  uploadFileList.value = fileList.map((f: any) => f.raw)
}

function handleUploadFileRemove(_file: any, fileList: any[]) {
  uploadFileList.value = fileList.map((f: any) => f.raw)
}

async function handleUploadConfirm() {
  if (uploadFileList.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  // 前端校验文件类型（图片类型允许额外附带 .txt 标注文件）
  const allowedExts = typeCodeToExtensions[typeCode.value]
  if (allowedExts) {
    const isImageType = typeCode.value === '05'
    const invalidFiles = uploadFileList.value.filter(f => {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase()
      if (isImageType && ext === '.txt') return false
      return !allowedExts.includes(ext)
    })
    if (invalidFiles.length > 0) {
      ElMessage.warning(`以下文件类型不符合该样本集要求：${invalidFiles.map(f => f.name).join('、')}`)
      return
    }
  }

  uploadSaving.value = true
  try {
    const msg = await uploadSamples(setNo.value, setName.value, typeCode.value, uploadFileList.value)
    ElMessage.success(msg)
    uploadDialogVisible.value = false
    loadSamples()
  } catch (e: any) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploadSaving.value = false
  }
}

// ========== 批量导入弹框（仅图片类型，分片上传）==========
const batchDialogVisible = ref(false)

function openBatchDialog() {
  if (typeCode.value !== '05') {
    ElMessage.warning('批量导入仅支持图片类型样本集')
    return
  }
  batchDialogVisible.value = true
}

function handleBatchUploadSuccess() {
  loadSamples()
}

// 筛选条件
const filterName = ref('')
const filterLabelFlag = ref('')
const filterLabels = ref<string[]>([]) // 标签筛选（多选）
const classOptions = ref<string[]>([]) // classes.txt 中的标签选项
const labelFilteredSamples = ref<SampleInfoRow[] | null>(null) // 标签筛选结果（null 表示未启用标签筛选）

// 分页
const currentPage = ref(1)
const pageSize = 20

// 筛选后的数据
const filteredList = computed(() => {
  // 基础列表：若启用了标签筛选，则从标签筛选结果中再过滤
  let list = labelFilteredSamples.value !== null ? labelFilteredSamples.value : sampleList.value
  if (filterName.value) {
    const kw = filterName.value.toLowerCase()
    list = list.filter(s => String(s.sampleName || '').toLowerCase().includes(kw))
  }
  if (filterLabelFlag.value) {
    list = list.filter(s => String(s.labelFlag || '') === filterLabelFlag.value)
  }
  return list
})

// 当前页数据
const pagedList = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredList.value.slice(start, start + pageSize)
})

const totalPages = computed(() => Math.ceil(filteredList.value.length / pageSize))

function handlePageChange(page: number) {
  currentPage.value = page
}

function resetFilters() {
  filterName.value = ''
  filterLabelFlag.value = ''
  filterLabels.value = []
  labelFilteredSamples.value = null
  currentPage.value = 1
}

// 标签筛选变化时请求后端
watch(filterLabels, async (val) => {
  currentPage.value = 1
  if (!val || val.length === 0) {
    labelFilteredSamples.value = null
    return
  }
  try {
    const data = await getSamplesByLabels(setNo.value, val)
    labelFilteredSamples.value = data
  } catch (e: any) {
    ElMessage.error(e.message || '标签筛选失败')
    labelFilteredSamples.value = []
  }
})

// 筛选条件变化时重置页码
watch([filterName, filterLabelFlag], () => {
  currentPage.value = 1
})

async function loadSamples() {
  if (!setNo.value) return
  loading.value = true
  try {
    const data = await getSamples(setNo.value)
    sampleList.value = data
    // 根据返回数据动态生成列
    if (data.length > 0) {
      columns.value = Object.keys(data[0]).map(key => ({
        key,
        label: keyToLabel(key)
      }))
    } else {
      columns.value = []
    }
    // 图片类型样本集：加载标签选项
    if (isImageSet.value) {
      try {
        classOptions.value = await getClasses(setNo.value)
      } catch {
        classOptions.value = []
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '查询样本信息失败')
  } finally {
    loading.value = false
  }
}

// 常见字段名映射为中文
const labelMap: Record<string, string> = {
  recordId: '记录ID',
  setNo: '样本集编号',
  sampleNo: '样本编号',
  sampleName: '样本名称',
  typeCode: '样本类型编号',
  typeName: '样本类型',
  suffix: '后缀名',
  labelFlagCode: '标注状态编号',
  labelFlag: '标注状态',
  labelThink: '思维链',
  filePath: '文件路径',
  fileName: '文件名',
  fileSize: '文件大小',
  sampleScore: '质量评分',
  resultCount: '数据数量',
  status: '状态',
  createTime: '创建时间',
  updateTime: '更新时间'
}

function keyToLabel(key: string): string {
  return labelMap[key] || key
}

function goBack() {
  router.push('/sample-set')
}

// ========== 时序类型查看/下载 ==========
const tsViewVisible = ref(false)
const tsViewLoading = ref(false)
const tsViewData = ref<{ taskNo: string; taskName: string; executeTime: string; totalCount: number; removedCount: number; resultCount: number; columns: string[]; rows: Record<string, any>[] } | null>(null)
const tsViewSampleName = ref('')  // 当前查看的样本名称
const tsViewCurrentPage = ref(1)
const tsViewPageSize = 20

const tsViewPagedRows = computed(() => {
  if (!tsViewData.value?.rows) return []
  const start = (tsViewCurrentPage.value - 1) * tsViewPageSize
  return tsViewData.value.rows.slice(start, start + tsViewPageSize)
})

async function handleViewTimeSeries(row: SampleInfoRow) {
  const filePath = row.filePath
  if (!filePath) {
    ElMessage.warning('该样本无文件路径')
    return
  }
  tsViewVisible.value = true
  tsViewLoading.value = true
  tsViewData.value = null
  tsViewSampleName.value = row.sampleName || ''
  tsViewCurrentPage.value = 1
  try {
    const res = await fetch(`/api/clean/view-clean-result-by-path?filePath=${encodeURIComponent(filePath)}`)
    const json = await res.json()
    if (json.code !== 0) throw new Error(json.message || '查看失败')
    tsViewData.value = json.data
  } catch (e: any) {
    ElMessage.error(e.message || '查看失败')
  } finally {
    tsViewLoading.value = false
  }
}

function handleDownloadTimeSeries(row: SampleInfoRow) {
  const filePath = row.filePath
  if (!filePath) {
    ElMessage.warning('该样本无文件路径')
    return
  }
  const url = `/api/clean/download-clean-result-by-path?filePath=${encodeURIComponent(filePath)}`
  const loading = ElLoading.service({ lock: true, text: '正在下载文件...', background: 'rgba(0,0,0,0.7)' })
  fetch(url)
    .then(async res => {
      if (!res.ok) {
        const errData = await res.json().catch(() => null)
        throw new Error(errData?.message || '下载失败')
      }
      return res.blob()
    })
    .then(blob => {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = row.sampleName || 'data.json'
      a.click()
      URL.revokeObjectURL(a.href)
      ElMessage.success('下载成功')
    })
    .catch(e => {
      console.error('下载失败:', e)
      ElMessage.error(e.message || '下载出错')
    })
    .finally(() => {
      loading.close()
    })
}

// 隐藏的字段（不需要在表格中展示）
const hiddenColumns = computed(() => {
  const base = new Set(['recordId', 'sampleNo', 'typeCode', 'filePath', 'fileName', 'labelFlagCode', 'labelFlag', 'sampleScore', 'labelThink', 'labelContent'])
  return base
})

// ========== 文件预览 ==========
const imageExtSet = new Set(['jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp', 'tif', 'tiff'])
const audioExtSet = new Set(['mp3', 'wav', 'ogg', 'flac', 'aac', 'wma', 'm4a'])

function isImageRow(row: SampleInfoRow): boolean {
  const suffix = String(row.suffix || '').toLowerCase().replace('.', '')
  if (suffix && imageExtSet.has(suffix)) return true
  return String(row.typeCode || '') === '05'
}

function isAudioRow(row: SampleInfoRow): boolean {
  const suffix = String(row.suffix || '').toLowerCase().replace('.', '')
  if (suffix && audioExtSet.has(suffix)) return true
  return String(row.typeCode || '') === '03'
}

function isPreviewable(row: SampleInfoRow): boolean {
  return isImageRow(row) || isAudioRow(row)
}

const previewVisible = ref(false)
const previewLoading = ref(false)
const imageLoading = ref(false) // 图片二进制加载中（独立于标注获取）
const previewName = ref('')
const previewFilePath = ref('')
const previewType = ref<'image' | 'audio'>('image')

// 预览遮罩文本：标注获取与图片加载分阶段提示
const previewLoadingText = computed(() => {
  if (previewLoading.value) return '正在加载标注信息...'
  if (imageLoading.value) return '正在获取图片...'
  return ''
})
const annotationData = ref<AnnotationData | null>(null)
const previewCanvas = ref<HTMLCanvasElement | null>(null)

// 标注框颜色
const boxColors = [
  '#00d4ff', '#00ff88', '#ff5555', '#ffaa00', '#a855f7',
  '#ff6b9d', '#45ffbc', '#ffd93d', '#6c5ce7', '#fd79a8'
]

// ========== 标注面板状态 ==========
const selectedBoxIndex = ref<number | null>(null)
const panelSearchKeyword = ref('')
const panelCategoryFilter = ref('')

// ========== 思维链状态 ==========
const thinkVisible = ref(false)       // 思维链框是否展开
const thinkCollapsed = ref(false)     // 思维链框是否最小化
const thinkContent = ref('')          // 思维链文本内容
const thinkHeight = ref(200)          // 思维链框高度（px）
const thinkSaving = ref(false)        // 保存中
const thinkSampleNo = ref('')         // 当前样本编号
const thinkSampleName = ref('')       // 当前样本名称
let thinkResizing = false             // 是否正在拖拽调整大小
let thinkResizeStartY = 0
let thinkResizeStartH = 0

function startThinkResize(e: MouseEvent) {
  thinkResizing = true
  thinkResizeStartY = e.clientY
  thinkResizeStartH = thinkHeight.value
  document.addEventListener('mousemove', onThinkResize)
  document.addEventListener('mouseup', stopThinkResize)
  e.preventDefault()
}

function onThinkResize(e: MouseEvent) {
  if (!thinkResizing) return
  const delta = thinkResizeStartY - e.clientY
  thinkHeight.value = Math.max(80, Math.min(600, thinkResizeStartH + delta))
}

function stopThinkResize() {
  thinkResizing = false
  document.removeEventListener('mousemove', onThinkResize)
  document.removeEventListener('mouseup', stopThinkResize)
}

function toggleThinkCollapse() {
  thinkCollapsed.value = !thinkCollapsed.value
}

async function handleSaveThink() {
  if (!thinkSampleNo.value || !thinkSampleName.value) return
  thinkSaving.value = true
  try {
    await saveLabelThink(thinkSampleNo.value, thinkSampleName.value, thinkContent.value)
    ElMessage.success('思维链保存成功')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    thinkSaving.value = false
  }
}

// ========== 音频播放状态 ==========
const audioRef = ref<HTMLAudioElement | null>(null)
const audioPlaying = ref(false)
const audioCurrentTime = ref(0)
const audioDuration = ref(0)
const audioPlaybackRate = ref(1)
const audioSampleRate = ref<number | null>(null)
const audioChannels = ref<number | null>(null)
const audioText = ref<string | null>(null)
const playbackRates = [0.5, 0.75, 1, 1.25, 1.5, 2]

function onAudioLoaded() {
  if (!audioRef.value) return
  audioDuration.value = audioRef.value.duration
  // 尝试获取技术参数
  const audioCtx = new AudioContext()
  audioRef.value.addEventListener('canplaythrough', () => {
    // 通过 AudioContext 获取采样率
    audioSampleRate.value = audioCtx.sampleRate
    audioCtx.close()
  }, { once: true })
}

function toggleAudioPlay() {
  if (!audioRef.value) return
  if (audioPlaying.value) {
    audioRef.value.pause()
  } else {
    audioRef.value.play()
  }
  audioPlaying.value = !audioPlaying.value
}

function onAudioTimeUpdate() {
  if (!audioRef.value) return
  audioCurrentTime.value = audioRef.value.currentTime
}

function onAudioEnded() {
  audioPlaying.value = false
  audioCurrentTime.value = 0
}

function seekAudio(e: MouseEvent) {
  if (!audioRef.value) return
  const bar = e.currentTarget as HTMLElement
  const rect = bar.getBoundingClientRect()
  const ratio = (e.clientX - rect.left) / rect.width
  audioRef.value.currentTime = ratio * audioDuration.value
}

function setPlaybackRate(rate: number) {
  audioPlaybackRate.value = rate
  if (audioRef.value) {
    audioRef.value.playbackRate = rate
  }
}

function downloadAudio() {
  const url = getImageUrl(previewFilePath.value)
  const a = document.createElement('a')
  a.href = url
  a.download = previewName.value || 'audio'
  a.click()
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// 面板筛选后的标注列表
const filteredBoxes = computed(() => {
  if (!annotationData.value?.boxes) return []
  let boxes = annotationData.value.boxes.map((box, index) => ({ ...box, _index: index }))
  if (panelCategoryFilter.value) {
    boxes = boxes.filter(b => b.className === panelCategoryFilter.value)
  }
  if (panelSearchKeyword.value) {
    const kw = panelSearchKeyword.value.toLowerCase()
    boxes = boxes.filter(b => b.className.toLowerCase().includes(kw))
  }
  return boxes
})

// 类别列表（用于筛选下拉）
const categoryOptions = computed(() => {
  if (!annotationData.value?.boxes) return []
  const set = new Set(annotationData.value.boxes.map(b => b.className))
  return Array.from(set)
})

// 类别统计
const categoryStats = computed(() => {
  if (!annotationData.value?.boxes) return []
  const map = new Map<string, number>()
  annotationData.value.boxes.forEach(b => {
    map.set(b.className, (map.get(b.className) || 0) + 1)
  })
  return Array.from(map.entries()).map(([name, count]) => ({ name, count }))
})

// 画布渲染缓存
let cachedImage: HTMLImageElement | null = null
let cachedDisplayW = 0
let cachedDisplayH = 0

async function openPreview(row: SampleInfoRow) {
  const filePath = row.filePath
  if (!filePath) {
    ElMessage.warning('该样本无文件路径')
    return
  }
  previewName.value = row.sampleName || ''
  previewFilePath.value = filePath
  annotationData.value = null
  selectedBoxIndex.value = null
  panelSearchKeyword.value = ''
  panelCategoryFilter.value = ''
  cachedImage = null

  if (isImageRow(row)) {
    previewType.value = 'image'
    previewVisible.value = true
    previewLoading.value = true
    imageLoading.value = true // 图片开始加载

    // 初始化思维链状态
    thinkSampleNo.value = String(row.sampleNo || '')
    thinkSampleName.value = String(row.sampleName || '')
    const thinkText = (row.labelThink as string) || ''
    thinkContent.value = thinkText
    thinkVisible.value = true
    thinkCollapsed.value = !thinkText  // 有值则展开，无值则最小化

    try {
      const ann = await getAnnotations(String(row.sampleNo || ''))
      annotationData.value = ann
    } catch {
      annotationData.value = null
    }

    previewLoading.value = false

    if (annotationData.value?.hasAnnotations) {
      await nextTick()
      drawAnnotations()
      // drawAnnotations 内部会在图片 onload/onerror 时关闭 imageLoading
    }
    // 无标注分支由 <img> 的 @load/@error 关闭 imageLoading
  } else if (isAudioRow(row)) {
    previewType.value = 'audio'
    audioText.value = null
    previewVisible.value = true
    // 查询转写文字
    try {
      const sampleNo = String(row.sampleNo || '')
      const sampleName = String(row.sampleName || '')
      if (sampleNo && sampleName) {
        audioText.value = await getAudioText(sampleNo, sampleName)
      }
    } catch {
      audioText.value = null
    }
  }
}

function drawAnnotations(highlightIndex?: number | null) {
  const canvas = previewCanvas.value
  if (!canvas || !annotationData.value) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // 如果已有缓存的图片，直接使用
  const drawImage = (img: HTMLImageElement) => {
    const nw = img.naturalWidth
    const nh = img.naturalHeight

    // 使用 canvas 容器的实际尺寸来计算缩放
    const scrollContainer = canvas.parentElement
    const containerW = scrollContainer ? scrollContainer.clientWidth : Math.round(window.innerWidth * 0.9 * 0.65)
    const containerH = scrollContainer ? scrollContainer.clientHeight : Math.round(window.innerHeight * 0.82)

    const scaleByW = containerW / nw
    const scaleByH = containerH / nh
    const scale = Math.min(scaleByW, scaleByH)

    const displayW = Math.round(nw * scale)
    const displayH = Math.round(nh * scale)

    canvas.width = displayW
    canvas.height = displayH
    canvas.style.width = displayW + 'px'
    canvas.style.height = displayH + 'px'

    cachedDisplayW = displayW
    cachedDisplayH = displayH

    ctx.drawImage(img, 0, 0, displayW, displayH)

    // 绘制标注框
    const boxes = annotationData.value!.boxes
    boxes.forEach((box, i) => {
      const x = (box.cx - box.w / 2) * displayW
      const y = (box.cy - box.h / 2) * displayH
      const w = box.w * displayW
      const h = box.h * displayH

      const color = boxColors[box.classId % boxColors.length]
      const isHighlighted = highlightIndex !== undefined && highlightIndex !== null && highlightIndex === i
      const isOtherDimmed = highlightIndex !== undefined && highlightIndex !== null && highlightIndex !== i

      // 非选中框半透明
      if (isOtherDimmed) {
        ctx.globalAlpha = 0.3
      }

      // 绘制矩形
      ctx.strokeStyle = color
      ctx.lineWidth = isHighlighted
        ? Math.max(4, Math.min(displayW, displayH) / 150)
        : Math.max(2, Math.min(displayW, displayH) / 300)
      ctx.strokeRect(x, y, w, h)

      // 选中框填充半透明背景
      if (isHighlighted) {
        ctx.fillStyle = color
        ctx.globalAlpha = 0.15
        ctx.fillRect(x, y, w, h)
        ctx.globalAlpha = 1
      }

      // 绘制标签背景和文字
      const label = box.className
      const fontSize = Math.max(14, Math.min(displayW, displayH) / 45)
      ctx.font = `bold ${fontSize}px sans-serif`
      const textMetrics = ctx.measureText(label)
      const padding = 4
      const labelH = fontSize + padding * 2

      const labelOnTop = y - labelH >= 0
      const labelY = labelOnTop ? y - labelH : y + h - labelH

      ctx.fillStyle = color
      ctx.globalAlpha = isOtherDimmed ? 0.3 : 0.8
      ctx.fillRect(x, labelY, textMetrics.width + padding * 2, labelH)
      ctx.globalAlpha = isOtherDimmed ? 0.3 : 1

      ctx.fillStyle = '#fff'
      ctx.fillText(label, x + padding, labelY + fontSize + padding)

      ctx.globalAlpha = 1
    })
  }

  if (cachedImage) {
    drawImage(cachedImage)
    imageLoading.value = false
  } else {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      cachedImage = img
      drawImage(img)
      imageLoading.value = false
    }
    img.onerror = () => {
      imageLoading.value = false
      ElMessage.error('图片加载失败')
    }
    img.src = getImageUrl(previewFilePath.value)
  }
}

// ========== 双向联动 ==========

// 点击面板中的标注项 → 左侧图片高亮，其他框变暗
function selectBoxFromPanel(index: number) {
  if (selectedBoxIndex.value === index) {
    // 取消选中，恢复所有框原色
    selectedBoxIndex.value = null
    drawAnnotations(null)
    return
  }
  selectedBoxIndex.value = index
  // 选中框高亮，其他框变暗（不闪烁）
  drawAnnotations(index)
}

// 点击 canvas 上的标注框 → 右侧面板滚动高亮
function handleCanvasClick(e: MouseEvent) {
  if (!annotationData.value?.boxes || !cachedDisplayW || !cachedDisplayH) return

  const canvas = previewCanvas.value
  if (!canvas) return

  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height
  const clickX = (e.clientX - rect.left) * scaleX
  const clickY = (e.clientY - rect.top) * scaleY

  // 从后往前遍历，优先选中上层框
  const boxes = annotationData.value.boxes
  for (let i = boxes.length - 1; i >= 0; i--) {
    const box = boxes[i]
    const x = (box.cx - box.w / 2) * cachedDisplayW
    const y = (box.cy - box.h / 2) * cachedDisplayH
    const w = box.w * cachedDisplayW
    const h = box.h * cachedDisplayH

    if (clickX >= x && clickX <= x + w && clickY >= y && clickY <= y + h) {
      selectBoxFromPanel(i)
      // 滚动面板到对应行
      nextTick(() => {
        const el = document.getElementById(`anno-item-${i}`)
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      })
      return
    }
  }
  // 点击空白区域取消选中
  selectedBoxIndex.value = null
  drawAnnotations(null)
}

// 面板搜索/筛选变化时重置选中
watch([panelSearchKeyword, panelCategoryFilter], () => {
  selectedBoxIndex.value = null
  drawAnnotations(null)
})

// 弹框关闭时清理
watch(previewVisible, (val) => {
  if (!val) {
    selectedBoxIndex.value = null
    cachedImage = null
    thinkVisible.value = false
    thinkCollapsed.value = false
    thinkContent.value = ''
    imageLoading.value = false
  }
})

// ========== 质量评分 ==========
const scoreCodeMap: Record<string, string> = { '01': '优质', '02': '良好', '03': '一般', '04': '较差' }
// 星级与编码映射：5星→01优质，4星→02良好，3星→03一般，2星/1星→04较差
const starToCode: Record<number, string> = { 5: '01', 4: '02', 3: '03', 2: '04', 1: '04' }
const codeToStar: Record<string, number> = { '01': 5, '02': 4, '03': 3, '04': 2 }
const starLabels: Record<number, string> = { 5: '优质', 4: '良好', 3: '一般', 2: '较差', 1: '较差' }
const ratingLoading = ref<string | null>(null) // 正在评分的行标识

async function handleRate(row: SampleInfoRow, star: number) {
  const sampleNo = String(row.sampleNo || '')
  const sampleName = String(row.sampleName || '')
  if (!sampleNo || !sampleName) return
  const key = `${sampleNo}_${sampleName}`
  ratingLoading.value = key
  const code = starToCode[star]
  try {
    await updateSampleScore(sampleNo, sampleName, code)
    row.sampleScore = code
    ElMessage.success(`评分成功：${star}星 - ${starLabels[star]}`)
  } catch (e: any) {
    ElMessage.error(e.message || '评分失败')
  } finally {
    ratingLoading.value = null
  }
}

function getScoreStars(score: string | null | undefined): number {
  if (!score) return 0
  return codeToStar[score] || 0
}

function getScoreLabel(score: string | null | undefined): string {
  if (!score) return '未评分'
  return scoreCodeMap[score] || '未评分'
}

onMounted(() => {
  loadSamples()
})
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="样本详情" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="page-header">
          <div class="page-title">
            <h2>
              <span class="back-btn" @click="goBack" title="返回高质量样本管理">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
              </span>
              {{ setName || setNo }}
            </h2>
            <p>样本集编号：{{ setNo }}，共 {{ filteredList.length }} 条样本</p>
          </div>
          <div class="page-actions">
            <div v-if="isImageSet" class="view-toggle">
              <button class="view-btn" :class="{ active: viewMode === 'thumbnail' }" @click="viewMode = 'thumbnail'" title="缩略图视图">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                <span>缩略图</span>
              </button>
              <button class="view-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" title="列表视图">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></svg>
                <span>列表</span>
              </button>
            </div>
            <el-button type="primary" @click="openUploadDialog">上传样本</el-button>
            <el-button v-if="isImageSet" @click="openBatchDialog">批量导入</el-button>
            <el-button v-if="isImageSet" type="success" @click="openExportDialog">导出</el-button>
          </div>
        </div>

        <!-- 导出对话框 -->
        <el-dialog v-model="exportDialogVisible" title="选择导出格式" width="400px" :close-on-click-modal="false">
          <el-radio-group v-model="exportFormat" class="export-radio-group">
            <el-radio :label="'original'">原件（打包下载图片+标注文件）</el-radio>
            <el-radio :label="'json'">JSON（ShareGPT 格式）</el-radio>
          </el-radio-group>
          <template #footer>
            <el-button @click="exportDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="exportLoading" @click="confirmExport">确认导出</el-button>
          </template>
        </el-dialog>

        <!-- 筛选条件 -->
        <div class="filter-bar">
          <div class="filter-item">
            <label>样本名称</label>
            <el-input v-model="filterName" placeholder="输入样本名称" clearable size="default" style="width: 200px" />
          </div>
          <div class="filter-item" v-if="!isTimeSeriesSet">
            <label>标注状态</label>
            <el-select v-model="filterLabelFlag" placeholder="全部" clearable size="default" style="width: 140px">
              <el-option label="已标注" value="已标注" />
              <el-option label="未标注" value="未标注" />
            </el-select>
          </div>
          <div class="filter-item" v-if="isImageSet && classOptions.length > 0">
            <label>标签</label>
            <el-select v-model="filterLabels" placeholder="全部" clearable multiple collapse-tags collapse-tags-tooltip size="default" style="width: 200px">
              <el-option v-for="cls in classOptions" :key="cls" :label="cls" :value="cls" />
            </el-select>
          </div>
          <el-button size="default" @click="resetFilters">重置</el-button>
        </div>

        <!-- 缩略图视图 -->
        <div v-if="isImageSet && viewMode === 'thumbnail'" class="thumbnail-grid" v-loading="loading">
          <div class="thumbnail-card" v-for="(row, idx) in pagedList" :key="idx" @click="openPreview(row)">
            <div class="thumbnail-img-wrap">
              <img v-if="isImageRow(row) && row.filePath" :src="getImageUrl(row.filePath)" :alt="row.sampleName" class="thumbnail-img" />
              <div v-else class="thumbnail-placeholder">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1.5"><path d="M4 16l4.586-4.586a2 2 0 0 1 2.828 0L16 16m-2-2l1.586-1.586a2 2 0 0 1 2.828 0L20 14m-6-6h.01M6 20h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z"/></svg>
              </div>
            </div>
            <div class="thumbnail-name" :title="row.sampleName">{{ row.sampleName }}</div>
            <div class="thumbnail-meta">
              <span class="thumbnail-score" :class="`score-${getScoreStars(row.sampleScore)}`">{{ getScoreLabel(row.sampleScore) }}</span>
              <span class="thumbnail-label-flag">{{ row.labelFlag || '未标注' }}</span>
            </div>
          </div>
          <div v-if="pagedList.length === 0 && !loading" class="empty-state">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1"><path d="M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z"/></svg>
            <p>暂无样本数据</p>
          </div>
        </div>

        <!-- 列表视图 -->
        <div class="table-wrapper" v-if="!isImageSet || viewMode === 'list'" v-loading="loading">
          <table v-if="pagedList.length > 0" class="sample-table">
            <thead>
              <tr>
                <th class="col-index">#</th>
                <th v-for="col in columns" :key="col.key" v-show="!hiddenColumns.has(col.key)">{{ col.label }}</th>
                <th v-if="!isTimeSeriesSet" class="col-score">质量评分</th>
                <th v-if="isTimeSeriesSet" class="col-action">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in pagedList" :key="idx">
                <td class="col-index">{{ (currentPage - 1) * pageSize + idx + 1 }}</td>
                <td v-for="col in columns" :key="col.key" v-show="!hiddenColumns.has(col.key)">
                  <template v-if="col.key === 'sampleName' && isPreviewable(row)">
                    <span class="link-name" @click="openPreview(row)">{{ row[col.key] ?? '-' }}</span>
                  </template>
                  <template v-else>{{ row[col.key] ?? '-' }}</template>
                </td>
                <td v-if="!isTimeSeriesSet" class="col-score">
                  <div class="star-rating">
                    <span
                      v-for="star in 5"
                      :key="star"
                      class="star-item"
                      :class="{ active: star <= getScoreStars(row.sampleScore), loading: ratingLoading === `${row.sampleNo}_${row.sampleName}` }"
                      @click="handleRate(row, star)"
                      :title="`${star}星 - ${starLabels[star]}`"
                    >★</span>
                    <span class="score-label" :class="`score-${getScoreStars(row.sampleScore)}`">{{ getScoreLabel(row.sampleScore) }}</span>
                  </div>
                </td>
                <td v-if="isTimeSeriesSet" class="col-action">
                  <el-button size="small" @click="handleViewTimeSeries(row)">查看</el-button>
                  <el-button size="small" @click="handleDownloadTimeSeries(row)">下载</el-button>
                </td>
              </tr>
            </tbody>
          </table>

          <div v-else-if="!loading" class="empty-state">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1">
              <path d="M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z"/>
            </svg>
            <p>暂无样本数据</p>
          </div>
        </div>

        <!-- 分页 -->
        <div class="pagination-bar" v-if="totalPages > 1">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="filteredList.length"
            layout="prev, pager, next, total"
            background
            @current-change="handlePageChange"
          />
        </div>
      </main>
    </div>

    <!-- 上传样本弹框 -->
    <el-dialog v-model="uploadDialogVisible" title="上传样本" width="520px" :close-on-click-modal="false" class="upload-dialog">
      <div class="upload-dialog-content">
        <div class="upload-info-row">
          <span class="upload-info-label">样本集：</span>
          <span class="upload-info-value">{{ setName }}</span>
        </div>
        <div class="upload-info-row">
          <span class="upload-info-label">允许格式：</span>
          <span class="upload-info-value">{{ typeCode === '05' ? '图像文件（jpg/png/bmp等）' : typeCode === '02' ? '文本文件（txt/csv/doc等）' : typeCode === '03' ? '音频文件（mp3/wav等）' : typeCode === '04' ? '视频文件（mp4/avi等）' : '不限' }}</span>
        </div>
        <el-upload
          :accept="typeCodeToAccept[typeCode] || ''"
          :auto-upload="false"
          :file-list="uploadDisplayList"
          :on-change="handleUploadFileChange"
          :on-remove="handleUploadFileRemove"
          multiple
          drag
        >
          <div class="upload-drag-content">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.5)" stroke-width="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
            </svg>
            <p>将文件拖到此处，或<em>点击上传</em></p>
            <p class="upload-tip">图片类型可同时选择图片和同名txt标注文件</p>
          </div>
        </el-upload>
      </div>
      <template #footer>
        <el-button type="primary" :loading="uploadSaving" @click="handleUploadConfirm">确认上传</el-button>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹框（分片上传，仅图片类型） -->
    <ChunkUploadDialog
      v-model="batchDialogVisible"
      :setNo="setNo"
      :setName="setName"
      :typeCode="typeCode"
      source="sample"
      title="批量导入（ZIP 分片上传）"
      description="上传 ZIP，自动分片上传并解压图片；同名 .txt 标注和 classes.txt 内容将写入数据库"
      @success="handleBatchUploadSuccess"
    />

    <!-- 文件预览弹框 -->
    <el-dialog v-model="previewVisible" :title="previewName || '文件预览'" width="90vw" :close-on-click-modal="true" class="preview-dialog" destroy-on-close top="3vh">
      <div class="preview-container" v-loading="previewLoading || imageLoading" :element-loading-text="previewLoadingText">
        <!-- 图片预览 - 分栏布局 -->
        <template v-if="previewType === 'image' && !previewLoading">
          <template v-if="annotationData?.hasAnnotations">
            <div class="split-layout">
              <!-- 左侧：上方图片 + 下方思维链 -->
              <div class="split-left">
                <!-- 上方：图片预览区 -->
                <div class="split-left-image">
                  <div class="canvas-scroll">
                    <canvas ref="previewCanvas" class="preview-canvas" @click="handleCanvasClick"></canvas>
                  </div>
                </div>
                <!-- 下方：思维链框 -->
                <div v-if="thinkVisible" class="think-box" :class="{ collapsed: thinkCollapsed }">
                  <div class="think-header" @click="toggleThinkCollapse">
                    <span class="think-title">思维链</span>
                    <span class="think-toggle-icon">
                      <svg v-if="thinkCollapsed" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
                      <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 15l-6-6-6 6"/></svg>
                    </span>
                  </div>
                  <template v-if="!thinkCollapsed">
                    <div class="think-resize-handle" @mousedown="startThinkResize"></div>
                    <div class="think-body" :style="{ height: thinkHeight + 'px' }">
                      <textarea v-model="thinkContent" class="think-textarea" placeholder="请输入思维链内容..."></textarea>
                      <div class="think-footer">
                        <el-button type="primary" size="small" :loading="thinkSaving" @click="handleSaveThink">保存</el-button>
                      </div>
                    </div>
                  </template>
                </div>
              </div>
              <!-- 右侧：标注信息面板 -->
              <div class="split-right">
                <div class="anno-panel">
                  <!-- 面板头部：搜索和筛选 -->
                  <div class="anno-panel-header">
                    <div class="anno-panel-title">标注信息</div>
                    <div class="anno-panel-filters">
                      <el-input
                        v-model="panelSearchKeyword"
                        placeholder="搜索标签"
                        clearable
                        size="small"
                        class="anno-search"
                      >
                        <template #prefix>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
                        </template>
                      </el-input>
                      <el-select
                        v-model="panelCategoryFilter"
                        placeholder="类别筛选"
                        clearable
                        size="small"
                        class="anno-category-select"
                      >
                        <el-option
                          v-for="cat in categoryOptions"
                          :key="cat"
                          :label="cat"
                          :value="cat"
                        />
                      </el-select>
                    </div>
                  </div>

                  <!-- 标注列表 -->
                  <div class="anno-list">
                    <div
                      v-for="box in filteredBoxes"
                      :key="box._index"
                      :id="`anno-item-${box._index}`"
                      class="anno-item"
                      :class="{ 'anno-item-active': selectedBoxIndex === box._index }"
                      @click="selectBoxFromPanel(box._index)"
                    >
                      <div class="anno-item-top">
                        <span class="anno-color-dot" :style="{ backgroundColor: boxColors[box.classId % boxColors.length] }"></span>
                        <span class="anno-label-name">{{ box.className }}</span>
                        <span class="anno-index">#{{ box._index + 1 }}</span>
                      </div>
                      <div class="anno-item-detail">
                        <span class="anno-detail-item">
                          <span class="anno-detail-label">位置</span>
                          <span class="anno-detail-value">x:{{ ((box.cx - box.w / 2) * 100).toFixed(1) }} y:{{ ((box.cy - box.h / 2) * 100).toFixed(1) }}</span>
                        </span>
                        <span class="anno-detail-item">
                          <span class="anno-detail-label">尺寸</span>
                          <span class="anno-detail-value">{{ (box.w * 100).toFixed(1) }}×{{ (box.h * 100).toFixed(1) }}</span>
                        </span>
                      </div>
                    </div>
                    <div v-if="filteredBoxes.length === 0" class="anno-empty">
                      无匹配标注
                    </div>
                  </div>

                  <!-- 面板底部统计 -->
                  <div class="anno-panel-footer">
                    <div class="anno-stat-total">共 {{ annotationData.boxes.length }} 个标注</div>
                    <div class="anno-stat-categories">
                      <span v-for="stat in categoryStats" :key="stat.name" class="anno-stat-tag">
                        {{ stat.name }}: {{ stat.count }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <template v-else>
            <div class="split-layout">
              <!-- 左侧：上方图片 + 下方思维链 -->
              <div class="split-left">
                <div class="split-left-image">
                  <img :src="getImageUrl(previewFilePath)" class="preview-img" @load="imageLoading = false" @error="() => { imageLoading = false; ElMessage.error('图片加载失败') }" />
                </div>
                <div v-if="thinkVisible" class="think-box" :class="{ collapsed: thinkCollapsed }">
                  <div class="think-header" @click="toggleThinkCollapse">
                    <span class="think-title">思维链</span>
                    <span class="think-toggle-icon">
                      <svg v-if="thinkCollapsed" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
                      <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 15l-6-6-6 6"/></svg>
                    </span>
                  </div>
                  <template v-if="!thinkCollapsed">
                    <div class="think-resize-handle" @mousedown="startThinkResize"></div>
                    <div class="think-body" :style="{ height: thinkHeight + 'px' }">
                      <textarea v-model="thinkContent" class="think-textarea" placeholder="请输入思维链内容..."></textarea>
                      <div class="think-footer">
                        <el-button type="primary" size="small" :loading="thinkSaving" @click="handleSaveThink">保存</el-button>
                      </div>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </template>
        </template>
        <!-- 音频播放 -->
        <template v-if="previewType === 'audio'">
          <div class="audio-player-wrapper">
            <div class="audio-icon">
              <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="1.5">
                <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
              </svg>
            </div>
            <div class="audio-name">{{ previewName }}</div>

            <!-- 自定义播放器 -->
            <div class="audio-player">
              <audio
                ref="audioRef"
                :src="getImageUrl(previewFilePath)"
                @loadedmetadata="onAudioLoaded"
                @timeupdate="onAudioTimeUpdate"
                @ended="onAudioEnded"
                preload="metadata"
                style="display:none"
              ></audio>

              <!-- 进度条 -->
              <div class="audio-progress-bar" @click="seekAudio">
                <div class="audio-progress-fill" :style="{ width: audioDuration ? (audioCurrentTime / audioDuration * 100) + '%' : '0%' }"></div>
                <div class="audio-progress-thumb" :style="{ left: audioDuration ? (audioCurrentTime / audioDuration * 100) + '%' : '0%' }"></div>
              </div>

              <!-- 时间和控制 -->
              <div class="audio-controls-row">
                <span class="audio-time">{{ formatTime(audioCurrentTime) }} / {{ formatTime(audioDuration) }}</span>
                <div class="audio-btn-group">
                  <button class="audio-ctrl-btn" @click="toggleAudioPlay" :title="audioPlaying ? '暂停' : '播放'">
                    <svg v-if="!audioPlaying" width="20" height="20" viewBox="0 0 24 24" fill="#00d4ff"><polygon points="5,3 19,12 5,21"/></svg>
                    <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="#00d4ff"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                  </button>
                </div>
                <!-- 倍速 -->
                <div class="audio-speed-group">
                  <button
                    v-for="rate in playbackRates"
                    :key="rate"
                    class="audio-speed-btn"
                    :class="{ 'audio-speed-active': audioPlaybackRate === rate }"
                    @click="setPlaybackRate(rate)"
                  >{{ rate }}x</button>
                </div>
                <!-- 下载 -->
                <button class="audio-ctrl-btn audio-download-btn" @click="downloadAudio" title="下载">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </button>
              </div>
            </div>

            <!-- 技术参数 -->
            <div class="audio-tech-info">
              <div class="audio-tech-item">
                <span class="audio-tech-label">时长</span>
                <span class="audio-tech-value">{{ formatTime(audioDuration) }}</span>
              </div>
              <div class="audio-tech-item">
                <span class="audio-tech-label">采样率</span>
                <span class="audio-tech-value">{{ audioSampleRate ? audioSampleRate + ' Hz' : '-' }}</span>
              </div>
              <div class="audio-tech-item">
                <span class="audio-tech-label">声道数</span>
                <span class="audio-tech-value">{{ audioChannels ?? '-' }}</span>
              </div>
            </div>

            <!-- 转写文字 -->
            <div class="audio-transcription" v-if="audioText">
              <div class="audio-transcription-title">转写文字</div>
              <div class="audio-transcription-text">{{ audioText }}</div>
            </div>
          </div>
        </template>
      </div>
    </el-dialog>

    <!-- 时序类型查看弹框 -->
    <el-dialog v-model="tsViewVisible" :title="`数据查看 - ${tsViewSampleName}`" width="90%" top="5vh" :close-on-click-modal="false" class="preview-dialog" destroy-on-close>
      <div v-if="tsViewLoading" style="text-align:center;padding:60px;color:rgba(255,255,255,0.5)">加载中...</div>
      <div v-else-if="tsViewData" class="ts-view-content">
        <div class="ts-view-summary">
          <span>任务编号：<b>{{ tsViewData.taskNo }}</b></span>
          <span>执行时间：<b>{{ tsViewData.executeTime }}</b></span>
          <span>原始数据：<b>{{ tsViewData.totalCount }}</b> 条</span>
          <span>移除重复：<b>{{ tsViewData.removedCount }}</b> 条</span>
          <span>结果数据：<b style="color:#00ff88">{{ tsViewData.resultCount }}</b> 条</span>
        </div>
        <div class="ts-view-table-wrap">
          <table class="ts-view-table">
            <thead>
              <tr>
                <th class="th-index">#</th>
                <th v-for="col in tsViewData.columns" :key="col">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in tsViewPagedRows" :key="idx">
                <td class="td-index">{{ (tsViewCurrentPage - 1) * tsViewPageSize + idx + 1 }}</td>
                <td v-for="col in tsViewData.columns" :key="col" :title="String(row[col] ?? '')">{{ row[col] ?? '' }}</td>
              </tr>
              <tr v-if="tsViewPagedRows.length === 0">
                <td :colspan="tsViewData.columns.length + 1" class="td-empty">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="ts-view-pagination" v-if="tsViewData.rows.length > tsViewPageSize">
          <el-pagination
            v-model:current-page="tsViewCurrentPage"
            :page-size="tsViewPageSize"
            :total="tsViewData.rows.length"
            layout="prev, pager, next"
            background
          />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 20px 24px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
}

.export-radio-group {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px 8px;
}

.export-radio-group .el-radio {
  margin-right: 0;
}

.page-title h2 {
  font-size: 22px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 8px 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-title p {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.view-toggle {
  display: flex;
  gap: 2px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  padding: 2px;
}

.view-btn {
  background: transparent;
  border: none;
  border-radius: 6px;
  padding: 6px 10px;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  white-space: nowrap;

  &.active {
    background: rgba(0, 212, 255, 0.15);
    color: #00d4ff;
  }

  &:hover {
    color: #00d4ff;
  }
}

.back-btn {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.6);
  transition: color 0.2s;
  &:hover {
    color: #00d4ff;
  }
}

// ========== 缩略图视图 ==========
.thumbnail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
  padding: 16px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  min-height: 200px;
}

.thumbnail-card {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.25s;

  &:hover {
    border-color: rgba(0, 212, 255, 0.5);
    box-shadow: 0 4px 16px rgba(0, 212, 255, 0.12);
    transform: translateY(-2px);
  }
}

.thumbnail-img-wrap {
  width: 100%;
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.thumbnail-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;

  .thumbnail-card:hover & {
    transform: scale(1.05);
  }
}

.thumbnail-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.thumbnail-name {
  padding: 8px 10px 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thumbnail-meta {
  padding: 0 10px 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.thumbnail-score {
  font-size: 11px;
  font-weight: 600;

  &.score-1, &.score-2 { color: #f56c6c; }
  &.score-3 { color: #e6a23c; }
  &.score-4 { color: #67c23a; }
  &.score-5 { color: #00d4ff; }
  &.score-0 { color: rgba(255, 255, 255, 0.3); }
}

.thumbnail-label-flag {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.table-wrapper {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  overflow: auto;
}

.sample-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;

  thead {
    background: rgba(0, 212, 255, 0.08);
    position: sticky;
    top: 0;
    z-index: 1;
  }

  th {
    padding: 12px 16px;
    text-align: left;
    color: rgba(255, 255, 255, 0.65);
    font-weight: 600;
    border-bottom: 1px solid rgba(0, 212, 255, 0.15);
    white-space: nowrap;
  }

  td {
    padding: 10px 16px;
    color: rgba(255, 255, 255, 0.8);
    border-bottom: 1px solid rgba(0, 212, 255, 0.08);
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  tbody tr {
    transition: background 0.2s;
    &:hover {
      background: rgba(0, 212, 255, 0.06);
    }
  }

  .col-index {
    width: 50px;
    text-align: center;
    color: rgba(255, 255, 255, 0.4);
  }

  .col-score {
    min-width: 180px;
  }
}

// ========== 质量评分 ==========
.star-rating {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.star-item {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.2);
  cursor: pointer;
  transition: color 0.15s, transform 0.15s;
  user-select: none;
  line-height: 1;

  &:hover {
    transform: scale(1.2);
  }

  &.active {
    color: #f5a623;
  }

  &.loading {
    pointer-events: none;
    opacity: 0.5;
  }
}

.score-label {
  margin-left: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);

  &.score-1, &.score-2 {
    color: #f56c6c;
  }
  &.score-3 {
    color: #e6a23c;
  }
  &.score-4 {
    color: #67c23a;
  }
  &.score-5 {
    color: #00d4ff;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 16px;

  p {
    font-size: 16px;
    color: rgba(255, 255, 255, 0.4);
    margin: 0;
  }
}

.link-name {
  color: #00d4ff;
  cursor: pointer;
  &:hover {
    color: #66e0ff;
  }
}

.audio-player-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 20px;
  gap: 20px;
  width: 100%;
  max-width: 600px;
  margin: 0 auto;

  .audio-icon {
    opacity: 0.8;
  }

  .audio-name {
    font-size: 16px;
    color: rgba(255, 255, 255, 0.8);
    text-align: center;
  }
}

// ========== 自定义音频播放器 ==========
.audio-player {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.audio-progress-bar {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  cursor: pointer;
  position: relative;

  &:hover {
    height: 8px;

    .audio-progress-thumb {
      width: 14px;
      height: 14px;
      margin-left: -7px;
      margin-top: -3px;
    }
  }
}

.audio-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #00d4ff, #00ff88);
  border-radius: 3px;
  transition: width 0.1s linear;
}

.audio-progress-thumb {
  position: absolute;
  top: 50%;
  width: 12px;
  height: 12px;
  background: #00d4ff;
  border: 2px solid #fff;
  border-radius: 50%;
  transform: translateY(-50%);
  margin-left: -6px;
  transition: width 0.15s, height 0.15s;
  box-shadow: 0 0 6px rgba(0, 212, 255, 0.5);
}

.audio-controls-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.audio-time {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  font-family: 'Consolas', 'Monaco', monospace;
  min-width: 80px;
}

.audio-btn-group {
  display: flex;
  align-items: center;
}

.audio-ctrl-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(0, 212, 255, 0.3);
  border-radius: 8px;
  background: rgba(0, 212, 255, 0.08);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: rgba(0, 212, 255, 0.15);
    border-color: rgba(0, 212, 255, 0.5);
  }
}

.audio-speed-group {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.audio-speed-btn {
  padding: 4px 8px;
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 4px;
  background: transparent;
  color: rgba(255, 255, 255, 0.5);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: rgba(0, 212, 255, 0.08);
    color: rgba(255, 255, 255, 0.8);
  }

  &.audio-speed-active {
    background: rgba(0, 212, 255, 0.2);
    border-color: rgba(0, 212, 255, 0.5);
    color: #00d4ff;
    font-weight: 600;
  }
}

.audio-download-btn {
  margin-left: 4px;
}

// ========== 音频技术参数 ==========
.audio-tech-info {
  display: flex;
  gap: 24px;
  padding: 14px 20px;
  background: rgba(0, 212, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.12);
  border-radius: 8px;
  width: 100%;
}

.audio-tech-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.audio-tech-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.audio-tech-value {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  font-family: 'Consolas', 'Monaco', monospace;
}

// ========== 转写文字 ==========
.audio-transcription {
  width: 100%;
  padding: 14px 20px;
  background: rgba(0, 212, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.12);
  border-radius: 8px;
}

.audio-transcription-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 8px;
}

.audio-transcription-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.8;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding: 14px 20px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;

  .filter-item {
    display: flex;
    align-items: center;
    gap: 8px;

    label {
      color: rgba(255, 255, 255, 0.65);
      font-size: 13px;
      white-space: nowrap;
    }
  }
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding: 12px 20px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
}
</style>

<style lang="scss">
// 分页深色主题
.el-pagination {
  --el-pagination-bg-color: rgba(0, 212, 255, 0.1);
  --el-pagination-text-color: rgba(255, 255, 255, 0.7);
  --el-pagination-button-bg-color: rgba(0, 212, 255, 0.1);
  --el-pagination-hover-color: #00d4ff;

  .el-pager li {
    background: rgba(0, 212, 255, 0.1) !important;
    color: rgba(255, 255, 255, 0.7) !important;
    &.is-active {
      background: rgba(0, 212, 255, 0.3) !important;
      color: #00d4ff !important;
    }
    &:hover {
      color: #00d4ff !important;
    }
  }

  .btn-prev, .btn-next {
    background: rgba(0, 212, 255, 0.1) !important;
    color: rgba(255, 255, 255, 0.7) !important;
  }

  .el-pagination__total {
    color: rgba(255, 255, 255, 0.5) !important;
  }
}

.preview-dialog.el-dialog {
  background: transparent !important;
  border: none !important;
  border-radius: 12px !important;
  overflow: hidden;
  margin: 0 !important;
  box-shadow: none !important;
  --el-dialog-bg-color: transparent;
  --el-dialog-padding-primary: 0;
}

.preview-dialog.el-dialog .el-dialog__header {
  border-bottom: 1px solid rgba(255, 255, 255, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-bottom: none;
  padding: 10px 16px;
  margin-right: 0;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.98) 0%, rgba(26, 35, 50, 0.95) 100%) !important;
  border-radius: 12px 12px 0 0 !important;
}

.preview-dialog.el-dialog .el-dialog__title {
  color: #fff !important;
  font-weight: 600;
  font-size: 15px;
}

.preview-dialog.el-dialog .el-dialog__headerbtn .el-dialog__close {
  color: rgba(255, 255, 255, 0.5) !important;
}

.preview-dialog.el-dialog .el-dialog__headerbtn:hover .el-dialog__close {
  color: #00d4ff !important;
}

.preview-dialog.el-dialog .el-dialog__body {
  padding: 8px 10px;
  color: rgba(255, 255, 255, 0.85) !important;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.98) 0%, rgba(26, 35, 50, 0.95) 100%) !important;
  border: 1px solid rgba(255, 255, 255, 0.4) !important;
  border-top: none !important;
  border-radius: 0 0 12px 12px !important;
}
</style>

<!-- 全局样式：覆盖 el-dialog overlay 的默认间距，消除白框 -->
<style lang="scss">
.el-overlay-dialog:has(.preview-dialog) {
  padding: 3vh 0 0 !important;
  display: flex !important;
  justify-content: center !important;
  align-items: flex-start !important;
}

// 上传弹框暗色主题
.el-dialog.upload-dialog {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.98) 0%, rgba(26, 35, 50, 0.95) 100%) !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;
  border-radius: 12px !important;

  --el-text-color-regular: rgba(255, 255, 255, 0.85);
  --el-text-color-primary: #fff;
  --el-text-color-placeholder: rgba(255, 255, 255, 0.3);
  --el-fill-color-blank: rgba(255, 255, 255, 0.05);
  --el-fill-color-light: rgba(255, 255, 255, 0.05);
  --el-border-color: rgba(0, 212, 255, 0.2);
  --el-bg-color: rgba(17, 24, 39, 0.98);
  --el-bg-color-overlay: rgba(17, 24, 39, 0.98);
  --el-color-primary: #00d4ff;

  .el-dialog__header {
    border-bottom: 1px solid rgba(0, 212, 255, 0.15);
    padding: 16px 20px;
    margin-right: 0;
  }

  .el-dialog__title {
    color: #fff !important;
    font-weight: 600;
  }

  .el-dialog__headerbtn .el-dialog__close {
    color: rgba(255, 255, 255, 0.5) !important;
  }

  .el-dialog__headerbtn:hover .el-dialog__close {
    color: #00d4ff !important;
  }

  .el-dialog__body {
    padding: 24px 20px;
    color: rgba(255, 255, 255, 0.85) !important;
  }

  .el-dialog__footer {
    border-top: 1px solid rgba(0, 212, 255, 0.15);
    padding: 12px 20px;
  }

  .el-upload {
    width: 100%;
  }

  .el-upload-dragger {
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px dashed rgba(0, 212, 255, 0.3) !important;
    &:hover {
      border-color: #00d4ff !important;
    }
  }

  .el-upload-list__item {
    color: rgba(255, 255, 255, 0.85) !important;
    &:hover {
      background: rgba(0, 212, 255, 0.08) !important;
    }
  }

  .el-upload-list__item-name {
    color: rgba(255, 255, 255, 0.85) !important;
  }

  .el-button--default {
    background: rgba(255, 255, 255, 0.05) !important;
    border-color: rgba(0, 212, 255, 0.3) !important;
    color: rgba(255, 255, 255, 0.7) !important;
    &:hover {
      border-color: #00d4ff !important;
      color: #00d4ff !important;
    }
  }
}
</style>

<style scoped lang="scss">
.preview-container {
  display: flex;
  justify-content: center;
  align-items: stretch;
  min-height: 200px;
}

.preview-img {
  max-width: 100%;
  max-height: 100%;
  border-radius: 8px;
  object-fit: contain;
}

// ========== 分栏布局 ==========
.split-layout {
  display: flex;
  width: 100%;
  height: 82vh;
  gap: 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(0, 212, 255, 0.15);
}

.split-left {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: rgba(0, 0, 0, 0.3);
  overflow: hidden;

  .split-left-image {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .canvas-scroll {
    width: 100%;
    height: 100%;
    overflow: auto;
    display: flex;
    align-items: center;
    justify-content: center;

    & > canvas {
      flex-shrink: 0;
      cursor: pointer;
    }
  }
}

.preview-canvas {
  display: block;
}

// ========== 思维链框 ==========
.think-box {
  flex-shrink: 0;
  background: rgba(17, 24, 39, 0.95);
  border-top: 1px solid rgba(0, 212, 255, 0.25);
  display: flex;
  flex-direction: column;

  &.collapsed {
    .think-header {
      border-bottom: none;
    }
  }
}

.think-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  cursor: pointer;
  border-bottom: 1px solid rgba(0, 212, 255, 0.12);
  user-select: none;
  transition: background 0.2s;

  &:hover {
    background: rgba(0, 212, 255, 0.05);
  }
}

.think-title {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
}

.think-toggle-icon {
  display: flex;
  align-items: center;
  color: rgba(255, 255, 255, 0.5);
  transition: color 0.2s;

  .think-header:hover & {
    color: #00d4ff;
  }
}

.think-resize-handle {
  height: 4px;
  background: rgba(0, 212, 255, 0.15);
  cursor: ns-resize;
  transition: background 0.2s;

  &:hover {
    background: rgba(0, 212, 255, 0.4);
  }
}

.think-body {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.think-textarea {
  flex: 1;
  width: 100%;
  resize: none;
  border: none;
  outline: none;
  padding: 12px 14px;
  background: rgba(0, 0, 0, 0.3);
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  font-family: 'Consolas', 'Monaco', monospace;
  line-height: 1.6;
  overflow-y: auto;

  &::placeholder {
    color: rgba(255, 255, 255, 0.25);
  }

  &:focus {
    background: rgba(0, 0, 0, 0.4);
  }
}

.think-footer {
  display: flex;
  justify-content: flex-end;
  padding: 8px 14px;
  border-top: 1px solid rgba(0, 212, 255, 0.12);
  flex-shrink: 0;
}

.split-right {
  width: 340px;
  flex-shrink: 0;
  background: rgba(17, 24, 39, 0.95);
  border-left: 1px solid rgba(0, 212, 255, 0.15);
  display: flex;
  flex-direction: column;
}

// ========== 标注信息面板 ==========
.anno-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.anno-panel-header {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.12);
  flex-shrink: 0;
}

.anno-panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 10px;
}

.anno-panel-filters {
  display: flex;
  gap: 8px;

  .anno-search {
    flex: 1;
  }

  .anno-category-select {
    width: 120px;
  }
}

// 标注列表
.anno-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
}

.anno-item {
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 1px solid rgba(0, 212, 255, 0.06);
  transition: background 0.2s;

  &:hover {
    background: rgba(0, 212, 255, 0.06);
  }

  &.anno-item-active {
    background: rgba(0, 212, 255, 0.12);
    border-left: 3px solid #00d4ff;
    padding-left: 11px;
  }
}

.anno-item-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.anno-color-dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}

.anno-label-name {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.anno-index {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  flex-shrink: 0;
}

.anno-item-detail {
  display: flex;
  gap: 16px;
  padding-left: 18px;
}

.anno-detail-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.anno-detail-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.anno-detail-value {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.65);
  font-family: 'Consolas', 'Monaco', monospace;
}

.anno-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.35);
}

// 面板底部统计
.anno-panel-footer {
  padding: 10px 14px;
  border-top: 1px solid rgba(0, 212, 255, 0.12);
  flex-shrink: 0;
}

.anno-stat-total {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 6px;
}

.anno-stat-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.anno-stat-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.2);
  color: rgba(255, 255, 255, 0.7);
}

// ========== 上传弹框 ==========
.upload-dialog-content {
  .upload-info-row {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
    font-size: 14px;
  }
  .upload-info-label {
    color: rgba(255, 255, 255, 0.5);
    width: 80px;
    flex-shrink: 0;
  }
  .upload-info-value {
    color: rgba(255, 255, 255, 0.85);
  }
  .upload-drag-content {
    text-align: center;
    padding: 20px 0;
    p {
      margin: 8px 0 0;
      color: rgba(255, 255, 255, 0.5);
      font-size: 14px;
      em {
        color: #00d4ff;
        font-style: normal;
      }
    }
    .upload-tip {
      font-size: 12px;
      color: rgba(255, 255, 255, 0.3);
    }
  }
  .batch-version-row {
    margin-top: 16px;
    padding-left: 0;
  }
  .batch-remark-row {
    margin-top: 12px;
  }
  .batch-remark-label {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.7);
    margin-bottom: 6px;
  }
  .batch-remark-tip {
    color: rgba(255, 255, 255, 0.4);
    font-size: 12px;
  }
}

// ========== 时序类型查看弹框 ==========
.ts-view-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ts-view-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  padding: 14px 20px;
  background: rgba(0, 212, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.12);
  border-radius: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);

  b {
    color: #e6edf3;
  }
}

.ts-view-table-wrap {
  max-height: 60vh;
  overflow: auto;
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
}

.ts-view-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;

  thead th {
    position: sticky;
    top: 0;
    z-index: 10;
    background: #0d2137;
    border-bottom: 2px solid rgba(0, 212, 255, 0.6);
  }

  th, td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid rgba(0, 212, 255, 0.08);
    white-space: nowrap;
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  th {
    color: rgba(255, 255, 255, 0.85);
    font-weight: 600;
  }

  td {
    color: rgba(255, 255, 255, 0.8);
    background: transparent;
  }

  .th-index, .td-index {
    width: 50px;
    text-align: center;
    color: rgba(255, 255, 255, 0.4);
  }

  .td-empty {
    text-align: center;
    padding: 40px;
    color: rgba(255, 255, 255, 0.35);
  }

  tbody tr:hover td {
    background: rgba(0, 212, 255, 0.06);
  }
}

.ts-view-pagination {
  display: flex;
  justify-content: flex-end;
}

.col-action {
  min-width: 140px;
}
</style>
