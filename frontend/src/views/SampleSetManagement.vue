<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getCodeDict, saveSampleSet, querySampleSet, type CodeDictItem } from '@/api/sample'
import { ElMessage, ElLoading } from 'element-plus'

type ViewMode = 'card' | 'list'
type SortField = 'updateTime' | 'scale' | 'quality' | 'popularity'
type SortOrder = 'asc' | 'desc'

interface SampleSet {
  id: number
  setNo: string
  name: string
  modality: string[]
  updateTime: string
  qualityLevel: string
  version: string
  popularity: number
  scale: number
  businessSystem: string
  fieldCode: string
  setDescription: string
  _fromDb?: boolean
}

const router = useRouter()

const modalityOptions = ref<{ value: string; label: string }[]>([])
const qualityOptions = ref<{ value: string; label: string }[]>([])
const fieldOptions = ref<{ value: string; label: string }[]>([])
const dictLoading = ref(false)

const defaultModalityOptions = [
  { value: 'text', label: '文本' },
  { value: 'image', label: '图片' },
  { value: 'audio', label: '语音' },
  { value: 'video', label: '视频' }
]

const defaultQualityOptions = [
  { value: '01', label: '优质' },
  { value: '02', label: '良好' },
  { value: '03', label: '一般' },
  { value: '04', label: '较差' }
]

const scaleOptions = [
  { value: 'small', label: '小型 (<1万)' },
  { value: 'medium', label: '中型 (1万-10万)' },
  { value: 'large', label: '大型 (10万-100万)' },
  { value: 'massive', label: '超大型 (>100万)' }
]

const sortOptions: { value: SortField; label: string }[] = [
  { value: 'updateTime', label: '更新时间' },
  { value: 'scale', label: '样本规模' },
  { value: 'quality', label: '质量等级' },
  { value: 'popularity', label: '热度' }
]

const sampleSets = ref<SampleSet[]>([
  { id: 1, setNo: 'SAMPLE-001', name: '线损异常诊断样本集', modality: ['text'], updateTime: '2026-05-28', qualityLevel: '01', version: 'v3.2', popularity: 342, scale: 2865, businessSystem: '线损诊断', fieldCode: '', setDescription: '线损异常诊断文本数据集' },
  { id: 2, setNo: 'SAMPLE-002', name: '采集异常识别样本集', modality: ['text'], updateTime: '2026-05-27', qualityLevel: '01', version: 'v2.8', popularity: 289, scale: 3215, businessSystem: '采集异常', fieldCode: '', setDescription: '采集运维异常识别专用文本数据集' },
  { id: 3, setNo: 'SAMPLE-003', name: '电能表故障识别样本集', modality: ['image'], updateTime: '2026-05-26', qualityLevel: '01', version: 'v4.1', popularity: 256, scale: 1542, businessSystem: '电能表', fieldCode: '', setDescription: '电能表外观及内部故障图像样本集' },
  { id: 4, setNo: 'SAMPLE-004', name: '负荷预测样本集', modality: ['text'], updateTime: '2026-05-25', qualityLevel: '02', version: 'v2.5', popularity: 198, scale: 4354, businessSystem: '负荷预测', fieldCode: '', setDescription: '中长期负荷预测训练文本样本' },
  { id: 5, setNo: 'SAMPLE-005', name: '作业风险识别样本集', modality: ['image'], updateTime: '2026-05-24', qualityLevel: '02', version: 'v1.9', popularity: 176, scale: 8632, businessSystem: '作业安全', fieldCode: '', setDescription: '现场作业风险场景图像集' },
  { id: 6, setNo: 'SAMPLE-006', name: '市场交易预测样本集', modality: ['text'], updateTime: '2026-05-23', qualityLevel: '02', version: 'v2.1', popularity: 145, scale: 2641, businessSystem: '市场交易', fieldCode: '', setDescription: '电力市场交易及价格预测文本数据' },
  { id: 7, setNo: 'SAMPLE-007', name: '低电压诊断样本集', modality: ['image'], updateTime: '2026-05-22', qualityLevel: '03', version: 'v1.3', popularity: 112, scale: 5420, businessSystem: '低电压', fieldCode: '', setDescription: '配电网低电压问题诊断图像样本' },
  { id: 8, setNo: 'SAMPLE-008', name: '谐波分析样本集', modality: ['audio'], updateTime: '2026-05-21', qualityLevel: '03', version: 'v1.1', popularity: 87, scale: 750, businessSystem: '谐波分析', fieldCode: '', setDescription: '电力谐波信号音频数据集' },
  { id: 9, setNo: 'SAMPLE-009', name: '故障录波识别样本集', modality: ['image'], updateTime: '2026-05-20', qualityLevel: '02', version: 'v2.0', popularity: 203, scale: 1300, businessSystem: '故障识别', fieldCode: '', setDescription: '电网故障录波图像样本' },
  { id: 10, setNo: 'SAMPLE-010', name: '巡检视频分析样本集', modality: ['video'], updateTime: '2026-05-19', qualityLevel: '04', version: 'v1.0', popularity: 64, scale: 800, businessSystem: '设备缺陷', fieldCode: '', setDescription: '变电站巡检视频及标注数据' },
  { id: 11, setNo: 'SAMPLE-011', name: '计量异常语音报工样本集', modality: ['audio'], updateTime: '2026-05-18', qualityLevel: '03', version: 'v1.2', popularity: 53, scale: 410, businessSystem: '计量异常', fieldCode: '', setDescription: '计量异常现场语音报工记录数据' },
  { id: 12, setNo: 'SAMPLE-012', name: '综合能源调度样本集', modality: ['video'], updateTime: '2026-05-17', qualityLevel: '01', version: 'v3.0', popularity: 318, scale: 9100, businessSystem: '市场交易', fieldCode: '', setDescription: '综合能源系统调度优化视频数据集' }
])

const viewMode = ref<ViewMode>('card')
const sortOrder = ref<SortOrder>('desc')
const sortField = ref<SortField>('updateTime')

const filterName = ref('')
const filterModality = ref<string[]>([])
const filterQuality = ref<string[]>([])
const filterField = ref<string[]>([])
const filterScale = ref<string[]>([])
const filterTagsText = ref('')
const filterUpdateTime = ref('')

const modalityLabel = ref<Record<string, string>>({})
const modalityIcon: Record<string, string> = {
  text: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z',
  image: 'M4 16l4.586-4.586a2 2 0 0 1 2.828 0L16 16m-2-2l1.586-1.586a2 2 0 0 1 2.828 0L20 14m-6-6h.01M6 20h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z',
  audio: 'M9 18V5l12-2v13M9 18a3 3 0 1 1 0-6 3 3 0 0 1 0 6zm12-5a3 3 0 1 1 0-6 3 3 0 0 1 0 6z',
  video: 'M15 10l4.553-2.276A1 1 0 0 1 21 8.618v6.764a1 1 0 0 1-1.447.894L15 14M5 18h8a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2z'
}
// codeValue 到图标类型的映射（数据库编码 → 图标 key）
const codeToIconKey = ref<Record<string, string>>({})
const qualityLabel = ref<Record<string, string>>({})
const qualityColor = ref<Record<string, string>>({})
const qualityOrder = ref<Record<string, number>>({})
const fieldLabel = ref<Record<string, string>>({})

function matchScale(scale: number, range: string): boolean {
  switch (range) {
    case 'small': return scale < 10000
    case 'medium': return scale >= 10000 && scale < 100000
    case 'large': return scale >= 100000 && scale < 1000000
    case 'massive': return scale >= 1000000
    default: return true
  }
}

const filteredData = computed(() => {
  let result = sampleSets.value

  if (filterName.value) {
    const kw = filterName.value.toLowerCase()
    result = result.filter(s => s.name.toLowerCase().includes(kw))
  }
  if (filterModality.value.length > 0) {
    result = result.filter(s => filterModality.value.some(m => s.modality.includes(m)))
  }
  if (filterQuality.value.length > 0) {
    result = result.filter(s => filterQuality.value.includes(s.qualityLevel))
  }
  if (filterField.value.length > 0) {
    result = result.filter(s => filterField.value.includes(s.fieldCode))
  }
  if (filterScale.value.length > 0) {
    result = result.filter(s => filterScale.value.some(r => matchScale(s.scale, r)))
  }
  if (filterTagsText.value) {
    const kw = filterTagsText.value.toLowerCase()
    result = result.filter(s => s.businessSystem?.toLowerCase().includes(kw))
  }
  if (filterUpdateTime.value) {
    result = result.filter(s => s.updateTime >= filterUpdateTime.value)
  }

  const field = sortField.value
  const order = sortOrder.value === 'asc' ? 1 : -1

  result = [...result].sort((a, b) => {
    let cmp = 0
    switch (field) {
      case 'updateTime':
        cmp = a.updateTime.localeCompare(b.updateTime)
        break
      case 'scale':
        cmp = a.scale - b.scale
        break
      case 'quality':
        cmp = qualityOrder.value[a.qualityLevel] - qualityOrder.value[b.qualityLevel]
        break
      case 'popularity':
        cmp = a.popularity - b.popularity
        break
    }
    return cmp * order
  })

  return result
})

function formatScale(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + ' 万'
  return n.toLocaleString()
}

function toggleSort(field: SortField) {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
}

function goToDetail(item: SampleSet) {
  router.push({ path: '/sample-detail', query: { setNo: item.setNo, setName: item.name } })
}

async function downloadSampleSet(item: SampleSet) {
  const now = new Date()
  const ts = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`
  const fileName = `${item.name}_${ts}`
  const url = `/api/sample/download-sample-set?setNo=${encodeURIComponent(item.setNo)}&fileName=${encodeURIComponent(fileName)}`
  const loadingInstance = ElLoading.service({ lock: true, text: '正在打包下载...', background: 'rgba(0,0,0,0.7)' })
  try {
    const res = await fetch(url)
    if (!res.ok) {
      const data = await res.json().catch(() => null)
      ElMessage.warning(data?.message || '下载失败')
      return
    }
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = fileName + '.zip'
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success('下载成功')
  } catch (e) {
    ElMessage.error('下载出错')
  } finally {
    loadingInstance.close()
  }
}

function resetFilters() {
  filterName.value = ''
  filterModality.value = []
  filterQuality.value = []
  filterField.value = []
  filterScale.value = []
  filterTagsText.value = ''
  filterUpdateTime.value = ''
}

function handleCardCommand(command: string, item: SampleSet) {
  if (command === 'download') {
    downloadSampleSet(item)
  }
}

const qualityColors = ['#00d4ff', '#00ff88', '#ffaa00', '#ff5555']

async function loadCodeDict() {
  dictLoading.value = true
  try {
    const data = await getCodeDict()

    if (data.SAMPLE_TYPE && data.SAMPLE_TYPE.length > 0) {
      modalityOptions.value = data.SAMPLE_TYPE.map(item => ({
        value: item.codeValue,
        label: item.codeName
      }))
      const labelMap: Record<string, string> = {}
      const iconMap: Record<string, string> = {}
      // 根据编码名称中的关键字匹配图标类型
      const nameToIcon: Record<string, string> = { '文本': 'text', '图': 'image', '语音': 'audio', '音频': 'audio', '视频': 'video' }
      data.SAMPLE_TYPE.forEach((item) => {
        labelMap[item.codeValue] = item.codeName
        // 优先按名称关键字匹配，再按顺序兜底
        let iconKey = ''
        for (const [kw, key] of Object.entries(nameToIcon)) {
          if (item.codeName.includes(kw)) { iconKey = key; break }
        }
        if (!iconKey) {
          const fallbackKeys = ['text', 'image', 'audio', 'video']
          const idx = data.SAMPLE_TYPE!.indexOf(item)
          iconKey = fallbackKeys[idx] || 'text'
        }
        iconMap[item.codeValue] = iconKey
      })
      // 同时添加默认 key 的映射，确保假数据也能正常展示
      defaultModalityOptions.forEach(o => {
        if (!labelMap[o.value]) labelMap[o.value] = o.label
        if (!iconMap[o.value]) iconMap[o.value] = o.value
      })
      modalityLabel.value = labelMap
      codeToIconKey.value = iconMap
    } else {
      modalityOptions.value = defaultModalityOptions
      modalityLabel.value = Object.fromEntries(defaultModalityOptions.map(o => [o.value, o.label]))
      codeToIconKey.value = Object.fromEntries(defaultModalityOptions.map(o => [o.value, o.value]))
    }

    if (data.QUALITY_LEVEL && data.QUALITY_LEVEL.length > 0) {
      qualityOptions.value = data.QUALITY_LEVEL.map(item => ({
        value: item.codeValue,
        label: item.codeName
      }))
      const labelMap: Record<string, string> = {}
      const colorMap: Record<string, string> = {}
      const orderMap: Record<string, number> = {}
      data.QUALITY_LEVEL.forEach((item, idx) => {
        labelMap[item.codeValue] = item.codeName
        colorMap[item.codeValue] = qualityColors[idx] || '#00d4ff'
        orderMap[item.codeValue] = data.QUALITY_LEVEL!.length - idx
      })
      // 同时添加默认 key 的映射，确保假数据也能正常展示
      defaultQualityOptions.forEach((o, idx) => {
        if (!labelMap[o.value]) labelMap[o.value] = o.label
        if (!colorMap[o.value]) colorMap[o.value] = qualityColors[idx] || '#00d4ff'
        if (!orderMap[o.value]) orderMap[o.value] = defaultQualityOptions.length - idx
      })
      qualityLabel.value = labelMap
      qualityColor.value = colorMap
      qualityOrder.value = orderMap
    } else {
      qualityOptions.value = defaultQualityOptions
      qualityLabel.value = Object.fromEntries(defaultQualityOptions.map(o => [o.value, o.label]))
      qualityColor.value = { '01': '#00d4ff', '02': '#00ff88', '03': '#ffaa00', '04': '#ff5555' }
      qualityOrder.value = { '01': 4, '02': 3, '03': 2, '04': 1 }
    }

    if (data.SAMPLE_FIELD && data.SAMPLE_FIELD.length > 0) {
      fieldOptions.value = data.SAMPLE_FIELD.map(item => ({
        value: item.codeValue,
        label: item.codeName
      }))
      const labelMap: Record<string, string> = {}
      data.SAMPLE_FIELD.forEach(item => {
        labelMap[item.codeValue] = item.codeName
      })
      fieldLabel.value = labelMap
    }
  } catch (e) {
    console.error('获取字典编码失败，使用默认值:', e)
    modalityOptions.value = defaultModalityOptions
    modalityLabel.value = Object.fromEntries(defaultModalityOptions.map(o => [o.value, o.label]))
    codeToIconKey.value = Object.fromEntries(defaultModalityOptions.map(o => [o.value, o.value]))
    qualityOptions.value = defaultQualityOptions
    qualityLabel.value = Object.fromEntries(defaultQualityOptions.map(o => [o.value, o.label]))
    qualityColor.value = { '01': '#00d4ff', '02': '#00ff88', '03': '#ffaa00', '04': '#ff5555' }
    qualityOrder.value = { '01': 4, '02': 3, '03': 2, '04': 1 }
  } finally {
    dictLoading.value = false
  }
}

onMounted(() => {
  loadCodeDict()
  loadSampleSets()
})

async function loadSampleSets() {
  try {
    const rows = await querySampleSet()
    if (rows.length > 0) {
      const dbData: SampleSet[] = rows.map((row: any, idx: number) => ({
        id: row.recordId ?? row.id ?? -(idx + 1),
        setNo: row.setNo || '',
        name: row.setName || row.setNo || '',
        modality: row.typeCode ? [row.typeCode] : [],
        updateTime: row.updateTime ? String(row.updateTime).slice(0, 16) : (row.createTime ? String(row.createTime).slice(0, 16) : ''),
        qualityLevel: row.qualityLevel || '',
        version: row.version || '',
        popularity: row.popularity ?? 0,
        scale: row.sampleCount ?? 0,
        businessSystem: row.businessSystem || '',
        fieldCode: row.sampleFieldCode || '',
        setDescription: row.setDescription || '',
        _fromDb: true
      }))
      sampleSets.value = [...dbData, ...sampleSets.value]
    }
  } catch (e) {
    console.error('查询样本集失败:', e)
  }
}

// ========== 新建样本集弹框 ==========
const dialogVisible = ref(false)
const dialogSaving = ref(false)

const dialogForm = ref({
  setCode: '',
  setName: '',
  description: '',
  businessSystem: '',
  sampleTypeCode: '',
  sampleFieldCode: ''
})

function openCreateDialog() {
  dialogForm.value = {
    setCode: '',
    setName: '',
    description: '',
    businessSystem: '',
    sampleTypeCode: '',
    sampleFieldCode: ''
  }
  dialogVisible.value = true
}

function onSampleTypeChange(val: string) {
  dialogForm.value.sampleTypeCode = val
}

async function handleCreateConfirm() {
  if (!dialogForm.value.setCode.trim()) {
    ElMessage.warning('请输入样本集编号')
    return
  }
  if (!dialogForm.value.setName.trim()) {
    ElMessage.warning('请输入样本集名称')
    return
  }
  if (!dialogForm.value.sampleTypeCode) {
    ElMessage.warning('请选择样本类型')
    return
  }

  dialogSaving.value = true
  try {
    const typeMatch = modalityOptions.value.find(o => o.value === dialogForm.value.sampleTypeCode)
    const fieldMatch = fieldOptions.value.find(o => o.value === dialogForm.value.sampleFieldCode)
    await saveSampleSet({
      setCode: dialogForm.value.setCode.trim(),
      setName: dialogForm.value.setName.trim(),
      description: dialogForm.value.description,
      businessSystem: dialogForm.value.businessSystem.trim(),
      sampleTypeCode: dialogForm.value.sampleTypeCode,
      sampleTypeName: typeMatch?.label || '',
      sampleFieldCode: dialogForm.value.sampleFieldCode,
      sampleFieldName: fieldMatch?.label || ''
    })
    ElMessage.success('新建样本集成功')
    dialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.message || '新建失败')
  } finally {
    dialogSaving.value = false
  }
}
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="样本集管理" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="page-header">
          <div class="page-title">
            <h2>样本集管理</h2>
            <p>管理和浏览全部样本集，支持多维度筛选与排序</p>
          </div>
          <div class="page-actions">
            <el-button type="primary" @click="openCreateDialog">新建样本集</el-button>
            <!-- <el-button>导入样本集</el-button> -->
          </div>
        </div>

        <div class="filter-bar">
          <div class="filter-row">
            <div class="filter-item filter-name">
              <label>名称</label>
              <el-input v-model="filterName" placeholder="搜索样本集名称" clearable size="default" />
            </div>
            <div class="filter-item">
              <label>样本类型</label>
              <el-select v-model="filterModality" multiple placeholder="全部" clearable size="default">
                <el-option v-for="m in modalityOptions" :key="m.value" :label="m.label" :value="m.value" />
              </el-select>
            </div>
            <div class="filter-item">
              <label>样本领域</label>
              <el-select v-model="filterField" multiple placeholder="全部" clearable size="default">
                <el-option v-for="f in fieldOptions" :key="f.value" :label="f.label" :value="f.value" />
              </el-select>
            </div>
            <div class="filter-item">
              <label>质量等级</label>
              <el-select v-model="filterQuality" multiple placeholder="全部" clearable size="default">
                <el-option v-for="q in qualityOptions" :key="q.value" :label="q.label" :value="q.value" />
              </el-select>
            </div>
            <div class="filter-item">
              <label>样本规模</label>
              <el-select v-model="filterScale" multiple placeholder="全部" clearable size="default">
                <el-option v-for="s in scaleOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </div>
            <div class="filter-item">
              <label>业务标签</label>
              <el-input v-model="filterTagsText" placeholder="输入业务标签" clearable size="default" />
            </div>
            <div class="filter-item">
              <label>更新时间</label>
              <el-date-picker v-model="filterUpdateTime" type="date" placeholder="起始日期" value-format="YYYY-MM-DD" clearable size="default" />
            </div>
            <el-button class="reset-btn" @click="resetFilters">重置</el-button>
          </div>
        </div>

        <div class="toolbar">
          <div class="toolbar-left">
            <span class="result-count">共 {{ filteredData.length }} 个样本集</span>
          </div>
          <div class="toolbar-right">
            <div class="sort-group">
              <span class="sort-label">排序：</span>
              <button
                v-for="opt in sortOptions"
                :key="opt.value"
                class="sort-btn"
                :class="{ active: sortField === opt.value }"
                @click="toggleSort(opt.value)"
              >
                {{ opt.label }}
                <svg v-if="sortField === opt.value" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <path :d="sortOrder === 'asc' ? 'M5 12h14M12 5l7 7-7 7' : 'M5 12h14M12 19l7-7-7-7'" transform="rotate(90 12 12) scale(0.7)" :style="{ transform: sortOrder === 'asc' ? 'rotate(-90deg) scale(0.7)' : 'rotate(90deg) scale(0.7)' }"/>
                </svg>
              </button>
            </div>
            <div class="view-toggle">
              <button class="view-btn" :class="{ active: viewMode === 'card' }" @click="viewMode = 'card'">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
                </svg>
                <span>卡片</span>
              </button>
              <button class="view-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>
                </svg>
                <span>列表</span>
              </button>
            </div>
          </div>
        </div>

        <div v-if="viewMode === 'card'" class="card-grid">
          <div class="sample-card" v-for="item in filteredData" :key="item.id">
            <div class="card-header-bar">
              <div class="modality-badges">
                <span v-for="m in item.modality" :key="m" class="modality-badge" :class="codeToIconKey[m] || m">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path :d="modalityIcon[codeToIconKey[m] || m]"/></svg>
                  {{ modalityLabel[m] }}
                </span>
              </div>
              <span class="quality-badge" :style="{ color: qualityColor[item.qualityLevel], borderColor: qualityColor[item.qualityLevel] }">{{ qualityLabel[item.qualityLevel] }}</span>
            </div>
            <div class="card-body">
              <h4 class="card-name link-name" :title="item.name" @click="goToDetail(item)">{{ item.name }}</h4>
              <p class="card-desc" :title="item.setDescription">{{ item.setDescription }}</p>
              <div class="card-tags">
                <span class="tag tag-field" v-if="item.fieldCode && fieldLabel[item.fieldCode]">{{ fieldLabel[item.fieldCode] }}</span>
                <span class="tag" v-if="item.businessSystem">{{ item.businessSystem }}</span>
              </div>
            </div>
            <div class="card-footer">
              <div class="meta-row">
                <div class="meta-item">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z"/></svg>
                  <span>{{ formatScale(item.scale) }}条</span>
                </div>
                <div class="meta-item">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                  <span>{{ item.popularity }}</span>
                </div>
                <div class="meta-item">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7v10c0 .55.45 1 1 1h14c.55 0 1-.45 1-1V7c0-.55-.45-1-1-1H5c-.55 0-1 .45-1 1zm0 0l9 6 9-6"/></svg>
                  <span>{{ item.version }}</span>
                </div>
                <div class="meta-item">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                  <span>{{ item.updateTime }}</span>
                </div>
              </div>
              <el-dropdown trigger="click" @command="(cmd: string) => handleCardCommand(cmd, item)">
                <span class="card-more-btn">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2.5"/><circle cx="12" cy="12" r="2.5"/><circle cx="19" cy="12" r="2.5"/></svg>
                </span>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="download">下载</el-dropdown-item>
                    <el-dropdown-item command="delete" disabled>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </div>

        <div v-else class="list-view">
          <div class="list-header">
            <span class="col col-name">样本集名称</span>
            <span class="col col-modality">类型</span>
            <span class="col col-scale">样本规模</span>
            <span class="col col-quality">质量等级</span>
            <span class="col col-version">版本号</span>
            <span class="col col-popularity">热度</span>
            <span class="col col-update">更新时间</span>
            <span class="col col-action">操作</span>
          </div>
          <div class="list-row" v-for="item in filteredData" :key="item.id">
            <span class="col col-name">
              <div class="name-cell">
                <div class="name-text link-name" @click="goToDetail(item)">{{ item.name }}</div>
                <div class="name-tags">
                  <span class="tag tag-field" v-if="item.fieldCode && fieldLabel[item.fieldCode]">{{ fieldLabel[item.fieldCode] }}</span>
                  <span class="tag" v-if="item.businessSystem">{{ item.businessSystem }}</span>
                </div>
              </div>
            </span>
            <span class="col col-modality">
              <div class="modality-badges-sm">
                <span v-for="m in item.modality" :key="m" class="modality-dot" :class="codeToIconKey[m] || m">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path :d="modalityIcon[codeToIconKey[m] || m]"/></svg>
                  <span class="modality-text">{{ modalityLabel[m] }}</span>
                </span>
              </div>
            </span>
            <span class="col col-scale">{{ formatScale(item.scale) }}条</span>
            <span class="col col-quality">
              <span class="quality-badge-sm" :style="{ color: qualityColor[item.qualityLevel], borderColor: qualityColor[item.qualityLevel] }">{{ qualityLabel[item.qualityLevel] }}</span>
            </span>
            <span class="col col-version">{{ item.version }}</span>
            <span class="col col-popularity">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ff5555" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
              {{ item.popularity }}
            </span>
            <span class="col col-update">{{ item.updateTime }}</span>
            <span class="col col-action">
              <el-button text size="small" class="action-btn" @click="downloadSampleSet(item)">下载</el-button>
            </span>
          </div>
        </div>

        <div v-if="filteredData.length === 0" class="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1">
            <path d="M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z"/>
          </svg>
          <p>暂无符合条件的样本集</p>
          <el-button type="primary" @click="resetFilters">重置筛选条件</el-button>
        </div>
      </main>
    </div>

    <el-dialog v-model="dialogVisible" title="新建样本集" width="520px" :close-on-click-modal="false" class="create-dialog">
      <el-form label-width="100px" label-position="right">
        <el-form-item label="样本集编号" required>
          <el-input v-model="dialogForm.setCode" placeholder="请输入样本集编号" maxlength="50" />
        </el-form-item>
        <el-form-item label="样本集名称" required>
          <el-input v-model="dialogForm.setName" placeholder="请输入样本集名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="dialogForm.description" type="textarea" :rows="3" placeholder="请输入描述" maxlength="500" />
        </el-form-item>
        <el-form-item label="业务系统">
          <el-input v-model="dialogForm.businessSystem" placeholder="请输入业务系统" maxlength="50" />
        </el-form-item>
        <el-form-item label="样本类型" required>
          <el-select v-model="dialogForm.sampleTypeCode" placeholder="请选择样本类型" @change="onSampleTypeChange" style="width: 100%" popper-class="create-dialog-popper">
            <el-option v-for="m in modalityOptions" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="样本领域">
          <el-select v-model="dialogForm.sampleFieldCode" placeholder="请选择样本领域" clearable style="width: 100%" popper-class="create-dialog-popper">
            <el-option v-for="f in fieldOptions" :key="f.value" :label="f.label" :value="f.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="dialogSaving" @click="handleCreateConfirm">确定</el-button>
        <el-button @click="dialogVisible = false">取消</el-button>
      </template>
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

.page-title h2 {
  font-size: 22px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 8px 0;
}

.page-title p {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.page-actions {
  display: flex;
  gap: 12px;
}

.filter-bar {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 6px;

  label {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.5);
    white-space: nowrap;
  }

  :deep(.el-input),
  :deep(.el-select),
  :deep(.el-date-editor) {
    width: 160px;
  }

  :deep(.el-input__wrapper),
  :deep(.el-select .el-input__wrapper) {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(0, 212, 255, 0.2);
    box-shadow: none;
    .el-input__inner {
      color: rgba(255, 255, 255, 0.85);
      &::placeholder {
        color: rgba(255, 255, 255, 0.3);
      }
    }
  }

  :deep(.el-select .el-select__tags .el-tag) {
    background: rgba(0, 212, 255, 0.15);
    border-color: rgba(0, 212, 255, 0.3);
    color: #00d4ff;
  }

  :deep(.el-date-editor) {
    .el-input__wrapper {
      width: 100%;
    }
    .el-input__prefix .el-icon,
    .el-input__suffix .el-icon {
      color: rgba(255, 255, 255, 0.5);
    }
  }
}

.filter-name {
  :deep(.el-input) {
    width: 200px;
  }
}

.reset-btn {
  margin-bottom: 1px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 0 4px;
}

.toolbar-left {
  .result-count {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.6);
  }
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.sort-group {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sort-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin-right: 4px;
}

.sort-btn {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 3px;
  transition: all 0.2s;
}

.sort-btn:hover {
  border-color: rgba(0, 212, 255, 0.4);
  color: #00d4ff;
}

.sort-btn.active {
  background: rgba(0, 212, 255, 0.12);
  border-color: rgba(0, 212, 255, 0.4);
  color: #00d4ff;
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
}

.view-btn.active {
  background: rgba(0, 212, 255, 0.15);
  color: #00d4ff;
}

.view-btn:hover {
  color: #00d4ff;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.sample-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
}

.sample-card:hover {
  border-color: rgba(0, 212, 255, 0.5);
  box-shadow: 0 4px 24px rgba(0, 212, 255, 0.15);
  transform: translateY(-2px);
}

.card-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.modality-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.modality-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;

  &.text {
    background: rgba(0, 212, 255, 0.15);
    color: #00d4ff;
  }
  &.image {
    background: rgba(0, 255, 136, 0.15);
    color: #00ff88;
  }
  &.audio {
    background: rgba(168, 85, 247, 0.15);
    color: #a855f7;
  }
  &.video {
    background: rgba(255, 170, 0, 0.15);
    color: #ffaa00;
  }
}

.quality-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid;
  white-space: nowrap;
}

.card-body {
  flex: 1;
  margin-bottom: 16px;
}

.card-name {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 8px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.link-name {
  cursor: pointer;
  &:hover {
    color: #00d4ff;
  }
}

.name-text.link-name {
  cursor: pointer;
  &:hover {
    color: #00d4ff;
  }
}

.card-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0 0 10px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  background: rgba(0, 212, 255, 0.08);
  border: 1px solid rgba(0, 212, 255, 0.15);
  color: rgba(255, 255, 255, 0.6);
}

.tag-field {
  background: rgba(255, 170, 0, 0.1);
  border-color: rgba(255, 170, 0, 0.25);
  color: rgba(255, 200, 60, 0.9);
}

.card-footer {
  border-top: 1px solid rgba(0, 212, 255, 0.1);
  padding-top: 12px;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}

.card-more-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;

  &:hover {
    background: rgba(0, 212, 255, 0.1);
    color: rgba(255, 255, 255, 0.7);
  }
}

.meta-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);

  svg {
    flex-shrink: 0;
    opacity: 0.6;
  }
}

.list-view {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  overflow: hidden;
}

.list-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: rgba(0, 212, 255, 0.08);
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.65);
}

.list-row {
  display: flex;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.08);
  transition: background 0.2s;

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background: rgba(0, 212, 255, 0.06);
  }
}

.col {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  flex-shrink: 0;
}

.col-name {
  flex: 2;
  min-width: 0;
}

.col-modality {
  width: 120px;
}

.col-scale {
  width: 90px;
  text-align: center;
}

.col-quality {
  width: 80px;
  text-align: center;
}

.col-version {
  width: 60px;
  text-align: center;
}

.col-popularity {
  width: 80px;
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: center;
}

.col-update {
  width: 110px;
  text-align: center;
}

.col-action {
  width: 80px;
  text-align: center;
}

.action-btn {
  color: #00d4ff !important;
  &:hover {
    color: #66e0ff !important;
  }
}

.name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.name-text {
  font-weight: 600;
  color: #fff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.name-tags {
  display: flex;
  gap: 4px;
}

.modality-badges-sm {
  display: flex;
  gap: 4px;
}

.modality-dot {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;

  .modality-text {
    white-space: nowrap;
  }

  &.text { background: rgba(0, 212, 255, 0.15); color: #00d4ff; }
  &.image { background: rgba(0, 255, 136, 0.15); color: #00ff88; }
  &.audio { background: rgba(168, 85, 247, 0.15); color: #a855f7; }
  &.video { background: rgba(255, 170, 0, 0.15); color: #ffaa00; }
}

.quality-badge-sm {
  font-size: 12px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 4px;
  border: 1px solid;
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
</style>

<style lang="scss">
// class="create-dialog" 加在 el-dialog 上，实际渲染到 .el-dialog 元素本身
// 因此用 .el-dialog.create-dialog 选择器（无空格 = 同一元素）
.el-dialog.create-dialog {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.98) 0%, rgba(26, 35, 50, 0.95) 100%) !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;
  border-radius: 12px !important;

  // 覆盖 Element Plus CSS 变量，确保暗色主题下所有组件文字可见
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

  .el-form-item__label {
    color: rgba(255, 255, 255, 0.7) !important;
  }

  .el-form-item.is-required .el-form-item__label::before {
    color: #ff5555 !important;
  }

  .el-input__wrapper {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
    box-shadow: none !important;
  }

  .el-input__inner {
    color: rgba(255, 255, 255, 0.85) !important;
    &::placeholder {
      color: rgba(255, 255, 255, 0.3) !important;
    }
  }

  .el-textarea__inner {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
    box-shadow: none !important;
    color: rgba(255, 255, 255, 0.85) !important;
    &::placeholder {
      color: rgba(255, 255, 255, 0.3) !important;
    }
  }

  // el-select 选中项和 placeholder
  .el-select__wrapper {
    background: rgba(255, 255, 255, 0.05) !important;
    box-shadow: 0 0 0 1px rgba(0, 212, 255, 0.2) inset !important;
    color: rgba(255, 255, 255, 0.85) !important;
  }

  .el-select__placeholder {
    color: rgba(255, 255, 255, 0.3) !important;
  }

  .el-select__selected-item {
    color: rgba(255, 255, 255, 0.85) !important;
    span {
      color: rgba(255, 255, 255, 0.85) !important;
    }
  }

  .el-select__suffix .el-select__caret {
    color: rgba(255, 255, 255, 0.5) !important;
  }

  .el-select .el-input__wrapper {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
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

// 下拉框弹出面板暗色主题
.el-select__popper.create-dialog-popper {
  background: rgba(17, 24, 39, 0.98) !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;

  .el-select-dropdown__item {
    color: rgba(255, 255, 255, 0.7) !important;
    &:hover,
    &.hover {
      background: rgba(0, 212, 255, 0.12) !important;
      color: #00d4ff !important;
    }
    &.is-selected {
      color: #00d4ff !important;
      font-weight: 600;
    }
  }

  .el-popper__arrow::before {
    background: rgba(17, 24, 39, 0.98) !important;
    border-color: rgba(0, 212, 255, 0.25) !important;
  }
}

// 卡片更多下拉菜单暗色主题
.el-dropdown__popper {
  background: rgba(17, 24, 39, 0.98) !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;

  .el-dropdown-menu {
    background: transparent !important;
    padding: 4px 0 !important;
  }

  .el-dropdown-menu__item {
    color: rgba(255, 255, 255, 0.7) !important;
    padding: 8px 20px !important;

    &:hover,
    &:focus {
      background: rgba(0, 212, 255, 0.12) !important;
      color: #00d4ff !important;
    }

    &.is-disabled {
      color: rgba(255, 255, 255, 0.25) !important;
      cursor: not-allowed;
    }
  }

  .el-popper__arrow::before {
    background: rgba(17, 24, 39, 0.98) !important;
    border-color: rgba(0, 212, 255, 0.25) !important;
  }
}
</style>
