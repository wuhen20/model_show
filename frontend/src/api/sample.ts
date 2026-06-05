const BASE_URL = '/api/sample'

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
