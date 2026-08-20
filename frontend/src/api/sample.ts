const BASE_URL = '/api/sample'

export interface CodeDictItem {
  codeValue: string
  codeName: string
}

export interface CodeDictResult {
  SAMPLE_TYPE?: CodeDictItem[]
  QUALITY_LEVEL?: CodeDictItem[]
  SAMPLE_FIELD?: CodeDictItem[]
  DATABASE_TYPE?: CodeDictItem[]
  FILE_GET_MODE?: CodeDictItem[]
}

export async function getCodeDict(sortNo: string[] = ['SAMPLE_TYPE', 'QUALITY_LEVEL', 'SAMPLE_FIELD', 'DATABASE_TYPE']): Promise<CodeDictResult> {
  const params = sortNo.map(s => `sortNo=${encodeURIComponent(s)}`).join('&')
  const res = await fetch(`${BASE_URL}/code-dict?${params}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '获取字典编码失败')
  return json.data
}

export interface SaveSampleSetParams {
  setName: string
  description: string
  businessSystem: string
  sampleTypeCode: string
  sampleTypeName: string
  sampleFieldCode: string
  sampleFieldName: string
  sampleLabels?: string
}

export async function saveSampleSet(params: SaveSampleSetParams): Promise<void> {
  const res = await fetch(`${BASE_URL}/save-sample-set`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存失败')
}

export interface UpdateSampleSetParams {
  setNo: string
  description: string
  businessSystem: string
  sampleFieldCode: string
  sampleFieldName: string
  sampleLabels?: string
}

export async function updateSampleSet(params: UpdateSampleSetParams): Promise<void> {
  const res = await fetch(`${BASE_URL}/update-sample-set`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '更新失败')
}

export interface SampleSetRow {
  [key: string]: any
}

export async function querySampleSet(): Promise<SampleSetRow[]> {
  const res = await fetch(`${BASE_URL}/query-sample-set`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询样本集失败')
  return json.data || []
}

export interface SampleInfoRow {
  [key: string]: any
}

export async function getSamples(setNo: string, dirId?: string): Promise<SampleInfoRow[]> {
  let url = `${BASE_URL}/get-samples?setNo=${encodeURIComponent(setNo)}`
  if (dirId !== undefined) {
    url += `&dirId=${encodeURIComponent(dirId)}`
  }
  const res = await fetch(url)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询样本信息失败')
  return json.data || []
}

// ========== 目录管理 ==========

export interface DirectoryNode {
  dirId: string
  setNo: string
  parentId: string | null
  dirName: string
  dirPath: string
  createTime: string
  children?: DirectoryNode[]
}

export interface DirectoryPathItem {
  dirId: string
  dirName: string
  dirPath: string
}

export async function getDirectoryTree(setNo: string): Promise<DirectoryNode[]> {
  const res = await fetch(`${BASE_URL}/get-directory-tree?setNo=${encodeURIComponent(setNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询目录树失败')
  return json.data || []
}

export async function getDirectoryPath(dirId: string): Promise<DirectoryPathItem[]> {
  const res = await fetch(`${BASE_URL}/get-directory-path?dirId=${encodeURIComponent(dirId)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询目录路径失败')
  return json.data || []
}

export async function createDirectory(setNo: string, parentId: string, dirName: string): Promise<DirectoryNode> {
  const params = new URLSearchParams({ setNo, parentId, dirName })
  const res = await fetch(`${BASE_URL}/create-directory?${params}`, { method: 'POST' })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '创建目录失败')
  return json.data
}

export async function deleteDirectory(dirId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/delete-directory?dirId=${encodeURIComponent(dirId)}`, { method: 'POST' })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '删除目录失败')
}

export async function deleteSampleSet(setNo: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/delete-sample-set`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ setNo }),
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '删除样本集失败')
}

export function getImageUrl(filePath: string): string {
  return `${BASE_URL}/serve-image?filePath=${encodeURIComponent(filePath)}`
}

export interface AnnotationBox {
  classId: number
  className: string
  cx: number
  cy: number
  w: number
  h: number
}

export interface AnnotationData {
  hasAnnotations: boolean
  classNames: string[]
  boxes: AnnotationBox[]
}

export async function getAnnotations(sampleNo: string): Promise<AnnotationData> {
  const res = await fetch(`${BASE_URL}/get-annotations?sampleNo=${encodeURIComponent(sampleNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '获取标注信息失败')
  return json.data
}

export async function getClasses(setNo: string): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/get-classes?setNo=${encodeURIComponent(setNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '获取标签列表失败')
  return json.data || []
}

export async function getSamplesByLabels(setNo: string, labels: string[]): Promise<SampleInfoRow[]> {
  const res = await fetch(`${BASE_URL}/get-samples-by-labels?setNo=${encodeURIComponent(setNo)}&labels=${encodeURIComponent(labels.join(','))}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '标签筛选失败')
  return json.data || []
}

export async function getAudioText(sampleNo: string, sampleName: string): Promise<string | null> {
  const res = await fetch(`${BASE_URL}/get-audio-text?sampleNo=${encodeURIComponent(sampleNo)}&sampleName=${encodeURIComponent(sampleName)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '获取转写文字失败')
  return json.data?.audioText ?? null
}

export async function updateSampleScore(sampleNo: string, sampleName: string, scoreCode: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/update-sample-score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sampleNo, sampleName, scoreCode })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '评分失败')
}

export interface SampleImageRow {
  sampleNo: string
  sampleName: string
  suffix: string
  filePath: string
  fileSize: number
  labelThink: string
}

export async function randomSampleImages(setNo: string, count: number = 30): Promise<SampleImageRow[]> {
  const res = await fetch(`${BASE_URL}/random-sample-images`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ setNo, count })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '抽样失败')
  return json.data || []
}

export async function submitQualityInspection(setNo: string, averageStar: number): Promise<void> {
  const res = await fetch(`${BASE_URL}/submit-quality-inspection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ setNo, averageStar })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '提交质检评分失败')
}

export async function resetQualityLevel(setNo: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/reset-quality-level`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ setNo })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '重置质量等级失败')
}

export async function saveLabelThink(sampleNo: string, sampleName: string, labelThink: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/update-label-think`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sampleNo, sampleName, labelThink })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存思维链失败')
}

export interface SampleStatistic {
  setCount: number
  sampleCount: number
  labeledCount: number
  highQualityCount: number
  domainCount: number
  avgQualityScore: number
  avgQualityName: string
  monthNewCount: number
  monthQualityCount: number
  domainDistribution: { domain: string; setCount: number; sampleCount: number }[]
  qualityDistribution: { qualityName: string; count: number }[]
  typeDistribution: { typeName: string; count: number }[]
}

export async function getSampleStatistic(): Promise<SampleStatistic> {
  const res = await fetch(`${BASE_URL}/sample-statistic`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '获取统计数据失败')
  return json.data
}

export interface SampleTrend {
  months: string[]
  counts: number[]
}

export async function getSampleTrend(): Promise<SampleTrend> {
  const res = await fetch(`${BASE_URL}/sample-trend`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '获取趋势数据失败')
  return json.data
}

export async function uploadSamples(setNo: string, setName: string, typeCode: string, files: File[], dirId: string = ''): Promise<string> {
  const formData = new FormData()
  formData.append('setNo', setNo)
  formData.append('setName', setName)
  formData.append('typeCode', typeCode)
  formData.append('dirId', dirId)
  files.forEach(f => formData.append('files', f))
  const res = await fetch(`${BASE_URL}/upload-samples`, { method: 'POST', body: formData })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '上传失败')
  return json.message
}

export async function uploadSamplesBatch(
  setNo: string,
  setName: string,
  typeCode: string,
  file: File,
  majorVersionChange: boolean = false,
  versionRemark: string = '',
  dirId: string = ''
): Promise<string> {
  const formData = new FormData()
  formData.append('setNo', setNo)
  formData.append('setName', setName)
  formData.append('typeCode', typeCode)
  formData.append('file', file)
  formData.append('majorVersionChange', String(majorVersionChange))
  formData.append('versionRemark', versionRemark)
  formData.append('dirId', dirId)
  const res = await fetch(`${BASE_URL}/upload-samples-batch`, { method: 'POST', body: formData })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '批量导入失败')
  return json.message
}

// ========== 数据采集任务 ==========

export interface CollectTask {
  taskNo: string
  taskName: string
  remark: string
  createTime: string
  lastExecuteTime: string
  lastExecuteFlagCode: number
  lastExecuteFlagName: string
  taskStatusCode: string
  taskStatusName: string
  executeTypeCode: string
  executeTypeName: string
  cronFormula: string
  sampleTypeCode: string
  sampleSetNo: string
}

export async function getCollectTasks(): Promise<CollectTask[]> {
  const res = await fetch(`${BASE_URL}/query-collect-task`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询采集任务失败')
  return json.data
}

export async function saveCollectTask(
  taskName: string,
  remark: string,
  executeType: string = '01',
  cronFormula: string = '',
  sampleType: string = '',
  sampleSetNo: string = ''
): Promise<string> {
  const res = await fetch(`${BASE_URL}/save-collect-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskName, remark, executeType, cronFormula, sampleType, sampleSetNo })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存失败')
  return json.data.taskNo
}

export interface SampleSetOption {
  setNo: string
  setName: string
  setDescription: string
  businessSystem: string
  /** 时序类型样本集已绑定的目标表名（未绑定时为空） */
  bindingTable?: string | null
}

export async function querySampleSetByType(sampleType: string): Promise<SampleSetOption[]> {
  const res = await fetch(`${BASE_URL}/query-sample-set-by-type?sampleType=${encodeURIComponent(sampleType)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询样本集失败')
  return json.data || []
}

export interface CollectLog {
  recordId: number
  taskNo: string
  startTime: string
  endTime: string | null
  executeStatusCode: number
  executeStatusName: string
  executeLog: string
}

export async function getCollectLogs(taskNo: string): Promise<CollectLog[]> {
  const res = await fetch(`${BASE_URL}/query-collect-log?taskNo=${encodeURIComponent(taskNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询执行记录失败')
  return json.data || []
}

export interface CollectTaskDetParams {
  taskNo: string
  sourceDbId: number
  targetTable: string
  collectSql: string
  fileGetMode?: string
  bucketName?: string
  fileId?: string
  fileName?: string
}

export interface CollectTaskDet {
  taskNo: string
  sourceDbId: number | null
  sourceDbType: string | null
  sourceDbTypeName: string | null
  sourceDbAlias: string | null
  sourceDbHost: string | null
  sourceDbPort: string | null
  sourceDbUsr: string | null
  sourceDbName: string | null
  sourceDbAuth: string | null
  targetTable: string
  collectSql: string
  lastExecuteTime: string
  lastExecuteFlagCode: number
  lastExecuteFlagName: string
  sampleTypeCode?: string
  /** 关联原始样本集已绑定的目标表（时序任务，绑定后目标表名不可更改） */
  bindingTable?: string | null
  originalSampleSetNo?: string | null
  fileGetMode?: string
  bucketName?: string
  fileId?: string
  fileName?: string
}

export async function getCollectTaskDet(taskNo: string): Promise<CollectTaskDet | null> {
  const res = await fetch(`${BASE_URL}/query-collect-task-det?taskNo=${encodeURIComponent(taskNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询明细失败')
  return json.data
}

export interface TaskSampleSetInfo {
  originalSampleSetNo: string | null
  sampleSetName: string | null
  bindingTable: string | null
}

export async function getTaskSampleSet(taskNo: string): Promise<TaskSampleSetInfo | null> {
  const res = await fetch(`${BASE_URL}/query-task-sample-set?taskNo=${encodeURIComponent(taskNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询样本集信息失败')
  return json.data
}

export async function saveCollectTaskDet(params: CollectTaskDetParams): Promise<void> {
  const res = await fetch(`${BASE_URL}/save-collect-task-det`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存失败')
}

export async function testDbConnection(params: {
  dbType?: string
  host?: string
  port?: string
  user?: string
  pwd?: string
  database?: string
  auth?: string
  /** 按已保存的数据源配置测试（任务明细页使用，传此参数时忽略其他字段） */
  dbConfigId?: number
}): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${BASE_URL}/test-db-connection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  const json = await res.json()
  return { success: json.code === 0, message: json.message }
}

// ========== 数据源配置（s_database_config）==========

export interface DatabaseConfigItem {
  recordId: number
  dbTypeCode: string
  dbTypeName: string
  dbAlias: string
  dbHost: string
  dbPort: string
  dbUsr: string
  dbAuth: string | null
  dbName: string
  remark: string | null
  createTime: string
}

export async function queryDbConfig(): Promise<DatabaseConfigItem[]> {
  const res = await fetch(`${BASE_URL}/query-db-config`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询数据源配置失败')
  return json.data || []
}

export interface DbConfigParams {
  recordId?: number
  dbType?: string
  dbAlias: string
  dbHost: string
  dbPort: string
  dbUsr: string
  /** 新增必填；编辑留空表示不修改密码 */
  dbPwd: string
  dbAuth: string
  dbName: string
  remark: string
}

export async function saveDbConfig(params: DbConfigParams): Promise<void> {
  const res = await fetch(`${BASE_URL}/save-db-config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存失败')
}

export async function updateDbConfig(params: DbConfigParams): Promise<void> {
  const res = await fetch(`${BASE_URL}/update-db-config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '更新失败')
}

export async function deleteDbConfig(recordId: number): Promise<void> {
  const res = await fetch(`${BASE_URL}/delete-db-config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ recordId })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '删除失败')
}

export async function executeCollectTask(taskNo: string): Promise<string> {
  const res = await fetch(`${BASE_URL}/execute-collect-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskNo })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '执行失败')
  return json.message
}

export async function stopCollectTask(taskNo: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/stop-collect-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskNo })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '停止失败')
}

export async function deleteCollectTask(taskNo: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/delete-collect-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskNo })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '删除失败')
}

export interface UpdateExecTypeParams {
  taskNo: string
  executeType: string
  cronFormula: string
}

export async function updateCollectTaskExecType(params: UpdateExecTypeParams): Promise<void> {
  const res = await fetch(`${BASE_URL}/update-collect-task-exec-type`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存失败')
}

export interface TaskExecType {
  executeType: string
  executeTypeName: string
  cronFormula: string
}

export async function getCollectTaskExecType(taskNo: string): Promise<TaskExecType | null> {
  const res = await fetch(`${BASE_URL}/query-collect-task-exec-type?taskNo=${encodeURIComponent(taskNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data
}

// ========== 字段映射配置 ==========

export interface TableColumnInfo {
  columnName: string
  columnType: string
  columnComment: string
}

export async function queryTableColumns(taskNo: string, tableName: string): Promise<TableColumnInfo[]> {
  const res = await fetch(`${BASE_URL}/query-table-columns`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskNo, tableName })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询表字段失败')
  return json.data || []
}

export interface ColMapItem {
  sourceColumn: string
  targetColumn: string
}

export async function queryColMap(taskNo: string): Promise<ColMapItem[]> {
  const res = await fetch(`${BASE_URL}/query-col-map?taskNo=${encodeURIComponent(taskNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询映射失败')
  return json.data || []
}

export async function saveColMap(taskNo: string, targetTable: string, mappings: ColMapItem[]): Promise<void> {
  const res = await fetch(`${BASE_URL}/save-col-map`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskNo, targetTable, mappings })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存失败')
}
