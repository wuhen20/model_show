<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getCodeDict, getCollectTaskDet, getTaskSampleSet, saveCollectTaskDet, testDbConnection, queryDbConfig, queryTableColumns, queryColMap, saveColMap, getCollectTaskExecType, updateCollectTaskExecType, type CodeDictItem, type DatabaseConfigItem, type TableColumnInfo, type ColMapItem } from '@/api/sample'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()

const taskNo = ref<string>((route.query.taskNo as string) || '')

// 任务数据类型（用于判断是否图像类型）：优先从路由参数获取（新建后立即生效），loadTaskDet 后更新
const sampleTypeCode = ref<string>((route.query.sampleType as string) || '')

const fileGetModeOptions = ref<{ value: string; label: string }[]>([])
const loading = ref(false)
const savingSource = ref(false)
const testingConnection = ref(false)
const savingMapping = ref(false)
const savingImageConfig = ref(false)

// ========== 执行方式配置 ==========
const execTypeForm = ref({ executeType: '01', cronFormula: '' })
const savingExecType = ref(false)

async function loadExecType() {
  try {
    const data = await getCollectTaskExecType(taskNo.value)
    if (data) {
      execTypeForm.value = {
        executeType: data.executeType || '01',
        cronFormula: data.cronFormula || ''
      }
    }
  } catch {
    // 查询失败忽略
  }
}

async function handleSaveExecType() {
  if (execTypeForm.value.executeType === '02' && !execTypeForm.value.cronFormula.trim()) {
    ElMessage.warning('执行方式为定时时，请输入 cron 表达式')
    return
  }
  savingExecType.value = true
  try {
    await updateCollectTaskExecType({
      taskNo: taskNo.value,
      executeType: execTypeForm.value.executeType,
      cronFormula: execTypeForm.value.cronFormula.trim()
    })
    ElMessage.success('执行方式保存成功')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingExecType.value = false
  }
}

// ========== 上方：数据源配置 ==========
const form = ref({
  targetTable: '',
  collectSql: ''
})

// 已选数据源（展示用，密码不返回）
const selectedDb = ref<DatabaseConfigItem | null>(null)

// 是否为 Oracle 数据源（用于展示 sid/服务名 标签）
const isOracleDb = computed(() => {
  if (!selectedDb.value) return false
  return (selectedDb.value.dbTypeName || '').toUpperCase() === 'ORACLE'
})

// 是否为图像类型采集任务
const isImageType = computed(() => sampleTypeCode.value === '05')

// 时序样本集已绑定的目标表（binding_table 一旦绑定永久锁定，目标表名自动带出不可编辑）
const boundTable = ref('')
const isTableBound = computed(() => !!boundTable.value)

// 关联的原始样本集信息（编号/名称；用于页面展示）
const sampleSetNo = ref('')
const sampleSetName = ref('')

// ========== 数据源选择弹窗 ==========
const dbSelectVisible = ref(false)
const dbSelectLoading = ref(false)
const dbConfigList = ref<DatabaseConfigItem[]>([])
const dbSelectCurrent = ref<DatabaseConfigItem | null>(null)
const dbSelectFilterType = ref('')
const dbTypeOptions = ref<{ value: string; label: string }[]>([])

const filteredDbConfigList = computed(() => {
  if (!dbSelectFilterType.value) return dbConfigList.value
  return dbConfigList.value.filter(c => c.dbTypeCode === dbSelectFilterType.value)
})

function openDbSelectDialog() {
  dbSelectCurrent.value = null
  dbSelectFilterType.value = ''
  dbSelectVisible.value = true
  loadDbConfigList()
}

async function loadDbConfigList() {
  dbSelectLoading.value = true
  try {
    dbConfigList.value = await queryDbConfig()
    // 加载数据库类型字典
    const data = await getCodeDict(['DATABASE_TYPE'])
    if (data.DATABASE_TYPE && data.DATABASE_TYPE.length > 0) {
      dbTypeOptions.value = data.DATABASE_TYPE.map((item: CodeDictItem) => ({
        value: item.codeValue,
        label: item.codeName
      }))
    }
    // 若已有选中数据源，回显高亮行
    if (selectedDb.value) {
      dbSelectCurrent.value = dbConfigList.value.find(c => c.recordId === selectedDb.value?.recordId) || null
    }
  } catch (e: any) {
    ElMessage.error(e.message || '查询数据源配置失败')
  } finally {
    dbSelectLoading.value = false
  }
}

function handleDbSelectCurrentChange(row: DatabaseConfigItem | null) {
  dbSelectCurrent.value = row
}

function handleDbSelectConfirm() {
  if (!dbSelectCurrent.value) {
    ElMessage.warning('请先选择数据源')
    return
  }
  selectedDb.value = dbSelectCurrent.value
  dbSelectVisible.value = false
}

// ========== 图像获取配置 ==========
const imageConfig = ref({
  fileId: '',        // 图像获取字段名
  fileName: '',      // 图像名称字段名
  fileGetMode: '',   // 获取方式编码：01-存储路径 02-ceph 03-oss
  bucketName: ''     // 桶名称（ceph模式）
})

/** 从 SELECT ... FROM 形式的 SQL 中提取列别名（忽略大小写），用于图像字段下拉框选项 */
const sqlAliases = computed(() => {
  if (!form.value.collectSql) return []
  return extractSelectAliases(form.value.collectSql)
})

// 执行结果信息
const execInfo = ref({
  lastExecuteTime: '',
  lastExecuteFlagName: ''
})

async function loadDbTypeDict() {
  try {
    const data = await getCodeDict(['FILE_GET_MODE'])
    if (data.FILE_GET_MODE && data.FILE_GET_MODE.length > 0) {
      fileGetModeOptions.value = data.FILE_GET_MODE.map((item: CodeDictItem) => ({
        value: item.codeValue,
        label: item.codeName
      }))
    }
  } catch {
    // 字典加载失败时忽略
  }
}

// 加载任务关联的原始样本集信息（样本集编号/名称/绑定表）
// 不依赖明细行：新建任务首次进入明细页时也能自动带出已绑定样本集的目标表
async function loadTaskSampleSet() {
  try {
    const info = await getTaskSampleSet(taskNo.value)
    if (info) {
      sampleSetNo.value = info.originalSampleSetNo || ''
      sampleSetName.value = info.sampleSetName || ''
      // 样本集已绑定目标表：目标表名自动带出并锁定（以样本集绑定表为准）
      if (info.bindingTable) {
        boundTable.value = info.bindingTable
        form.value.targetTable = info.bindingTable
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '查询样本集信息失败')
  }
}

async function loadTaskDet() {
  loading.value = true
  try {
    const det = await getCollectTaskDet(taskNo.value)
    if (det) {
      form.value = {
        targetTable: det.targetTable || '',
        collectSql: det.collectSql || ''
      }
      // 样本集已绑定目标表（时序类型）：目标表名自动带出，不可编辑
      boundTable.value = det.bindingTable || ''
      if (boundTable.value) {
        form.value.targetTable = boundTable.value
      }
      // 回填关联原始样本集信息（编号/名称）
      sampleSetNo.value = det.originalSampleSetNo || ''
      // 回填已配置的数据源（只读展示，密码不返回）
      if (det.sourceDbId) {
        selectedDb.value = {
          recordId: det.sourceDbId,
          dbTypeCode: det.sourceDbType || '',
          dbTypeName: det.sourceDbTypeName || det.sourceDbType || '',
          dbAlias: det.sourceDbAlias || '',
          dbHost: det.sourceDbHost || '',
          dbPort: det.sourceDbPort || '',
          dbUsr: det.sourceDbUsr || '',
          dbAuth: det.sourceDbAuth || '',
          dbName: det.sourceDbName || '',
          remark: '',
          createTime: ''
        }
      } else {
        selectedDb.value = null
      }
      execInfo.value = {
        lastExecuteTime: det.lastExecuteTime || '',
        lastExecuteFlagName: det.lastExecuteFlagName || ''
      }
      // 回填数据类型和图像配置
      sampleTypeCode.value = det.sampleTypeCode || ''
      imageConfig.value = {
        fileId: det.fileId || '',
        fileName: det.fileName || '',
        fileGetMode: det.fileGetMode || '',
        bucketName: det.bucketName || ''
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '查询明细失败')
  } finally {
    loading.value = false
  }
}

// ========== 测试数据库连接（按已保存的数据源配置测试） ==========
async function handleTestConnection() {
  if (!selectedDb.value) {
    ElMessage.warning('请先选择数据源')
    return
  }

  testingConnection.value = true
  try {
    const result = await testDbConnection({ dbConfigId: selectedDb.value.recordId })
    if (result.success) {
      ElMessageBox.alert(result.message, '测试连接', { type: 'success' })
    } else {
      ElMessageBox.alert(result.message, '测试连接', { type: 'error' })
    }
  } catch (e: any) {
    ElMessageBox.alert(e.message || '测试失败', '测试连接', { type: 'error' })
  } finally {
    testingConnection.value = false
  }
}

async function handleSaveSource() {
  if (!selectedDb.value) {
    ElMessage.warning('请选择数据源')
    return
  }
  if (!form.value.collectSql.trim()) {
    ElMessage.warning('请输入采集SQL')
    return
  }

  savingSource.value = true
  try {
    await saveCollectTaskDet({
      taskNo: taskNo.value,
      sourceDbId: selectedDb.value.recordId,
      targetTable: form.value.targetTable.trim(),
      collectSql: form.value.collectSql.trim()
    })
    ElMessage.success('数据源配置保存成功')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingSource.value = false
  }
}

// ========== 下方：目标字段映射配置 ==========
const tableColumns = ref<TableColumnInfo[]>([])
const columnLoading = ref(false)
const columnsQueried = ref(false)

// 映射列表：每行 { sourceColumn, targetColumn }
const mappings = ref<ColMapItem[]>([])

/** 从 SELECT ... FROM 形式的 SQL 中提取列别名（忽略大小写） */
function extractSelectAliases(sql: string): string[] {
  const fromMatch = sql.match(/\bFROM\b/i)
  if (!fromMatch || fromMatch.index === undefined) return []
  const selectPart = sql.substring(sql.search(/\bSELECT\b/i) + 6, fromMatch.index)
  // 按顶层逗号分割列
  const cols: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < selectPart.length; i++) {
    const ch = selectPart[i]
    if (ch === '(') depth++
    else if (ch === ')') depth--
    else if (ch === ',' && depth === 0) {
      cols.push(selectPart.substring(start, i).trim())
      start = i + 1
    }
  }
  cols.push(selectPart.substring(start).trim())
  // 提取每列的别名：优先取 AS 后的部分，否则取列名本身
  return cols.map(c => {
    const asMatch = c.match(/\bAS\s+(\w+)\s*$/i)
    if (asMatch) return asMatch[1]
    // 无 AS 时取最后一个 . 后的部分或整体（去掉表别名前缀）
    const lastWord = c.split('.').pop() || c
    return lastWord.trim()
  }).filter(s => s.length > 0)
}

async function handleQueryColumns() {
  if (!form.value.targetTable.trim()) {
    ElMessage.warning('请先输入目标表名')
    return
  }
  columnLoading.value = true
  try {
    tableColumns.value = await queryTableColumns(taskNo.value, form.value.targetTable.trim())
    columnsQueried.value = true
    // 从采集SQL中提取源列别名，用于自动匹配
    const sourceAliases = form.value.collectSql ? extractSelectAliases(form.value.collectSql) : []
    const sourceLowerMap = new Map<string, string>()
    sourceAliases.forEach(a => sourceLowerMap.set(a.toLowerCase(), a))
    // 初始化映射：为每个目标字段创建一行，自动匹配源字段（忽略大小写）
    mappings.value = tableColumns.value.map(col => {
      const matched = sourceLowerMap.get(col.columnName.toLowerCase())
      return {
        sourceColumn: matched || '',
        targetColumn: col.columnName
      }
    })
    // 加载已有映射并回填（忽略大小写）
    const existingMaps = await queryColMap(taskNo.value)
    if (existingMaps && existingMaps.length > 0) {
      for (const map of existingMaps) {
        const idx = mappings.value.findIndex(
          m => m.targetColumn.toLowerCase() === (map.targetColumn || '').toLowerCase()
        )
        if (idx !== -1) {
          mappings.value[idx].sourceColumn = map.sourceColumn
        }
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '查询表字段失败')
  } finally {
    columnLoading.value = false
  }
}

async function handleSaveMapping() {
  if (!form.value.targetTable.trim()) {
    ElMessage.warning('请先输入目标表名')
    return
  }
  if (mappings.value.length === 0) {
    ElMessage.warning('请先查询表字段')
    return
  }
  // 过滤掉源字段为空的行
  const validMappings = mappings.value.filter(m => m.sourceColumn.trim())
  if (validMappings.length === 0) {
    ElMessage.warning('至少配置一个源字段映射')
    return
  }
  savingMapping.value = true
  try {
    await saveColMap(taskNo.value, form.value.targetTable.trim(), validMappings)
    ElMessage.success('字段映射保存成功')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingMapping.value = false
  }
}

// ========== 图像获取配置保存 ==========
async function handleSaveImageConfig() {
  if (!selectedDb.value) {
    ElMessage.warning('请先选择数据源')
    return
  }
  if (!form.value.collectSql.trim()) {
    ElMessage.warning('请先输入采集SQL')
    return
  }
  if (!imageConfig.value.fileId) {
    ElMessage.warning('请选择图像获取字段')
    return
  }
  if (!imageConfig.value.fileGetMode) {
    ElMessage.warning('请选择获取方式')
    return
  }
  if (imageConfig.value.fileGetMode === '02' && !imageConfig.value.bucketName.trim()) {
    ElMessage.warning('ceph 模式下请输入桶名称')
    return
  }

  savingImageConfig.value = true
  try {
    await saveCollectTaskDet({
      taskNo: taskNo.value,
      sourceDbId: selectedDb.value.recordId,
      targetTable: form.value.targetTable.trim(),
      collectSql: form.value.collectSql.trim(),
      fileGetMode: imageConfig.value.fileGetMode,
      bucketName: imageConfig.value.bucketName.trim(),
      fileId: imageConfig.value.fileId,
      fileName: imageConfig.value.fileName
    })
    ElMessage.success('图像获取配置保存成功')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingImageConfig.value = false
  }
}

function goBack() {
  router.push('/collect-task')
}

async function init() {
  await loadTaskSampleSet()
  await loadTaskDet()
  // 如果目标表名已有值，自动查询字段
  if (form.value.targetTable.trim()) {
    handleQueryColumns()
  }
}

onMounted(() => {
  if (!taskNo.value) {
    ElMessage.warning('缺少任务编号，请从任务列表进入')
    router.push('/collect-task')
    return
  }
  loadDbTypeDict()
  loadExecType()
  init()
})
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="采集任务明细" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="page-header">
          <div class="page-title-row">
            <div class="title-left">
              <span class="back-btn" @click="goBack">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M19 12H5M12 19l-7-7 7-7" />
                </svg>
                返回
              </span>
              <h2 class="page-title">采集任务明细</h2>
            </div>
            <div class="title-right">
              <span class="task-no-tag">任务编号：{{ taskNo }}</span>
              <span v-if="sampleSetNo" class="task-no-tag sample-set-tag">关联原始样本集：{{ sampleSetName || sampleSetNo }}({{ sampleSetNo }})</span>
            </div>
          </div>
        </div>

        <!-- ========== 顶部：执行方式配置 ========== -->
        <div class="section-card">
          <div class="section-title">
            <h3>执行方式配置</h3>
          </div>
          <el-form label-width="100px" label-position="right">
            <el-form-item label="执行方式" required>
              <el-radio-group v-model="execTypeForm.executeType">
                <el-radio value="01">手动</el-radio>
                <el-radio value="02">定时</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="execTypeForm.executeType === '02'" label="cron表达式" required>
              <el-input v-model="execTypeForm.cronFormula" placeholder="请输入cron表达式，如：0 0 2 * * ?" maxlength="200" style="max-width: 400px" />
              <div class="cron-tip">示例：0 0 2 * * ? 表示每天凌晨2点执行；0 */5 * * * ? 表示每5分钟执行一次</div>
            </el-form-item>
          </el-form>
          <div class="section-footer">
            <el-button type="primary" :loading="savingExecType" @click="handleSaveExecType">保存执行方式</el-button>
          </div>
        </div>

        <!-- ========== 上方：数据源配置 ========== -->
        <div class="section-card">
          <div class="section-title">
            <h3>数据源配置</h3>
          </div>
          <div v-if="loading" class="loading-mask-inline">
            <span>加载中...</span>
          </div>
          <div v-if="!loading && execInfo.lastExecuteTime" class="exec-info">
            <span class="exec-label">最近执行时间：</span>
            <span class="exec-value">{{ execInfo.lastExecuteTime }}</span>
            <span class="exec-label" style="margin-left: 24px;">执行结果：</span>
            <span class="exec-value" :style="{ color: execInfo.lastExecuteFlagName === '成功' ? '#00ff88' : execInfo.lastExecuteFlagName === '失败' ? '#ff5555' : 'rgba(255,255,255,0.5)' }">
              {{ execInfo.lastExecuteFlagName || '未执行' }}
            </span>
          </div>
          <el-form label-width="100px" label-position="right">
            <div class="form-row">
              <el-button type="primary" @click="openDbSelectDialog">选择数据源</el-button>
            </div>
            <div class="form-row">
              <div class="form-col form-col-full">
                <el-form-item label="数据源">
                  <el-input :model-value="selectedDb?.dbAlias || ''" readonly placeholder="请选择数据源" class="readonly-input" />
                </el-form-item>
              </div>
            </div>
            <template v-if="selectedDb">
              <div class="form-row">
                <div class="form-col">
                  <el-form-item label="数据库类型">
                    <el-input :model-value="selectedDb.dbTypeName || ''" readonly class="readonly-input" />
                  </el-form-item>
                </div>
                <div class="form-col">
                  <el-form-item label="数据库地址">
                    <el-input :model-value="selectedDb.dbHost || ''" readonly class="readonly-input" />
                  </el-form-item>
                </div>
                <div class="form-col form-col-small">
                  <el-form-item label="端口">
                    <el-input :model-value="selectedDb.dbPort || ''" readonly class="readonly-input" />
                  </el-form-item>
                </div>
              </div>
              <div class="form-row">
                <div class="form-col">
                  <el-form-item label="用户名">
                    <el-input :model-value="selectedDb.dbUsr || ''" readonly class="readonly-input" />
                  </el-form-item>
                </div>
                <div class="form-col">
                  <el-form-item :label="isOracleDb ? 'sid/服务名' : '数据库'">
                    <el-input :model-value="selectedDb.dbName || ''" readonly class="readonly-input" />
                  </el-form-item>
                </div>
                <div class="form-col form-col-small" v-if="selectedDb.dbAuth">
                  <el-form-item label="认证方式">
                    <el-input :model-value="selectedDb.dbAuth || ''" readonly class="readonly-input" />
                  </el-form-item>
                </div>
              </div>
            </template>
            <div class="form-row form-row-full">
              <el-form-item label="采集SQL" required class="full-width-item">
                <el-input v-model="form.collectSql" type="textarea" :rows="6" placeholder="请输入采集数据的SQL语句" />
              </el-form-item>
            </div>
          </el-form>
          <div class="section-footer">
            <el-button :loading="testingConnection" @click="handleTestConnection">测试连接</el-button>
            <el-button type="primary" :loading="savingSource" @click="handleSaveSource">保存数据源配置</el-button>
          </div>
        </div>

        <!-- 数据源选择弹窗 -->
        <el-dialog v-model="dbSelectVisible" title="选择数据源" width="960px" :close-on-click-modal="false" class="db-select-dialog">
          <div class="db-select-filter">
            <span class="db-select-filter-label">数据库类型</span>
            <el-select v-model="dbSelectFilterType" placeholder="全部" clearable popper-class="detail-popper" style="width: 160px">
              <el-option v-for="opt in dbTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
          </div>
          <el-table
            :data="filteredDbConfigList"
            v-loading="dbSelectLoading"
            highlight-current-row
            style="width: 100%"
            @current-change="handleDbSelectCurrentChange"
          >
            <el-table-column label="" width="50">
              <template #default="{ row }">
                <span class="db-radio" :class="{ active: dbSelectCurrent?.recordId === row.recordId }"></span>
              </template>
            </el-table-column>
            <el-table-column prop="dbTypeName" label="数据库类型" width="110">
              <template #default="{ row }">{{ row.dbTypeName || row.dbTypeCode || '-' }}</template>
            </el-table-column>
            <el-table-column prop="dbAlias" label="数据源名称" min-width="150" show-overflow-tooltip />
            <el-table-column label="地址" min-width="170" show-overflow-tooltip>
              <template #default="{ row }">{{ row.dbHost }}{{ row.dbPort ? ':' + row.dbPort : '' }}</template>
            </el-table-column>
            <el-table-column prop="dbUsr" label="用户名" min-width="110" show-overflow-tooltip>
              <template #default="{ row }">{{ row.dbUsr || '-' }}</template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.remark || '-' }}</template>
            </el-table-column>
            <template #empty>
              <div class="db-select-empty">暂无数据源，请先在「数据源配置」页面新增</div>
            </template>
          </el-table>
          <template #footer>
            <el-button @click="dbSelectVisible = false">取消</el-button>
            <el-button type="primary" @click="handleDbSelectConfirm">确定</el-button>
          </template>
        </el-dialog>

        <!-- ========== 下方：目标字段映射配置（仅时序类型显示） ========== -->
        <div class="section-card" v-if="!isImageType">
          <div class="section-title">
            <h3>目标字段映射</h3>
          </div>
          <div class="target-table-row">
            <el-form label-width="100px" label-position="right" inline>
              <el-form-item label="目标表名" required>
                <el-input
                  v-model="form.targetTable"
                  :placeholder="isTableBound ? '样本集已绑定目标表，自动带出不可更改' : '数据写入的目标表名'"
                  maxlength="64"
                  style="width: 260px"
                  :disabled="isTableBound"
                  class="target-table-input"
                />
              </el-form-item>
              <el-button type="primary" :loading="columnLoading" @click="handleQueryColumns" style="margin-left: 12px">
                字段自动匹配
              </el-button>
            </el-form>
          </div>

          <div v-if="columnsQueried && tableColumns.length > 0" class="mapping-area">
            <el-table :data="mappings" style="width: 100%" class="mapping-table" max-height="360">
              <el-table-column label="源字段/别名" min-width="200">
                <template #default="{ row }">
                  <el-input v-model="row.sourceColumn" placeholder="源字段" maxlength="32" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="目标字段" min-width="150" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="field-text">{{ row.targetColumn }}</span>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="120" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="field-text">{{ tableColumns.find(c => c.columnName === row.targetColumn)?.columnType || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="注释" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="field-text">{{ tableColumns.find(c => c.columnName === row.targetColumn)?.columnComment || '-' }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div v-else-if="columnsQueried && tableColumns.length === 0" class="empty-columns">
            <span>未查询到表字段信息，请确认目标表名是否正确</span>
          </div>

          <div v-else class="mapping-placeholder">
            <span>请输入目标表名后点击"字段自动匹配"按钮</span>
          </div>

          <div class="section-footer">
            <el-button type="primary" :loading="savingMapping" @click="handleSaveMapping">保存字段映射</el-button>
          </div>
        </div>

        <!-- ========== 图像获取配置（仅图像类型显示） ========== -->
        <div class="section-card" v-if="isImageType">
          <div class="section-title">
            <h3>图像获取配置</h3>
          </div>
          <el-form label-width="120px" label-position="right">
            <el-form-item label="图像获取字段" required>
              <el-select v-model="imageConfig.fileId" placeholder="请选择图像获取字段" filterable popper-class="detail-popper" style="width: 100%">
                <el-option v-for="alias in sqlAliases" :key="alias" :label="alias" :value="alias" />
              </el-select>
              <div class="field-tip">从采集SQL的结果列中选择用于获取图像的字段（字段值是文件路径或ceph对象key）</div>
            </el-form-item>
            <el-form-item label="图像名称字段">
              <el-select v-model="imageConfig.fileName" placeholder="请选择图像名称字段（可选）" filterable clearable popper-class="detail-popper" style="width: 100%">
                <el-option v-for="alias in sqlAliases" :key="alias" :label="alias" :value="alias" />
              </el-select>
              <div class="field-tip">从采集SQL的结果列中选择作为文件名的字段，未选择时使用图像获取字段的文件名</div>
            </el-form-item>
            <el-form-item label="获取方式" required>
              <el-radio-group v-model="imageConfig.fileGetMode">
                <el-radio v-for="opt in fileGetModeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="imageConfig.fileGetMode === '02'" label="桶名称" required>
              <el-input v-model="imageConfig.bucketName" placeholder="请输入 Ceph 桶名称" maxlength="128" style="max-width: 400px" />
            </el-form-item>
          </el-form>
          <div class="section-footer">
            <el-button type="primary" :loading="savingImageConfig" @click="handleSaveImageConfig">保存图像获取配置</el-button>
          </div>
        </div>
      </main>
    </div>
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
  gap: 20px;
}

.page-header {
  margin-bottom: 0;
}

.page-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  font-size: 13px;
  transition: color 0.2s;

  &:hover {
    color: #00d4ff;
  }
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #fff;
  margin: 0;
}

.task-no-tag {
  font-size: 16px;
  color: #00d4ff;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.25);
  padding: 5px 14px;
  border-radius: 6px;
  white-space: nowrap;
}

.sample-set-tag {
  color: #00d4ff;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.25);
  white-space: normal;
}

// 通用卡片样式
.section-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 24px 28px;
  position: relative;
}

.section-title {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.12);

  h3 {
    font-size: 16px;
    font-weight: 600;
    color: #fff;
    margin: 0;
  }
}

.section-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(0, 212, 255, 0.12);
}

.loading-mask-inline {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;

  span {
    color: rgba(255, 255, 255, 0.6);
    font-size: 14px;
  }
}

.exec-info {
  margin-bottom: 16px;
  padding: 10px 14px;
  background: rgba(0, 212, 255, 0.08);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  font-size: 13px;
}

.exec-label {
  color: rgba(255, 255, 255, 0.5);
}

.exec-value {
  color: rgba(255, 255, 255, 0.85);
}

.form-row {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  max-width: 1100px;
}

.form-row-full {
  display: block;
  max-width: 1100px;
}

.form-col {
  flex: 1;
  min-width: 180px;
  max-width: 250px;
}

.form-col-full {
  flex: 1;
  min-width: 180px;
  max-width: 100%;
}

.form-col-small {
  flex: 0 0 160px;
  max-width: 160px;
}

// 只读数据源展示输入框
.readonly-input {
  :deep(.el-input__wrapper) {
    background: rgba(255, 255, 255, 0.02) !important;
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06) inset !important;

    &.is-focus,
    &:hover {
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06) inset !important;
    }
  }

  :deep(.el-input__inner) {
    color: rgba(255, 255, 255, 0.65) !important;
    cursor: default;
  }
}

// 样本集已绑定目标表时，目标表名输入框置灰且去除 hover/focus 高亮
.target-table-input {
  :deep(.el-input__wrapper) {
    background: rgba(255, 255, 255, 0.04) !important;
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.07) inset !important;
    cursor: default;

    &.is-focus,
    &:hover {
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.07) inset !important;
    }
  }
  :deep(.el-input__inner) {
    color: rgba(255, 255, 255, 0.45) !important;
    cursor: default;
  }
}

.full-width-item {
  width: 100%;

  .el-form-item__content {
    width: 100%;
  }
}

// 目标表名行
.target-table-row {
  margin-bottom: 16px;

  :deep(.el-form--inline .el-form-item) {
    margin-bottom: 0;
  }
}

// 映射区域
.mapping-area {
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  overflow: hidden;
}

.field-text {
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
}

.empty-columns,
.mapping-placeholder {
  padding: 32px 0;
  text-align: center;
  color: rgba(255, 255, 255, 0.4);
  font-size: 14px;
}

.cron-tip {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 4px;
  line-height: 1.5;
}

.field-tip {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 4px;
  line-height: 1.5;
}
</style>

<style lang="scss">
.detail-popper {
  background: rgba(17, 24, 39, 0.98) !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;

  .el-select-dropdown__item {
    color: rgba(255, 255, 255, 0.7) !important;

    &.is-selected {
      color: #00d4ff !important;
    }
  }
}

// 数据源选择弹窗（深色主题）
.db-select-dialog {
  .el-dialog {
    background: linear-gradient(160deg, #111827 0%, #161e2e 100%);
    border: 1px solid rgba(0, 212, 255, 0.25);
  }

  .el-dialog__title {
    color: #fff;
    font-weight: 600;
  }

  .db-select-filter {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;

    .db-select-filter-label {
      color: rgba(255, 255, 255, 0.5);
      font-size: 13px;
      white-space: nowrap;
    }
  }

  .el-table {
    --el-table-tr-bg-color: transparent;
    --el-table-bg-color: transparent;
    --el-table-header-bg-color: rgba(0, 212, 255, 0.08);
    --el-table-header-text-color: rgba(255, 255, 255, 0.85);
    --el-table-text-color: rgba(255, 255, 255, 0.8);
    --el-table-border-color: rgba(0, 212, 255, 0.14);
    --el-table-row-hover-bg-color: rgba(0, 212, 255, 0.1);
    --el-table-current-row-bg-color: rgba(0, 212, 255, 0.16);
  }

  .el-table th.el-table__cell {
    background: linear-gradient(180deg, rgba(0, 212, 255, 0.12) 0%, rgba(0, 212, 255, 0.06) 100%) !important;
  }

  .db-radio {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 1px solid rgba(0, 212, 255, 0.4);
    border-radius: 50%;
    position: relative;

    &.active {
      border-color: #00d4ff;

      &::after {
        content: '';
        position: absolute;
        top: 3px;
        left: 3px;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #00d4ff;
      }
    }
  }

  .db-select-empty {
    padding: 40px 0;
    text-align: center;
    color: rgba(255, 255, 255, 0.4);
    font-size: 14px;
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

.section-card {
  --el-fill-color-blank: transparent;
  --el-bg-color: transparent;

  .el-form-item__label {
    color: rgba(255, 255, 255, 0.7) !important;
  }

  .el-radio__label {
    color: rgba(255, 255, 255, 0.85) !important;
  }

  // el-select 组件需要特殊处理
  .el-select__wrapper {
    background: transparent !important;
    border: 1px solid rgba(0, 212, 255, 0.25) !important;
    box-shadow: none !important;
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

  // 映射区域小号输入框
  .mapping-area .el-input__wrapper {
    padding: 0px 8px;
  }
}
</style>
