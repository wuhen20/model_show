<template>
  <div class="app-layout">
    <Header title="人工智能分部 · 模型微调组" subtitle="文件夹知识库" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div v-if="loading" class="loading-state"><p>加载中...</p></div>

        <div v-else class="detail-layout">
          <!-- Left: Info & Import panel -->
          <aside class="info-panel">
            <div class="panel-inner">
              <el-button text @click="goBack" class="back-btn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
                返回
              </el-button>

              <!-- KB info strip -->
              <div class="kb-strip">
                <div class="kb-icon-sm" style="background-color: rgba(255, 170, 0, 0.2)">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffaa00" stroke-width="2">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                  </svg>
                </div>
                <div class="kb-strip-info">
                  <span class="kb-strip-name">
                    {{ kbName }}
                    <span class="folder-badge">文件夹</span>
                  </span>
                  <span class="kb-strip-desc">文件夹知识库 · 目录结构自动解析</span>
                </div>
              </div>

              <!-- Stats row -->
              <div class="stats-row">
                <div class="mini-stat">
                  <span class="mini-val">{{ totalFiles }}</span>
                  <span class="mini-label">文档</span>
                </div>
                <div class="mini-stat">
                  <span class="mini-val">{{ dirCount }}</span>
                  <span class="mini-label">目录</span>
                </div>
                <div class="mini-stat">
                  <span class="mini-val">{{ totalSize }}</span>
                  <span class="mini-label">总大小</span>
                </div>
              </div>

              <!-- Tags display (read-only, from folder structure) -->
              <div class="kb-tags-display" v-if="tags.length">
                <span class="section-label">目录标签体系</span>
                <div class="folder-tag-tree">
                  <FolderTagItem v-for="t in tags" :key="t.name" :tag="t" :depth="1" />
                </div>
              </div>

              <!-- Import section -->
              <div class="import-section">
                <span class="section-label">导入至知识库</span>
                <p class="import-hint">将文件夹知识库导入系统，可使用 LightRAG 同步、切片等完整功能</p>
                <div class="import-form">
                  <el-input v-model="importForm.description" size="small" placeholder="知识库描述（可选）" />
                  <el-button type="primary" :loading="importing" @click="handleImport" class="import-btn">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
                    </svg>
                    开始导入
                  </el-button>
                </div>
              </div>
            </div>
          </aside>

          <!-- Right: File table + Graph -->
          <section class="content-panel">
            <!-- File table -->
            <div class="file-section">
              <div class="section-header">
                <h2>文件列表</h2>
                <div class="section-actions">
                  <el-input
                    v-model="searchKeyword"
                    size="small"
                    placeholder="搜索文件名"
                    clearable
                    style="width: 200px"
                    @clear="loadFiles"
                    @keyup.enter="loadFiles"
                  >
                    <template #prefix>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM21 21l-4.35-4.35"/></svg>
                    </template>
                  </el-input>
                  <el-button size="small" @click="loadFiles">刷新</el-button>
                </div>
              </div>
              <div class="file-table-wrap">
                <el-table :data="files" style="width:100%" v-loading="filesLoading" empty-text="暂无文件" height="100%">
                  <el-table-column prop="file_name" label="文件名" min-width="240">
                    <template #default="{ row }">
                      <div class="file-name-cell">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" :stroke="getFileColor(row.extension)" stroke-width="2">
                          <path :d="getFileIcon(row.extension)"/>
                        </svg>
                        <span>{{ row.file_name }}</span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="关联标签" min-width="200">
                    <template #default="{ row }">
                      <el-tag
                        v-for="tag in row.tags"
                        :key="tag"
                        size="small"
                        class="folder-file-tag"
                      >{{ tag }}</el-tag>
                      <span v-if="!row.tags?.length" class="no-data">-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="类型" width="80" align="center">
                    <template #default="{ row }">
                      <span class="ext-badge">{{ row.extension }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="大小" width="90" align="center">
                    <template #default="{ row }">
                      {{ formatFileSize(row.file_size) }}
                    </template>
                  </el-table-column>
                  <el-table-column label="修改时间" width="160">
                    <template #default="{ row }">
                      {{ formatTime(row.modified_time) }}
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <div class="pagination-bar" v-if="totalFiles > pageSize">
                <el-pagination
                  v-model:current-page="currentPage"
                  :page-size="pageSize"
                  :total="totalFiles"
                  layout="prev, pager, next"
                  @current-change="loadFiles"
                  small
                />
              </div>
            </div>

            <!-- Graph section -->
            <div class="graph-section">
              <div class="section-header">
                <h2>目录知识图谱</h2>
                <el-button text size="small" class="graph-detail-btn" @click="showGraphDetail = true">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:3px">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                  查看详情
                </el-button>
              </div>
              <div class="graph-card" v-loading="graphLoading">
                <div ref="graphRef" class="graph-chart"></div>
                <div class="graph-stats" v-if="graphStats">
                  <div class="graph-stat-item">
                    <span class="gs-val">{{ graphStats.entity_count }}</span>
                    <span class="gs-label">节点数</span>
                  </div>
                  <div class="graph-stat-item">
                    <span class="gs-val">{{ graphStats.relation_count }}</span>
                    <span class="gs-label">关系数</span>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- Graph Detail Modal -->
        <GraphDetailModal
          v-model="showGraphDetail"
          :title="`${kbName} · 目录知识图谱详情`"
          :nodes="graphNodes"
          :links="graphLinks"
        />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import {
  fetchFolderKBFiles, fetchFolderKBTags, fetchFolderKBGraph, importFolderKB,
  fetchKnowledgeGraph,
  type FolderDocumentResponse, type FolderTagResponse, type GraphStats,
  type GraphNode, type GraphLink,
} from '@/api/knowledge'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import GraphDetailModal from '@/components/GraphDetailModal.vue'

const route = useRoute()
const router = useRouter()
const kbName = computed(() => decodeURIComponent(route.params.name as string))

// Derive workspace name from KB name (must match backend logic)
function kbNameToWorkspace(name: string): string {
  let ws = name.toLowerCase().trim()
  ws = ws.replace(/[\s\-]+/g, '_')
  ws = ws.replace(/[^a-z0-9_一-鿿]/g, '')
  return ws
}

interface FolderTagItemProps { tag: FolderTagResponse; depth: number }

// Recursive tag tree display component
const FolderTagItem = {
  name: 'FolderTagItem',
  props: { tag: Object, depth: Number },
  template: `
    <div class="ftag-item" :style="{ paddingLeft: (depth - 1) * 16 + 'px' }">
      <div class="ftag-row">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ffaa00" stroke-width="2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        <span class="ftag-name">{{ tag.name }}</span>
        <span class="ftag-level">L{{ depth }}</span>
      </div>
      <FolderTagItem v-for="c in tag.children" :key="c.name" :tag="c" :depth="depth + 1" />
    </div>
  `,
}

const loading = ref(true)
const files = ref<FolderDocumentResponse[]>([])
const tags = ref<FolderTagResponse[]>([])
const filesLoading = ref(false)
const graphLoading = ref(false)
const importing = ref(false)
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = 50
const totalFiles = ref(0)
const totalSize = ref('0 KB')
const dirCount = ref(0)
const graphStats = ref<GraphStats | null>(null)
const graphRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

// Graph detail modal state
const graphNodes = ref<GraphNode[]>([])
const graphLinks = ref<GraphLink[]>([])
const showGraphDetail = ref(false)

const importForm = ref({
  description: '',
})

function countDirs(tagTree: FolderTagResponse[]): number {
  let count = 0
  for (const t of tagTree) {
    count += 1
    if (t.children?.length) count += countDirs(t.children)
  }
  return count
}

function calcTotalSize(items: FolderDocumentResponse[]): string {
  const bytes = items.reduce((s, f) => s + (f.file_size || 0), 0)
  return formatFileSize(bytes)
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(iso: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function getFileColor(ext: string): string {
  const map: Record<string, string> = {
    '.pdf': '#ff5555', '.doc': '#4a90d9', '.docx': '#4a90d9',
    '.xlsx': '#00ff88', '.xls': '#00ff88', '.csv': '#00ff88',
    '.pptx': '#ffaa00', '.ppt': '#ffaa00', '.md': '#a855f7',
    '.txt': '#888', '.json': '#ffaa00', '.html': '#ff5555',
  }
  return map[ext] || '#00d4ff'
}

function getFileIcon(ext: string): string {
  const map: Record<string, string> = {
    '.pdf': 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8',
    '.doc': 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8',
    '.docx': 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8',
    '.xlsx': 'M3 3h18v18H3zM9 3v18M15 3v18M3 9h18M3 15h18',
    '.xls': 'M3 3h18v18H3zM9 3v18M15 3v18M3 9h18M3 15h18',
    '.csv': 'M3 3h18v18H3zM9 3v18M15 3v18M3 9h18M3 15h18',
    '.pptx': 'M4 4h16v16H4zM8 8h8M8 12h6',
    '.ppt': 'M4 4h16v16H4zM8 8h8M8 12h6',
    '.md': 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z',
    '.txt': 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6',
  }
  return map[ext] || map['.txt']
}

async function loadFiles() {
  filesLoading.value = true
  try {
    const data = await fetchFolderKBFiles(kbName.value, currentPage.value, pageSize, searchKeyword.value || undefined)
    files.value = data.items
    totalFiles.value = data.total
    totalSize.value = calcTotalSize(data.items)
  } catch (e: any) {
    ElMessage.error(e.message || '加载文件列表失败')
    files.value = []
  } finally {
    filesLoading.value = false
  }
}

async function loadTags() {
  try {
    tags.value = await fetchFolderKBTags(kbName.value)
    dirCount.value = countDirs(tags.value)
  } catch {
    tags.value = []
  }
}

async function loadGraph() {
  graphLoading.value = true
  try {
    // First try Memgraph (real LightRAG-extracted entities) using kb_name
    const memgraphData = await fetchKnowledgeGraph(undefined, kbName.value)
    if (memgraphData && memgraphData.nodes && memgraphData.nodes.length > 0) {
      graphStats.value = memgraphData.stats
      graphNodes.value = memgraphData.nodes
      graphLinks.value = memgraphData.links
      await nextTick()
      renderGraph(memgraphData)
      graphLoading.value = false
      return
    }
  } catch {
    // Fall through to synthetic graph
  }

  // Fallback: synthetic folder graph
  try {
    const data = await fetchFolderKBGraph(kbName.value)
    graphStats.value = data.stats
    graphNodes.value = data.nodes
    graphLinks.value = data.links
    await nextTick()
    renderGraph(data)
  } catch {
    graphStats.value = null
  } finally {
    graphLoading.value = false
  }
}

function renderGraph(data: { nodes: any[]; links: any[] }) {
  if (!graphRef.value) {
    // DOM not ready yet, retry after a short delay
    setTimeout(() => renderGraph(data), 200)
    return
  }
  const w = graphRef.value.clientWidth
  const h = graphRef.value.clientHeight
  if (w <= 0 || h <= 0) {
    // Container has no size yet, retry
    setTimeout(() => renderGraph(data), 300)
    return
  }
  if (!chartInstance) {
    chartInstance = echarts.init(graphRef.value, 'dark')
  }
  const categories = [
    { name: '核心实体' }, { name: '关联实体' }, { name: '边缘实体' },
  ]
  chartInstance.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#fff', fontSize: 12 },
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const d = params.data
          let html = `<b style="color:#00d4ff">${d.name}</b>`
          if (d.entityType) html += `<br/><span style="color:rgba(255,255,255,0.5)">类型:</span> ${d.entityType}`
          if (d.description) html += `<br/><span style="color:rgba(255,255,255,0.5)">描述:</span> ${d.description}`
          if (d.kbName) html += `<br/><span style="color:rgba(255,255,255,0.5)">知识库:</span> ${d.kbName}`
          return html
        }
        if (params.dataType === 'edge') {
          const d = params.data
          let html = `<span style="color:#00d4ff">${d.source}</span> → <span style="color:#00ff88">${d.target}</span>`
          if (d.relType) html += `<br/><span style="color:rgba(255,255,255,0.5)">关系:</span> ${d.relType}`
          if (d.description) html += `<br/><span style="color:#ffaa00">${d.description}</span>`
          return html
        }
        return ''
      }
    },
    legend: { data: categories.map(c => c.name), textStyle: { color: 'rgba(255,255,255,0.6)', fontSize: 11 }, bottom: 0 },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      categories,
      data: data.nodes,
      links: data.links,
      force: { repulsion: 150, gravity: 0.08, edgeLength: [60, 180] },
      label: {
        show: true,
        fontSize: 10,
        color: 'rgba(255,255,255,0.8)',
        formatter: (params: any) => {
          const n = params.name || ''
          return n.length > 10 ? n.slice(0, 10) + '..' : n
        },
      },
      lineStyle: { color: 'rgba(0,212,255,0.25)', width: 1.5, curveness: 0.1 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 3, color: '#00d4ff' } },
    }],
  }, true)
}

async function handleImport() {
  importing.value = true
  try {
    const result = await importFolderKB(kbName.value, {
      kb_name: kbName.value,
      description: importForm.value.description,
    })
    ElMessage.success(`导入成功！共导入 ${result.imported_docs} 个文档，${result.imported_tags} 个标签`)
    router.push(`/knowledge-base/${result.kb_id}`)
  } catch (e: any) {
    ElMessage.error(e.message || '导入失败')
  } finally {
    importing.value = false
  }
}

function goBack() { router.push('/knowledge-management?tab=management') }

onMounted(async () => {
  try {
    // Load files and tags first, then set loading=false so DOM renders
    await Promise.all([loadFiles(), loadTags()])
  } finally {
    loading.value = false
  }
  // Now the DOM is rendered (graphRef is visible), load graph
  await nextTick()
  await loadGraph()
})

onUnmounted(() => {
  chartInstance?.dispose()
  chartInstance = null
})

watch(kbName, () => {
  if (kbName.value) {
    loading.value = true
    Promise.all([loadFiles(), loadTags(), loadGraph()]).finally(() => { loading.value = false })
  }
})
</script>

<style scoped>
.app-layout { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
.main-content { display: flex; flex: 1; overflow: hidden; min-height: 0; }
.content-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 0; min-height: 0; }

.detail-layout { flex: 1; display: flex; overflow: hidden; }

/* Left panel */
.info-panel {
  width: 320px; flex-shrink: 0;
  border-right: 1px solid rgba(255, 170, 0, 0.12);
  background: linear-gradient(180deg, rgba(17,24,39,0.95) 0%, rgba(10,14,26,0.9) 100%);
}
.panel-inner { height: 100%; overflow-y: auto; padding: 20px 18px; display: flex; flex-direction: column; gap: 16px; }
.back-btn { color: rgba(255,255,255,0.6); font-size: 12px; padding: 0; margin-bottom: 2px; }

.kb-strip { display: flex; align-items: center; gap: 12px; }
.kb-icon-sm { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.kb-strip-info { min-width: 0; }
.kb-strip-name { display: block; font-size: 15px; font-weight: 600; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kb-strip-desc { display: block; font-size: 11px; color: rgba(255,255,255,0.45); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.folder-badge {
  display: inline-block; font-size: 9px; font-weight: 600;
  padding: 1px 5px; border-radius: 3px; margin-left: 6px; vertical-align: middle;
  background: linear-gradient(135deg, rgba(255,170,0,0.3), rgba(255,85,85,0.2));
  color: #ffaa00; letter-spacing: 0.5px;
}

.stats-row { display: flex; gap: 16px; }
.mini-stat { display: flex; flex-direction: column; align-items: center; }
.mini-val { font-size: 18px; font-weight: 700; color: #fff; }
.mini-label { font-size: 10px; color: rgba(255,255,255,0.4); }

/* Tags display */
.section-label { font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.55); margin-bottom: 8px; display: flex; align-items: center; }
.folder-tag-tree { max-height: 240px; overflow-y: auto; }
.ftag-item { }
.ftag-row { display: flex; align-items: center; gap: 6px; padding: 3px 0; }
.ftag-name { font-size: 12px; color: #ffaa00; }
.ftag-level { font-size: 9px; color: rgba(255,255,255,0.3); background: rgba(255,255,255,0.06); padding: 0 4px; border-radius: 2px; }

/* Import section */
.import-section {
  background: rgba(255,170,0,0.04); border: 1px solid rgba(255,170,0,0.15);
  border-radius: 10px; padding: 14px;
}
.import-hint { font-size: 11px; color: rgba(255,255,255,0.4); margin: 4px 0 10px; }
.import-form { display: flex; flex-direction: column; gap: 8px; }
.import-btn { width: 100%; }

/* Right content panel */
.content-panel {
  flex: 1; display: flex; flex-direction: column; overflow-y: auto; padding: 20px 24px; gap: 16px;
}

.file-section { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.section-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-shrink: 0;
}
.section-header h2 { font-size: 18px; font-weight: 600; color: #fff; margin: 0; }
.section-actions { display: flex; gap: 8px; }
.file-table-wrap {
  flex: 1; min-height: 0; border-radius: 10px; overflow: hidden;
  background: rgba(17,24,39,0.6); border: 1px solid rgba(0,212,255,0.15);
}

.file-name-cell { display: flex; align-items: center; gap: 6px; }
.ext-badge {
  font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px;
  background: rgba(0,212,255,0.1); color: #00d4ff;
}

.folder-file-tag {
  background: rgba(255,170,0,0.1) !important; border-color: rgba(255,170,0,0.3) !important;
  color: #ffaa00 !important;
}

.pagination-bar { display: flex; justify-content: center; margin-top: 12px; }
.no-data { color: rgba(255,255,255,0.4); font-size: 13px; }

/* Graph section */
.graph-section { flex-shrink: 0; }
.graph-detail-btn {
  color: #00d4ff !important;
  font-size: 12px;
  padding: 4px 8px;
  flex-shrink: 0;
  transition: all 0.2s;
}
.graph-detail-btn:hover {
  background: rgba(0,212,255,0.08) !important;
}
.graph-card {
  background: linear-gradient(135deg, rgba(17,24,39,0.9) 0%, rgba(26,35,50,0.8) 100%);
  border: 1px solid rgba(0,212,255,0.2); border-radius: 12px;
  padding: 16px; position: relative; min-height: 320px;
}
.graph-chart { height: 280px; }
.graph-stats { display: flex; gap: 20px; margin-top: 8px; justify-content: center; }
.graph-stat-item { display: flex; flex-direction: column; align-items: center; }
.gs-val { font-size: 16px; font-weight: 600; color: #00d4ff; }
.gs-label { font-size: 10px; color: rgba(255,255,255,0.4); }

.loading-state { display: flex; align-items: center; justify-content: center; height: 100%; color: rgba(255,255,255,0.5); }
</style>
