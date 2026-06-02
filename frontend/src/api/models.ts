// 后端 API 封装：小模型管理 / 首页统计 / 统一推理
import type { DashboardStats, InvokeTrendPoint, ModelBrief, ModelDetail, SceneInfo } from '@/data/models'

// 默认走 Vite proxy（/api -> http://localhost:3002），可通过 VITE_API_BASE 覆盖
const BASE_URL = (import.meta as any).env?.VITE_API_BASE || ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init
  })
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${await resp.text()}`)
  }
  const json = await resp.json()
  if (json.code !== 0) {
    throw new Error(json.message || `API error: ${path}`)
  }
  return json.data as T
}

// ========== 首页 ==========
export const dashboardApi = {
  stats: () => request<DashboardStats>('/api/dashboard/stats'),
  sceneSummary: () => request<SceneInfo[]>('/api/dashboard/scene-summary'),
  invokeTrend: (range = 24, granularity = 5) =>
    request<InvokeTrendPoint[]>(`/api/dashboard/invoke-trend?range=${range}&granularity=${granularity}`),
  recent: () => request<{ training: unknown[]; mcp: unknown[]; logs: unknown[] }>('/api/dashboard/recent')
}

// ========== 小模型管理 ==========
export const modelsApi = {
  listScenes: () => request<SceneInfo[]>('/api/models/scenes'),
  list: (filters: { scene?: string; status?: string } = {}) => {
    const params = new URLSearchParams()
    if (filters.scene) params.append('scene', filters.scene)
    if (filters.status) params.append('status', filters.status)
    const qs = params.toString()
    return request<ModelBrief[]>(`/api/models${qs ? '?' + qs : ''}`)
  },
  detail: (code: string) => request<ModelDetail>(`/api/models/${code}`),
  online: (code: string) =>
    request<{ code: string; status: string }>(`/api/models/${code}/online`, { method: 'POST' }),
  offline: (code: string) =>
    request<{ code: string; status: string }>(`/api/models/${code}/offline`, { method: 'POST' })
}

// ========== 统一推理 ==========
export interface PredictResult {
  code: string
  output: Record<string, any>
  latency_ms: number
  trace_id?: string
  mock?: boolean
}

export const predictApi = {
  invoke: (code: string, input: unknown, subScene?: string) =>
    fetch(`${BASE_URL}/api/predict/${code}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input, sub_scene: subScene })
    }).then(async (r) => {
      if (!r.ok) throw new Error(await r.text())
      return (await r.json()) as PredictResult
    })
}
