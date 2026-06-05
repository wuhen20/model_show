<template>
  <div class="app-layout">
    <Header title="人工智能分部 · 模型微调组" subtitle="知识管理" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="knowledge-management">
          <!-- Page Header -->
          <div class="page-header">
            <div class="page-title">
              <h2>知识管理</h2>
              <p class="page-desc">构建高质量知识体系，赋能智能应用与业务决策</p>
            </div>
          </div>

          <!-- Secondary Tabs -->
          <el-tabs v-model="activeTab" class="knowledge-tabs">
            <!-- Tab 1: 首页 - 数据看板 -->
            <el-tab-pane name="home">
              <template #label>
                <span class="tab-label">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:5px">
                    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                    <polyline points="9 22 9 12 15 12 15 22"/>
                  </svg>
                  首页
                </span>
              </template>

              <div class="tab-content">
                <!-- Stats Row -->
                <div class="stats-row" v-if="stats">
                  <div class="stats-grid">
                    <div class="k-stat-card" v-for="stat in statCards" :key="stat.title">
                      <div class="k-stat-icon" :style="{ backgroundColor: stat.bgColor }">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" :stroke="stat.color" stroke-width="2">
                          <path :d="stat.iconPath"/>
                        </svg>
                      </div>
                      <div class="k-stat-info">
                        <div class="k-stat-title">{{ stat.title }}</div>
                        <div class="k-stat-value">
                          <span class="k-stat-number">{{ stat.value }}</span>
                          <span class="k-stat-unit">{{ stat.unit }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Charts Row -->
                <div class="charts-row">
                  <KnowledgeCharts />
                  <KnowledgeSource />
                  <KnowledgeTrend />
                </div>

                <!-- Bottom Row -->
                <div class="bottom-row">
                  <div class="bottom-left">
                    <KnowledgeTable :category-id="activeCategory" :workspace="activeWorkspace" @back="clearCategory" />
                  </div>
                  <div class="bottom-right">
                    <KnowledgeGraph :category-id="activeCategory" :workspace="activeWorkspace" @back="clearCategory" />
                  </div>
                </div>
              </div>
            </el-tab-pane>

            <!-- Tab 2: 知识库管理 — folder KBs only -->
            <el-tab-pane name="management">
              <template #label>
                <span class="tab-label">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:5px">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                  </svg>
                  知识库管理
                </span>
              </template>

              <div class="tab-content">
                <!-- Category card — only folder KBs -->
                <div class="category-card" v-if="!folderKBsLoading || folderKBs.length">
                  <div class="category-card-header">
                    <div class="category-card-header-left">
                      <div class="category-card-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffaa00" stroke-width="2">
                          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                      </div>
                      <span class="category-card-title">知识库分类</span>
                      <span class="category-card-count">共 {{ folderKBs.length }} 个知识库</span>
                    </div>
                  </div>
                  <div class="category-card-body" v-loading="folderKBsLoading">
                    <div
                      v-for="fkb in folderKBs"
                      :key="'folder-' + fkb.name"
                      class="sub-category-card folder-kb-card"
                      @click="navigateToFolderKB(fkb)"
                    >
                      <div class="sub-cat-header">
                        <div class="sub-cat-icon" style="background-color: rgba(255, 170, 0, 0.2)">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffaa00" stroke-width="2">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                          </svg>
                        </div>
                        <div class="sub-cat-info">
                          <div class="sub-cat-name">
                            {{ fkb.name }}
                            <span class="folder-kb-badge">文件夹</span>
                          </div>
                          <div class="sub-cat-count">
                            <span class="number">{{ fkb.doc_count }}</span>
                            <span class="unit">份文档</span>
                          </div>
                        </div>
                      </div>
                      <p class="sub-cat-desc">文件夹知识库 · 目录结构自动解析</p>
                      <div class="sub-cat-tags">
                        <template v-for="(tag, idx) in (fkb.top_tags || []).slice(0, 6)" :key="idx">
                          <span class="sub-tag depth-tag-1">{{ tag }}</span>
                        </template>
                        <span class="sub-overflow" v-if="(fkb.top_tags || []).length > 6">+{{ (fkb.top_tags || []).length - 6 }}</span>
                      </div>
                      <div class="sub-cat-action">
                        <span>浏览文件</span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M9 18l6-6-6-6"/>
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else-if="!folderKBsLoading && !folderKBs.length" class="empty-management">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(255,170,0,0.3)" stroke-width="1.5">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                  </svg>
                  <p>暂无知识库</p>
                  <p class="sub">请在环境变量 KNOWLEDGE_BASE_DIR 指向的目录中添加文件夹</p>
                </div>
              </div>
            </el-tab-pane>

            <!-- Tab 3: 知识能力工具 — 已隐藏 -->
          </el-tabs>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import KnowledgeCharts from '@/components/KnowledgeCharts.vue'
import KnowledgeSource from '@/components/KnowledgeSource.vue'
import KnowledgeTrend from '@/components/KnowledgeTrend.vue'
import KnowledgeTable from '@/components/KnowledgeTable.vue'
import KnowledgeGraph from '@/components/KnowledgeGraph.vue'
import { fetchKnowledgeStats, type KnowledgeStats } from '@/api/knowledge'
import { fetchFolderKBs, type FolderKBResponse } from '@/api/knowledge'

const router = useRouter()
const route = useRoute()
const activeTab = ref('home')
const stats = ref<KnowledgeStats | null>(null)
const activeCategory = ref<string>('')
const activeWorkspace = ref<string>('')
const folderKBs = ref<FolderKBResponse[]>([])
const folderKBsLoading = ref(false)
const folderKBsLoaded = ref(false)  // track if we've loaded at least once

watch(() => route.query.category, (val) => {
  activeCategory.value = (val as string) || ''
}, { immediate: true })

watch(() => route.query.workspace, (val) => {
  if (val) activeWorkspace.value = val as string
}, { immediate: true })

// Switch to management tab when a query param is present
watch(() => route.query.tab, (val) => {
  if (val === 'management') activeTab.value = 'management'
  else if (val === 'home') activeTab.value = 'home'
}, { immediate: true })

// Auto-switch to management tab when category is selected
watch(activeCategory, (val) => {
  if (val) activeTab.value = 'management'
})

// Lazy-load folder KBs when management tab is activated
watch(activeTab, async (tab) => {
  if (tab === 'management' && !folderKBsLoaded.value) {
    await loadFolderKBs()
  }
  // When switching back to home tab, ECharts charts need a resize
  // because they were hidden (display:none) while another tab was active
  if (tab === 'home') {
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event('resize'))
    })
  }
})

onMounted(async () => {
  try {
    const statsData = await fetchKnowledgeStats()
    stats.value = statsData
  } catch (e) {
    console.warn('[KnowledgeManagement] fetchKnowledgeStats failed:', e)
    stats.value = {
      total_count: 3300, structured_count: 425, unstructured_count: 2875,
      graph_entities: 0, business_domains: 5, completeness: 92.5, availability: 95.8
    }
  }

  // If management tab is active on mount, load folder KBs
  if (activeTab.value === 'management') {
    await loadFolderKBs()
  }
})

async function loadFolderKBs() {
  if (folderKBsLoading.value) return
  folderKBsLoading.value = true
  try {
    const data = await fetchFolderKBs()
    folderKBs.value = data.bases || []
  } catch {
    folderKBs.value = []
  } finally {
    folderKBsLoading.value = false
    folderKBsLoaded.value = true
  }
}

// Stat cards
const statCards = computed(() => {
  if (!stats.value) return []
  const s = stats.value
  return [
    { title: '知识总量', value: s.total_count.toLocaleString(), unit: '份', color: '#00d4ff', bgColor: 'rgba(0, 212, 255, 0.15)', iconPath: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8' },
    { title: '结构化知识', value: s.structured_count.toLocaleString(), unit: '份', color: '#00ff88', bgColor: 'rgba(0, 255, 136, 0.15)', iconPath: 'M3 3h18v18H3zM9 3v18M15 3v18M3 9h18M3 15h18' },
    { title: '非结构化知识', value: s.unstructured_count.toLocaleString(), unit: '份', color: '#a855f7', bgColor: 'rgba(168, 85, 247, 0.15)', iconPath: 'M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z' },
    { title: '知识图谱实体', value: s.graph_entities.toLocaleString(), unit: '个', color: '#ffaa00', bgColor: 'rgba(255, 170, 0, 0.15)', iconPath: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71' },
    { title: '覆盖业务域', value: s.business_domains, unit: '个', color: '#ff5555', bgColor: 'rgba(255, 85, 85, 0.15)', iconPath: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
  ]
})

function clearCategory() {
  activeWorkspace.value = ''
  router.push({ path: '/knowledge-management' })
}

function navigateToFolderKB(kb: FolderKBResponse) {
  router.push({ path: `/folder-kb/${encodeURIComponent(kb.name)}` })
}
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 12px 16px;
  min-height: 0;
}

.knowledge-management {
  padding: 0;
  flex: 1;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  padding: 16px 24px;
  border-radius: 12px;
}

.page-title h2 {
  font-size: 24px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 4px 0;
}

.page-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

/* ===== Tab Styles ===== */
.knowledge-tabs {
  margin-top: 0;
}

.knowledge-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.knowledge-tabs :deep(.el-tabs__nav-wrap::after) {
  background-color: rgba(0, 212, 255, 0.15);
}

.knowledge-tabs :deep(.el-tabs__item) {
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
  font-weight: 500;
  padding: 0 20px;
  height: 42px;
  line-height: 42px;
  transition: all 0.25s;
}

.knowledge-tabs :deep(.el-tabs__item:hover) {
  color: rgba(255, 255, 255, 0.8);
}

.knowledge-tabs :deep(.el-tabs__item.is-active) {
  color: #00d4ff;
  font-weight: 600;
}

.knowledge-tabs :deep(.el-tabs__active-bar) {
  background-color: #00d4ff;
  height: 2px;
  border-radius: 1px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
}

.tab-content {
  animation: tabFadeIn 0.25s ease;
}

@keyframes tabFadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
}

/* ===== Stats Row ===== */
.stats-row {
  margin-bottom: 16px;
}

.stats-grid {
  display: flex;
  gap: 12px;
}

.k-stat-card {
  flex: 1;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 10px;
  padding: 14px;
  transition: all 0.3s;
  cursor: pointer;
  min-width: 0;
}

.k-stat-card:hover {
  border-color: rgba(0, 212, 255, 0.4);
  box-shadow: 0 4px 20px rgba(0, 212, 255, 0.1);
}

.k-stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 10px;
}

.k-stat-info {
  display: flex;
  flex-direction: column;
}

.k-stat-title {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.k-stat-value {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.k-stat-number {
  font-size: 20px;
  font-weight: 600;
  color: #ffffff;
}

.k-stat-unit {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

/* ===== Charts Row ===== */
.charts-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

/* ===== Category Card ===== */
.category-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(255, 170, 0, 0.2);
  border-radius: 12px;
  margin-bottom: 16px;
  overflow: hidden;
}

.category-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(255, 170, 0, 0.1);
}

.category-card-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.category-card-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: rgba(255, 170, 0, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.category-card-title {
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
}

.category-card-count {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-left: 8px;
}

.category-card-body {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  padding: 14px;
  min-height: 60px;
}

.sub-category-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 170, 0, 0.1);
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  flex-direction: column;
}

.sub-category-card:hover {
  border-color: rgba(255, 170, 0, 0.35);
  background: rgba(255, 255, 255, 0.05);
}

.sub-cat-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.sub-cat-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.sub-cat-info {
  flex: 1;
  min-width: 0;
}

.sub-cat-name {
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sub-cat-count {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.sub-cat-count .number {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
}

.sub-cat-count .unit {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.sub-cat-desc {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1.5;
  margin: 0 0 8px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.sub-cat-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 8px;
  flex: 1;
  max-height: 48px;
  overflow: hidden;
}

.sub-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.sub-overflow {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.45);
  white-space: nowrap;
}

.sub-cat-action {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  font-size: 12px;
  color: #ffaa00;
}

/* Folder KB card styles */
.folder-kb-card {
  border-color: rgba(255, 170, 0, 0.2);
  background: rgba(255, 170, 0, 0.03);
}

.folder-kb-card:hover {
  border-color: rgba(255, 170, 0, 0.45);
  background: rgba(255, 170, 0, 0.07);
  box-shadow: 0 0 16px rgba(255, 170, 0, 0.12);
}

.folder-kb-badge {
  display: inline-block;
  font-size: 9px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 3px;
  margin-left: 6px;
  vertical-align: middle;
  background: linear-gradient(135deg, rgba(255, 170, 0, 0.3), rgba(255, 85, 85, 0.2));
  color: #ffaa00;
  letter-spacing: 0.5px;
}

/* Depth-colored tags — consistent with FolderKBDetail tag system */
.depth-tag-1 {
  background: rgba(0, 212, 255, 0.1);
  color: #00d4ff;
}
.depth-tag-2 {
  background: rgba(0, 255, 136, 0.08);
  color: #00ff88;
}
.depth-tag-3 {
  background: rgba(192, 132, 252, 0.08);
  color: #c084fc;
}
.depth-tag-4 {
  background: rgba(255, 170, 0, 0.08);
  color: #ffaa00;
}

.empty-management {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: rgba(255, 255, 255, 0.35);
  font-size: 14px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.6) 0%, rgba(26, 35, 50, 0.5) 100%);
  border: 1px solid rgba(255, 170, 0, 0.1);
  border-radius: 12px;
}

.empty-management .sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.25);
  margin-top: 4px;
}

/* ===== Bottom Row ===== */
.bottom-row {
  display: grid;
  grid-template-columns: 7fr 5fr;
  gap: 12px;
  align-items: stretch;
}

.bottom-left,
.bottom-right {
  min-height: 0;
}

.bottom-right {
  display: flex;
}

.bottom-right :deep(.knowledge-graph-card) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.bottom-right :deep(.graph-body) {
  flex: 1;
  min-height: 0;
}

.bottom-right :deep(.graph-chart) {
  height: auto;
  min-height: 260px;
}
</style>
