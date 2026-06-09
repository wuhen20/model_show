// 后端 API 封装：训练数据集管理
import type {
  DatasetBrief,
  DatasetDetail,
  YoloPreviewItem,
} from '@/data/models'

const BASE_URL = (import.meta as any).env?.VITE_API_BASE || ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
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

export const datasetsApi = {
  /** 列表（支持过滤） */
  list: (filters?: { scene?: string; format?: string; dataset_type?: string; model_code?: string }) => {
    const params = new URLSearchParams()
    if (filters?.scene) params.append('scene', filters.scene)
    if (filters?.format) params.append('format', filters.format)
    if (filters?.dataset_type) params.append('dataset_type', filters.dataset_type)
    if (filters?.model_code) params.append('model_code', filters.model_code)
    const qs = params.toString()
    return request<DatasetBrief[]>(`/api/datasets${qs ? '?' + qs : ''}`)
  },

  /** 创建数据集（ZIP 上传） */
  create: (formData: FormData) =>
    fetch(`${BASE_URL}/api/datasets`, {
      method: 'POST',
      body: formData,
    }).then(async (r) => {
      if (!r.ok) throw new Error(await r.text())
      const json = await r.json()
      if (json.code !== 0) throw new Error(json.message || '创建失败')
      return json.data as DatasetDetail
    }),

  /** 详情 */
  detail: (id: number) => request<DatasetDetail>(`/api/datasets/${id}`),

  /** 删除 */
  delete: (id: number) =>
    fetch(`${BASE_URL}/api/datasets/${id}`, { method: 'DELETE' }).then(async (r) => {
      if (!r.ok) throw new Error(await r.text())
      return (await r.json()) as { code: number; message: string }
    }),

  /** 上传新版本（ZIP） */
  uploadVersion: (id: number, formData: FormData) =>
    fetch(`${BASE_URL}/api/datasets/${id}/versions`, {
      method: 'POST',
      body: formData,
    }).then(async (r) => {
      if (!r.ok) throw new Error(await r.text())
      const json = await r.json()
      if (json.code !== 0) throw new Error(json.message || '上传失败')
      return json.data as DatasetDetail
    }),

  /** 通用预览 */
  preview: (id: number, page: number = 1, size?: number) =>
    request<any>(`/api/datasets/${id}/preview?page=${page}${size ? `&size=${size}` : ''}`),

  /** YOLO 标注预览（分页） */
  yoloPreview: (id: number, page: number = 1, size: number = 20) =>
    request<{ items: YoloPreviewItem[]; total: number; page: number; page_size: number }>(
      `/api/datasets/${id}/yolo-preview?page=${page}&size=${size}`
    ),

  /** 统计信息 */
  stats: (id: number) => request<any>(`/api/datasets/${id}/stats`),

  /** 删除版本 */
  deleteVersion: (dsId: number, vid: number) =>
    fetch(`${BASE_URL}/api/datasets/${dsId}/versions/${vid}`, { method: 'DELETE' }).then(async (r) => {
      if (!r.ok) throw new Error(await r.text())
      return (await r.json()) as { code: number; message: string }
    }),
}