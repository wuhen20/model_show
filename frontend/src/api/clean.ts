const BASE_URL = '/api/clean'

export interface CleanTask {
  taskNo: string
  taskName: string
  remark: string
  taskStatusCode: string
  taskStatusName: string
  sampleType: string
  createTime: string
  lastExecuteTime: string
  lastExecuteFlagCode: number
  lastExecuteFlagName: string
}

export interface CleanTaskNodeConfig {
  tableName?: string
  fields?: string[]
}

export interface CleanTaskNode {
  nodeId: string
  nodeType: string
  nodeName: string
  nodeConfig: CleanTaskNodeConfig
  posX: number
  posY: number
  prevNodeId: string | null
}

export interface CleanTaskDetail {
  taskNo: string
  taskName: string
  remark: string
  taskStatusCode: string
  taskStatusName: string
  createTime: string
  lastExecuteTime: string
  lastExecuteFlagCode: number
  lastExecuteFlagName: string
  nodes: CleanTaskNode[]
}

export interface TableColumnInfo {
  fieldName: string
  fieldType: string
  fieldKey: string
  fieldNull: string
}

export async function getCleanTasks(): Promise<CleanTask[]> {
  const res = await fetch(`${BASE_URL}/query-clean-tasks`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data || []
}

export async function saveCleanTask(
  taskName: string,
  remark: string,
  sampleType: string = '',
  originalSampleSetNo: string = '',
  cleanTypes: string = ''
): Promise<string> {
  const res = await fetch(`${BASE_URL}/save-clean-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskName, remark, sampleType, originalSampleSetNo, cleanTypes })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存失败')
  return json.data.taskNo
}

export async function getCleanTaskDetail(taskNo: string): Promise<CleanTaskDetail> {
  const res = await fetch(`${BASE_URL}/query-clean-task-detail?taskNo=${encodeURIComponent(taskNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data
}

export async function saveCleanTaskNodes(taskNo: string, nodes: any[]): Promise<void> {
  const res = await fetch(`${BASE_URL}/save-clean-task-nodes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskNo, nodes })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存失败')
}

export async function deleteCleanTask(taskNo: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/delete-clean-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskNo })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '删除失败')
}

export async function queryDatabaseTables(): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/query-database-tables`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data || []
}

export async function queryCleanTableColumns(tableName: string): Promise<TableColumnInfo[]> {
  const res = await fetch(`${BASE_URL}/query-clean-table-columns?tableName=${encodeURIComponent(tableName)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data || []
}

export async function executeCleanTask(taskNo: string): Promise<{ fileName: string; filePath: string; resultCount: number }> {
  const res = await fetch(`${BASE_URL}/execute-clean-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskNo })
  })

  const contentType = res.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) {
    throw new Error('执行失败：响应格式异常')
  }

  const json = await res.json()
  if (json.code !== 0) {
    throw new Error(json.message || '执行失败')
  }
  return {
    fileName: json.data?.fileName || '',
    filePath: json.data?.filePath || '',
    resultCount: json.data?.resultCount || 0
  }
}

export interface CleanLog {
  recordId: number
  taskNo: string
  startTime: string
  endTime: string
  executeStatusCode: string
  executeStatusName: string
  totalCount: number
  removedCount: number
  resultCount: number
  executeLog: string
}

export async function getCleanLogs(taskNo: string): Promise<CleanLog[]> {
  const res = await fetch(`${BASE_URL}/query-clean-log?taskNo=${encodeURIComponent(taskNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data || []
}

// ========== 清洗结果 ==========

export interface CleanResult {
  recordId: number
  taskNo: string
  taskName: string
  sampleTypeCode: string
  startTime: string
  endTime: string
  resultCount: number
  fileName: string
  filePath: string
}

export async function getCleanResults(): Promise<CleanResult[]> {
  const res = await fetch(`${BASE_URL}/query-clean-results`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data || []
}

// ========== 清洗结果查看/下载 ==========

export interface CleanResultData {
  taskNo: string
  taskName: string
  executeTime: string
  totalCount: number
  removedCount: number
  resultCount: number
  columns: string[]
  rows: Record<string, any>[]
}

export async function viewCleanResult(recordId: number): Promise<CleanResultData> {
  const res = await fetch(`${BASE_URL}/view-clean-result?recordId=${recordId}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查看失败')
  return json.data
}

export function getDownloadCleanResultUrl(recordId: number, format: 'json' | 'excel'): string {
  return `${BASE_URL}/download-clean-result?recordId=${recordId}&format=${format}`
}

// ========== 清洗结果入库 ==========

export interface SampleSetOption {
  setNo: string
  setName: string
  typeCode: string
}

export async function getSampleSetOptions(typeCode: string = ''): Promise<SampleSetOption[]> {
  const params = typeCode ? `?typeCode=${encodeURIComponent(typeCode)}` : ''
  const res = await fetch(`${BASE_URL}/sample-set-options${params}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询样本集失败')
  return json.data || []
}

export interface ImportToSampleResult {
  count: number
  sampleNo: string
  preVersion?: string
  nextVersion?: string
}

export async function importToSample(
  recordId: number,
  setNo: string,
  sampleName: string = '',
  majorVersionChange: boolean = false,
  versionRemark: string = ''
): Promise<ImportToSampleResult> {
  const res = await fetch(`${BASE_URL}/import-to-sample`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ recordId, setNo, sampleName, majorVersionChange, versionRemark })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '入库失败')
  return {
    count: json.data?.count ?? 0,
    sampleNo: json.data?.sampleNo ?? '',
    preVersion: json.data?.preVersion,
    nextVersion: json.data?.nextVersion
  }
}

// ========== 图像样本清洗 ==========

export interface PicCleanType {
  codeValue: string
  codeName: string
  spare1: string
}

export async function queryPicCleanTypes(): Promise<PicCleanType[]> {
  const res = await fetch(`${BASE_URL}/query-pic-clean-types`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询清洗类型失败')
  return json.data || []
}

export interface OriginalSampleSetOption {
  setNo: string
  setName: string
}

export async function queryOriginalSampleSetOptions(typeCode: string = ''): Promise<OriginalSampleSetOption[]> {
  const params = typeCode ? `?typeCode=${encodeURIComponent(typeCode)}` : ''
  const res = await fetch(`${BASE_URL}/original-sample-set-options${params}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询原始样本集失败')
  return json.data || []
}

// ========== 图像清洗结果（被清洗图片） ==========

export interface CleanPicRecord {
  recordId: number
  taskNo: string
  cleanType: string
  cleanTypeName: string
  fileName: string
  filePath: string
}

export async function queryCleanPics(taskNo: string): Promise<CleanPicRecord[]> {
  const res = await fetch(`${BASE_URL}/query-clean-pics?taskNo=${encodeURIComponent(taskNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询清洗图片失败')
  return json.data || []
}

/** 构造被清洗图片的展示 URL */
export function getCleanPicImageUrl(filePath: string): string {
  return `${BASE_URL}/serve-image?filePath=${encodeURIComponent(filePath)}`
}

export async function rollbackCleanPics(taskNo: string): Promise<{ restoredCount: number; skippedCount: number }> {
  const res = await fetch(`${BASE_URL}/rollback-clean-pics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskNo })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '回滚失败')
  return json.data
}
