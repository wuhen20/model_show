<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getCodeDict, getCollectTaskDet, saveCollectTaskDet, queryTableColumns, queryColMap, saveColMap, getCollectTaskExecType, updateCollectTaskExecType, type CodeDictItem, type TableColumnInfo, type ColMapItem } from '@/api/sample'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()

const taskNo = ref<string>((route.query.taskNo as string) || '')

const dbTypeOptions = ref<{ value: string; label: string }[]>([])
const loading = ref(false)
const savingSource = ref(false)
const savingMapping = ref(false)

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

// ========== 上方：源数据配置 ==========
const form = ref({
  sourceDbType: '',
  sourceDbHost: '',
  sourceDbPort: '',
  sourceDbUsr: '',
  sourceDbPwd: '',
  sourceDbName: '',
  targetTable: '',
  collectSql: '',
  sourceDbAuth: 'NONE'
})

// Hive 认证方式选项
const hiveAuthOptions = [
  { value: 'NONE', label: 'NONE（无认证）' },
  { value: 'LDAP', label: 'LDAP' },
  { value: 'PLAIN', label: 'PLAIN' },
  { value: 'KERBEROS', label: 'KERBEROS' },
  { value: 'CUSTOM', label: 'CUSTOM' }
]

// 是否为 Hive 数据源（根据字典 label 名称判断，兼容不同编码值）
const isHiveSource = computed(() => {
  const opt = dbTypeOptions.value.find(o => o.value === form.value.sourceDbType)
  return opt ? opt.label.toUpperCase() === 'HIVE' : false
})

// 执行结果信息
const execInfo = ref({
  lastExecuteTime: '',
  lastExecuteFlagName: ''
})

async function loadDbTypeDict() {
  try {
    const data = await getCodeDict(['DATABASE_TYPE'])
    if (data.DATABASE_TYPE && data.DATABASE_TYPE.length > 0) {
      dbTypeOptions.value = data.DATABASE_TYPE.map((item: CodeDictItem) => ({
        value: item.codeValue,
        label: item.codeName
      }))
    }
  } catch {
    // 字典加载失败时忽略
  }
}

async function loadTaskDet() {
  loading.value = true
  try {
    const det = await getCollectTaskDet(taskNo.value)
    if (det) {
      form.value = {
        sourceDbType: det.sourceDbType || '',
        sourceDbHost: det.sourceDbHost || '',
        sourceDbPort: det.sourceDbPort || '',
        sourceDbUsr: det.sourceDbUsr || '',
        sourceDbPwd: det.sourceDbPwd || '',
        sourceDbName: det.sourceDbName || '',
        targetTable: det.targetTable || '',
        collectSql: det.collectSql || '',
        sourceDbAuth: det.sourceDbAuth || 'NONE'
      }
      execInfo.value = {
        lastExecuteTime: det.lastExecuteTime || '',
        lastExecuteFlagName: det.lastExecuteFlagName || ''
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '查询明细失败')
  } finally {
    loading.value = false
  }
}

async function handleSaveSource() {
  if (!form.value.sourceDbType) {
    ElMessage.warning('请选择数据库类型')
    return
  }
  if (!form.value.sourceDbHost.trim()) {
    ElMessage.warning('请输入数据库地址')
    return
  }
  if (!form.value.sourceDbUsr.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!form.value.sourceDbName.trim()) {
    ElMessage.warning('请输入数据库名称')
    return
  }
  if (!form.value.collectSql.trim()) {
    ElMessage.warning('请输入采集SQL')
    return
  }
  if (form.value.sourceDbType === '03' && !form.value.sourceDbAuth) {
    ElMessage.warning('Hive 数据源请选择认证方式')
    return
  }

  savingSource.value = true
  try {
    await saveCollectTaskDet({
      taskNo: taskNo.value,
      sourceDbType: form.value.sourceDbType,
      sourceDbHost: form.value.sourceDbHost.trim(),
      sourceDbPort: form.value.sourceDbPort.trim(),
      sourceDbUsr: form.value.sourceDbUsr.trim(),
      sourceDbPwd: form.value.sourceDbPwd.trim(),
      sourceDbName: form.value.sourceDbName.trim(),
      targetTable: form.value.targetTable.trim(),
      collectSql: form.value.collectSql.trim(),
      sourceDbAuth: form.value.sourceDbAuth
    })
    ElMessage.success('源数据配置保存成功')
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

function goBack() {
  router.push('/collect-task')
}

onMounted(() => {
  if (!taskNo.value) {
    ElMessage.warning('缺少任务编号，请从任务列表进入')
    router.push('/collect-task')
    return
  }
  loadDbTypeDict()
  loadExecType()
  loadTaskDet().then(() => {
    // 如果目标表名已有值，自动查询字段
    if (form.value.targetTable.trim()) {
      handleQueryColumns()
    }
  })
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
            <span class="task-no-tag">任务编号：{{ taskNo }}</span>
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

        <!-- ========== 上方：源数据配置 ========== -->
        <div class="section-card">
          <div class="section-title">
            <h3>源数据配置</h3>
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
              <div class="form-col">
                <el-form-item label="数据库类型" required>
                  <el-select v-model="form.sourceDbType" placeholder="请选择" popper-class="detail-popper">
                    <el-option v-for="opt in dbTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                  </el-select>
                </el-form-item>
              </div>
              <div class="form-col">
                <el-form-item label="数据库地址" required>
                  <el-input v-model="form.sourceDbHost" placeholder="如 127.0.0.1" maxlength="100" />
                </el-form-item>
              </div>
            </div>
            <div class="form-row">
              <div class="form-col form-col-small">
                <el-form-item label="端口">
                  <el-input v-model="form.sourceDbPort" placeholder="如 3306" maxlength="32" />
                </el-form-item>
              </div>
              <div class="form-col">
                <el-form-item label="用户名" required>
                  <el-input v-model="form.sourceDbUsr" placeholder="请输入用户名" maxlength="32" />
                </el-form-item>
              </div>
              <div class="form-col">
                <el-form-item label="密码">
                  <el-input v-model="form.sourceDbPwd" type="password" show-password placeholder="请输入密码" maxlength="32" />
                </el-form-item>
              </div>
              <div class="form-col">
                <el-form-item label="数据库" required>
                  <el-input v-model="form.sourceDbName" placeholder="请输入数据库名称" maxlength="64" />
                </el-form-item>
              </div>
            </div>
            <div v-if="form.sourceDbType === '03'" class="form-row">
              <div class="form-col form-col-small">
                <el-form-item label="认证方式" required>
                  <el-select v-model="form.sourceDbAuth" placeholder="请选择Hive认证方式" popper-class="detail-popper">
                    <el-option v-for="opt in hiveAuthOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                  </el-select>
                </el-form-item>
              </div>
            </div>
            <div class="form-row form-row-full">
              <el-form-item label="采集SQL" required class="full-width-item">
                <el-input v-model="form.collectSql" type="textarea" :rows="6" placeholder="请输入采集数据的SQL语句" />
              </el-form-item>
            </div>
          </el-form>
          <div class="section-footer">
            <el-button type="primary" :loading="savingSource" @click="handleSaveSource">保存源数据配置</el-button>
          </div>
        </div>

        <!-- ========== 下方：目标字段映射配置 ========== -->
        <div class="section-card">
          <div class="section-title">
            <h3>目标字段映射</h3>
          </div>
          <div class="target-table-row">
            <el-form label-width="100px" label-position="right" inline>
              <el-form-item label="目标表名" required>
                <el-input v-model="form.targetTable" placeholder="数据写入的目标表名" maxlength="64" style="width: 260px" />
              </el-form-item>
              <el-button type="primary" :loading="columnLoading" @click="handleQueryColumns" style="margin-left: 12px">
                查询字段
              </el-button>
            </el-form>
          </div>

          <div v-if="columnsQueried && tableColumns.length > 0" class="mapping-area">
            <div class="mapping-header">
              <span class="mapping-col mapping-col-source">源字段/别名</span>
              <span class="mapping-col mapping-col-target">目标字段</span>
              <span class="mapping-col mapping-col-info">类型</span>
              <span class="mapping-col mapping-col-info">注释</span>
            </div>
            <div class="mapping-row" v-for="(item, idx) in mappings" :key="idx">
              <span class="mapping-col mapping-col-source">
                <el-input v-model="item.sourceColumn" placeholder="源字段" maxlength="32" size="small" />
              </span>
              <span class="mapping-col mapping-col-target">
                <span class="field-text">{{ item.targetColumn }}</span>
              </span>
              <span class="mapping-col mapping-col-info">
                <span class="field-text">{{ tableColumns.find(c => c.columnName === item.targetColumn)?.columnType || '-' }}</span>
              </span>
              <span class="mapping-col mapping-col-info">
                <span class="field-text" :title="tableColumns.find(c => c.columnName === item.targetColumn)?.columnComment">
                  {{ tableColumns.find(c => c.columnName === item.targetColumn)?.columnComment || '-' }}
                </span>
              </span>
            </div>
          </div>

          <div v-else-if="columnsQueried && tableColumns.length === 0" class="empty-columns">
            <span>未查询到表字段信息，请确认目标表名是否正确</span>
          </div>

          <div v-else class="mapping-placeholder">
            <span>请输入目标表名后点击"查询字段"按钮</span>
          </div>

          <div class="section-footer">
            <el-button type="primary" :loading="savingMapping" @click="handleSaveMapping">保存字段映射</el-button>
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
  font-size: 13px;
  color: #00d4ff;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.25);
  padding: 4px 12px;
  border-radius: 6px;
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

.form-col-small {
  flex: 0 0 160px;
  max-width: 160px;
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

.mapping-header {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: rgba(0, 212, 255, 0.08);
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.65);
}

.mapping-row {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  transition: background 0.2s;

  &:hover {
    background: rgba(0, 212, 255, 0.04);
  }

  &:last-child {
    border-bottom: none;
  }
}

.mapping-col {
  padding: 0 6px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
}

.mapping-col-source {
  flex: 1;
  min-width: 0;
}

.mapping-col-target {
  flex: 1;
  min-width: 0;
}

.mapping-col-info {
  width: 140px;
  flex-shrink: 0;
}

.field-text {
  display: inline-block;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
