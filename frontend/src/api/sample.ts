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
}

export async function getCodeDict(sortNo: string[] = ['SAMPLE_TYPE', 'QUALITY_LEVEL', 'SAMPLE_FIELD', 'DATABASE_TYPE']): Promise<CodeDictResult> {
  const params = sortNo.map(s => `sortNo=${encodeURIComponent(s)}`).join('&')
  const res = await fetch(`${BASE_URL}/code-dict?${params}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '获取字典编码失败')
  return json.data
}

export interface SaveSampleSetParams {
  setCode: string
  setName: string
  description: string
  businessSystem: string
  sampleTypeCode: string
  sampleTypeName: string
  sampleFieldCode: string
  sampleFieldName: string
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

export async function getSamples(setNo: string): Promise<SampleInfoRow[]> {
  const res = await fetch(`${BASE_URL}/get-samples?setNo=${encodeURIComponent(setNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询样本信息失败')
  return json.data || []
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

export async function getAnnotations(filePath: string): Promise<AnnotationData> {
  const res = await fetch(`${BASE_URL}/get-annotations?filePath=${encodeURIComponent(filePath)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '获取标注信息失败')
  return json.data
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

export async function uploadSamples(setNo: string, setName: string, typeCode: string, files: File[]): Promise<string> {
  const formData = new FormData()
  formData.append('setNo', setNo)
  formData.append('setName', setName)
  formData.append('typeCode', typeCode)
  files.forEach(f => formData.append('files', f))
  const res = await fetch(`${BASE_URL}/upload-samples`, { method: 'POST', body: formData })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '上传失败')
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
  cronFormula: string = ''
): Promise<string> {
  const res = await fetch(`${BASE_URL}/save-collect-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskName, remark, executeType, cronFormula })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存失败')
  return json.data.taskNo
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
  sourceDbType: string
  sourceDbHost: string
  sourceDbPort: string
  sourceDbUsr: string
  sourceDbPwd: string
  sourceDbName: string
  targetTable: string
  collectSql: string
}

export interface CollectTaskDet {
  taskNo: string
  sourceDbType: string
  sourceDbHost: string
  sourceDbPort: string
  sourceDbUsr: string
  sourceDbPwd: string
  sourceDbName: string
  targetTable: string
  collectSql: string
  lastExecuteTime: string
  lastExecuteFlagCode: number
  lastExecuteFlagName: string
}

export async function getCollectTaskDet(taskNo: string): Promise<CollectTaskDet | null> {
  const res = await fetch(`${BASE_URL}/query-collect-task-det?taskNo=${encodeURIComponent(taskNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询明细失败')
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
