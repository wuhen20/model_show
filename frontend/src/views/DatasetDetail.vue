<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { datasetsApi } from '@/api/datasets'
import {
  datasetFormatLabels,
  datasetTypeLabels,
  sceneCatalog,
  type DatasetDetail,
} from '@/data/models'
import YoloPreview from '@/components/YoloPreview.vue'

const route = useRoute()
const router = useRouter()

const dsId = Number(route.params.id)
const data = ref<DatasetDetail | null>(null)
const loading = ref(false)
const errorMsg = ref('')
const activeTab = ref('info')

// 预览数据
const previewData = ref<any>(null)
const previewLoading = ref(false)
const previewPage = ref(1)
const previewPageSize = 20

// 统计
const statsData = ref<any>(null)
const statsLoading = ref(false)

const sceneNameMap = computed(() => {
  const m: Record<string, string> = {}
  for (const s of sceneCatalog) m[s.code] = s.name
  return m
})

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    data.value = await datasetsApi.detail(dsId)
  } catch (e: any) {
    errorMsg.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadPreview() {
  if (!data.value) return
  previewLoading.value = true
  try {
    if (data.value.dataset_type === 'yolo_detection') {
      previewData.value = await datasetsApi.yoloPreview(dsId, previewPage.value, previewPageSize)
    } else {
      previewData.value = await datasetsApi.preview(dsId, previewPage.value, previewPageSize)
    }
  } catch (e: any) {
    errorMsg.value = e?.message || '预览加载失败'
  } finally {
    previewLoading.value = false
  }
}

function goPreviewPage(p: number) {
  previewPage.value = p
  loadPreview()
}

async function loadStats() {
  if (!data.value) return
  statsLoading.value = true
  try {
    statsData.value = await datasetsApi.stats(dsId)
  } catch (e: any) {
    errorMsg.value = e?.message || '统计加载失败'
  } finally {
    statsLoading.value = false
  }
}

function onTabChange(tab: string) {
  activeTab.value = tab
  if (tab === 'preview') {
    previewPage.value = 1
    if (!previewData.value) loadPreview()
  }
  if (tab === 'stats' && !statsData.value) loadStats()
}

async function deleteVersion(vid: number) {
  if (!confirm('确认删除此版本？')) return
  try {
    await datasetsApi.deleteVersion(dsId, vid)
    await load()
  } catch (e: any) {
    errorMsg.value = e?.message || '删除版本失败'
  }
}

function goBack() {
  router.push('/datasets')
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div v-if="errorMsg" class="error-bar">⚠ {{ errorMsg }}</div>
    <div v-if="loading" class="loading">加载中…</div>

    <template v-if="data">
      <header class="page-header">
        <button class="btn-back" @click="goBack">← 返回</button>
        <h1>{{ data.name }}</h1>
        <div class="header-tags">
          <span class="tag scene">[{{ sceneNameMap[data.scene] || data.scene }}]</span>
          <span class="tag model">{{ data.model_code || '-' }}</span>
          <span class="tag fmt">{{ datasetFormatLabels[data.format] || data.format }}</span>
          <span v-if="data.dataset_type === 'yolo_detection'" class="tag yolo">YOLO 目标检测</span>
          <span v-if="data.current_version" class="tag ver">{{ data.current_version }}</span>
        </div>
      </header>

      <!-- Tab 切换 -->
      <div class="tabs">
        <button :class="['tab', { active: activeTab === 'info' }]" @click="onTabChange('info')">基本信息</button>
        <button :class="['tab', { active: activeTab === 'preview' }]" @click="onTabChange('preview')">样本预览</button>
        <button :class="['tab', { active: activeTab === 'stats' }]" @click="onTabChange('stats')">统计信息</button>
        <button :class="['tab', { active: activeTab === 'versions' }]" @click="onTabChange('versions')">版本历史</button>
      </div>

      <!-- 基本信息 -->
      <div v-if="activeTab === 'info'" class="tab-content">
        <div class="info-grid">
          <div class="info-item">
            <span class="label">名称</span>
            <span class="value">{{ data.name }}</span>
          </div>
          <div class="info-item">
            <span class="label">场景</span>
            <span class="value">{{ sceneNameMap[data.scene] || data.scene }}</span>
          </div>
          <div class="info-item">
            <span class="label">关联模型</span>
            <span class="value">{{ data.model_code || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">格式</span>
            <span class="value">{{ datasetFormatLabels[data.format] || data.format }}</span>
          </div>
          <div class="info-item">
            <span class="label">类型</span>
            <span class="value">{{ datasetTypeLabels[data.dataset_type] || data.dataset_type }}</span>
          </div>
          <div class="info-item">
            <span class="label">描述</span>
            <span class="value">{{ data.description || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">当前版本</span>
            <span class="value">{{ data.current_version || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">样本数</span>
            <span class="value">{{ data.sample_count }}</span>
          </div>
          <div class="info-item">
            <span class="label">文件数</span>
            <span class="value">{{ data.file_count }}</span>
          </div>
          <div class="info-item">
            <span class="label">大小</span>
            <span class="value">{{ formatSize(data.size_bytes) }}</span>
          </div>
          <div class="info-item" v-if="data.dataset_type === 'yolo_detection'">
            <span class="label">图片数</span>
            <span class="value">{{ data.image_count }}</span>
          </div>
          <div class="info-item" v-if="data.dataset_type === 'yolo_detection'">
            <span class="label">标注框数</span>
            <span class="value">{{ data.label_count }}</span>
          </div>
          <div class="info-item" v-if="data.classes?.length">
            <span class="label">类别</span>
            <span class="value">{{ data.classes.join(', ') }}</span>
          </div>
          <div class="info-item">
            <span class="label">版本数</span>
            <span class="value">{{ data.version_count }}</span>
          </div>
          <div class="info-item">
            <span class="label">创建时间</span>
            <span class="value">{{ data.created_at?.slice(0, 16) || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">更新时间</span>
            <span class="value">{{ data.updated_at?.slice(0, 16) || '-' }}</span>
          </div>
        </div>
      </div>

      <!-- 样本预览 -->
      <div v-if="activeTab === 'preview'" class="tab-content">
        <div v-if="previewLoading" class="loading">加载预览中…</div>

        <!-- YOLO 标注预览 -->
        <YoloPreview
          v-else-if="data.dataset_type === 'yolo_detection'"
          :ds-id="dsId"
        />

        <!-- CSV 预览 -->
        <div v-else-if="previewData?.type === 'csv'" class="csv-preview">
          <p class="preview-info">共 {{ previewData.total_rows }} 行，{{ previewData.columns.length }} 列（最多显示 {{ 500 }} 行）</p>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th v-for="col in previewData.columns" :key="col">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in previewData.rows" :key="ri">
                  <td v-for="col in previewData.columns" :key="col">{{ row[col] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="previewData.total_pages > 1" class="pagination">
            <button :disabled="previewPage <= 1" @click="goPreviewPage(previewPage - 1)">上一页</button>
            <span class="page-info">{{ previewData.page }} / {{ previewData.total_pages }}</span>
            <button :disabled="previewPage >= previewData.total_pages" @click="goPreviewPage(previewPage + 1)">下一页</button>
          </div>
        </div>

        <!-- 图片预览 -->
        <div v-else-if="previewData?.type === 'image'" class="image-preview">
          <div class="img-grid">
            <div v-for="(img, i) in previewData.items" :key="i" class="img-card">
              <img :src="img.image_url" :alt="img.image_file" loading="lazy" />
              <span class="img-name">{{ img.image_file }}</span>
            </div>
          </div>
          <div v-if="previewData.total_pages > 1" class="pagination">
            <button :disabled="previewPage <= 1" @click="goPreviewPage(previewPage - 1)">上一页</button>
            <span class="page-info">{{ previewData.page }} / {{ previewData.total_pages }}</span>
            <button :disabled="previewPage >= previewData.total_pages" @click="goPreviewPage(previewPage + 1)">下一页</button>
          </div>
        </div>

        <div v-else class="empty">暂无预览数据</div>
      </div>

      <!-- 统计信息 -->
      <div v-if="activeTab === 'stats'" class="tab-content">
        <div v-if="statsLoading" class="loading">加载统计中…</div>

        <!-- YOLO 统计 -->
        <div v-else-if="statsData?.type === 'yolo_detection'" class="yolo-stats">
          <div class="stat-cards">
            <div class="stat-card">
              <span class="stat-num">{{ statsData.image_count }}</span>
              <span class="stat-label">图片数</span>
            </div>
            <div class="stat-card">
              <span class="stat-num">{{ statsData.label_count }}</span>
              <span class="stat-label">标注框总数</span>
            </div>
          </div>
          <h4>类别分布</h4>
          <div class="class-bars">
            <div v-for="(item, i) in statsData.class_distribution" :key="i" class="class-bar-row">
              <span class="class-name">{{ item.name }}</span>
              <div class="bar-wrap">
                <div
                  class="bar-fill"
                  :style="{
                    width: Math.max((item.count / statsData.label_count) * 100, 2) + '%',
                    backgroundColor: ['#00d4ff','#00ff88','#ffaa00','#ff5555','#a855f7','#f97316','#06b6d4','#ec4899','#84cc16','#f43f5e'][i % 10]
                  }"
                />
              </div>
              <span class="class-count">{{ item.count }}</span>
            </div>
          </div>
        </div>

        <!-- CSV 统计 -->
        <div v-else-if="statsData?.type === 'csv'" class="csv-stats">
          <p>共 {{ statsData.total_rows }} 行，{{ statsData.columns.length }} 列</p>
          <h4>缺失率</h4>
          <table class="missing-table">
            <thead>
              <tr>
                <th>列名</th>
                <th>缺失率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(rate, col) in statsData.missing_rates" :key="col">
                <td>{{ col }}</td>
                <td>
                  <span :class="rate > 50 ? 'high' : rate > 10 ? 'mid' : 'low'">{{ rate }}%</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-else class="empty">暂无统计信息</div>
      </div>

      <!-- 版本历史 -->
      <div v-if="activeTab === 'versions'" class="tab-content">
        <table v-if="data.versions.length" class="ver-table">
          <thead>
            <tr>
              <th>版本</th>
              <th>文件数</th>
              <th>样本数</th>
              <th>大小</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in data.versions" :key="v.id">
              <td><strong>{{ v.version }}</strong></td>
              <td>{{ v.file_count }}</td>
              <td>{{ v.sample_count }}</td>
              <td>{{ formatSize(v.size_bytes) }}</td>
              <td>{{ v.created_at?.slice(0, 16) || '-' }}</td>
              <td>
                <button class="btn-sm btn-danger" @click="deleteVersion(v.id)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无版本记录</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { padding: 24px; color: #e4e7ed; }
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 20px; color: #00d4ff; margin: 8px 0; }
.header-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.tag.scene { background: rgba(255,170,0,0.15); color: #ffaa00; }
.tag.model { font-family: monospace; background: rgba(0,212,255,0.15); color: #00d4ff; }
.tag.fmt { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.7); }
.tag.yolo { background: rgba(0,255,136,0.15); color: #00ff88; }
.tag.ver { background: rgba(255,170,0,0.15); color: #ffaa00; font-weight: 600; }

.btn-back {
  padding: 4px 12px; background: rgba(255,255,255,0.08); color: #e4e7ed;
  border: 1px solid rgba(255,255,255,0.15); border-radius: 6px;
  cursor: pointer; font-size: 13px;
}
.btn-back:hover { border-color: rgba(255,255,255,0.3); }

.error-bar { padding: 10px; background: rgba(255,80,80,0.15); border: 1px solid #ff5555; border-radius: 6px; margin-bottom: 16px; }
.loading, .empty { padding: 40px; text-align: center; color: rgba(255,255,255,0.5); }

/* Tabs */
.tabs { display: flex; gap: 0; border-bottom: 1px solid rgba(0,212,255,0.2); margin-bottom: 20px; }
.tab {
  padding: 10px 20px; background: none; color: rgba(255,255,255,0.5);
  border: none; border-bottom: 2px solid transparent; cursor: pointer;
  font-size: 14px; transition: all 0.2s;
}
.tab:hover { color: #e4e7ed; }
.tab.active { color: #00d4ff; border-bottom-color: #00d4ff; }
.tab-content { min-height: 300px; }

/* 基本信息 */
.info-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.info-item { display: flex; gap: 12px; padding: 10px 14px; background: rgba(17,24,39,0.4); border-radius: 6px; }
.label { color: rgba(255,255,255,0.5); min-width: 80px; font-size: 13px; }
.value { color: #e4e7ed; font-size: 13px; word-break: break-all; }

/* CSV 预览 */
.preview-info { color: rgba(255,255,255,0.5); font-size: 13px; margin-bottom: 12px; }
.table-wrap { overflow-x: auto; }
.table-wrap table { width: 100%; border-collapse: collapse; font-size: 12px; }
.table-wrap th, .table-wrap td {
  padding: 6px 10px; border: 1px solid rgba(255,255,255,0.1);
  text-align: left; white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis;
}
.table-wrap th { background: rgba(0,212,255,0.1); color: #00d4ff; }

/* 图片预览 */
.img-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.img-card { background: rgba(17,24,39,0.4); border-radius: 8px; overflow: hidden; text-align: center; }
.img-card img { width: 100%; height: 150px; object-fit: cover; }
.img-name { display: block; padding: 6px; font-size: 11px; color: rgba(255,255,255,0.5); }

/* 统计 */
.stat-cards { display: flex; gap: 16px; margin-bottom: 20px; }
.stat-card {
  background: rgba(17,24,39,0.6); border: 1px solid rgba(0,212,255,0.2);
  border-radius: 8px; padding: 20px 30px; text-align: center;
}
.stat-num { display: block; font-size: 28px; color: #00d4ff; font-weight: 700; }
.stat-label { font-size: 13px; color: rgba(255,255,255,0.5); }

h4 { color: #fff; margin: 16px 0 10px; font-size: 14px; }

.class-bars { display: flex; flex-direction: column; gap: 8px; }
.class-bar-row { display: flex; align-items: center; gap: 10px; }
.class-name { width: 100px; font-size: 13px; color: #e4e7ed; text-align: right; }
.bar-wrap { flex: 1; height: 20px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; transition: width 0.3s; min-width: 2px; }
.class-count { width: 50px; font-size: 13px; color: rgba(255,255,255,0.7); }

/* 缺失率表格 */
.missing-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.missing-table th, .missing-table td { padding: 8px 12px; border: 1px solid rgba(255,255,255,0.1); text-align: left; }
.missing-table th { background: rgba(0,212,255,0.1); color: #00d4ff; }
.high { color: #ff5555; font-weight: 600; }
.mid { color: #ffaa00; }
.low { color: #00ff88; }

/* 版本历史 */
.ver-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.ver-table th, .ver-table td { padding: 8px 12px; border: 1px solid rgba(255,255,255,0.1); text-align: left; }
.ver-table th { background: rgba(0,212,255,0.1); color: #00d4ff; }
.ver-table strong { color: #ffaa00; }

.btn-sm {
  padding: 4px 10px; background: rgba(0,212,255,0.15); color: #00d4ff;
  border: 1px solid rgba(0,212,255,0.3); border-radius: 4px;
  cursor: pointer; font-size: 12px;
}
.btn-sm:hover { background: rgba(0,212,255,0.25); }
.btn-danger { background: rgba(255,80,80,0.15); color: #ff5555; border-color: rgba(255,80,80,0.3); }
.btn-danger:hover { background: rgba(255,80,80,0.25); }

/* 分页 */
.pagination { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 16px; padding: 10px 0; }
.pagination button {
  padding: 6px 16px; background: rgba(0,212,255,0.15); color: #00d4ff;
  border: 1px solid rgba(0,212,255,0.3); border-radius: 6px;
  cursor: pointer; font-size: 13px;
}
.pagination button:disabled { opacity: 0.3; cursor: not-allowed; }
.pagination button:hover:not(:disabled) { background: rgba(0,212,255,0.25); }
.page-info { color: rgba(255,255,255,0.7); font-size: 13px; }
</style>