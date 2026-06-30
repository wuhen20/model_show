<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { createMeterRemovalApi, type MeterOperationModelInfo, type MeterOperationTaskStatus, type MeterOperationResults } from '@/api/demo'

const api = createMeterRemovalApi()
const serverOnline = ref(false)
const loading = ref(false)
const statusMsg = ref('')
const statusClass = ref('')

const modelInfo = ref<MeterOperationModelInfo | null>(null)
const builtinVideos = ref<string[]>([])
const selectedVideo = ref('')
const uploadFileRef = ref<HTMLInputElement | null>(null)
const uploadedFile = ref<File | null>(null)

const taskId = ref('')
const taskStatus = ref<MeterOperationTaskStatus | null>(null)
const results = ref<MeterOperationResults | null>(null)
let pollTimer: any = null

const selectedKeyFrame = ref<string>('')

function setStatus(msg: string, cls: string = '') { statusMsg.value = msg; statusClass.value = cls }

async function checkServer() {
  try {
    await api.ping()
    serverOnline.value = true
    setStatus('服务已连接', 'ok')
    await loadModelInfo()
    await loadVideos()
  } catch {
    serverOnline.value = false
    setStatus('后端服务未启动，请先启动后端', 'err')
  }
}

async function loadModelInfo() {
  try {
    modelInfo.value = await api.modelInfo()
  } catch (e: any) {
    setStatus('加载模型信息失败: ' + e.message, 'err')
  }
}

async function loadVideos() {
  try {
    const data = await api.listVideos()
    builtinVideos.value = data.videos || []
  } catch {}
}

function triggerUpload() {
  uploadFileRef.value?.click()
}

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  uploadedFile.value = file
  setStatus(`已选择文件: ${file.name}`, 'ok')
}

async function startAnalysis() {
  let tid = ''
  try {
    if (uploadedFile.value) {
      const resp = await api.analyze(uploadedFile.value)
      tid = resp.task_id
    } else if (selectedVideo.value) {
      const resp = await api.analyzeBuiltin(selectedVideo.value)
      tid = resp.task_id
    } else {
      setStatus('请选择内置视频或上传视频文件', 'err')
      return
    }
    taskId.value = tid
    results.value = null
    taskStatus.value = null
    setStatus('分析任务已启动，正在处理视频...', 'ok')
    pollStatus()
  } catch (e: any) {
    setStatus('启动分析失败: ' + e.message, 'err')
  }
}

function pollStatus() {
  pollTimer = setInterval(async () => {
    try {
      const st = await api.getStatus(taskId.value)
      taskStatus.value = st
      if (st.status === 'completed') {
        clearInterval(pollTimer!)
        pollTimer = null
        const res = await api.getResults(taskId.value)
        results.value = res
        setStatus('分析完成', 'ok')
      } else if (st.status === 'error') {
        clearInterval(pollTimer!)
        pollTimer = null
        setStatus('分析失败: ' + (st.error || '未知错误'), 'err')
      }
    } catch (e: any) {
      clearInterval(pollTimer!)
      pollTimer = null
      setStatus('轮询状态失败: ' + e.message, 'err')
    }
  }, 2000)
}

const stateLabels: Record<string, string> = {
  'processing': '处理中',
  'success': '拆线成功',
  'verifying': '验证中',
  'completed': '已完成',
  'starting': '启动中',
}

onMounted(checkServer)
onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<template>
  <div class="demo-page">
    <!-- 模型信息卡 -->
    <section v-if="modelInfo" class="card info-card">
      <div class="card-title">XC-01 拆除旧表作业识别</div>
      <div class="info-grid">
        <div class="info-item"><span class="label">模型类型</span><span class="value">{{ modelInfo.model_type }}</span></div>
        <div class="info-item"><span class="label">置信度阈值</span><span class="value">{{ modelInfo.config?.conf_thresh }}</span></div>
        <div class="info-item"><span class="label">接触时长阈值</span><span class="value">{{ modelInfo.config?.need_sec }}s</span></div>
        <div class="info-item"><span class="label">缓冲帧数</span><span class="value">{{ modelInfo.config?.buffer_frames }}</span></div>
        <div class="info-item"><span class="label">Glove验证帧数</span><span class="value">{{ modelInfo.config?.glove_verify_frames }}</span></div>
        <div class="info-item"><span class="label" :class="{ ok: modelInfo.model_available, err: !modelInfo.model_available }">模型状态</span><span class="value">{{ modelInfo.model_available ? '已加载' : '未找到' }}</span></div>
      </div>
      <div class="class-tags">
        <span v-for="cls in modelInfo.classes" :key="cls.id" class="class-tag">{{ cls.cn }}({{ cls.name }})</span>
      </div>
    </section>

    <div v-if="statusMsg" class="status-bar" :class="statusClass">{{ statusMsg }}</div>

    <!-- 视频选择与分析 -->
    <section class="card">
      <div class="card-title">视频选择与分析</div>
      <div class="select-row">
        <div class="select-group">
          <label>内置视频：</label>
          <select v-model="selectedVideo" :disabled="!!uploadedFile">
            <option value="">-- 请选择 --</option>
            <option v-for="v in builtinVideos" :key="v" :value="v">{{ v }}</option>
          </select>
          <span v-if="builtinVideos.length === 0" class="hint">（暂无内置视频，请上传）</span>
        </div>
        <div class="upload-group">
          <button class="btn-outline" @click="triggerUpload" :disabled="!!selectedVideo">上传视频</button>
          <input ref="uploadFileRef" type="file" accept="video/*" style="display:none" @change="onFileChange" />
          <span v-if="uploadedFile" class="file-name">{{ uploadedFile.name }}</span>
        </div>
        <button class="btn-primary" @click="startAnalysis" :disabled="loading || !serverOnline || (!selectedVideo && !uploadedFile)">
          {{ taskStatus?.status === 'running' ? '分析中...' : '开始分析' }}
        </button>
      </div>

      <!-- 进度条 -->
      <div v-if="taskStatus && taskStatus.status === 'running'" class="progress-section">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: taskStatus.progress + '%' }"></div>
        </div>
        <div class="progress-text">
          进度: {{ taskStatus.progress }}% | 帧: {{ taskStatus.current_frame }} / {{ taskStatus.total_frames }} | 状态: {{ stateLabels[taskStatus.current_state] || taskStatus.current_state }}
        </div>
      </div>
    </section>

    <!-- 分析结果 -->
    <template v-if="results">
      <section class="card">
        <div class="card-title">标注视频</div>
        <video controls class="video-player" :src="api.getAnnotatedVideoUrl(results.task_id)"></video>
      </section>

      <section class="card">
        <div class="card-title">识别报告</div>
        <div class="report-summary">
          <div class="report-item"><span class="label">最终状态</span><span class="value">{{ results.report.final_state }}</span></div>
          <div class="report-item"><span class="label">总帧数</span><span class="value">{{ results.total_frames }}</span></div>
          <div class="report-item"><span class="label">视频时长</span><span class="value">{{ results.duration_seconds }}s</span></div>
          <div class="report-item"><span class="label">帧率</span><span class="value">{{ results.fps }} fps</span></div>
        </div>
        <table class="report-table" v-if="results.report.meters.length > 0">
          <thead>
            <tr><th>电表ID</th><th>拆线成功时间</th><th>拆除验证时间</th></tr>
          </thead>
          <tbody>
            <tr v-for="m in results.report.meters" :key="m.meter_id">
              <td>M{{ m.meter_id }}</td>
              <td>{{ m.wire_removal_time != null ? m.wire_removal_time + 's' : 'N/A' }}</td>
              <td>{{ m.verified_time != null ? m.verified_time + 's' : 'N/A' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="placeholder">未检测到电表拆除记录</div>
      </section>

      <section class="card">
        <div class="card-title">关键帧（状态转换截图）</div>
        <div v-if="results.key_frames.length > 0" class="key-frame-grid">
          <div v-for="(kf, i) in results.key_frames" :key="i" class="key-frame-item" @click="selectedKeyFrame = kf.image">
            <img :src="kf.image" :alt="kf.title" />
            <div class="kf-info">
              <div class="kf-title">{{ kf.title }}</div>
              <div class="kf-time">{{ kf.time_seconds }}s (第{{ kf.frame }}帧)</div>
            </div>
          </div>
        </div>
        <div v-else class="placeholder">无关键帧</div>
      </section>
    </template>

    <!-- 算法说明 -->
    <section class="card algo-card">
      <div class="card-title">检测算法说明</div>
      <div class="algo-content">
        <div class="algo-item">
          <h4>螺丝刀尖端检测</h4>
          <p>取螺丝刀框左上角 (0.05 极小区域) 作为尖端点，端子框右侧扩展 25%，判断尖端是否落在端子范围内。</p>
        </div>
        <div class="algo-item">
          <h4>端子盖开闭判断</h4>
          <p>基于 cover 中心 Y 坐标相对于电表底部的位置：打开 — cover 中心 Y <= 电表底部 - 电表高度*0.20；关闭 — cover 中心 Y >= 电表底部 - 电表高度*0.10。</p>
        </div>
        <div class="algo-item">
          <h4>两阶段拆除判定</h4>
          <p>阶段一：螺丝刀接触端子累计 >= 3 秒，标记阈值达成。阶段二：螺丝刀离开后连续分开 >= 15 帧，确认端子槽拆除成功。</p>
        </div>
        <div class="algo-item">
          <h4>Glove 拆除验证</h4>
          <p>电表拆线成功后，检测 glove 与电表上方 3/4 区域的 IOU，连续 20 帧 IOU > 0 则标记为 VERIFIED。</p>
        </div>
        <div class="algo-item">
          <h4>状态机流转</h4>
          <p>进行中(Open) → 端子槽数量固定 → 拆线成功(SUCCESS) → 拆除验证(VERIFIED)</p>
        </div>
      </div>
    </section>

    <!-- 关键帧放大弹窗 -->
    <div v-if="selectedKeyFrame" class="modal" @click="selectedKeyFrame = ''">
      <img :src="selectedKeyFrame" class="modal-img" />
    </div>
  </div>
</template>

<style scoped>
.demo-page { padding: 24px; color: #e4e7ed; }
.card { background: rgba(17,24,39,0.6); border: 1px solid rgba(0,212,255,0.15); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.card-title { font-size: 14px; color: #00d4ff; margin-bottom: 12px; }
.status-bar { padding: 8px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; }
.status-bar.ok { background: rgba(34,197,94,0.15); border: 1px solid #22c55e; color: #22c55e; }
.status-bar.err { background: rgba(239,68,68,0.15); border: 1px solid #ef4444; color: #ef4444; }

.info-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 12px; }
.info-item { display: flex; flex-direction: column; gap: 4px; }
.info-item .label { font-size: 11px; color: rgba(255,255,255,0.5); }
.info-item .label.ok { color: #22c55e; }
.info-item .label.err { color: #ef4444; }
.info-item .value { font-size: 13px; }
.class-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.class-tag { padding: 3px 10px; background: rgba(0,212,255,0.15); color: #00d4ff; border-radius: 4px; font-size: 12px; }

.select-row { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.select-group { display: flex; align-items: center; gap: 8px; }
.select-group label { font-size: 13px; color: rgba(255,255,255,0.7); }
.select-group select { background: rgba(0,0,0,0.4); color: #e4e7ed; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 6px 10px; font-size: 13px; }
.hint { font-size: 12px; color: rgba(255,255,255,0.4); }
.upload-group { display: flex; align-items: center; gap: 8px; }
.file-name { font-size: 12px; color: #00d4ff; }
.btn-outline { background: transparent; border: 1px solid rgba(0,212,255,0.3); color: #00d4ff; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn-outline:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary { background: #00d4ff; color: #0d1117; border: none; border-radius: 6px; padding: 8px 20px; cursor: pointer; font-weight: 600; font-size: 13px; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.progress-section { margin-top: 14px; }
.progress-bar { height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #00d4ff, #9b6cff); transition: width 0.3s; }
.progress-text { margin-top: 6px; font-size: 12px; color: rgba(255,255,255,0.6); }

.video-player { width: 100%; max-height: 480px; border-radius: 6px; background: #000; }

.report-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
.report-item { display: flex; flex-direction: column; gap: 4px; }
.report-item .label { font-size: 11px; color: rgba(255,255,255,0.5); }
.report-item .value { font-size: 14px; font-weight: 600; }
.report-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.report-table th { text-align: left; padding: 8px; color: rgba(255,255,255,0.6); border-bottom: 1px solid rgba(255,255,255,0.1); }
.report-table td { padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05); }
.placeholder { color: rgba(255,255,255,0.4); padding: 20px; text-align: center; }

.key-frame-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.key-frame-item { cursor: pointer; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; overflow: hidden; transition: border-color 0.2s; }
.key-frame-item:hover { border-color: #00d4ff; }
.key-frame-item img { width: 100%; display: block; }
.kf-info { padding: 8px; }
.kf-title { font-size: 12px; color: #00d4ff; margin-bottom: 4px; }
.kf-time { font-size: 11px; color: rgba(255,255,255,0.4); }

.algo-content { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.algo-item h4 { font-size: 13px; color: #00d4ff; margin: 0 0 6px; }
.algo-item p { font-size: 12px; color: rgba(255,255,255,0.6); line-height: 1.6; margin: 0; }

.modal { position: fixed; inset: 0; background: rgba(0,0,0,0.85); display: flex; align-items: center; justify-content: center; z-index: 1000; cursor: pointer; }
.modal-img { max-width: 90%; max-height: 90%; border-radius: 8px; }
</style>
