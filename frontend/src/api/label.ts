const BASE_URL = '/api/label'

// ==================== 类型定义 ====================

export interface LabelTask {
  taskNo: string
  taskName: string
  originalSampleSetNo: string
  originalSampleSetName: string
  sampleLabels: string
  taskStatus: string
  taskStatusName: string
  createTime: string
  finishTime: string | null
  totalCount: number
  labeledCount: number
}

export interface LabelTaskDetail extends LabelTask {}

export interface LabelSampleRow {
  recordId: string
  taskNo: string
  sampleNo: string
  sampleName: string
  filePath: string
  labelContent: string | null
  labelFlag: string
  updateTime: string
}

export interface LabelSampleDetail extends LabelSampleRow {}

// ==================== API 函数 ====================

/** 查询标注任务列表 */
export async function getLabelTasks(): Promise<LabelTask[]> {
  const res = await fetch(`${BASE_URL}/tasks`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data || []
}

/** 查询任务详情 */
export async function getLabelTaskDetail(taskNo: string): Promise<LabelTaskDetail> {
  const res = await fetch(`${BASE_URL}/tasks/${taskNo}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data
}

/** 创建标注任务 */
export async function createLabelTask(
  taskName: string,
  originalSampleSetNo: string,
  sampleLabels: string
): Promise<string> {
  const res = await fetch(`${BASE_URL}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskName, originalSampleSetNo, sampleLabels })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '创建失败')
  return json.data?.taskNo || ''
}

/** 编辑任务 */
export async function updateLabelTask(
  taskNo: string,
  taskName: string,
  sampleLabels: string
): Promise<void> {
  const res = await fetch(`${BASE_URL}/tasks/${taskNo}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskName, sampleLabels })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '更新失败')
}

/** 删除任务 */
export async function deleteLabelTask(taskNo: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/tasks/${taskNo}`, {
    method: 'DELETE'
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '删除失败')
}

/** 更新任务状态 */
export async function updateLabelTaskStatus(taskNo: string, status: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/tasks/${taskNo}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '状态更新失败')
}

/** 分页查询任务明细 */
export async function getLabelTaskSamples(
  taskNo: string,
  page: number = 1,
  pageSize: number = 50
): Promise<{ total: number; rows: LabelSampleRow[] }> {
  const res = await fetch(`${BASE_URL}/tasks/${taskNo}/samples?page=${page}&pageSize=${pageSize}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return { total: json.data.total, rows: json.data.rows || [] }
}

/** 获取单条明细的标注内容 */
export async function getLabelSample(recordId: string): Promise<LabelSampleDetail> {
  const res = await fetch(`${BASE_URL}/samples/${recordId}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data
}

/** 保存标注内容 */
export async function saveLabelContent(
  recordId: string,
  labelContent: string,
  labelFlag: string
): Promise<void> {
  const res = await fetch(`${BASE_URL}/samples/${recordId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ labelContent, labelFlag })
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '保存失败')
}
