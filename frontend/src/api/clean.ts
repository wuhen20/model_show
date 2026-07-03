const BASE_URL = '/api/clean'

export interface CleanTask {
  taskNo: string
  taskName: string
  remark: string
  taskStatusCode: string
  taskStatusName: string
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

export async function saveCleanTask(taskName: string, remark: string): Promise<string> {
  const res = await fetch(`${BASE_URL}/save-clean-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskName, remark })
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

export async function executeCleanTask(taskNo: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/execute-clean-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskNo })
  })

  // 检查是否是 JSON 错误响应（非文件下载）
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const json = await res.json()
    throw new Error(json.message || '执行失败')
  }

  if (!res.ok) {
    throw new Error('执行失败')
  }

  // 触发浏览器下载
  const blob = await res.blob()
  const disposition = res.headers.get('content-disposition') || ''
  let filename = '清洗结果.xlsx'
  // 优先解析 filename*=UTF-8'' 格式（RFC 5987，支持中文）
  const starMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (starMatch) {
    filename = decodeURIComponent(starMatch[1])
  } else {
    // 兼容旧的 filename="..." 格式
    const match = disposition.match(/filename="?([^"]+)"?/)
    if (match) {
      try {
        filename = decodeURIComponent(match[1])
      } catch {
        filename = match[1]
      }
    }
  }
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
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
