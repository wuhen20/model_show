<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="知识详情" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="knowledge-detail" v-if="detail">
          <div class="detail-header">
            <el-button text @click="goBack" class="back-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M15 18l-6-6 6-6"/>
              </svg>
              返回知识管理
            </el-button>
          </div>

          <div class="detail-card">
            <div class="detail-title-row">
              <h1 class="detail-title">{{ detail.title }}</h1>
              <el-tag :type="detail.status === '已发布' ? 'success' : 'warning'" size="large">
                {{ detail.status }}
              </el-tag>
            </div>

            <div class="detail-meta">
              <div class="meta-item">
                <span class="meta-label">所属知识库</span>
                <router-link :to="{ path: '/knowledge-management', query: { category: detail.parent_category } }" class="meta-link">
                  {{ detail.parent_category }}
                </router-link>
              </div>
              <div class="meta-item">
                <span class="meta-label">所属分类</span>
                <router-link :to="{ path: '/knowledge-management', query: { category: detail.category_id } }" class="meta-link">
                  {{ detail.category_name }}
                </router-link>
              </div>
              <div class="meta-item">
                <span class="meta-label">知识类型</span>
                <span class="meta-value">{{ detail.knowledge_type }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">知识来源</span>
                <span class="meta-value">{{ detail.source }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">更新时间</span>
                <span class="meta-value">{{ detail.update_time }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">质量评分</span>
                <div class="score-stars">
                  <svg
                    v-for="i in 5" :key="i"
                    width="18" height="18" viewBox="0 0 24 24" fill="none"
                    :stroke="i <= detail.score ? '#ffaa00' : 'rgba(255,255,255,0.2)'"
                    stroke-width="2"
                  >
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                  </svg>
                </div>
              </div>
            </div>

            <div class="detail-tags" v-if="detail.tags && detail.tags.length">
              <span class="tags-label">标签</span>
              <el-tag
                v-for="tag in detail.tags"
                :key="tag"
                size="small"
                type="info"
                class="detail-tag"
              >{{ tag }}</el-tag>
            </div>

            <div class="detail-section">
              <h3 class="section-heading">知识描述</h3>
              <p class="detail-desc">{{ detail.description }}</p>
            </div>

            <div class="detail-section">
              <h3 class="section-heading">内容摘要</h3>
              <div class="detail-content">{{ detail.content }}</div>
            </div>

            <div class="detail-section">
              <h3 class="section-heading">文件路径</h3>
              <div class="file-path">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span>{{ detail.file_path }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="loading-state" v-else>
          <p>加载中...</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { fetchKnowledgeDetail, type KnowledgeDetail } from '@/api/knowledge'

const route = useRoute()
const router = useRouter()
const detail = ref<KnowledgeDetail | null>(null)

onMounted(async () => {
  const id = route.params.id as string
  if (id) {
    try {
      detail.value = await fetchKnowledgeDetail(id)
    } catch {
      detail.value = null
    }
  }
})

function goBack() {
  const cat = detail.value?.category_id || ''
  router.push({ path: '/knowledge-management', query: cat ? { category: cat } : {} })
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

.knowledge-detail {
  flex: 1;
  overflow-y: auto;
}

.detail-header {
  margin-bottom: 16px;
}

.back-btn {
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
}

.back-btn:hover {
  color: #00d4ff;
}

.detail-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 32px;
}

.detail-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.detail-title {
  font-size: 24px;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
  line-height: 1.4;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  margin-bottom: 20px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.meta-value {
  font-size: 14px;
  color: #ffffff;
  font-weight: 500;
}

.meta-link {
  font-size: 14px;
  color: #00d4ff;
  text-decoration: none;
  font-weight: 500;
}

.meta-link:hover {
  text-decoration: underline;
}

.score-stars {
  display: flex;
  gap: 2px;
}

.detail-tags {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
}

.tags-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
}

.detail-tag {
  border: none;
}

.detail-section {
  margin-bottom: 24px;
}

.section-heading {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
}

.detail-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.8;
  margin: 0;
}

.detail-content {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.8;
  padding: 16px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  border-left: 3px solid #00d4ff;
}

.file-path {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  word-break: break-all;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: rgba(255, 255, 255, 0.5);
}
</style>
