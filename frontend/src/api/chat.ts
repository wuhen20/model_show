// 开发环境通过 Vite proxy 代理 /api → localhost:3002
const BASE_URL = '/api'
// SSE 流式调用绕开 Vite proxy 以获取更稳定的流传输
const DIRECT_URL = 'http://localhost:3002/api'

export interface ModelInfo {
  id: string
  name: string
  type: string
  description: string
}

export interface ChatRequest {
  modelId: string
  question: string
  history?: { role: string; content: string }[]
}

export interface ChatResponse {
  content: string
  suggestions: string[]
  tokens: number
  model: string
  timestamp: string
  file?: {
    name: string
    size: number
    url: string
  }
}

export interface ApiResult<T> {
  code: number
  data?: T
  message?: string
}

export async function fetchModels(): Promise<ModelInfo[]> {
  // 注意：与 /api/models（小模型管理）区分；此处获取对话用 LLM 列表。
  const res = await fetch(`${BASE_URL}/llm-models`)
  const json: ApiResult<ModelInfo[]> = await res.json()
  if (json.code !== 0) throw new Error(json.message || '获取模型列表失败')
  return json.data || []
}

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  })
  const json: ApiResult<ChatResponse> = await res.json()
  if (json.code !== 0) throw new Error(json.message || '请求失败')
  return json.data!
}

export async function sendChatStream(
  request: ChatRequest,
  onChunk: (content: string) => void,
  onComplete: (meta: { tokens: number; model: string; timestamp: string }) => void,
  onError: (error: string) => void
): Promise<void> {
  console.log('[sendChatStream] 开始请求, request:', request)
  const res = await fetch(`${DIRECT_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...request, stream: true })
  })
  console.log('[sendChatStream] 响应状态:', res.status, 'Content-Type:', res.headers.get('content-type'))

  if (!res.ok) {
    const json = await res.json()
    throw new Error(json.message || '请求失败')
  }

  const reader = res.body?.getReader()
  console.log('[sendChatStream] reader:', !!reader)
  const decoder = new TextDecoder('utf-8')
  let contentBuffer = ''
  let emittedLength = 0
  const END_MARKER = '\n\n---END---\n'
  const ERROR_MARKER = '\n\n---ERROR---\n'

  if (!reader) throw new Error('无法获取响应流')

  let chunkCount = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) { console.log('[sendChatStream] 流结束, 总chunk数:', chunkCount); break }

      const chunk = decoder.decode(value, { stream: true })
      chunkCount++
      if (chunkCount <= 3) console.log('[sendChatStream] chunk', chunkCount, ':', chunk.substring(0, 50))
      contentBuffer += chunk

      if (contentBuffer.includes(END_MARKER)) {
        console.log('[sendChatStream] 检测到 END_MARKER')
        const [contentPart, metaPart] = contentBuffer.split(END_MARKER)
        const newContent = contentPart.slice(emittedLength)
        if (newContent) onChunk(newContent)
        try {
          const meta = JSON.parse(metaPart)
          onComplete(meta)
        } catch (e) {
          console.error('解析元数据失败:', e)
        }
        return
      }

      if (contentBuffer.includes(ERROR_MARKER)) {
        console.log('[sendChatStream] 检测到 ERROR_MARKER')
        const [, errorPart] = contentBuffer.split(ERROR_MARKER)
        try {
          const errorData = JSON.parse(errorPart)
          onError(errorData.message || '未知错误')
        } catch (e) {
          onError('解析错误信息失败')
        }
        return
      }

      const newContent = contentBuffer.slice(emittedLength)
      if (newContent) {
        onChunk(newContent)
        emittedLength = contentBuffer.length
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function sendChatWithFile(
  modelId: string,
  question: string,
  file: File
): Promise<ChatResponse> {
  const formData = new FormData()
  formData.append('modelId', modelId)
  formData.append('question', question)
  formData.append('file', file)

  const res = await fetch(`${BASE_URL}/chat/upload`, {
    method: 'POST',
    body: formData
  })
  const json: ApiResult<ChatResponse> = await res.json()
  if (json.code !== 0) throw new Error(json.message || '请求失败')
  return json.data!
}