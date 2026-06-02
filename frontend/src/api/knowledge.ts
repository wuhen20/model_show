const API_BASE = '/api/knowledge'

async function request<T>(url: string): Promise<T> {
  const res = await fetch(url)
  const data = await res.json()
  if (data.code !== 0) {
    throw new Error(data.message || '请求失败')
  }
  return data.data as T
}

export interface KnowledgeStats {
  total_count: number
  structured_count: number
  unstructured_count: number
  graph_entities: number
  business_domains: number
  completeness: number
  availability: number
}

export interface KnowledgeCategory {
  id: string
  name: string
  description: string
  parent_id: string | null
  doc_count: number
  icon: string
  color: string
  sub_categories?: SubCategory[]
}

export interface SubCategory {
  id: string
  name: string
  doc_count: number
  color: string
}

export interface KnowledgeItem {
  id: string
  title: string
  category_id: string
  category_name: string
  parent_category: string
  knowledge_type: string
  source: string
  score: number
  status: string
  update_time: string
  file_path: string
  description: string
}

export interface KnowledgeDetail extends KnowledgeItem {
  content: string
  tags: string[]
}

export interface SourceDistribution {
  name: string
  value: number
  count: number
  color: string
}

export interface CategoryDistribution {
  name: string
  value: number
  count: number
  color: string
}

export interface QualityMetrics {
  overall_score: number
  metrics: { name: string; value: number }[]
}

export function fetchKnowledgeStats(): Promise<KnowledgeStats> {
  return request(`${API_BASE}/stats`)
}

export function fetchCategories(parentId?: string): Promise<KnowledgeCategory[]> {
  const params = parentId ? `?parent_id=${parentId}` : ''
  return request(`${API_BASE}/categories${params}`)
}

export function fetchKnowledgeList(params?: {
  category_id?: string
  tab?: string
  keyword?: string
  page?: number
  page_size?: number
  workspace?: string
}): Promise<{ items: KnowledgeItem[]; total: number; page: number; page_size: number; status_counts?: Record<string, number> }> {
  const searchParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) searchParams.set(k, String(v))
    })
  }
  const qs = searchParams.toString()
  return request(`${API_BASE}/list${qs ? '?' + qs : ''}`)
}

export function fetchKnowledgeDetail(id: string): Promise<KnowledgeDetail> {
  return request(`${API_BASE}/detail/${id}`)
}

export function fetchSourceDistribution(): Promise<SourceDistribution[]> {
  return request(`${API_BASE}/source-distribution`)
}

export function fetchCategoryDistribution(): Promise<CategoryDistribution[]> {
  return request(`${API_BASE}/category-distribution`)
}

export function fetchQualityMetrics(): Promise<QualityMetrics> {
  return request(`${API_BASE}/quality-metrics`)
}

// --- Knowledge base ---

export interface KnowledgeBase {
  id: string
  name: string
  workspace: string
  description: string
  icon: string
  color: string
  doc_count: number
  status_counts: Record<string, number>
}

export function fetchKnowledgeBases(): Promise<KnowledgeBase[]> {
  return request(`${API_BASE}/bases`)
}

// --- Pipeline status ---

export interface PipelineStatus {
  busy: boolean
  job_name: string
  docs: number
  cur_batch: number
  batches: number
  latest_message: string
}

export function fetchPipelineStatus(workspace?: string): Promise<PipelineStatus> {
  const params = workspace ? `?workspace=${workspace}` : ''
  return request(`${API_BASE}/pipeline-status${params}`)
}

// --- Knowledge graph ---

export interface GraphNode {
  name: string
  symbolSize: number
  category: number
  itemStyle: { color: string }
  label?: { show: boolean }
}

export interface GraphLink {
  source: string
  target: string
}

export interface GraphStats {
  entity_count: number
  relation_count: number
  coverage: number
}

export interface KnowledgeGraph {
  nodes: GraphNode[]
  links: GraphLink[]
  stats: GraphStats
}

export function fetchKnowledgeGraph(workspace?: string): Promise<KnowledgeGraph> {
  const params = workspace ? `?workspace=${workspace}` : ''
  return request(`${API_BASE}/graph${params}`)
}
