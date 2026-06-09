<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { datasetsApi } from '@/api/datasets'
import { modelsApi } from '@/api/models'
import {
  sceneCatalog,
  datasetFormatLabels,
  datasetTypeLabels,
  type DatasetBrief,
  type DatasetFormat,
  type DatasetType,
  type ModelBrief,
  type SceneCode,
} from '@/data/models'

const router = useRouter()

const list = ref<DatasetBrief[]>([])
const loading = ref(false)
const errorMsg = ref('')
const sceneFilter = ref<SceneCode | ''>('')
const typeFilter = ref<DatasetType | ''>('')
const formatFilter = ref<DatasetFormat | ''>('')

// 模型列表（用于上传时下拉选择）
const modelList = ref<ModelBrief[]>([])

// 上传弹窗
const uploadVisible = ref(false)
const uploadLoading = ref(false)
const uploadForm = ref({
  name: '',
  scene: '' as SceneCode | '',
  model_code: '',
  description: '',
})
const zipFile = ref<File | null>(null)

// 版本上传弹窗
const versionUploadVisible = ref(false)
const versionUploadLoading = ref(false)
const versionZipFile = ref<File | null>(null)
const versionTargetDs = ref<DatasetBrief | null>(null)

// 删除确认
const deleteVisible = ref(false)
const deleteTarget = ref<DatasetBrief | null>(null)
const deleteLoading = ref(false)

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    list.value = await datasetsApi.list({
      scene: sceneFilter.value || undefined,
      dataset_type: typeFilter.value || undefined,
      format: formatFilter.value || undefined,
    })
  } catch (e: any) {
    errorMsg.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadModels(scene: string) {
  try {
    modelList.value = await modelsApi.list({ scene })
  } catch {
    modelList.value = []
  }
}

watch(sceneFilter, load)
watch(typeFilter, load)
watch(formatFilter, load)

onMounted(load)

// 场景名称映射
const sceneNameMap = computed(() => {
  const m: Record<string, string> = {}
  for (const s of sceneCatalog) m[s.code] = s.name
  return m
})

// 格式化文件大小
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

// 格式化日期
function formatDate(s?: string | null): string {
  if (!s) return '-'
  return s.slice(0, 10)
}

// 上传弹窗
function openUpload() {
  uploadForm.value = { name: '', scene: '', model_code: '', description: '' }
  zipFile.value = null
  modelList.value = []
  uploadVisible.value = true
}

function onSceneChange(scene: SceneCode | '') {
  uploadForm.value.model_code = ''
  if (scene) loadModels(scene)
  else modelList.value = []
}

function onZipChange(e: Event) {
  const target = e.target as HTMLInputElement
  zipFile.value = target.files?.[0] || null
}

async function doUpload() {
  if (!uploadForm.value.name || !uploadForm.value.scene || !uploadForm.value.model_code || !zipFile.value) {
    errorMsg.value = '请填写所有必填字段并选择 ZIP 文件'
    return
  }
  uploadLoading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('file', zipFile.value)
    fd.append('name', uploadForm.value.name)
    fd.append('scene', uploadForm.value.scene)
    fd.append('model_code', uploadForm.value.model_code)
    if (uploadForm.value.description) fd.append('description', uploadForm.value.description)
    await datasetsApi.create(fd)
    uploadVisible.value = false
    await load()
  } catch (e: any) {
    errorMsg.value = e?.message || '上传失败'
  } finally {
    uploadLoading.value = false
  }
}

// 版本上传
function openVersionUpload(ds: DatasetBrief) {
  versionTargetDs.value = ds
  versionZipFile.value = null
  versionUploadVisible.value = true
}

function onVersionZipChange(e: Event) {
  const target = e.target as HTMLInputElement
  versionZipFile.value = target.files?.[0] || null
}

async function doVersionUpload() {
  if (!versionZipFile.value || !versionTargetDs.value) return
  versionUploadLoading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('file', versionZipFile.value)
    await datasetsApi.uploadVersion(versionTargetDs.value.id, fd)
    versionUploadVisible.value = false
    await load()
  } catch (e: any) {
    errorMsg.value = e?.message || '版本上传失败'
  } finally {
    versionUploadLoading.value = false
  }
}

// 删除
function openDelete(ds: DatasetBrief) {
  deleteTarget.value = ds
  deleteVisible.value = true
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleteLoading.value = true
  errorMsg.value = ''
  try {
    await datasetsApi.delete(deleteTarget.value.id)
    deleteVisible.value = false
    await load()
  } catch (e: any) {
    errorMsg.value = e?.message || '删除失败'
  } finally {
    deleteLoading.value = false
  }
}

// 跳转详情
function goDetail(id: number) {
  router.push(`/datasets/${id}`)
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1>训练数据集管理</h1>
      <button class="btn-primary" @click="openUpload">上传数据集 ZIP</button>
    </header>

    <div class="filters">
      <select v-model="sceneFilter">
        <option value="">全部场景</option>
        <option v-for="s in sceneCatalog" :key="s.code" :value="s.code">
          {{ s.code }} · {{ s.name }}
        </option>
      </select>
      <select v-model="typeFilter">
        <option value="">全部类型</option>
        <option value="general">通用</option>
        <option value="yolo_detection">YOLO 目标检测</option>
      </select>
      <select v-model="formatFilter">
        <option value="">全部格式</option>
        <option v-for="(label, key) in datasetFormatLabels" :key="key" :value="key">
          {{ label }}
        </option>
      </select>
      <span class="total">共 {{ list.length }} 个数据集</span>
    </div>

    <div v-if="errorMsg" class="error-bar">⚠ {{ errorMsg }}</div>
    <div v-if="loading" class="loading">加载中…</div>

    <!-- 数据集卡片列表 -->
    <div v-if="!loading && list.length" class="card-list">
      <div v-for="ds in list" :key="ds.id" class="ds-card" @click="goDetail(ds.id)">
        <div class="card-head">
          <span class="scene-tag">[{{ sceneNameMap[ds.scene] || ds.scene }}]</span>
          <span class="model-code">{{ ds.model_code || '-' }}</span>
          <span class="format-tag">{{ datasetFormatLabels[ds.format] || ds.format }}</span>
          <span v-if="ds.dataset_type === 'yolo_detection'" class="yolo-tag">YOLO检测</span>
          <span v-if="ds.current_version" class="ver">{{ ds.current_version }}</span>
        </div>
        <h3>{{ ds.name }}</h3>
        <div class="card-meta">
          <span class="meta-item">{{ datasetTypeLabels[ds.dataset_type] || ds.dataset_type }}</span>
          <template v-if="ds.dataset_type === 'yolo_detection'">
            <span class="meta-item" v-if="ds.classes?.length">{{ ds.classes.length }} 类</span>
            <span class="meta-item">{{ ds.image_count }} 张图片</span>
            <span class="meta-item">{{ ds.label_count }} 标注框</span>
          </template>
          <template v-else>
            <span class="meta-item" v-if="ds.sample_count">{{ ds.sample_count }} 条</span>
            <span class="meta-item" v-if="ds.file_count">{{ ds.file_count }} 个文件</span>
          </template>
          <span class="meta-item">{{ formatSize(ds.size_bytes) }}</span>
          <span class="meta-item">{{ ds.version_count }} 个版本</span>
          <span class="meta-item">{{ formatDate(ds.created_at) }}</span>
        </div>
        <div class="card-actions" @click.stop>
          <button class="btn-sm" @click="goDetail(ds.id)">预览</button>
          <button class="btn-sm" @click="openVersionUpload(ds)">上传新版本ZIP</button>
          <button class="btn-sm btn-danger" @click="openDelete(ds)">删除</button>
        </div>
      </div>
    </div>

    <div v-if="!loading && !list.length" class="empty">暂无数据集，请上传 ZIP 包</div>

    <!-- 上传弹窗 -->
    <div v-if="uploadVisible" class="modal-overlay" @click.self="uploadVisible = false">
      <div class="modal">
        <h3>上传数据集 ZIP</h3>
        <div class="form">
          <label>名称 *</label>
          <input v-model="uploadForm.name" placeholder="数据集名称" />

          <label>场景 *</label>
          <select v-model="uploadForm.scene" @change="onSceneChange(($event.target as HTMLSelectElement).value as SceneCode | '')">
            <option value="">请选择场景</option>
            <option v-for="s in sceneCatalog" :key="s.code" :value="s.code">
              {{ s.code }} · {{ s.name }}
            </option>
          </select>

          <label>关联模型 *</label>
          <select v-model="uploadForm.model_code" :disabled="!uploadForm.scene">
            <option value="">请选择模型</option>
            <option v-for="m in modelList" :key="m.code" :value="m.code">
              {{ m.code }} · {{ m.name }}
            </option>
          </select>

          <label>描述</label>
          <textarea v-model="uploadForm.description" rows="3" placeholder="可选描述" />

          <label>ZIP 文件 *</label>
          <input type="file" accept=".zip" @change="onZipChange" />
        </div>
        <div class="modal-actions">
          <button class="btn" @click="uploadVisible = false">取消</button>
          <button class="btn-primary" :disabled="uploadLoading" @click="doUpload">
            {{ uploadLoading ? '上传中…' : '确认上传' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 版本上传弹窗 -->
    <div v-if="versionUploadVisible" class="modal-overlay" @click.self="versionUploadVisible = false">
      <div class="modal">
        <h3>上传新版本 ZIP — {{ versionTargetDs?.name }}</h3>
        <div class="form">
          <label>ZIP 文件 *</label>
          <input type="file" accept=".zip" @change="onVersionZipChange" />
        </div>
        <div class="modal-actions">
          <button class="btn" @click="versionUploadVisible = false">取消</button>
          <button class="btn-primary" :disabled="versionUploadLoading" @click="doVersionUpload">
            {{ versionUploadLoading ? '上传中…' : '确认上传' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div v-if="deleteVisible" class="modal-overlay" @click.self="deleteVisible = false">
      <div class="modal">
        <h3>确认删除</h3>
        <p>确定要删除数据集「{{ deleteTarget?.name }}」及其所有版本文件吗？此操作不可撤销。</p>
        <div class="modal-actions">
          <button class="btn" @click="deleteVisible = false">取消</button>
          <button class="btn-danger" :disabled="deleteLoading" @click="doDelete">
            {{ deleteLoading ? '删除中…' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 24px; color: #e4e7ed; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h1 { font-size: 20px; color: #00d4ff; margin: 0; }

.filters { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.filters select {
  background: rgba(17,24,39,0.8); color: #e4e7ed;
  border: 1px solid rgba(0,212,255,0.3); border-radius: 6px;
  padding: 6px 12px; cursor: pointer;
}
.total { color: rgba(255,255,255,0.5); font-size: 13px; margin-left: auto; }

.btn-primary {
  padding: 8px 20px; background: rgba(0,212,255,0.2); color: #00d4ff;
  border: 1px solid rgba(0,212,255,0.4); border-radius: 6px;
  cursor: pointer; font-size: 14px; transition: all 0.2s;
}
.btn-primary:hover { background: rgba(0,212,255,0.3); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn {
  padding: 6px 14px; background: rgba(255,255,255,0.08); color: #e4e7ed;
  border: 1px solid rgba(255,255,255,0.15); border-radius: 6px;
  cursor: pointer; font-size: 13px;
}
.btn:hover { border-color: rgba(255,255,255,0.3); }

.btn-sm {
  padding: 4px 10px; background: rgba(0,212,255,0.15); color: #00d4ff;
  border: 1px solid rgba(0,212,255,0.3); border-radius: 4px;
  cursor: pointer; font-size: 12px; margin-right: 6px;
}
.btn-sm:hover { background: rgba(0,212,255,0.25); }

.btn-danger {
  padding: 6px 14px; background: rgba(255,80,80,0.2); color: #ff5555;
  border: 1px solid rgba(255,80,80,0.4); border-radius: 6px;
  cursor: pointer; font-size: 13px;
}
.btn-danger:hover { background: rgba(255,80,80,0.3); }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.error-bar { padding: 10px; background: rgba(255,80,80,0.15); border: 1px solid #ff5555; border-radius: 6px; margin-bottom: 16px; }
.loading, .empty { padding: 40px; text-align: center; color: rgba(255,255,255,0.5); }

.card-list { display: flex; flex-direction: column; gap: 12px; }
.ds-card {
  background: rgba(17,24,39,0.6); border: 1px solid rgba(0,212,255,0.2);
  border-radius: 8px; padding: 16px; cursor: pointer; transition: all 0.2s;
}
.ds-card:hover { border-color: #00d4ff; transform: translateY(-1px); }
.card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.scene-tag { color: #ffaa00; font-size: 12px; }
.model-code { font-family: monospace; color: #00d4ff; font-weight: 600; }
.format-tag {
  padding: 1px 6px; background: rgba(255,255,255,0.08);
  border-radius: 4px; font-size: 11px; color: rgba(255,255,255,0.7);
}
.yolo-tag {
  padding: 1px 6px; background: rgba(0,255,136,0.15); color: #00ff88;
  border-radius: 4px; font-size: 11px;
}
.ver { color: #ffaa00; font-size: 12px; font-weight: 600; }
.ds-card h3 { font-size: 15px; margin: 0 0 8px; color: #fff; }
.card-meta { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.meta-item { color: rgba(255,255,255,0.5); font-size: 12px; }
.card-actions { display: flex; gap: 4px; }

/* 弹窗 */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal {
  background: #1a1f2e; border: 1px solid rgba(0,212,255,0.3);
  border-radius: 10px; padding: 24px; min-width: 420px; max-width: 520px;
  color: #e4e7ed;
}
.modal h3 { margin: 0 0 16px; color: #00d4ff; }
.modal p { color: rgba(255,255,255,0.7); margin-bottom: 16px; }
.form { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.form label { font-size: 13px; color: rgba(255,255,255,0.7); }
.form input, .form select, .form textarea {
  background: rgba(17,24,39,0.8); color: #e4e7ed;
  border: 1px solid rgba(0,212,255,0.3); border-radius: 6px;
  padding: 8px 12px; font-size: 13px; resize: vertical;
}
.form select:disabled { opacity: 0.4; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
</style>
