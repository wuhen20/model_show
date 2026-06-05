<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import ImageViewer from '@/components/ImageViewer.vue'
import { detectionScenes, getSceneById } from '@/data/detectionScenes'
import { detectObjects, testApiConnection, type BoundingBox, type DetectionApiConfig } from '@/api/chat'

const activeTab = ref('meter-box')
const scene = computed(() => getSceneById(activeTab.value))

// API 配置
const configVisible = ref(true)
const apiEndpoint = ref('')
const apiKey = ref('')
const apiModelId = ref('')
const showApiKey = ref(false)
const systemPrompt = ref('')
const userPrompt = ref('')

// 图像与检测
const originalImageSrc = ref<string | null>(null)
const resultImageSrc = ref<string | null>(null)
const uploadedFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const detections = ref<BoundingBox[]>([])
const highlightIndex = ref(-1)
const statusText = ref('就绪')
const loading = ref(false)
const scalePercent = ref(100)
const rawResponse = ref('')

// Viewer refs
const originalViewer = ref<InstanceType<typeof ImageViewer> | null>(null)
const resultViewer = ref<InstanceType<typeof ImageViewer> | null>(null)
const syncing = ref(false)

// 初始化场景配置
watch(scene, (s) => {
  apiEndpoint.value = s.endpoint
  apiModelId.value = s.modelId
  systemPrompt.value = s.defaultPrompt
  userPrompt.value = s.userPrompt
  // 清空上次结果
  detections.value = []
  highlightIndex.value = -1
  rawResponse.value = ''
}, { immediate: true })

// 同步拖动
function onTransformSync(source: 'original' | 'result') {
  if (syncing.value) return
  syncing.value = true
  const from = source === 'original' ? originalViewer.value : resultViewer.value
  const to = source === 'original' ? resultViewer.value : originalViewer.value
  if (from && to) {
    const t = from.getTransform()
    to.applyTransform(t)
    scalePercent.value = Math.round(t.scale * 100)
  }
  syncing.value = false
}

function chooseImage() {
  fileInputRef.value?.click()
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  if (!target.files?.length) return
  const file = target.files[0]
  uploadedFile.value = file
  const reader = new FileReader()
  reader.onload = () => {
    originalImageSrc.value = reader.result as string
    resultImageSrc.value = reader.result as string
    detections.value = []
    highlightIndex.value = -1
    rawResponse.value = ''
    statusText.value = '图片已加载'
  }
  reader.readAsDataURL(file)
  if (fileInputRef.value) fileInputRef.value.value = ''
}

async function runDetection() {
  if (!uploadedFile.value) {
    statusText.value = '请先选择图片'
    return
  }
  loading.value = true
  statusText.value = '正在检测...'
  try {
    const config: DetectionApiConfig = {
      endpoint: apiEndpoint.value,
      apiKey: apiKey.value,
      modelId: apiModelId.value
    }
    const result = await detectObjects(uploadedFile.value, config, systemPrompt.value, userPrompt.value)
    detections.value = result.detections || []
    rawResponse.value = result.raw_response || ''
    statusText.value = `检测完成，发现 ${detections.value.length} 个目标`
  } catch (err: any) {
    statusText.value = `检测失败: ${err.message}`
    detections.value = []
  } finally {
    loading.value = false
  }
}

async function handleTestConnection() {
  statusText.value = '正在测试连接...'
  try {
    const config: DetectionApiConfig = {
      endpoint: apiEndpoint.value,
      apiKey: apiKey.value,
      modelId: apiModelId.value
    }
    const result = await testApiConnection(config)
    statusText.value = `连接成功${result.available_models?.length ? '，可用模型: ' + result.available_models.slice(0, 3).join(', ') : ''}`
  } catch (err: any) {
    statusText.value = `连接失败: ${err.message}`
  }
}

function saveConfig() {
  const key = `detection_config_${activeTab.value}`
  localStorage.setItem(key, JSON.stringify({
    endpoint: apiEndpoint.value,
    modelId: apiModelId.value,
    systemPrompt: systemPrompt.value,
    userPrompt: userPrompt.value,
  }))
  statusText.value = '配置已保存'
}

function loadSavedConfig() {
  // 清除旧版含 apiKey 的存储记录
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const k = localStorage.key(i)
    if (k && k.startsWith('detection_config_')) {
      try {
        const val = JSON.parse(localStorage.getItem(k) || '{}')
        if (val.apiKey) {
          delete val.apiKey
          localStorage.setItem(k, JSON.stringify(val))
        }
      } catch {}
    }
  }
  const key = `detection_config_${activeTab.value}`
  const saved = localStorage.getItem(key)
  if (saved) {
    try {
      const cfg = JSON.parse(saved)
      if (cfg.endpoint) apiEndpoint.value = cfg.endpoint
      if (cfg.modelId) apiModelId.value = cfg.modelId
      if (cfg.systemPrompt) systemPrompt.value = cfg.systemPrompt
      if (cfg.userPrompt) userPrompt.value = cfg.userPrompt
    } catch {}
  }
}

onMounted(() => {
  loadSavedConfig()
})

function zoomIn() { originalViewer.value?.zoomIn(); onTransformSync('original') }
function zoomOut() { originalViewer.value?.zoomOut(); onTransformSync('original') }
function resetView() { originalViewer.value?.resetView(); onTransformSync('original') }

function onResultRowClick(idx: number) {
  highlightIndex.value = highlightIndex.value === idx ? -1 : idx
}

function getLabelColor(label: string): string {
  return scene.value.labelColors[label] || '#00d4ff'
}
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" :subtitle="scene.name" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <!-- 场景描述 -->
        <div class="scene-header">
          <div class="scene-tabs">
            <button
              v-for="s in detectionScenes"
              :key="s.id"
              class="scene-tab"
              :class="{ active: activeTab === s.id }"
              @click="activeTab = s.id"
            >{{ s.name }}</button>
          </div>
          <p class="scene-desc">{{ scene.description }}</p>
        </div>

        <div class="detection-layout">
          <!-- 左侧配置面板 -->
          <div v-show="configVisible" class="config-panel">
            <div class="panel-header">
              <h3 class="panel-header-title">配置面板</h3>
              <button class="panel-collapse-btn" @click="configVisible = false" title="隐藏配置面板">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 19l-7-7 7-7"/>
                  <path d="M18 19l-7-7 7-7"/>
                </svg>
              </button>
            </div>
            <div class="panel-section">
              <h3 class="panel-title">API 配置</h3>
              <div class="form-group">
                <label>API 地址</label>
                <input v-model="apiEndpoint" type="text" class="form-input" placeholder="http://localhost:11434/v1" />
              </div>
              <div class="form-group">
                <label>API Key</label>
                <div class="key-input-wrap">
                  <input v-model="apiKey" :type="showApiKey ? 'text' : 'password'" class="form-input" placeholder="输入 API Key" />
                  <button class="toggle-key-btn" @click="showApiKey = !showApiKey">{{ showApiKey ? '隐藏' : '显示' }}</button>
                </div>
              </div>
              <div class="form-group">
                <label>模型 ID</label>
                <input v-model="apiModelId" type="text" class="form-input" placeholder="qwen2.5-vl" />
              </div>
            </div>

            <div class="panel-section">
              <h3 class="panel-title">提示词配置</h3>
              <div class="form-group">
                <label>系统提示词</label>
                <textarea v-model="systemPrompt" class="form-textarea" rows="5" placeholder="系统角色设定..."></textarea>
              </div>
              <div class="form-group">
                <label>用户提示词</label>
                <textarea v-model="userPrompt" class="form-textarea" rows="3" placeholder="用户请求模板..."></textarea>
              </div>
            </div>

            <div class="panel-actions">
              <button class="btn btn-primary" @click="saveConfig">保存配置</button>
              <button class="btn btn-outline" @click="handleTestConnection">测试连接</button>
            </div>
          </div>

          <!-- 配置面板收起时的展开按钮 -->
          <div v-show="!configVisible" class="config-expand-btn" @click="configVisible = true" title="显示配置面板">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M13 19l7-7-7-7"/>
              <path d="M6 19l7-7-7-7"/>
            </svg>
            <span>配置</span>
          </div>

          <!-- 右侧主区域 -->
          <div class="main-panel">
            <!-- 双视图区 -->
            <div class="dual-viewer">
              <div class="viewer-box">
                <div class="viewer-title">原图（滚轮缩放）</div>
                <div class="viewer-content">
                  <ImageViewer
                    ref="originalViewer"
                    :image-src="originalImageSrc"
                    @update:transform="() => onTransformSync('original')"
                  />
                </div>
              </div>
              <div class="viewer-box">
                <div class="viewer-title">检测结果（滚轮缩放）</div>
                <div class="viewer-content">
                  <ImageViewer
                    ref="resultViewer"
                    :image-src="resultImageSrc"
                    :annotations="detections"
                    :label-colors="scene.labelColors"
                    :highlight-index="highlightIndex"
                    @update:transform="() => onTransformSync('result')"
                  />
                </div>
              </div>
            </div>

            <!-- 操作栏 -->
            <div class="toolbar">
              <div class="toolbar-left">
                <button class="btn btn-sm" @click="chooseImage">选择图片</button>
                <button class="btn btn-sm btn-primary" :disabled="loading || !uploadedFile" @click="runDetection">
                  {{ loading ? '检测中...' : '上传检测' }}
                </button>
                <input ref="fileInputRef" type="file" accept="image/*" style="display:none" @change="onFileChange" />
              </div>
              <div class="toolbar-center">
                <button class="btn btn-sm" @click="zoomIn">放大 +</button>
                <button class="btn btn-sm" @click="zoomOut">缩小 -</button>
                <button class="btn btn-sm" @click="resetView">重置</button>
                <span class="scale-label">{{ scalePercent }}%</span>
              </div>
              <div class="toolbar-right">
                <span class="status-text">{{ statusText }}</span>
              </div>
            </div>

            <!-- 检测结果列表 -->
            <div class="result-table-wrap">
              <h3 class="result-table-title">检测结果列表（共 {{ detections.length }} 个目标）</h3>
              <div class="result-table-scroll">
                <table class="result-table">
                  <thead>
                    <tr>
                      <th style="width:40px">#</th>
                      <th>缺陷/目标类型</th>
                      <th>坐标 (x1, y1, x2, y2)</th>
                      <th style="width:80px">置信度</th>
                      <th v-if="detections.some(d => d.text)" style="width:120px">识别内容</th>
                      <th v-if="detections.some(d => d.severity)" style="width:80px">严重程度</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(det, idx) in detections"
                      :key="idx"
                      :class="{ highlighted: highlightIndex === idx }"
                      @click="onResultRowClick(idx)"
                    >
                      <td>{{ idx + 1 }}</td>
                      <td>
                        <span class="label-dot" :style="{ background: getLabelColor(det.label) }"></span>
                        {{ det.label }}
                      </td>
                      <td class="coord-cell">{{ det.bbox ? det.bbox.join(', ') : '-' }}</td>
                      <td>{{ det.confidence ? (det.confidence * 100).toFixed(1) + '%' : '-' }}</td>
                      <td v-if="detections.some(d => d.text)">{{ det.text || '-' }}</td>
                      <td v-if="detections.some(d => d.severity)">{{ det.severity || '-' }}</td>
                    </tr>
                    <tr v-if="detections.length === 0">
                      <td :colspan="6" class="empty-row">暂无检测结果，请选择图片并点击"上传检测"</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- 原始响应（可折叠） -->
            <details v-if="rawResponse" class="raw-response">
              <summary>模型原始响应</summary>
              <pre>{{ rawResponse }}</pre>
            </details>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

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

.scene-header {
  flex-shrink: 0;
  margin-bottom: 8px;
}

.scene-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 6px;
}

.scene-tab {
  padding: 8px 20px;
  border-radius: 8px;
  border: 1px solid rgba(0, 212, 255, 0.2);
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.scene-tab:hover {
  border-color: rgba(0, 212, 255, 0.4);
  color: #00d4ff;
}

.scene-tab.active {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
  border-color: rgba(0, 212, 255, 0.5);
}

.scene-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.detection-layout {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 左侧配置面板 */
.config-panel {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  background: linear-gradient(180deg, rgba(17, 24, 39, 0.95) 0%, rgba(13, 17, 23, 0.98) 100%);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 10px;
  padding: 14px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
}

.panel-header-title {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
  margin: 0;
}

.panel-collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all 0.2s;
}

.panel-collapse-btn:hover {
  color: #00d4ff;
  background: rgba(0, 212, 255, 0.1);
}

/* 配置面板收起时的展开按钮 */
.config-expand-btn {
  width: 32px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: linear-gradient(180deg, rgba(17, 24, 39, 0.95) 0%, rgba(13, 17, 23, 0.98) 100%);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all 0.2s;
  padding: 12px 0;
}

.config-expand-btn span {
  font-size: 10px;
  writing-mode: vertical-lr;
  letter-spacing: 2px;
}

.config-expand-btn:hover {
  color: #00d4ff;
  border-color: rgba(0, 212, 255, 0.4);
  background: rgba(0, 212, 255, 0.06);
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
  margin: 0;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-group label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
}

.form-input {
  padding: 7px 10px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus {
  border-color: rgba(0, 212, 255, 0.5);
}

.key-input-wrap {
  display: flex;
  gap: 4px;
}

.key-input-wrap .form-input {
  flex: 1;
}

.toggle-key-btn {
  padding: 0 8px;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  color: #00d4ff;
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
}

.form-textarea {
  padding: 7px 10px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  font-size: 12px;
  outline: none;
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.2s;
}

.form-textarea:focus {
  border-color: rgba(0, 212, 255, 0.5);
}

.panel-actions {
  display: flex;
  gap: 8px;
  padding-top: 4px;
}

/* 按钮 */
.btn {
  padding: 8px 14px;
  border: 1px solid rgba(0, 212, 255, 0.25);
  border-radius: 6px;
  background: rgba(0, 212, 255, 0.08);
  color: rgba(255, 255, 255, 0.8);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.btn:hover { background: rgba(0, 212, 255, 0.18); color: #00d4ff; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary { background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%); color: #fff; border-color: transparent; }
.btn-primary:hover { box-shadow: 0 0 12px rgba(0, 212, 255, 0.35); }
.btn-primary:disabled { box-shadow: none; }
.btn-outline { background: transparent; }
.btn-sm { padding: 6px 12px; font-size: 11px; }

/* 右侧主面板 */
.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow: hidden;
}

/* 双视图区 */
.dual-viewer {
  display: flex;
  gap: 8px;
  flex: 1;
  min-height: 0;
}

.viewer-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(17, 24, 39, 0.6);
}

.viewer-title {
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  background: rgba(0, 212, 255, 0.06);
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
  flex-shrink: 0;
}

.viewer-content {
  flex: 1;
  min-height: 0;
}

/* 操作栏 */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: rgba(17, 24, 39, 0.9);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  flex-shrink: 0;
  gap: 12px;
}

.toolbar-left, .toolbar-center, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-center { flex: 1; justify-content: center; }
.toolbar-right { flex-shrink: 0; }

.scale-label {
  font-size: 11px;
  color: #00d4ff;
  min-width: 40px;
  text-align: center;
}

.status-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 结果列表 */
.result-table-wrap {
  flex-shrink: 0;
  max-height: 200px;
  display: flex;
  flex-direction: column;
  background: rgba(17, 24, 39, 0.9);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  overflow: hidden;
}

.result-table-title {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  padding: 8px 12px 6px;
  margin: 0;
  flex-shrink: 0;
}

.result-table-scroll {
  overflow-y: auto;
  flex: 1;
}

.result-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.result-table th {
  padding: 6px 10px;
  text-align: left;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 500;
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
  position: sticky;
  top: 0;
  background: rgba(17, 24, 39, 0.98);
}

.result-table td {
  padding: 6px 10px;
  color: rgba(255, 255, 255, 0.8);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.result-table tr {
  cursor: pointer;
  transition: background 0.15s;
}

.result-table tbody tr:hover {
  background: rgba(0, 212, 255, 0.06);
}

.result-table tbody tr.highlighted {
  background: rgba(0, 212, 255, 0.12);
}

.label-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

.coord-cell {
  font-family: monospace;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
}

.empty-row {
  text-align: center;
  color: rgba(255, 255, 255, 0.3);
  padding: 20px 10px !important;
}

/* 原始响应 */
.raw-response {
  flex-shrink: 0;
  background: rgba(17, 24, 39, 0.9);
  border: 1px solid rgba(0, 212, 255, 0.1);
  border-radius: 8px;
  padding: 0;
  font-size: 11px;
  max-height: 120px;
  overflow: auto;
}

.raw-response summary {
  padding: 6px 12px;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  user-select: none;
}

.raw-response pre {
  padding: 8px 12px;
  margin: 0;
  color: rgba(255, 255, 255, 0.6);
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
