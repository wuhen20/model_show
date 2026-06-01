<template>
  <div class="app-layout">
    <Header title="人工智能分部 · 模型微调组" subtitle="知识管理" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="knowledge-management">
          <div class="page-header">
            <div class="page-title">
              <h2>知识管理</h2>
              <p class="page-desc">构建高质量知识体系，赋能智能应用与业务决策</p>
            </div>
            <div class="page-actions">
              <el-button type="primary">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px;">
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                新建知识
              </el-button>
              <el-button>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px;">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
                </svg>
                知识导入
              </el-button>
            </div>
          </div>

          <div class="breadcrumb-bar" v-if="activeCategory">
            <el-button text size="small" @click="clearCategory" class="breadcrumb-back">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M15 18l-6-6 6-6"/>
              </svg>
              全部知识库
            </el-button>
            <span class="breadcrumb-sep">/</span>
            <span class="breadcrumb-current">{{ activeCategory }}</span>
          </div>

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

          <div class="charts-row">
            <KnowledgeCharts />
            <KnowledgeSource />
            <KnowledgeQuality />
            <KnowledgeTrend />
          </div>

          <div class="category-card" v-if="categories.length">
            <div class="category-card-header">
              <div class="category-card-header-left">
                <div class="category-card-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                  </svg>
                </div>
                <span class="category-card-title">知识库分类</span>
                <span class="category-card-count">共 {{ categories.length }} 个知识库</span>
              </div>
            </div>
            <div class="category-card-body">
              <div
                v-for="cat in categories"
                :key="cat.id"
                class="sub-category-card"
                @click="navigateCategory(cat)"
              >
                <div class="sub-cat-header">
                  <div class="sub-cat-icon" :style="{ backgroundColor: cat.color }">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2">
                      <path :d="getCategoryIcon(cat.icon)"/>
                    </svg>
                  </div>
                  <div class="sub-cat-info">
                    <div class="sub-cat-name">{{ cat.name }}</div>
                    <div class="sub-cat-count">
                      <span class="number">{{ cat.doc_count }}</span>
                      <span class="unit">份文档</span>
                    </div>
                  </div>
                </div>
                <p class="sub-cat-desc">{{ cat.description }}</p>
                <div class="sub-cat-tags">
                  <template v-for="(sub, idx) in (cat.sub_categories || []).slice(0, 4)" :key="sub.id">
                    <span class="sub-tag" :style="{ backgroundColor: sub.color + '22', color: sub.color }">{{ sub.name }}({{ sub.doc_count }})</span>
                  </template>
                  <span class="sub-overflow" v-if="(cat.sub_categories || []).length > 4">+{{ (cat.sub_categories || []).length - 4 }}</span>
                </div>
                <div class="sub-cat-action">
                  <span>查看详情</span>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 18l6-6-6-6"/>
                  </svg>
                </div>
              </div>
            </div>
          </div>

          <div class="bottom-row">
            <div class="bottom-left">
              <KnowledgeTable :category-id="activeCategory" @back="clearCategory" />
            </div>
            <div class="bottom-right">
              <KnowledgeGraph :category-id="activeCategory" @back="clearCategory" />
            </div>
          </div>

          <div class="tools-row">
            <KnowledgeTools />
          </div>
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
import KnowledgeQuality from '@/components/KnowledgeQuality.vue'
import KnowledgeTrend from '@/components/KnowledgeTrend.vue'
import KnowledgeTable from '@/components/KnowledgeTable.vue'
import KnowledgeGraph from '@/components/KnowledgeGraph.vue'
import KnowledgeTools from '@/components/KnowledgeTools.vue'
import { fetchKnowledgeStats, fetchCategories, type KnowledgeStats, type KnowledgeCategory } from '@/api/knowledge'

const router = useRouter()
const route = useRoute()
const stats = ref<KnowledgeStats | null>(null)
const categories = ref<KnowledgeCategory[]>([])
const activeCategory = ref<string>('')

watch(() => route.query.category, (val) => {
  activeCategory.value = (val as string) || ''
}, { immediate: true })

onMounted(async () => {
  try {
    const [statsData, catsData] = await Promise.all([
      fetchKnowledgeStats(),
      fetchCategories()
    ])
    stats.value = statsData
    categories.value = catsData
  } catch {
    stats.value = {
      total_count: 2887, structured_count: 505, unstructured_count: 2382,
      graph_entities: 36584, business_domains: 5, completeness: 92.5, availability: 95.8
    }
  }
})

const statCards = computed(() => {
  if (!stats.value) return []
  const s = stats.value
  return [
    { title: '知识总量', value: s.total_count.toLocaleString(), unit: '份', color: '#00d4ff', bgColor: 'rgba(0, 212, 255, 0.15)', iconPath: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8' },
    { title: '结构化知识', value: s.structured_count.toLocaleString(), unit: '份', color: '#00ff88', bgColor: 'rgba(0, 255, 136, 0.15)', iconPath: 'M3 3h18v18H3zM9 3v18M15 3v18M3 9h18M3 15h18' },
    { title: '非结构化知识', value: s.unstructured_count.toLocaleString(), unit: '份', color: '#a855f7', bgColor: 'rgba(168, 85, 247, 0.15)', iconPath: 'M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z' },
    { title: '知识图谱实体', value: s.graph_entities.toLocaleString(), unit: '个', color: '#ffaa00', bgColor: 'rgba(255, 170, 0, 0.15)', iconPath: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71' },
    { title: '覆盖业务域', value: s.business_domains, unit: '个', color: '#ff5555', bgColor: 'rgba(255, 85, 85, 0.15)', iconPath: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
    { title: '知识完整度', value: s.completeness, unit: '%', color: '#36a3f7', bgColor: 'rgba(54, 163, 247, 0.15)', iconPath: 'M22 11.08V12a10 10 0 1 1-5.93-9.14' },
    { title: '知识可用性', value: s.availability, unit: '%', color: '#00ff88', bgColor: 'rgba(0, 255, 136, 0.15)', iconPath: 'M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z' }
  ]
})

function getCategoryIcon(iconName: string) {
  const icons: Record<string, string> = {
    brain: 'M12 2a8 8 0 0 0-8 8c0 3.4 2.1 6.3 5 7.5V20h6v-2.5c2.9-1.2 5-4.1 5-7.5a8 8 0 0 0-8-8z',
    plug: 'M12 22V8M5 12H2a10 10 0 0 0 20 0h-3',
    database: 'M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z',
    scale: 'M12 3v18M3 12h18M5.5 5.5l13 13M18.5 5.5l-13 13',
    'trending-down': 'M23 18l-9.5-9.5-5 5L1 6',
    shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'
  }
  return icons[iconName] || icons.brain
}

function navigateCategory(cat: KnowledgeCategory) {
  router.push({ path: '/knowledge-management', query: { category: cat.id } })
}

function clearCategory() {
  router.push({ path: '/knowledge-management' })
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
  margin-bottom: 16px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  padding: 20px 24px;
  border-radius: 12px;
}

.page-title h2 {
  font-size: 24px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 8px 0;
}

.page-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.page-actions {
  display: flex;
  gap: 12px;
}

.breadcrumb-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  padding: 8px 14px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
}

.breadcrumb-back {
  color: #00d4ff !important;
  font-size: 13px;
  padding: 0;
}

.breadcrumb-sep {
  color: rgba(255, 255, 255, 0.3);
  font-size: 13px;
}

.breadcrumb-current {
  color: #ffffff;
  font-size: 13px;
  font-weight: 500;
}

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

.charts-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.category-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  margin-bottom: 16px;
  overflow: hidden;
}

.category-card-header {
  padding: 14px 18px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
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
  background: rgba(0, 212, 255, 0.12);
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
  margin-left: auto;
}

.category-card-body {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  padding: 14px;
}

.sub-category-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(0, 212, 255, 0.1);
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  flex-direction: column;
}

.sub-category-card:hover {
  border-color: rgba(0, 212, 255, 0.35);
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
  color: #00d4ff;
}

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

.tools-row {
  margin-top: 16px;
}
</style>
