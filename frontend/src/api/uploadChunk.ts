/** 样本批量导入 - 分片上传 + 异步导入 API */

const BASE_URL = '/api/upload-chunk'

/** 默认分片大小（50MB），与后端 DEFAULT_CHUNK_SIZE 保持一致 */
export const DEFAULT_CHUNK_SIZE = 50 * 1024 * 1024

/** 导入任务状态码 */
export type TaskStatusCode =
  | '01' // 待上传
  | '02' // 上传中
  | '03' // 合并中
  | '04' // 导入中
  | '05' // 已完成
  | '06' // 失败
  | '07' // 已取消

export interface ImportTaskInfo {
  recordId: number
  taskNo: string
  setNo: string
  setName: string
  typeCode: string
  source: 'sample' | 'original'
  totalChunks: number
  uploadedChunks: number
  fileName: string
  fileSize: number
  taskStatusCode: TaskStatusCode
  taskStatusName: string
  majorVersionChange: number
  versionRemark: string
  imageCount: number
  txtCount: number
  skippedCount: number
  errorMessage: string
  createTime: string
  startTime: string
  finishTime: string
}

export interface InitChunkUploadParams {
  setNo: string
  setName: string
  typeCode: string
  fileName: string
  fileSize: number
  totalChunks: number
  source: 'sample' | 'original'
  majorVersionChange?: boolean
  versionRemark?: string
  dirId?: string
}

export interface InitChunkUploadResult {
  taskNo: string
  chunkSize: number
}

export interface UploadChunkResult {
  chunkIndex: number
  received: number
  uploadedChunks: number
  totalChunks: number
}

/** 初始化分片上传任务 */
export async function initChunkUpload(params: InitChunkUploadParams): Promise<InitChunkUploadResult> {
  const formData = new FormData()
  formData.append('setNo', params.setNo)
  formData.append('setName', params.setName)
  formData.append('typeCode', params.typeCode)
  formData.append('fileName', params.fileName)
  formData.append('fileSize', String(params.fileSize))
  formData.append('totalChunks', String(params.totalChunks))
  formData.append('source', params.source)
  formData.append('majorVersionChange', String(params.majorVersionChange || false))
  formData.append('versionRemark', params.versionRemark || '')
  formData.append('dirId', params.dirId || '')

  const res = await fetch(`${BASE_URL}/init`, { method: 'POST', body: formData })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '初始化失败')
  return json.data
}

/** 上传单个分片 */
export async function uploadChunk(
  taskNo: string,
  chunkIndex: number,
  totalChunks: number,
  chunk: Blob,
): Promise<UploadChunkResult> {
  const formData = new FormData()
  formData.append('taskNo', taskNo)
  formData.append('chunkIndex', String(chunkIndex))
  formData.append('chunks', String(totalChunks))
  formData.append('file', chunk)

  const res = await fetch(`${BASE_URL}/upload`, { method: 'POST', body: formData })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '分片上传失败')
  return json.data
}

/** 合并分片并触发异步导入 */
export async function mergeChunks(taskNo: string): Promise<{ taskNo: string; async: boolean }> {
  const formData = new FormData()
  formData.append('taskNo', taskNo)

  const res = await fetch(`${BASE_URL}/merge`, { method: 'POST', body: formData })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '合并失败')
  return json.data
}

/** 查询任务状态 */
export async function queryChunkStatus(taskNo: string): Promise<ImportTaskInfo> {
  const res = await fetch(`${BASE_URL}/status?taskNo=${encodeURIComponent(taskNo)}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data
}

/** 查询导入任务列表 */
export async function queryChunkList(setNo?: string): Promise<ImportTaskInfo[]> {
  const params = setNo ? `?setNo=${encodeURIComponent(setNo)}` : ''
  const res = await fetch(`${BASE_URL}/list${params}`)
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '查询失败')
  return json.data || []
}

/** 取消任务 */
export async function cancelChunkUpload(taskNo: string): Promise<void> {
  const formData = new FormData()
  formData.append('taskNo', taskNo)
  const res = await fetch(`${BASE_URL}/cancel`, { method: 'POST', body: formData })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '取消失败')
}

/** 删除任务记录 */
export async function deleteChunkTask(taskNo: string): Promise<void> {
  const formData = new FormData()
  formData.append('taskNo', taskNo)
  const res = await fetch(`${BASE_URL}/delete`, { method: 'POST', body: formData })
  const json = await res.json()
  if (json.code !== 0) throw new Error(json.message || '删除失败')
}

// ================ 高级封装：完整的分片上传流程 ================

export interface UploadProgressInfo {
  /** 当前阶段：uploading=上传分片, merging=合并导入中, done=完成, error=失败 */
  stage: 'uploading' | 'merging' | 'done' | 'error'
  /** 已上传分片数 */
  uploadedChunks: number
  /** 总分片数 */
  totalChunks: number
  /** 上传百分比（0-100） */
  percent: number
  /** 任务编号（init 后有值） */
  taskNo?: string
  /** 任务状态信息（合并后轮询有值） */
  taskInfo?: ImportTaskInfo
  /** 错误信息 */
  error?: string
}

export interface ChunkUploadOptions {
  /** 并行上传数（默认 3） */
  concurrency?: number
  /** 进度回调 */
  onProgress?: (info: UploadProgressInfo) => void
  /** 取消信号：返回 true 时中止上传 */
  shouldCancel?: () => boolean
}

/**
 * 完整的分片上传 + 触发异步导入流程：
 * 1. 文件分片
 * 2. 初始化任务
 * 3. 并行上传分片
 * 4. 触发合并（后端启动后台线程执行合并+导入）
 *
 * 注意：合并触发成功后立即返回，不在前端轮询等待导入完成。
 * 后端后台线程独立运行，不受前端弹窗/页面关闭影响。
 * 如需查看导入进度，调用 queryChunkStatus(taskNo) 主动查询。
 */
export async function uploadFileInChunks(
  file: File,
  params: Omit<InitChunkUploadParams, 'fileName' | 'fileSize' | 'totalChunks'>,
  options: ChunkUploadOptions = {},
): Promise<{ taskNo: string; merged: boolean }> {
  const concurrency = Math.max(1, options.concurrency || 3)
  const chunkSize = DEFAULT_CHUNK_SIZE

  // 1. 文件分片
  const totalChunks = Math.ceil(file.size / chunkSize)
  const chunks: Blob[] = []
  for (let i = 0; i < totalChunks; i++) {
    const start = i * chunkSize
    const end = Math.min(start + chunkSize, file.size)
    chunks.push(file.slice(start, end))
  }

  // 2. 初始化任务
  const initResult = await initChunkUpload({
    ...params,
    fileName: file.name,
    fileSize: file.size,
    totalChunks,
  })
  const taskNo = initResult.taskNo

  const emitProgress = (info: Partial<UploadProgressInfo>) => {
    options.onProgress?.({
      stage: 'uploading',
      uploadedChunks: 0,
      totalChunks,
      percent: 0,
      taskNo,
      ...info,
    } as UploadProgressInfo)
  }

  emitProgress({ uploadedChunks: 0, percent: 0 })

  // 3. 并行上传分片（带并发控制）
  let uploadedCount = 0
  let currentIndex = 0
  const failedChunks: number[] = []

  const uploadWorker = async () => {
    while (currentIndex < totalChunks) {
      if (options.shouldCancel?.()) {
        throw new Error('用户取消上传')
      }
      const idx = currentIndex++
      try {
        await uploadChunk(taskNo, idx, totalChunks, chunks[idx])
        uploadedCount++
        emitProgress({
          uploadedChunks: uploadedCount,
          percent: Math.round((uploadedCount / totalChunks) * 100),
        })
      } catch (e: any) {
        // 单片失败重试一次
        try {
          await uploadChunk(taskNo, idx, totalChunks, chunks[idx])
          uploadedCount++
          emitProgress({
            uploadedChunks: uploadedCount,
            percent: Math.round((uploadedCount / totalChunks) * 100),
          })
        } catch (e2: any) {
          failedChunks.push(idx)
          throw new Error(`分片 ${idx} 上传失败：${e2.message}`)
        }
      }
    }
  }

  // 启动并发工作线程
  const workers = Array.from({ length: Math.min(concurrency, totalChunks) }, () => uploadWorker())
  await Promise.all(workers)

  if (failedChunks.length > 0) {
    throw new Error(`部分分片上传失败：${failedChunks.join(', ')}`)
  }

  // 4. 触发合并（后端启动后台线程执行合并+导入，立即返回）
  emitProgress({ stage: 'merging', percent: 100 })
  await mergeChunks(taskNo)

  // 不再轮询等待导入完成，后端后台线程独立运行
  return { taskNo, merged: true }
}

/**
 * 轮询导入任务状态，直到完成/失败/取消
 */
export async function pollImportTask(
  taskNo: string,
  options: ChunkUploadOptions = {},
): Promise<ImportTaskInfo> {
  const POLL_INTERVAL = 2000 // 2 秒
  const POLL_TIMEOUT = 30 * 60 * 1000 // 30 分钟
  const startTime = Date.now()

  while (true) {
    if (options.shouldCancel?.()) {
      throw new Error('用户取消')
    }
    if (Date.now() - startTime > POLL_TIMEOUT) {
      throw new Error('导入任务超时')
    }

    const info = await queryChunkStatus(taskNo)
    options.onProgress?.({
      stage: 'merging',
      uploadedChunks: info.uploadedChunks,
      totalChunks: info.totalChunks,
      percent: 100,
      taskNo,
      taskInfo: info,
    })

    if (info.taskStatusCode === '05') {
      // 已完成
      options.onProgress?.({
        stage: 'done',
        uploadedChunks: info.uploadedChunks,
        totalChunks: info.totalChunks,
        percent: 100,
        taskNo,
        taskInfo: info,
      })
      return info
    }
    if (info.taskStatusCode === '06') {
      // 失败
      options.onProgress?.({
        stage: 'error',
        uploadedChunks: info.uploadedChunks,
        totalChunks: info.totalChunks,
        percent: 100,
        taskNo,
        taskInfo: info,
        error: info.errorMessage || '导入失败',
      })
      throw new Error(info.errorMessage || '导入失败')
    }
    if (info.taskStatusCode === '07') {
      // 已取消
      throw new Error('任务已取消')
    }

    // 等待下一轮轮询
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL))
  }
}
