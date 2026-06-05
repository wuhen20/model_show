<template>
  <div class="app-layout">
    <Header title="人工智能分部 · 模型微调组" subtitle="知识库详情" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <!-- Loading / Empty states -->
        <div v-if="loading" class="loading-state"><p>加载中...</p></div>
        <div v-else-if="!kb" class="loading-state"><p>知识库不存在</p></div>

        <div v-else class="detail-layout">
          <!-- Left: Upload panel -->
          <aside class="upload-panel">
            <div class="panel-inner">
              <el-button text @click="goBack" class="back-btn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
                返回
              </el-button>

              <!-- KB info strip -->
              <div class="kb-strip">
                <div class="kb-icon-sm" :style="{ backgroundColor: kb.color }">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path :d="getIconPath(kb.icon)"/></svg>
                </div>
                <div class="kb-strip-info">
                  <span class="kb-strip-name">{{ kb.name }}</span>
                  <span class="kb-strip-desc">{{ kb.description }}</span>
                </div>
              </div>

              <!-- Stats row -->
              <div class="stats-row">
                <div class="mini-stat">
                  <span class="mini-val">{{ kb.doc_count }}</span>
                  <span class="mini-label">文档</span>
                </div>
                <div class="mini-stat">
                  <span class="mini-val">{{ totalChunks }}</span>
                  <span class="mini-label">切片</span>
                </div>
                <div class="mini-stat">
                  <span class="mini-val">{{ pendingSyncCount }}</span>
                  <span class="mini-label">待同步</span>
                </div>
              </div>

              <!-- Tags display (read-only) -->
              <div class="kb-tags-display" v-if="kb.tags && kb.tags.length">
                <span class="section-label">标签体系</span>
                <TagTreeReadonly :tags="kb.tags" />
              </div>

              <!-- Tag selection for upload -->
              <div class="upload-section">
                <div class="section-label">
                  选择标签 <span class="required">*</span>
                  <el-button size="small" text @click="showNewTagForm = !showNewTagForm" style="margin-left:8px">+ 新建</el-button>
                </div>
                <div class="tag-check-area" v-if="tagTree.length">
                  <TagCheckbox
                    v-for="t in tagTree"
                    :key="t.id"
                    :tag="t"
                    :depth="1"
                    :all-tags="tagTree"
                    @check-change="onTagCheckChange"
                  />
                </div>
                <div v-else class="tag-empty-hint">
                  暂无标签，
                  <el-button size="small" text type="primary" @click="showNewTagForm = true">去创建</el-button>
                </div>

                <!-- New tag form -->
                <div v-if="showNewTagForm" class="new-tag-form">
                  <div class="new-tag-row">
                    <el-select v-model="newTagParentId" size="small" placeholder="挂载位置" style="width:160px" clearable>
                      <el-option value="" label="（根级）" />
                      <el-option v-for="t in flatAllTags" :key="t.id" :value="t.id" :label="indentLabel(t)" />
                    </el-select>
                    <el-input v-model="newTagName" size="small" placeholder="标签名" style="width:120px" />
                    <el-button size="small" type="primary" :disabled="!newTagName" @click="handleCreateTag">确认</el-button>
                    <el-button size="small" @click="showNewTagForm = false">取消</el-button>
                  </div>
                </div>

                <div class="selected-tags-bar" v-if="selectedTagIds.length">
                  已选：
                  <el-tag v-for="tid in selectedTagIds" :key="tid" size="small" type="info" closable @close="removeSelectedTag(tid)">
                    {{ getTagName(tid) }}
                  </el-tag>
                </div>
              </div>

              <!-- Drop zone -->
              <el-upload
                ref="uploadRef"
                :auto-upload="false"
                multiple
                drag
                :on-change="onFileChange"
                :file-list="fileList"
                :before-upload="() => false"
                accept=".pdf,.docx,.doc,.txt,.xlsx,.xls,.md,.csv"
              >
                <div class="upload-drop">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
                  <p class="drop-text">拖拽或<em>点击上传</em></p>
                  <p class="drop-sub">PDF / DOCX / TXT / XLSX / MD</p>
                </div>
              </el-upload>

              <div class="upload-actions" v-if="fileList.length">
                <el-button type="primary" :loading="uploading" :disabled="!selectedTagIds.length" @click="handleUpload">
                  上传 {{ fileList.length }} 个文件
                </el-button>
                <el-button @click="clearFiles">清空</el-button>
              </div>
            </div>
          </aside>

          <!-- Right: Document table -->
          <section class="doc-panel">
            <div class="doc-header">
              <h2>文档列表</h2>
              <div class="doc-header-actions">
                <el-button size="small" type="success" :disabled="!pendingSyncCount" :loading="syncing" @click="handleSync">
                  同步 LightRAG ({{ pendingSyncCount }})
                </el-button>
                <el-button size="small" @click="refreshDocs">刷新</el-button>
              </div>
            </div>
            <div class="doc-table-wrap">
              <el-table :data="docs" style="width:100%" v-loading="docsLoading" empty-text="暂无文档，请先上传文件" height="100%">
                <el-table-column prop="file_name" label="文件名" min-width="220">
                  <template #default="{ row }">
                    <span class="file-name-link" @click="viewChunks(row)">{{ row.file_name }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="标签" min-width="160">
                  <template #default="{ row }">
                    <el-tag v-for="t in row.tags" :key="t.id" size="small" style="margin-right:4px">{{ t.name }}</el-tag>
                    <span v-if="!row.tags?.length" class="no-data">-</span>
                  </template>
                </el-table-column>
                <el-table-column prop="chunk_count" label="切片" width="70" align="center" />
                <el-table-column prop="status" label="状态" width="90" align="center">
                  <template #default="{ row }">
                    <el-tag :type="getStatusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="140" align="center">
                  <template #default="{ row }">
                    <el-button size="small" text type="primary" @click="viewChunks(row)">切片</el-button>
                    <el-button size="small" text type="danger" @click="handleDeleteDoc(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </section>
        </div>

        <!-- Chunk drawer -->
        <el-drawer v-model="chunkDrawer" title="切片详情" direction="rtl" size="50%">
          <div v-loading="chunksLoading">
            <div v-for="c in chunks" :key="c.id" class="chunk-card">
              <div class="chunk-meta">
                <el-tag :type="c.chunk_type === 'parent' ? 'warning' : 'info'" size="small">
                  {{ c.chunk_type === 'parent' ? '父切片' : '子切片' }} #{{ c.chunk_index }}
                </el-tag>
              </div>
              <div class="chunk-content">{{ c.content }}</div>
            </div>
            <div v-if="!chunks.length && !chunksLoading" class="no-data">暂无切片</div>
          </div>
        </el-drawer>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import TagCheckbox from '@/components/TagCheckbox.vue'
import TagTreeReadonly from '@/components/TagTreeReadonly.vue'
import {
  fetchKnowledgeBaseDetail, fetchKBDocuments, fetchDocumentChunks,
  uploadDocuments, deleteDocument, syncToLightRAG,
  fetchKBTags, createKBTag,
  type KBResponse, type DocumentResponse, type TagResponse, type ChunkResponse,
} from '@/api/knowledge'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const kbId = computed(() => route.params.id as string)

const loading = ref(true)
const kb = ref<KBResponse | null>(null)
const docs = ref<DocumentResponse[]>([])
const docsLoading = ref(false)
const uploading = ref(false)
const syncing = ref(false)
const fileList = ref<any[]>([])
const uploadRef = ref<any>()
const tagTree = ref<(TagResponse & { _selected?: boolean })[]>([])
const showNewTagForm = ref(false)
const newTagName = ref('')
const newTagParentId = ref('')

const chunkDrawer = ref(false)
const chunks = ref<ChunkResponse[]>([])
const chunksLoading = ref(false)

const selectedTagIds = computed(() => {
  const ids: string[] = []
  function collect(tags: (TagResponse & { _selected?: boolean })[]) {
    for (const t of tags) {
      if (t._selected) ids.push(t.id)
      if (t.children?.length) collect(t.children as (TagResponse & { _selected?: boolean })[])
    }
  }
  collect(tagTree.value)
  return ids
})

const totalChunks = computed(() => docs.value.reduce((s, d) => s + (d.chunk_count || 0), 0))
const pendingSyncCount = ref(0)

function getIconPath(icon: string) {
  const m: Record<string, string> = {
    brain: 'M12 2a8 8 0 0 0-8 8c0 3.4 2.1 6.3 5 7.5V20h6v-2.5c2.9-1.2 5-4.1 5-7.5a8 8 0 0 0-8-8z',
    plug: 'M12 22V8M5 12H2a10 10 0 0 0 20 0h-3', database: 'M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z',
    scale: 'M12 3v18M3 12h18M5.5 5.5l13 13M18.5 5.5l-13 13',
    'trending-down': 'M23 18l-9.5-9.5-5 5L1 6', shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
    book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z',
    'file-text': 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8',
    layers: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
    cpu: 'M6 3v3M10 3v3M14 3v3M18 3v3M6 21v-3M10 21v-3M14 21v-3M18 21v-3M3 6h3M3 10h3M3 14h3M3 18h3M21 6h-3M21 10h-3M21 14h-3M21 18h-3M6 6h12v12H6z',
    globe: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z',
    zap: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
    target: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 6v6l4 2',
    search: 'M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM21 21l-4.35-4.35',
    code: 'M16 18l6-6-6-6M8 6l-6 6 6 6',
    box: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zM3.27 6.96L12 12.01l8.73-5.05M12 22.08V12',
    share: 'M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8M16 6l-4-4-4 4M12 2v13',
    cog: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z',
    link: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71',
    feather: 'M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5zM16 8L2 22M17.5 15H9',
    'git-branch': 'M6 3v6M6 21v-4a2 2 0 0 1 2-2h4M18 3a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM6 9a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM18 7v4a2 2 0 0 1-2 2H10',
  }
  return m[icon] || m.brain
}

function getStatusType(s: string) { return s === 'completed' ? 'success' : s === 'failed' ? 'danger' : s === 'pending' ? 'info' : 'warning' }
function statusLabel(s: string) {
  const m: Record<string, string> = { pending: '待处理', chunking: '切片中', vectorizing: '向量化', completed: '已完成', failed: '失败', synced: '已同步' }
  return m[s] || s
}

function getTagName(tagId: string) {
  function find(tags: TagResponse[]): string {
    for (const t of tags) {
      if (t.id === tagId) return t.name
      if (t.children?.length) { const r = find(t.children); if (r !== tagId) return r }
    }
    return tagId
  }
  return find(tagTree.value)
}

function onTagCheckChange() { /* reactivity trigger */ }

function removeSelectedTag(tid: string) {
  function uncheck(tags: (TagResponse & { _selected?: boolean })[]): boolean {
    for (const t of tags) {
      if (t.id === tid) { t._selected = false; return true }
      if (t.children?.length && uncheck(t.children as (TagResponse & { _selected?: boolean })[])) return true
    }
    return false
  }
  uncheck(tagTree.value)
}

const flatAllTags = computed(() => {
  const result: (TagResponse & { _depth: number })[] = []
  function walk(tags: TagResponse[], depth: number) {
    for (const t of tags) { result.push({ ...t, _depth: depth }); if (t.children?.length) walk(t.children, depth + 1) }
  }
  walk(tagTree.value, 1)
  return result
})

function indentLabel(t: TagResponse & { _depth: number }): string {
  return '　'.repeat(t._depth - 1) + t.name
}

async function handleCreateTag() {
  if (!newTagName.value) return
  try {
    const parentId = newTagParentId.value || null
    let level = 1
    if (parentId) { const parent = flatAllTags.value.find(t => t.id === parentId); level = parent ? parent._depth + 1 : 2 }
    await createKBTag(kbId.value, { level, name: newTagName.value, parent_tag_id: parentId })
    ElMessage.success('标签创建成功')
    showNewTagForm.value = false; newTagName.value = ''; newTagParentId.value = ''
    await refreshTags()
  } catch (e: any) { ElMessage.error(e.message || '创建标签失败') }
}

function onFileChange(_file: any, fileListIn: any[]) { fileList.value = fileListIn }
function clearFiles() { fileList.value = []; uploadRef.value?.clearFiles() }

async function handleUpload() {
  if (!selectedTagIds.value.length) { ElMessage.warning('请先选择标签'); return }
  uploading.value = true
  try {
    const fd = new FormData()
    for (const f of fileList.value) { if (f.raw) fd.append('files', f.raw) }
    fd.append('tag_ids', JSON.stringify(selectedTagIds.value))
    await uploadDocuments(kbId.value, fd)
    ElMessage.success('上传成功'); clearFiles(); await refreshDocs()
  } catch (e: any) { ElMessage.error(e.message || '上传失败') } finally { uploading.value = false }
}

async function handleDeleteDoc(row: DocumentResponse) {
  try { await ElMessageBox.confirm(`确定要删除 "${row.file_name}" 吗？`, '确认删除', { type: 'warning' }) } catch { return }
  try { await deleteDocument(row.id); ElMessage.success('删除成功'); await refreshDocs() }
  catch (e: any) { ElMessage.error(e.message || '删除失败') }
}

async function viewChunks(row: DocumentResponse) {
  chunkDrawer.value = true; chunksLoading.value = true
  try { chunks.value = await fetchDocumentChunks(row.id) } catch { chunks.value = [] } finally { chunksLoading.value = false }
}

async function handleSync() {
  syncing.value = true
  try { const r = await syncToLightRAG(kbId.value); ElMessage.success(r.message); await refreshDocs() }
  catch (e: any) { ElMessage.error(e.message || '同步失败') } finally { syncing.value = false }
}

async function refreshDocs() {
  docsLoading.value = true
  try { const r = await fetchKBDocuments(kbId.value, 1, 100); docs.value = r.items; pendingSyncCount.value = r.items.filter(d => d.status === 'completed').length }
  catch { docs.value = [] } finally { docsLoading.value = false }
}

async function refreshTags() {
  try { tagTree.value = (await fetchKBTags(kbId.value)).map(t => ({ ...t, _selected: false })) } catch { tagTree.value = [] }
}

function goBack() { router.push('/knowledge-management?tab=management') }

onMounted(async () => {
  try { kb.value = await fetchKnowledgeBaseDetail(kbId.value) } catch { kb.value = null } finally { loading.value = false }
  await Promise.all([refreshDocs(), refreshTags()])
})
</script>

<style scoped>
.app-layout { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
.main-content { display: flex; flex: 1; overflow: hidden; min-height: 0; }
.content-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 0; min-height: 0; position: relative; }

/* Full-height layout: left aside + right table */
.detail-layout {
  flex: 1; display: flex; overflow: hidden;
}

/* Left upload panel */
.upload-panel {
  width: 340px; flex-shrink: 0;
  border-right: 1px solid rgba(0,212,255,0.12);
  background: linear-gradient(180deg, rgba(17,24,39,0.95) 0%, rgba(10,14,26,0.9) 100%);
}
.panel-inner {
  height: 100%; overflow-y: auto; padding: 20px 18px;
  display: flex; flex-direction: column; gap: 16px;
}
.back-btn { color: rgba(255,255,255,0.6); font-size: 12px; padding: 0; margin-bottom: 2px; }

.kb-strip { display: flex; align-items: center; gap: 12px; }
.kb-icon-sm { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.kb-strip-info { min-width: 0; }
.kb-strip-name { display: block; font-size: 15px; font-weight: 600; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kb-strip-desc { display: block; font-size: 11px; color: rgba(255,255,255,0.45); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.stats-row { display: flex; gap: 16px; }
.mini-stat { display: flex; flex-direction: column; align-items: center; }
.mini-val { font-size: 18px; font-weight: 700; color: #fff; }
.mini-label { font-size: 10px; color: rgba(255,255,255,0.4); }

.kb-tags-display { }
.section-label { font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.55); margin-bottom: 8px; display: flex; align-items: center; }

/* Upload section */
.upload-section {
  background: rgba(255,255,255,0.03); border: 1px solid rgba(0,212,255,0.1);
  border-radius: 10px; padding: 14px;
}
.tag-check-area { max-height: 180px; overflow-y: auto; }
.tag-empty-hint { font-size: 12px; color: rgba(255,255,255,0.35); }
.new-tag-form { margin-top: 10px; padding: 10px; background: rgba(0,212,255,0.05); border-radius: 6px; }
.new-tag-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.selected-tags-bar { margin-top: 10px; font-size: 12px; color: rgba(255,255,255,0.5); display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }

/* Upload drop zone */
.upload-drop { padding: 16px 12px; text-align: center; }
.drop-text { font-size: 13px; color: rgba(255,255,255,0.55); margin: 8px 0 2px; }
.drop-text em { color: #00d4ff; font-style: normal; cursor: pointer; }
.drop-sub { font-size: 11px; color: rgba(255,255,255,0.3); margin: 0; }
.upload-actions { display: flex; gap: 10px; justify-content: flex-end; }

/* Right: doc table */
.doc-panel {
  flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 20px 24px;
}
.doc-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-shrink: 0;
}
.doc-header h2 { font-size: 18px; font-weight: 600; color: #fff; margin: 0; }
.doc-header-actions { display: flex; gap: 8px; }
.doc-table-wrap {
  flex: 1; min-height: 0; border-radius: 10px; overflow: hidden;
  background: rgba(17,24,39,0.6); border: 1px solid rgba(0,212,255,0.15);
}

.file-name-link { color: #00d4ff; cursor: pointer; }
.file-name-link:hover { text-decoration: underline; }
.no-data { color: rgba(255,255,255,0.4); font-size: 13px; }
.required { color: #ff5555; }

/* Chunk drawer content */
.chunk-card { background: rgba(255,255,255,0.04); border-radius: 8px; padding: 14px; margin-bottom: 10px; border: 1px solid rgba(0,212,255,0.1); }
.chunk-meta { margin-bottom: 8px; }
.chunk-content { font-size: 13px; color: rgba(255,255,255,0.75); line-height: 1.7; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; }

.loading-state { display: flex; align-items: center; justify-content: center; height: 100%; color: rgba(255,255,255,0.5); }
</style>
