const BASE_URL = '/api/original-sample'

export interface CodeDictItem {
  codeValue: string
  codeName: string
}

export interface CodeDictResult {
  SAMPLE_TYPE?: CodeDictItem[]
  QUALITY_LEVEL?: CodeDictItem[]
  SAMPLE_FIELD?: CodeDictItem[]
}

export async function getCodeDict(sortNo: string[] = ['SAMPLE_TYPE', 'QUALITY_LEVEL', 'SAMPLE_FIELD']): Promise<CodeDictResult> {
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

export async function deleteOriginalSampleSet(setNo: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/delete-original-sample-set`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ setNo }),
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '删除样本集失败')
}

export interface TimeSeriesColumn {
  key: string
  label: string
}

export interface TimeSeriesData {
  targetTable: string | null
  total: number
  rows: SampleInfoRow[]
  columns: TimeSeriesColumn[]
}

export async function queryTimeSeriesData(
  setNo: string,
  page: number = 1,
  pageSize: number = 20
): Promise<TimeSeriesData> {
  const params = new URLSearchParams({
    setNo,
    page: String(page),
    pageSize: String(pageSize)
  })
  const res = await fetch(`${BASE_URL}/query-time-series-data?${params}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询时序数据失败')
  return json.data || { targetTable: null, total: 0, rows: [], columns: [] }
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

export async function saveLabelThink(sampleNo: string, sampleName: string, labelThink: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/update-label-think`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sampleNo, sampleName, labelThink })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存思维链失败')
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

export async function uploadSamplesBatch(setNo: string, setName: string, typeCode: string, file: File, dirId: string = ''): Promise<string> {
  const formData = new FormData()
  formData.append('setNo', setNo)
  formData.append('setName', setName)
  formData.append('typeCode', typeCode)
  formData.append('file', file)
  formData.append('dirId', dirId)
  const res = await fetch(`${BASE_URL}/upload-samples-batch`, { method: 'POST', body: formData })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '批量导入失败')
  return json.message
}
