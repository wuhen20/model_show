<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="文件夹知识库" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div v-if="loading" class="loading-state"><p>加载中...</p></div>

        <div v-else class="detail-layout">
          <!-- Left: Info & Tag system panel -->
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

              <!-- Tag system display — full tree with hierarchy -->
              <div class="tag-system-section">
                <div class="section-label">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2" style="margin-right:4px">
                    <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01"/>
                  </svg>
                  标签体系
                </div>

                <div class="tag-tree-card" v-if="tags.length">
                  <!-- Full tag tree -->
                  <div class="tag-tree-content">
                    <FolderTagItem
                      v-for="t in tags"
                      :key="t.name"
                      :tag="t"
                      :depth="1"
                    />
                  </div>
                  <!-- Summary stats at bottom -->
                  <div class="tag-tree-summary">
                    <div class="summary-chip">
                      <span class="summary-chip-val">{{ tags.length }}</span>
                      <span class="summary-chip-label">一级</span>
                    </div>
                    <div class="summary-chip">
                      <span class="summary-chip-val">{{ totalTagCount }}</span>
                      <span class="summary-chip-label">总计</span>
                    </div>
                    <div class="summary-chip">
                      <span class="summary-chip-val">{{ maxTagDepth }}</span>
                      <span class="summary-chip-label">层级</span>
                    </div>
                  </div>
                </div>
                <div v-else class="tag-empty">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1.5">
                    <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01"/>
                  </svg>
                  <p>暂无标签</p>
                </div>
              </div>
            </div>
          </aside>

          <!-- Right: File table + Detail Preview + Graph -->
          <section class="content-panel">

            <!-- ========= File List View ========= -->
            <div v-if="!selectedFile" class="file-section">
              <div class="section-header">
                <h2>文件列表</h2>
                <div class="section-actions">
                  <el-input
                    v-model="searchKeyword"
                    size="small"
                    placeholder="搜索文件名"
                    clearable
                    style="width: 200px"
                    @clear="handleSearch"
                    @keyup.enter="handleSearch"
                    :prefix-icon="SearchIcon"
                  />
                  <el-button size="small" @click="loadFiles">刷新</el-button>
                </div>
              </div>
              <div class="file-table-wrap">
                <el-table
                  :data="filteredFiles"
                  style="width:100%"
                  v-loading="filesLoading"
                  empty-text="暂无文件"
                  height="100%"
                  @row-click="handleFileClick"
                  highlight-current-row
                  class="file-table"
                >
                  <el-table-column prop="file_name" label="文件名" min-width="240">
                    <template #default="{ row }">
                      <div class="file-name-cell clickable">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" :stroke="getFileColor(row.extension)" stroke-width="2">
                          <path :d="getFileIcon(row.extension)"/>
                        </svg>
                        <span>{{ row.file_name }}</span>
                        <svg class="drill-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.4)" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="关联标签" min-width="200">
                    <template #default="{ row }">
                      <el-tag
                        v-for="(tag, idx) in row.tags"
                        :key="tag"
                        size="small"
                        :class="tagDepthClass(idx)"
                        class="depth-tag"
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

            <!-- ========= File Detail View ========= -->
            <div v-else class="file-detail-section">
              <div class="detail-header">
                <el-button text @click="closeFileDetail" class="back-btn detail-back-btn">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
                  返回文件列表
                </el-button>
                <div class="detail-file-info">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" :stroke="getFileColor(selectedFile.extension)" stroke-width="2">
                    <path :d="getFileIcon(selectedFile.extension)"/>
                  </svg>
                  <span class="detail-file-name">{{ selectedFile.file_name }}</span>
                  <span class="ext-badge">{{ selectedFile.extension }}</span>
                </div>
              </div>

              <!-- File metadata row -->
              <div class="detail-meta-row">
                <div class="meta-item">
                  <span class="meta-label">文件大小</span>
                  <span class="meta-value">{{ formatFileSize(selectedFile.file_size) }}</span>
                </div>
                <div class="meta-item">
                  <span class="meta-label">修改时间</span>
                  <span class="meta-value">{{ formatTime(selectedFile.modified_time) }}</span>
                </div>
                <div class="meta-item" v-if="selectedFile.knowledge_type">
                  <span class="meta-label">知识类型</span>
                  <span class="meta-value">{{ selectedFile.knowledge_type }}</span>
                </div>
                <div class="meta-item" v-if="selectedFile.source">
                  <span class="meta-label">知识来源</span>
                  <span class="meta-value">{{ selectedFile.source }}</span>
                </div>
                <div class="meta-item" v-if="selectedFile.score">
                  <span class="meta-label">知识评分</span>
                  <span class="meta-value">
                    <span v-for="i in 5" :key="i" class="detail-star" :class="{ active: i <= selectedFile.score }">★</span>
                  </span>
                </div>
                <div class="meta-item">
                  <span class="meta-label">相对路径</span>
                  <span class="meta-value" :title="selectedFile.relative_path">{{ selectedFile.relative_path }}</span>
                </div>
                <div class="meta-item" v-if="selectedFile.tags?.length">
                  <span class="meta-label">关联标签</span>
                  <div class="meta-tags">
                    <el-tag
                      v-for="(tag, idx) in selectedFile.tags"
                      :key="tag"
                      size="small"
                      :class="tagDepthClass(idx)"
                      class="depth-tag"
                    >{{ tag }}</el-tag>
                  </div>
                </div>
              </div>

              <!-- File preview area -->
              <div class="preview-section">
                <div class="section-header">
                  <h3>文件预览</h3>
                  <div class="preview-actions">
                    <el-button
                      v-if="previewUrl"
                      size="small"
                      text
                      class="open-new-btn"
                      @click="openPreviewNewTab"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:3px">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
                      </svg>
                      新窗口打开
                    </el-button>
                  </div>
                </div>
                <div class="preview-card" v-loading="previewLoading">
                  <!-- docx preview via vue-office -->
                  <VueOfficeDocx
                    v-if="selectedFile.extension === '.docx'"
                    :src="officePreviewSrc"
                    class="preview-vue-office"
                    @rendered="onPreviewRendered"
                    @error="onPreviewError"
                  />

                  <!-- xlsx / xls preview via vue-office -->
                  <VueOfficeExcel
                    v-else-if="isExcelFile(selectedFile.extension)"
                    :src="officePreviewSrc"
                    class="preview-vue-office"
                    @rendered="onPreviewRendered"
                    @error="onPreviewError"
                  />

                  <!-- pptx preview via vue-office -->
                  <VueOfficePptx
                    v-else-if="selectedFile.extension === '.pptx'"
                    :src="officePreviewSrc"
                    class="preview-vue-office"
                    @rendered="onPreviewRendered"
                    @error="onPreviewError"
                  />

                  <!-- PDF preview via vue-office -->
                  <VueOfficePdf
                    v-else-if="selectedFile.extension === '.pdf'"
                    :src="officePreviewSrc"
                    class="preview-vue-office"
                    @rendered="onPreviewRendered"
                    @error="onPreviewError"
                  />

                  <!-- Text-based file preview -->
                  <div v-else-if="isTextFile(selectedFile.extension)" class="preview-text-wrap">
                    <pre class="preview-text" v-if="textContent">{{ textContent }}</pre>
                    <div v-else class="preview-empty">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.2)" stroke-width="1.5">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8"/>
                      </svg>
                      <p>无法加载文件内容</p>
                    </div>
                  </div>

                  <!-- Image preview -->
                  <div v-else-if="isImageFile(selectedFile.extension)" class="preview-image-wrap">
                    <img :src="previewUrl" class="preview-image" :alt="selectedFile.file_name" />
                  </div>

                  <!-- Unsupported / binary file -->
                  <div v-else class="preview-unsupported">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.25)" stroke-width="1.5">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8"/>
                    </svg>
                    <p class="unsupported-title">该文件格式不支持在线预览</p>
                    <p class="unsupported-desc">{{ selectedFile.extension.toUpperCase().slice(1) }} 格式文件需要下载后查看</p>
                    <el-button type="primary" size="small" @click="openPreviewNewTab" style="margin-top:8px">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                      </svg>
                      下载文件
                    </el-button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Graph section (only show in file list view) -->
            <div v-if="!selectedFile" class="graph-section">
              <div class="section-header">
                <h2>目录知识图谱预览</h2>
                <el-button text size="small" class="graph-detail-btn" @click="openGraphDetail">
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
          :nodes="detailNodes"
          :links="detailLinks"
          :stats="detailStats"
        />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import {
  fetchFolderKBFiles, fetchFolderKBTags, fetchFolderKBGraph,
  fetchKnowledgeGraph,
  getFolderFilePreviewUrl,
  type FolderDocumentResponse, type FolderTagResponse, type GraphStats,
  type GraphNode, type GraphLink,
} from '@/api/knowledge'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import GraphDetailModal from '@/components/GraphDetailModal.vue'
import FolderTagItem from '@/components/FolderTagItem.vue'

// vue-office preview components — lazy loaded for code splitting
import { defineAsyncComponent } from 'vue'
import '@vue-office/docx/lib/index.css'
import '@vue-office/excel/lib/index.css'

const VueOfficeDocx = defineAsyncComponent(() => import('@vue-office/docx'))
const VueOfficeExcel = defineAsyncComponent(() => import('@vue-office/excel'))
const VueOfficePdf = defineAsyncComponent(() => import('@vue-office/pdf'))
const VueOfficePptx = defineAsyncComponent(() => import('@vue-office/pptx'))

// Search icon component for el-input prefix
const SearchIcon = {
  name: 'SearchIcon',
  render() {
    return h('svg', { width: 14, height: 14, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2 },
      [h('path', { d: 'M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM21 21l-4.35-4.35' })])
  },
}

const route = useRoute()
const router = useRouter()
const kbName = computed(() => decodeURIComponent(route.params.name as string))

const loading = ref(true)
const files = ref<FolderDocumentResponse[]>([])
const tags = ref<FolderTagResponse[]>([])
const filesLoading = ref(false)
const graphLoading = ref(false)
const GRAPH_PREVIEW_MAX_NODES = 80
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = 50
const totalFiles = ref(0)
const totalSize = ref('0 KB')
const dirCount = ref(0)
const graphStats = ref<GraphStats | null>(null)
const graphRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

// Preview graph data (always stays as the small preview)
const previewNodes = ref<GraphNode[]>([])
const previewLinks = ref<GraphLink[]>([])

// Detail modal graph data (full graph, only shown in the modal)
const detailNodes = ref<GraphNode[]>([])
const detailLinks = ref<GraphLink[]>([])
const detailStats = ref<GraphStats | null>(null)

const showGraphDetail = ref(false)
let detailDataLoaded = false                // avoid duplicate fetch for detail modal

// File detail & preview state
const selectedFile = ref<FolderDocumentResponse | null>(null)
const textContent = ref('')
const previewUrl = ref('')
const previewLoading = ref(false)
const officePreviewSrc = ref<string | ArrayBuffer>('')  // ArrayBuffer for vue-office

// ---- Search: client-side filtering on loaded files ----
const filteredFiles = computed(() => {
  if (!searchKeyword.value.trim()) return files.value
  const kw = searchKeyword.value.trim().toLowerCase()
  return files.value.filter(f => f.file_name.toLowerCase().includes(kw))
})

function handleSearch() {
  currentPage.value = 1
  loadFiles()
}

// ---- Tag system statistics ----
const totalTagCount = computed(() => countAllTags(tags.value))
const maxTagDepth = computed(() => getMaxDepth(tags.value, 1))

function countAllTags(tree: FolderTagResponse[]): number {
  let count = 0
  for (const t of tree) {
    count += 1
    if (t.children?.length) count += countAllTags(t.children)
  }
  return count
}

function getMaxDepth(tree: FolderTagResponse[], baseDepth: number): number {
  let max = baseDepth
  for (const t of tree) {
    if (t.children?.length) {
      max = Math.max(max, getMaxDepth(t.children, baseDepth + 1))
    }
  }
  return max
}

// ---- File type helpers ----
const TEXT_EXTENSIONS = new Set(['.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.log', '.rtf'])
const IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'])
const EXCEL_EXTENSIONS = new Set(['.xlsx', '.xls'])

function isTextFile(ext: string): boolean { return TEXT_EXTENSIONS.has(ext) }

// Map tag index (0-based) in a file's tag array to depth-based CSS class
// tag[0] = L1 (cyan), tag[1] = L2 (green), tag[2] = L3 (purple), tag[3+] = L4 (amber)
function tagDepthClass(idx: number): string {
  const map = ['depth-tag-1', 'depth-tag-2', 'depth-tag-3', 'depth-tag-4']
  return map[Math.min(idx, 3)]
}
function isImageFile(ext: string): boolean { return IMAGE_EXTENSIONS.has(ext) }
function isExcelFile(ext: string): boolean { return EXCEL_EXTENSIONS.has(ext) }

// ---- File detail & preview ----
function isOfficeFile(ext: string): boolean {
  return ext === '.docx' || ext === '.xlsx' || ext === '.xls' || ext === '.pptx' || ext === '.pdf'
}

function handleFileClick(row: FolderDocumentResponse) {
  selectedFile.value = row
  previewUrl.value = getFolderFilePreviewUrl(kbName.value, row.relative_path)
  textContent.value = ''
  officePreviewSrc.value = ''
  previewLoading.value = true

  // For text files, load content via fetch as text
  if (isTextFile(row.extension)) {
    loadTextContent(row.relative_path)
  }
  // For Office/PDF files, load as ArrayBuffer for vue-office
  else if (isOfficeFile(row.extension)) {
    loadOfficeContent(row.relative_path)
  }
  // For images, just use the URL directly (no preloading needed)
  else {
    previewLoading.value = false
  }
}

async function loadOfficeContent(relativePath: string) {
  try {
    const url = getFolderFilePreviewUrl(kbName.value, relativePath)
    const res = await fetch(url)
    if (res.ok) {
      officePreviewSrc.value = await res.arrayBuffer()
    } else {
      officePreviewSrc.value = ''
      previewLoading.value = false
      ElMessage.warning(`文件加载失败 (${res.status})`)
    }
  } catch (e: any) {
    officePreviewSrc.value = ''
    previewLoading.value = false
    ElMessage.warning('文件加载失败，可尝试下载后查看')
  }
}

async function loadTextContent(relativePath: string) {
  try {
    const url = getFolderFilePreviewUrl(kbName.value, relativePath)
    const res = await fetch(url)
    if (res.ok) {
      textContent.value = await res.text()
    } else {
      textContent.value = ''
    }
  } catch {
    textContent.value = ''
  } finally {
    previewLoading.value = false
  }
}

function onPreviewRendered() {
  previewLoading.value = false
}

function onPreviewError() {
  previewLoading.value = false
  ElMessage.warning('文件预览渲染失败，可尝试下载后查看')
}

function closeFileDetail() {
  selectedFile.value = null
  textContent.value = ''
  previewUrl.value = ''
  officePreviewSrc.value = ''
  previewLoading.value = false
  // Re-render graph chart after the graph section becomes visible again.
  // The v-if toggling destroys the DOM element, so we must dispose the old
  // chartInstance and re-create it on the new graphRef element.
  nextTick(() => {
    if (previewNodes.value.length) {
      // Dispose old instance that was bound to the now-destroyed DOM
      if (chartInstance) {
        chartInstance.dispose()
        chartInstance = null
      }
      renderGraph({ nodes: previewNodes.value, links: previewLinks.value })
    }
  })
}

function openPreviewNewTab() {
  if (previewUrl.value) {
    window.open(previewUrl.value, '_blank')
  }
}

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
    const data = await fetchFolderKBFiles(kbName.value, currentPage.value, pageSize)
    files.value = data.items
    totalFiles.value = data.total
    totalSize.value = data.total_size != null ? formatFileSize(data.total_size) : calcTotalSize(data.items)
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

async function loadGraph(maxNodes?: number) {
  graphLoading.value = true
  try {
    // First try Memgraph (real LightRAG-extracted entities) using kb_name
    const memgraphData = await fetchKnowledgeGraph(undefined, kbName.value, maxNodes)
    if (memgraphData && memgraphData.nodes && memgraphData.nodes.length > 0) {
      graphStats.value = memgraphData.stats
      previewNodes.value = memgraphData.nodes
      previewLinks.value = memgraphData.links
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
    previewNodes.value = data.nodes
    previewLinks.value = data.links
    await nextTick()
    renderGraph(data)
  } catch {
    graphStats.value = null
  } finally {
    graphLoading.value = false
  }
}

/** Open the detail modal - load full graph data for the modal only */
async function openGraphDetail() {
  // Always start with preview data in the modal (quick display)
  detailNodes.value = previewNodes.value
  detailLinks.value = previewLinks.value
  detailStats.value = graphStats.value
  showGraphDetail.value = true

  // Then load full data if not yet fetched
  if (!detailDataLoaded) {
    try {
      const data = await fetchKnowledgeGraph(undefined, kbName.value, 5000, true)
      if (data && data.nodes && data.nodes.length > 0) {
        detailNodes.value = data.nodes
        detailLinks.value = data.links
        detailStats.value = data.stats || graphStats.value
        if (data.stats) graphStats.value = data.stats
        detailDataLoaded = true
        return
      }
    } catch {
      // fall through to synthetic graph
    }
    try {
      const data = await fetchFolderKBGraph(kbName.value)
      detailNodes.value = data.nodes
      detailLinks.value = data.links
      detailStats.value = data.stats || graphStats.value
      detailDataLoaded = true
    } catch {
      // keep preview data as fallback
    }
  }
}

function renderGraph(data: { nodes: any[]; links: any[] }) {
  if (!graphRef.value) {
    setTimeout(() => renderGraph(data), 200)
    return
  }
  const w = graphRef.value.clientWidth
  const h = graphRef.value.clientHeight
  if (w <= 0 || h <= 0) {
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

function goBack() { router.push('/knowledge-management?tab=management') }

onMounted(async () => {
  try {
    await Promise.all([loadFiles(), loadTags()])
  } finally {
    loading.value = false
  }
  await nextTick()
  await loadGraph(GRAPH_PREVIEW_MAX_NODES)
})

onUnmounted(() => {
  chartInstance?.dispose()
  chartInstance = null
})

watch(kbName, () => {
  if (kbName.value) {
    loading.value = true
    selectedFile.value = null
    detailDataLoaded = false
    Promise.all([loadFiles(), loadTags(), loadGraph(GRAPH_PREVIEW_MAX_NODES)])
      .finally(() => { loading.value = false })
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
  width: 340px; flex-shrink: 0;
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

/* Tag system section */
.tag-system-section {
  display: flex; flex-direction: column; gap: 8px; flex: 1; min-height: 0;
}
.section-label {
  font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.55); margin-bottom: 4px;
  display: flex; align-items: center;
}

.tag-tree-card {
  background: linear-gradient(180deg, rgba(0,212,255,0.03) 0%, rgba(17,24,39,0.5) 100%);
  border: 1px solid rgba(0,212,255,0.12);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  backdrop-filter: blur(4px);
}

/* Tag tree content — scrollable, takes remaining space */
.tag-tree-content {
  padding: 12px 10px 8px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

/* Summary chips at bottom */
.tag-tree-summary {
  display: flex;
  gap: 6px;
  padding: 8px 10px;
  border-top: 1px solid rgba(0,212,255,0.08);
  background: rgba(0,212,255,0.02);
  flex-shrink: 0;
}
.summary-chip {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 4px 0;
  border-radius: 6px;
  background: rgba(0,212,255,0.04);
}
.summary-chip-val {
  font-size: 15px; font-weight: 700;
  background: linear-gradient(135deg, #00d4ff, #00ff88);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.summary-chip-label { font-size: 9px; color: rgba(255,255,255,0.3); }

.tag-empty {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 20px 0; color: rgba(255,255,255,0.3); font-size: 12px;
}

/* Right content panel */
.content-panel {
  flex: 1; display: flex; flex-direction: column; overflow-y: auto; padding: 20px 24px; gap: 16px;
}

.file-section { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.section-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-shrink: 0;
}
.section-header h2 { font-size: 18px; font-weight: 600; color: #fff; margin: 0; }
.section-header h3 { font-size: 15px; font-weight: 600; color: #fff; margin: 0; }
.section-actions { display: flex; gap: 8px; }
.file-table-wrap {
  flex: 1; min-height: 0; border-radius: 10px; overflow: hidden;
  background: rgba(17,24,39,0.6); border: 1px solid rgba(0,212,255,0.15);
}

/* Clickable file rows */
:deep(.file-table) { cursor: pointer; }
:deep(.file-table .el-table__row):hover { cursor: pointer; }

.file-name-cell { display: flex; align-items: center; gap: 6px; }
.file-name-cell.clickable { cursor: pointer; }
.file-name-cell.clickable:hover span { color: #00d4ff; }
.drill-icon { margin-left: auto; opacity: 0; transition: opacity 0.2s; }
.file-name-cell.clickable:hover .drill-icon { opacity: 1; }

.ext-badge {
  font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px;
  background: rgba(0,212,255,0.1); color: #00d4ff;
}

.folder-file-tag {
  background: rgba(255,170,0,0.1) !important; border-color: rgba(255,170,0,0.3) !important;
  color: #ffaa00 !important;
}

/* Depth-colored tags in file list — match tag system hierarchy colors */
.depth-tag { margin-right: 4px; }
.depth-tag-1 {
  background: rgba(0, 212, 255, 0.08) !important;
  border-color: rgba(0, 212, 255, 0.25) !important;
  color: #00d4ff !important;
}
.depth-tag-2 {
  background: rgba(0, 255, 136, 0.06) !important;
  border-color: rgba(0, 255, 136, 0.2) !important;
  color: #00ff88 !important;
}
.depth-tag-3 {
  background: rgba(192, 132, 252, 0.06) !important;
  border-color: rgba(192, 132, 252, 0.2) !important;
  color: #c084fc !important;
}
.depth-tag-4 {
  background: rgba(255, 170, 0, 0.06) !important;
  border-color: rgba(255, 170, 0, 0.2) !important;
  color: #ffaa00 !important;
}

.pagination-bar { display: flex; justify-content: center; margin-top: 12px; }
.no-data { color: rgba(255,255,255,0.4); font-size: 13px; }

/* ---- File Detail View ---- */
.file-detail-section {
  display: flex; flex-direction: column; gap: 16px; flex: 1; min-height: 0;
}
.detail-header {
  display: flex; align-items: center; gap: 16px; flex-shrink: 0;
}
.detail-back-btn { font-size: 12px; }
.detail-file-info {
  display: flex; align-items: center; gap: 8px;
  background: rgba(17,24,39,0.6);
  border: 1px solid rgba(0,212,255,0.15);
  border-radius: 10px;
  padding: 10px 16px;
  flex: 1;
  min-width: 0;
}
.detail-file-name {
  font-size: 15px; font-weight: 600; color: #fff;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.detail-meta-row {
  display: flex; gap: 16px; flex-wrap: wrap; flex-shrink: 0;
}
.meta-item {
  display: flex; flex-direction: column; gap: 2px;
  background: rgba(17,24,39,0.4);
  border: 1px solid rgba(0,212,255,0.08);
  border-radius: 8px;
  padding: 8px 14px;
  min-width: 120px;
}
.meta-label { font-size: 10px; color: rgba(255,255,255,0.35); }
.meta-value { font-size: 12px; color: rgba(255,255,255,0.7); word-break: break-all; }
.meta-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.detail-star { color: rgba(255,255,255,0.15); font-size: 14px; }
.detail-star.active { color: #ffaa00; }

/* Preview section */
.preview-section {
  display: flex; flex-direction: column; gap: 10px; flex: 1; min-height: 0;
}
.preview-actions { display: flex; gap: 8px; }
.open-new-btn {
  color: #00d4ff !important;
  font-size: 12px;
  padding: 4px 8px;
}
.preview-card {
  flex: 1; min-height: 500px;
  background: linear-gradient(135deg, rgba(17,24,39,0.9) 0%, rgba(26,35,50,0.8) 100%);
  border: 1px solid rgba(0,212,255,0.2);
  border-radius: 12px;
  overflow: auto;
  position: relative;
}

/* vue-office preview container */
.preview-vue-office {
  height: 100%;
  min-height: 500px;
}

/* Text file preview */
.preview-text-wrap {
  height: 100%; min-height: 500px; overflow: auto;
}
.preview-text {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 13px; line-height: 1.6;
  color: rgba(255,255,255,0.8);
  padding: 16px 20px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  tab-size: 4;
}
.preview-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; min-height: 400px;
  gap: 10px; color: rgba(255,255,255,0.3); font-size: 13px;
}

/* Image preview */
.preview-image-wrap {
  display: flex; align-items: center; justify-content: center;
  height: 100%; min-height: 400px; padding: 20px;
  background: repeating-conic-gradient(rgba(255,255,255,0.03) 0% 25%, transparent 0% 50%) 0 0 / 20px 20px;
}
.preview-image {
  max-width: 100%; max-height: 600px; border-radius: 4px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}

/* Unsupported file preview */
.preview-unsupported {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; min-height: 400px;
  gap: 6px;
}
.unsupported-title { font-size: 14px; color: rgba(255,255,255,0.5); font-weight: 500; }
.unsupported-desc { font-size: 12px; color: rgba(255,255,255,0.3); }

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
.graph-loading-overlay {
  position: absolute; inset: 0; z-index: 10;
  display: flex; align-items: center; justify-content: center;
  background: rgba(17,24,39,0.75); border-radius: 12px;
  backdrop-filter: blur(2px); animation: fadeIn 0.2s ease;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.graph-loading-spinner { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.spinner-ring {
  width: 36px; height: 36px;
  border: 3px solid rgba(0,212,255,0.15); border-top-color: #00d4ff;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.spinner-text { font-size: 12px; color: rgba(255,255,255,0.7); letter-spacing: 0.5px; }
.graph-chart { height: 280px; }
.graph-stats { display: flex; gap: 20px; margin-top: 8px; justify-content: center; }
.graph-stat-item { display: flex; flex-direction: column; align-items: center; }
.gs-val { font-size: 16px; font-weight: 600; color: #00d4ff; }
.gs-label { font-size: 10px; color: rgba(255,255,255,0.4); }

.loading-state { display: flex; align-items: center; justify-content: center; height: 100%; color: rgba(255,255,255,0.5); }
</style>