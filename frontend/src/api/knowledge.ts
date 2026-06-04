const API_BASE = '/api/knowledge'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
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
  tags?: TagResponse[]
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
  /** Detail fields for the graph detail dialog */
  entityType?: string
  description?: string
  kbName?: string
  degree?: number
}

export interface GraphLink {
  source: string
  target: string
  /** Detail fields for the graph detail dialog */
  relType?: string
  description?: string
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

export function fetchKnowledgeGraph(workspace?: string, kbName?: string, maxNodes?: number): Promise<KnowledgeGraph> {
  const params = new URLSearchParams()
  if (workspace) params.set('workspace', workspace)
  if (kbName) params.set('kb_name', kbName)
  if (maxNodes) params.set('max_nodes', String(maxNodes))
  const qs = params.toString()
  return request(`${API_BASE}/graph${qs ? '?' + qs : ''}`)
}

// ===========================================================================
// Knowledge Base Management API (Phase 1+)
// ===========================================================================

// --- Tags ---

export interface TagCreatePayload {
  level: number
  name: string
  parent_tag_id?: string | null
  children?: TagCreatePayload[]
}

export interface TagResponse {
  id: string
  kb_id?: string
  level: number
  name: string
  parent_tag_id?: string | null
  children?: TagResponse[]
}

// --- Knowledge Base CRUD ---

export interface KBCreatePayload {
  name: string
  description?: string
  icon?: string
  color?: string
  chunk_size?: number
  chunk_overlap?: number
  chunking_strategy?: string
  parent_chunk_size?: number
  chunk_separator?: string
  tags?: TagCreatePayload[]
}

export interface KBUpdatePayload {
  name?: string
  description?: string
  icon?: string
  color?: string
  chunk_size?: number
  chunk_overlap?: number
  chunking_strategy?: string
  parent_chunk_size?: number
  chunk_separator?: string
}

export interface KBResponse {
  id: string
  name: string
  workspace: string
  description: string
  icon: string
  color: string
  chunk_size: number
  chunk_overlap: number
  chunking_strategy: string
  parent_chunk_size: number
  chunk_separator: string
  doc_count: number
  tags: TagResponse[]
  created_at: string
  updated_at: string
}

export function createKnowledgeBase(data: KBCreatePayload): Promise<KBResponse> {
  return request(`${API_BASE}/bases`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function fetchKnowledgeBaseDetail(kbId: string): Promise<KBResponse> {
  return request(`${API_BASE}/bases/${kbId}`)
}

export function updateKnowledgeBase(kbId: string, data: KBUpdatePayload): Promise<KBResponse> {
  return request(`${API_BASE}/bases/${kbId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteKnowledgeBase(kbId: string): Promise<void> {
  return request(`${API_BASE}/bases/${kbId}`, { method: 'DELETE' })
}

// --- Tags API ---

export function fetchKBTags(kbId: string): Promise<TagResponse[]> {
  return request(`${API_BASE}/bases/${kbId}/tags`)
}

export function createKBTag(kbId: string, data: TagCreatePayload): Promise<TagResponse[]> {
  return request(`${API_BASE}/bases/${kbId}/tags`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateTag(tagId: string, data: { name?: string; level?: number; parent_tag_id?: string | null }): Promise<TagResponse> {
  return request(`${API_BASE}/tags/${tagId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteTag(tagId: string): Promise<void> {
  return request(`${API_BASE}/tags/${tagId}`, { method: 'DELETE' })
}

// --- Documents ---

export interface DocumentResponse {
  id: string
  kb_id: string
  file_name: string
  file_path: string
  file_size: number
  mime_type: string
  status: string
  chunk_count: number
  vector_count: number
  tags: TagResponse[]
  created_at: string
  updated_at: string
}

export interface PaginatedDocuments {
  items: DocumentResponse[]
  total: number
  page: number
  page_size: number
}

export async function uploadDocuments(
  kbId: string,
  formData: FormData
): Promise<{ uploaded: DocumentResponse[]; count: number }> {
  const res = await fetch(`${API_BASE}/bases/${kbId}/documents/upload`, {
    method: 'POST',
    body: formData,
  })
  const data = await res.json()
  if (data.code !== 0) {
    throw new Error(data.message || '上传失败')
  }
  return data.data
}

export function fetchKBDocuments(
  kbId: string,
  page?: number,
  pageSize?: number
): Promise<PaginatedDocuments> {
  const params = new URLSearchParams()
  if (page) params.set('page', String(page))
  if (pageSize) params.set('page_size', String(pageSize))
  const qs = params.toString()
  return request(`${API_BASE}/bases/${kbId}/documents${qs ? '?' + qs : ''}`)
}

export function fetchDocumentDetail(docId: string): Promise<DocumentResponse> {
  return request(`${API_BASE}/documents/${docId}`)
}

export function deleteDocument(docId: string): Promise<void> {
  return request(`${API_BASE}/documents/${docId}`, { method: 'DELETE' })
}

// --- Chunks ---

export interface ChunkResponse {
  id: string
  document_id: string
  kb_id: string
  content: string
  chunk_index: number
  chunk_type: string
  parent_chunk_id: string | null
  vector_id: string | null
  metadata_json: string
}

export function fetchDocumentChunks(docId: string): Promise<ChunkResponse[]> {
  return request(`${API_BASE}/documents/${docId}/chunks`)
}

// --- LightRAG Sync ---

export interface SyncResult {
  synced: number
  failed: number
  total: number
  errors?: { doc_id: string; file_name: string; error: string }[]
  message: string
}

export interface SyncStatus {
  pending_count: number
  pending_documents: { id: string; file_name: string }[]
}

export function syncToLightRAG(kbId: string): Promise<SyncResult> {
  return request(`${API_BASE}/bases/${kbId}/sync-lightrag`, { method: 'POST' })
}

export function fetchSyncStatus(kbId: string): Promise<SyncStatus> {
  return request(`${API_BASE}/bases/${kbId}/sync-status`)
}

// ===========================================================================
// Folder-Based Knowledge Base API
// ===========================================================================

const FOLDER_API_BASE = '/api/knowledge/folder'

export interface FolderTagResponse {
  name: string
  level: number
  children: FolderTagResponse[]
}

export interface FolderDocumentResponse {
  id: string
  file_name: string
  relative_path: string
  file_size: number
  extension: string
  tags: string[]
  modified_time: string
}

export interface FolderKBResponse {
  name: string
  doc_count: number
  top_tags: string[]
}

export interface FolderKBListResponse {
  bases: FolderKBResponse[]
  total: number
}

export interface ImportFolderKBRequest {
  kb_name: string
  description?: string
  icon?: string
  color?: string
  chunk_size?: number
  chunk_overlap?: number
}

export function fetchFolderKBs(): Promise<FolderKBListResponse> {
  return request(`${FOLDER_API_BASE}/bases`)
}

export function fetchFolderKBFiles(
  kbName: string,
  page?: number,
  pageSize?: number,
  keyword?: string
): Promise<{ items: FolderDocumentResponse[]; total: number; page: number; page_size: number }> {
  const params = new URLSearchParams()
  if (page) params.set('page', String(page))
  if (pageSize) params.set('page_size', String(pageSize))
  if (keyword) params.set('keyword', keyword)
  const qs = params.toString()
  return request(`${FOLDER_API_BASE}/bases/${encodeURIComponent(kbName)}/files${qs ? '?' + qs : ''}`)
}

export function fetchFolderKBTags(kbName: string): Promise<FolderTagResponse[]> {
  return request(`${FOLDER_API_BASE}/bases/${encodeURIComponent(kbName)}/tags`)
}

export function fetchFolderKBGraph(kbName: string): Promise<KnowledgeGraph> {
  return request(`${FOLDER_API_BASE}/bases/${encodeURIComponent(kbName)}/graph`)
}

export function importFolderKB(kbName: string, data: ImportFolderKBRequest): Promise<{ kb_id: string; imported_docs: number; imported_tags: number }> {
  return request(`${FOLDER_API_BASE}/bases/${encodeURIComponent(kbName)}/import`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ===========================================================================
// Folder KB Trend & Asset Stats API
// ===========================================================================

export interface TrendSeriesItem {
  name: string
  data: number[]
  color: string
}

export interface TrendSummary {
  new_count: number
  new_change_pct: number
  updated_count: number
  updated_change_pct: number
}

export interface TrendData {
  months: string[]
  series: TrendSeriesItem[]
  summary: TrendSummary
}

export interface AssetExtensionItem {
  ext: string
  count: number
}

export interface AssetCategory {
  name: string
  count: number
  size: number
  value: number
  color: string
  extensions: AssetExtensionItem[]
}

export interface ExtensionSummary {
  ext: string
  count: number
  value: number
}

export interface AssetStats {
  total_count: number
  total_size: number
  categories: AssetCategory[]
  extension_summary: ExtensionSummary[]
}

export function fetchFolderKBTrend(): Promise<TrendData> {
  return request(`${FOLDER_API_BASE}/trend`)
}

export function fetchFolderKBAssetStats(): Promise<AssetStats> {
  return request(`${FOLDER_API_BASE}/asset-stats`)
}

// --- Folder KB File List (cross-KB) ---

export function fetchFolderKBFileList(params?: {
  tab?: string
  keyword?: string
  category_id?: string
  page?: number
  page_size?: number
}): Promise<{ items: KnowledgeItem[]; total: number; page: number; page_size: number }> {
  const searchParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) searchParams.set(k, String(v))
    })
  }
  const qs = searchParams.toString()
  return request(`${FOLDER_API_BASE}/list${qs ? '?' + qs : ''}`)
}

// --- Folder KB Source Distribution ---

export interface FolderSourceItem {
  name: string
  value: number
  count: number
  color: string
  description?: string
}

export function fetchFolderKBSourceDistribution(): Promise<FolderSourceItem[]> {
  return request(`${FOLDER_API_BASE}/source-distribution`)
}
