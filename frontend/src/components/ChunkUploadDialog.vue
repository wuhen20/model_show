<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  uploadFileInChunks,
  cancelChunkUpload,
  DEFAULT_CHUNK_SIZE,
  type UploadProgressInfo,
} from '@/api/uploadChunk'

interface Props {
  /** 是否显示弹框 */
  modelValue: boolean
  /** 样本集编号 */
  setNo: string
  /** 样本集名称 */
  setName: string
  /** 样本类型编码（仅支持 05-图片） */
  typeCode: string
  /** 任务来源：sample=高质量样本, original=原始样本 */
  source: 'sample' | 'original'
  /** 弹框标题 */
  title?: string
  /** 说明文字 */
  description?: string
  /** 目录树（el-tree-select data 格式，可选） */
  directoryTree?: any[]
  /** 当前目录 ID（默认选中的目录） */
  currentDirId?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: '批量导入（ZIP 分片上传）',
  description: '上传 ZIP，自动分片上传并解压导入',
  directoryTree: () => [],
  currentDirId: '',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success', info: { taskNo: string }): void
  (e: 'cancel'): void
}>()

// 上传文件
const file = ref<File | null>(null)
const uploadRef = ref()

// 上传状态
const uploading = ref(false)
const cancelRequested = ref(false)
const progressInfo = ref<UploadProgressInfo | null>(null)

// 高质量样本专用：版本变更
const majorVersion = ref(false)
const versionRemark = ref('')

// 上传目标目录（默认当前目录，可切换到其他已有目录或根目录）
const selectedDirId = ref('')

// el-tree-select 目录选项（含"根目录"选项）
const dirTreeOptions = computed(() => [
  { value: '', label: '根目录', children: [] },
  ...props.directoryTree,
])

// 弹框打开时，默认选中当前目录
watch(() => props.modelValue, (visible) => {
  if (visible) {
    selectedDirId.value = props.currentDirId || ''
  }
})


// 是否高质量样本
const isSample = computed(() => props.source === 'sample')

// 阶段文案
const stageText = computed(() => {
  const stage = progressInfo.value?.stage
  if (stage === 'uploading') return `上传分片中 (${progressInfo.value?.uploadedChunks}/${progressInfo.value?.totalChunks})`
  if (stage === 'merging') {
    const status = progressInfo.value?.taskInfo?.taskStatusName
    return status || '处理中'
  }
  if (stage === 'done') return '已完成'
  if (stage === 'error') return '失败'
  return '准备中'
})

// 进度百分比
const percent = computed(() => {
  const stage = progressInfo.value?.stage
  if (stage === 'uploading') {
    return progressInfo.value?.percent || 0
  }
  if (stage === 'merging') {
    // 合并/导入阶段不显示具体进度，但保持进度条在 100%
    return 100
  }
  if (stage === 'done') return 100
  if (stage === 'error') return 100
  return 0
})

// 进度条状态
const progressStatus = computed(() => {
  const stage = progressInfo.value?.stage
  if (stage === 'done') return 'success'
  if (stage === 'error') return 'exception'
  return undefined
})

// 是否可取消
const canCancel = computed(() => {
  const stage = progressInfo.value?.stage
  // 上传阶段可取消，合并/导入阶段不可取消
  return uploading.value && stage === 'uploading'
})

// 是否可关闭弹框
const canClose = computed(() => !uploading.value)

function handleFileChange(f: any) {
  file.value = f.raw
  progressInfo.value = null
}

function handleFileRemove() {
  file.value = null
  progressInfo.value = null
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function handleClose() {
  if (!canClose.value) {
    ElMessage.warning('任务进行中，请先取消或等待完成')
    return
  }
  emit('update:modelValue', false)
  // 重置状态
  file.value = null
  progressInfo.value = null
  majorVersion.value = false
  versionRemark.value = ''
  selectedDirId.value = ''
  setTimeout(() => {
    uploadRef.value?.clearFiles()
  }, 0)
}

async function handleConfirm() {
  if (!file.value) {
    ElMessage.warning('请选择要上传的 ZIP 文件')
    return
  }
  const fileName = file.value.name.toLowerCase()
  if (!fileName.endsWith('.zip')) {
    ElMessage.warning('仅支持 ZIP 文件')
    return
  }
  if (isSample.value && versionRemark.value.length > 150) {
    ElMessage.warning('变更说明不能超过 150 个字')
    return
  }

  uploading.value = true
  cancelRequested.value = false
  progressInfo.value = {
    stage: 'uploading',
    uploadedChunks: 0,
    totalChunks: 0,
    percent: 0,
  }

  try {
    const result = await uploadFileInChunks(
      file.value,
      {
        setNo: props.setNo,
        setName: props.setName,
        typeCode: props.typeCode,
        source: props.source,
        majorVersionChange: isSample.value ? majorVersion.value : false,
        versionRemark: isSample.value ? versionRemark.value.trim() : '',
        dirId: selectedDirId.value,
      },
      {
        concurrency: 3,
        shouldCancel: () => cancelRequested.value,
        onProgress: (info) => {
          progressInfo.value = info
        },
      },
    )
    // 分片上传 + 合并触发成功，后端后台线程开始执行导入
    // 前端不再等待导入完成，立即提示并关闭弹窗
    ElMessage.success(`分片上传完成，后台正在导入（任务号：${result.taskNo}）。可关闭页面，导入不受影响。`)
    emit('success', { taskNo: result.taskNo })
    // 立即关闭弹窗
    setTimeout(() => {
      handleClose()
    }, 800)
  } catch (e: any) {
    if (cancelRequested.value) {
      ElMessage.info('已取消上传')
    } else {
      ElMessage.error(e.message || '导入失败')
    }
    progressInfo.value = {
      ...progressInfo.value!,
      stage: 'error',
      error: e.message || '导入失败',
    }
  } finally {
    uploading.value = false
    cancelRequested.value = false
  }
}

async function handleCancel() {
  try {
    await ElMessageBox.confirm('确认取消当前上传任务？已上传的分片将被清理。', '取消确认', {
      type: 'warning',
      confirmButtonText: '取消任务',
      cancelButtonText: '继续上传',
    })
  } catch {
    return
  }
  cancelRequested.value = true
  const taskNo = progressInfo.value?.taskNo
  if (taskNo) {
    try {
      await cancelChunkUpload(taskNo)
    } catch (e: any) {
      // 后端取消失败也不阻塞，前端已标记取消
      console.error('后端取消失败:', e)
    }
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="title"
    width="560px"
    :close-on-click-modal="false"
    :close-on-press-escape="canClose"
    :show-close="canClose"
    class="chunk-upload-dialog"
  >
    <div class="upload-content">
      <!-- 样本集信息 -->
      <div class="info-row">
        <span class="info-label">样本集：</span>
        <span class="info-value">{{ setName }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">说明：</span>
        <span class="info-value">{{ description }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">分片大小：</span>
        <span class="info-value">{{ formatSize(DEFAULT_CHUNK_SIZE) }} / 片，大文件自动分片上传，支持断点续传</span>
      </div>
      <div class="subdir-row">
        <div class="subdir-label">目标目录<span class="subdir-tip">（选择已有目录或根目录）</span></div>
        <el-tree-select
          v-model="selectedDirId"
          :data="dirTreeOptions"
          :props="{ label: 'label', value: 'value', children: 'children' }"
          :render-after-expand="false"
          check-strictly
          default-expand-all
          placeholder="根目录"
          :disabled="uploading"
          clearable
          style="width: 100%"
        />
      </div>

      <!-- 文件选择 -->
      <el-upload
        ref="uploadRef"
        accept=".zip"
        :auto-upload="false"
        :limit="1"
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
        :disabled="uploading"
        drag
      >
        <div class="upload-drag-content">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.5)" stroke-width="1.5">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
          </svg>
          <p>将 ZIP 文件拖到此处，或<em>点击上传</em></p>
          <p class="upload-tip">仅支持单个 ZIP，图片类型样本集</p>
          <p v-if="file" class="file-size-tip">文件大小：{{ formatSize(file.size) }}</p>
        </div>
      </el-upload>

      <!-- 高质量样本专用：版本变更 -->
      <template v-if="isSample">
        <div class="version-row">
          <el-checkbox v-model="majorVersion" :disabled="uploading">大版本变更</el-checkbox>
        </div>
        <div v-if="majorVersion" class="remark-row">
          <div class="remark-label">变更说明<span class="remark-tip">（非必填，最多 150 字）</span></div>
          <el-input
            v-model="versionRemark"
            type="textarea"
            :rows="3"
            placeholder="请输入变更说明，留空则自动生成"
            maxlength="150"
            show-word-limit
            :disabled="uploading"
          />
        </div>
      </template>

      <!-- 上传进度 -->
      <div v-if="progressInfo" class="progress-section">
        <div class="progress-header">
          <span class="progress-stage">{{ stageText }}</span>
          <span v-if="progressInfo.stage === 'uploading'" class="progress-percent">{{ percent }}%</span>
        </div>
        <el-progress
          :percentage="percent"
          :status="progressStatus"
          :stroke-width="10"
          :indeterminate="progressInfo.stage === 'merging'"
        />
        <div v-if="progressInfo.stage === 'uploading'" class="progress-detail">
          已上传 {{ progressInfo.uploadedChunks }} / {{ progressInfo.totalChunks }} 分片
        </div>
        <div v-if="progressInfo.stage === 'merging' && progressInfo.taskInfo" class="progress-detail">
          {{ progressInfo.taskInfo.taskStatusName }}
          <span v-if="progressInfo.taskInfo.imageCount > 0">
            （已导入 {{ progressInfo.taskInfo.imageCount }} 张图片）
          </span>
        </div>
        <div v-if="progressInfo.stage === 'error' && progressInfo.error" class="progress-error">
          {{ progressInfo.error }}
        </div>
      </div>
    </div>

    <template #footer>
      <el-button
        v-if="canCancel"
        type="danger"
        @click="handleCancel"
      >取消上传</el-button>
      <el-button @click="handleClose" :disabled="!canClose">关闭</el-button>
      <el-button
        type="primary"
        :loading="uploading"
        :disabled="uploading || !file"
        @click="handleConfirm"
      >{{ uploading ? '处理中' : '开始导入' }}</el-button>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
.upload-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.info-row {
  display: flex;
  font-size: 13px;
  line-height: 1.6;

  .info-label {
    color: rgba(255, 255, 255, 0.5);
    min-width: 70px;
  }
  .info-value {
    color: rgba(255, 255, 255, 0.85);
    flex: 1;
  }
}

.upload-drag-content {
  p {
    margin: 8px 0 0 0;
    color: rgba(255, 255, 255, 0.7);
    font-size: 13px;
  }
  .upload-tip {
    color: rgba(255, 255, 255, 0.4);
    font-size: 12px;
  }
  .file-size-tip {
    color: #00d4ff;
    font-size: 12px;
    margin-top: 4px;
  }
}

.version-row {
  margin-top: 4px;
}

.subdir-row {
  .subdir-label {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.7);
    margin-bottom: 6px;
  }
  .subdir-tip {
    color: rgba(255, 255, 255, 0.4);
    font-size: 12px;
    margin-left: 6px;
  }
}

.remark-row {
  .remark-label {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.7);
    margin-bottom: 6px;
  }
  .remark-tip {
    color: rgba(255, 255, 255, 0.4);
    font-size: 12px;
    margin-left: 6px;
  }
}

.progress-section {
  margin-top: 8px;
  padding: 14px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  border: 1px solid rgba(0, 212, 255, 0.15);

  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;

    .progress-stage {
      color: #00d4ff;
      font-size: 13px;
      font-weight: 600;
    }
    .progress-percent {
      color: rgba(255, 255, 255, 0.85);
      font-size: 13px;
    }
  }

  .progress-detail {
    margin-top: 8px;
    color: rgba(255, 255, 255, 0.6);
    font-size: 12px;
  }

  .progress-error {
    margin-top: 8px;
    color: #ff5555;
    font-size: 12px;
    word-break: break-all;
  }
}
</style>

<style lang="scss">
.el-dialog.chunk-upload-dialog {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.98) 0%, rgba(26, 35, 50, 0.95) 100%) !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;
  border-radius: 12px !important;

  --el-text-color-regular: rgba(255, 255, 255, 0.85);
  --el-text-color-primary: #fff;
  --el-text-color-placeholder: rgba(255, 255, 255, 0.3);
  --el-fill-color-blank: transparent;
  --el-border-color: rgba(0, 212, 255, 0.2);
  --el-bg-color: transparent;
  --el-bg-color-overlay: rgba(17, 24, 39, 0.98);
  --el-color-primary: #00d4ff;

  .el-dialog__header {
    border-bottom: 1px solid rgba(0, 212, 255, 0.15);
  }
  .el-dialog__title {
    color: #fff !important;
  }
  .el-dialog__body {
    padding: 24px 20px;
  }
  .el-form-item__label {
    color: rgba(255, 255, 255, 0.7) !important;
  }
  .el-button--primary {
    background: linear-gradient(135deg, #00d4ff, #0099cc) !important;
    border: none !important;
    color: #0d1117 !important;
    font-weight: 600;
  }
  .el-button:not(.el-button--primary):not(.el-button--danger) {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
    color: rgba(255, 255, 255, 0.7) !important;
  }
  .el-upload-dragger {
    background: rgba(0, 212, 255, 0.04);
    border: 1px dashed rgba(0, 212, 255, 0.3);
    &:hover {
      border-color: rgba(0, 212, 255, 0.5);
    }
  }
}
</style>
