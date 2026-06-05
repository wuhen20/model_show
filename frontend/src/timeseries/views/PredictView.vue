<template>
  <div class="predict-view">
    <StatStrip :items="stats" />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据预测</span>
        </div>
      </template>

      <!-- 步骤指示器 -->
      <el-steps :active="currentStep" finish-status="success" style="margin-bottom: 30px">
        <el-step title="选择数据源" />
        <el-step title="配置预测参数" />
        <el-step title="执行预测" />
      </el-steps>

      <!-- 步骤1：选择数据源 -->
      <div v-if="currentStep === 0" class="step-content">
        <h3>选择预测数据源</h3>
        <p class="hint">请选择已上传、已处理或已整合的文件作为预测数据源</p>
        
        <!-- 已上传文件 -->
        <h4 style="margin-top: 20px">已上传文件</h4>
        <el-table 
          :data="uploadedFiles" 
          @row-click="selectSourceFile"
          highlight-current-row
          border
          style="width: 100%; margin-bottom: 20px"
        >
          <el-table-column prop="original_name" label="文件名" />
          <el-table-column label="文件大小" width="120">
            <template #default="scope">
              {{ formatFileSize(scope.row.file_size) }}
            </template>
          </el-table-column>
          <el-table-column label="上传时间" width="180">
            <template #default="scope">
              {{ formatDateTime(scope.row.upload_time) }}
            </template>
          </el-table-column>
          <el-table-column label="文件类型" width="120">
            <template #default>
              <el-tag type="info">已上传</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="scope">
              <el-button 
                type="info" 
                size="small"
                @click.stop="selectSourceFile(scope.row)"
              >
                选择
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 已处理文件 -->
        <h4 style="margin-top: 20px">已处理文件</h4>
        <el-table 
          :data="processedFiles" 
          @row-click="selectSourceFile"
          highlight-current-row
          border
          style="width: 100%; margin-bottom: 20px"
        >
          <el-table-column prop="file_name" label="文件名" />
          <el-table-column prop="original_name" label="原始文件名" />
          <el-table-column label="文件类型" width="120">
            <template #default>
              <el-tag type="primary">已处理</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="scope">
              <el-button 
                type="primary" 
                size="small"
                @click.stop="selectSourceFile(scope.row)"
              >
                选择
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 已整合文件 -->
        <h4 style="margin-top: 20px">已整合文件</h4>
        <el-table 
          :data="mergedFiles" 
          @row-click="selectSourceFile"
          highlight-current-row
          border
          style="width: 100%"
        >
          <el-table-column prop="file_name" label="文件名" />
          <el-table-column prop="original_name" label="原始文件名" />
          <el-table-column label="文件类型" width="120">
            <template #default>
              <el-tag type="success">已整合</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="scope">
              <el-button 
                type="success" 
                size="small"
                @click.stop="selectSourceFile(scope.row)"
              >
                选择
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="uploadedFiles.length === 0 && processedFiles.length === 0 && mergedFiles.length === 0" class="empty-tip">
          <el-empty description="暂无可用文件，请先上传文件、进行数据处理或样本整合" />
        </div>
      </div>

      <!-- 步骤2：配置预测参数 -->
      <div v-if="currentStep === 1" class="step-content">
        <h3>配置预测参数</h3>
        
        <el-alert 
          v-if="selectedFile" 
          :title="`数据源：${selectedFile.file_name}`" 
          type="success" 
          :closable="false"
          style="margin-bottom: 20px"
        />

        <el-form :model="predictForm" label-width="150px" style="max-width: 800px">
          <el-form-item label="预测模型">
            <div style="display: flex; gap: 8px; width: 100%">
              <el-select
                v-model="predictForm.model_path"
                placeholder="选择本机模型（留空则使用默认内置模型）"
                clearable
                filterable
                style="flex: 1"
              >
                <el-option
                  v-for="m in models"
                  :key="m.path"
                  :label="m.name + (m.size_mb ? ` (${m.size_mb} MB)` : '')"
                  :value="m.path"
                >
                  <span>{{ m.name }}</span>
                  <span style="float: right; color: #8a97a8; font-size: 12px">{{ m.path }}</span>
                </el-option>
              </el-select>
              <el-button @click="openModelBrowser">
                <el-icon style="margin-right: 4px"><FolderOpened /></el-icon>浏览…
              </el-button>
            </div>
            <div class="form-hint">
              在本机选择 Chronos 模型目录（需含 config.json 与权重文件）。留空则使用默认模型：{{ defaultModelPath || '内置 Model/chronos-2' }}
            </div>
          </el-form-item>

          <el-form-item label="时序ID列">
            <el-select 
              v-model="predictForm.id_column" 
              placeholder="请选择时序ID列"
              style="width: 100%"
            >
              <el-option
                v-for="col in headers"
                :key="col"
                :label="col"
                :value="col"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="时间列">
            <el-select 
              v-model="predictForm.timestamp_columns" 
              multiple
              collapse-tags
              :multiple-limit="2"
              placeholder="请选择时间列（支持多选1-2列）"
              style="width: 100%"
            >
              <el-option
                v-for="col in headers"
                :key="col"
                :label="col"
                :value="col"
              />
            </el-select>
            <div class="form-hint">选择1-2个时间字段。若选择2列（如日期+时间），系统将自动拼接为 "日期T时间" 格式</div>
          </el-form-item>

          <el-form-item label="预测目标字段">
            <el-select 
              v-model="predictForm.target_fields" 
              multiple
              placeholder="请选择需要预测的字段"
              style="width: 100%"
            >
              <el-option
                v-for="col in headers"
                :key="col"
                :label="col"
                :value="col"
              />
            </el-select>
            <div class="form-hint">可选择多个字段进行预测</div>
          </el-form-item>

          <el-form-item label="关联目标字段">
            <el-select 
              v-model="predictForm.related_target_fields" 
              multiple
              placeholder="请选择关联目标字段（可选）"
              style="width: 100%"
            >
              <el-option
                v-for="col in relatedFieldOptions"
                :key="col"
                :label="col"
                :value="col"
              />
            </el-select>
            <div class="form-hint">排除预测目标字段、时序ID列和时间列后的剩余字段。关联数据的时间轴将延伸至预测起始时间，为模型提供额外协变量信息</div>
          </el-form-item>

          <el-form-item label="预测长度">
            <el-input-number 
              v-model="predictForm.prediction_length" 
              :min="1" 
              :max="999"
              placeholder="预测点数（如24、96）"
              style="width: 100%"
            />
            <div class="form-hint">预测未来的时间点数量</div>
          </el-form-item>

          <el-form-item label="预测起始时间">
            <el-date-picker
              v-model="predictForm.prediction_start_time"
              type="datetime"
              placeholder="选择预测起始时间（可选）"
              format="YYYY-MM-DD HH:mm:ss"
              value-format="YYYY-MM-DD HH:mm:ss"
              style="width: 100%"
            />
            <div class="form-hint">不填则默认从历史数据最后时刻继续预测。格式：YYYY-MM-DD HH:mm:ss</div>
          </el-form-item>

          <el-form-item label="预测策略">
            <el-radio-group v-model="predictForm.predict_strategy">
              <el-radio label="line">整行预测（所有字段一起预测）</el-radio>
              <el-radio label="col">逐列预测（每个字段单独预测）</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="分位数水平">
            <el-select 
              v-model="predictForm.quantile_levels" 
              multiple
              filterable
              allow-create
              :multiple-limit="3"
              placeholder="选择或输入分位数（0.1-0.99，最多3个）"
              style="width: 100%"
            >
              <el-option label="0.1 (下限)" :value="0.1" />
              <el-option label="0.25" :value="0.25" />
              <el-option label="0.5 (中位数)" :value="0.5" />
              <el-option label="0.75" :value="0.75" />
              <el-option label="0.9 (上限)" :value="0.9" />
            </el-select>
            <div class="form-hint">可选择或输入 0.1-0.99 范围内的分位数，最多3个。常用值：0.1(下限)、0.5(中位数)、0.9(上限)</div>
          </el-form-item>
        </el-form>

        <div class="step-actions">
          <el-button @click="currentStep = 0">上一步</el-button>
          <el-button type="primary" @click="executePrediction" :loading="predicting">
            执行预测
          </el-button>
        </div>
      </div>

      <!-- 步骤3：执行预测 -->
      <div v-if="currentStep === 2" class="step-content">
        <el-result
          icon="success"
          title="预测完成"
          :sub-title="predictMessage"
        >
          <template #extra>
            <el-button type="primary" @click="resetPrediction">继续预测</el-button>
            <el-button type="success" @click="goToDownload">查看预测结果</el-button>
          </template>
        </el-result>
      </div>

      <!-- 模型目录浏览对话框 -->
      <el-dialog v-model="modelBrowserVisible" title="选择本机模型目录" width="640px">
        <div class="browser-path">
          <el-icon><FolderOpened /></el-icon>
          <span>{{ browser.current || '此电脑（选择盘符）' }}</span>
          <el-tag v-if="browser.is_model" type="success" size="small" effect="dark" style="margin-left: auto">
            有效模型目录
          </el-tag>
        </div>
        <div class="browser-toolbar">
          <el-button size="small" :disabled="!browser.parent" @click="browseTo(browser.parent)">
            ⬆ 上一级
          </el-button>
          <el-button size="small" @click="browseTo('')">此电脑</el-button>
        </div>
        <div class="browser-list" v-loading="browser.loading">
          <div
            v-for="d in browser.dirs"
            :key="d.path"
            class="browser-item"
            :class="{ 'is-model': d.is_model }"
            @click="browseTo(d.path)"
          >
            <el-icon class="browser-item-icon"><Folder /></el-icon>
            <span class="browser-item-name">{{ d.name }}</span>
            <el-tag v-if="d.is_model" type="success" size="small" effect="plain">模型</el-tag>
          </div>
          <div v-if="!browser.loading && browser.dirs.length === 0" class="browser-empty">
            （无子目录）
          </div>
        </div>
        <template #footer>
          <el-button @click="modelBrowserVisible = false">取消</el-button>
          <el-button type="primary" :disabled="!browser.is_model" @click="confirmModelSelection">
            选择当前目录
          </el-button>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Folder, FolderOpened } from '@element-plus/icons-vue'
import StatStrip from '@/timeseries/components/StatStrip.vue'
import { predictAPI } from '@/timeseries/api'

const router = useRouter()

const currentStep = ref(0)
const uploadedFiles = ref([])
const processedFiles = ref([])
const mergedFiles = ref([])
const selectedFile = ref(null)
const headers = ref([])
const predicting = ref(false)
const predictMessage = ref('')

// 模型选择相关状态
const models = ref([])
const defaultModelPath = ref('')
const modelBrowserVisible = ref(false)
const browser = reactive({
  current: '',
  parent: null,
  is_model: false,
  dirs: [],
  loading: false
})

const predictForm = reactive({
  id_column: 'series_id',
  timestamp_columns: ['data_date'],
  target_fields: [],
  related_target_fields: [],
  prediction_length: 96,
  prediction_start_time: '',  // 预测起始时间（可选）
  predict_strategy: 'line',
  quantile_levels: [0.1, 0.5, 0.9],
  model_path: ''  // 用户选择的模型目录（留空=默认模型）
})

const stats = computed(() => [
  { label: '可预测文件', value: uploadedFiles.value.length + processedFiles.value.length + mergedFiles.value.length, icon: 'Files', color: '#00d4ff' },
  { label: '可用模型', value: models.value.length, icon: 'Cpu', color: '#5ee7ff' },
  { label: '预测目标字段', value: predictForm.target_fields.length, icon: 'TrendCharts', color: '#2fd6a0' },
  { label: '预测长度', value: predictForm.prediction_length, icon: 'Histogram', color: '#ffb454' }
])

const relatedFieldOptions = computed(() => {
  const exclude = new Set([
    ...predictForm.target_fields,
    predictForm.id_column,
    ...predictForm.timestamp_columns
  ])
  return headers.value.filter(h => !exclude.has(h))
})

// 加载可用文件
const loadAvailableFiles = async () => {
  try {
    const result = await predictAPI.getAvailableFiles()
    uploadedFiles.value = result.uploaded_files || []
    processedFiles.value = result.processed_files || []
    mergedFiles.value = result.merged_files || []
  } catch (error) {
    ElMessage.error('加载文件列表失败')
  }
}

// 加载本机可选模型列表
const loadModels = async () => {
  try {
    const res = await predictAPI.getModels()
    models.value = res.models || []
    defaultModelPath.value = res.default || ''
  } catch (error) {
    // 模型列表加载失败不影响默认预测，仅记录
    console.error('加载模型列表失败:', error)
  }
}

// 打开模型目录浏览对话框
const openModelBrowser = async () => {
  modelBrowserVisible.value = true
  // 定位到已选模型的上级目录，否则从模型根/盘符开始
  const start = predictForm.model_path
    ? predictForm.model_path.split('/').slice(0, -1).join('/')
    : ''
  await browseTo(start)
}

// 浏览到指定目录
const browseTo = async (path) => {
  browser.loading = true
  try {
    const res = await predictAPI.browseModels(path || '')
    browser.current = res.current || ''
    browser.parent = res.parent
    browser.is_model = !!res.is_model
    browser.dirs = res.dirs || []
  } catch (error) {
    ElMessage.error('浏览目录失败：' + (error.response?.data?.detail || error.message))
  } finally {
    browser.loading = false
  }
}

// 确认选择当前目录为模型
const confirmModelSelection = () => {
  if (!browser.is_model) {
    ElMessage.warning('当前目录不是有效的模型目录（需包含 config.json 与权重文件）')
    return
  }
  predictForm.model_path = browser.current
  // 若不在下拉列表则补入
  if (!models.value.find(m => m.path === browser.current)) {
    const name = browser.current.split('/').filter(Boolean).pop() || browser.current
    models.value.push({ name, path: browser.current, size_mb: 0 })
  }
  modelBrowserVisible.value = false
  ElMessage.success('已选择模型：' + browser.current)
}

// 选择数据源文件
const selectSourceFile = async (file) => {
  selectedFile.value = file
  
  try {
    // 获取文件表头：对于uploaded类型使用file_id，其他类型使用file_name
    const identifier = file.file_type === 'uploaded' ? file.file_id : file.file_name
    const headerResult = await predictAPI.getHeaders(file.file_type, identifier)
    headers.value = headerResult.headers || []
    
    // 智能推荐
    if (headerResult.suggested_time_columns?.length > 0) {
      // 默认推荐第一个时间列，用户可以根据需要添加第二个
      predictForm.timestamp_columns = [headerResult.suggested_time_columns[0]]
    }
    if (headerResult.suggested_hour_columns?.length > 0) {
      predictForm.target_fields = headerResult.suggested_hour_columns.slice(0, 3)
    }
    
    currentStep.value = 1
  } catch (error) {
    ElMessage.error('获取文件表头失败')
  }
}

// 执行预测
const executePrediction = async () => {
  // 验证表单
  if (!predictForm.timestamp_columns || predictForm.timestamp_columns.length === 0) {
    ElMessage.warning('请至少选择一个时间列')
    return
  }
  
  if (predictForm.timestamp_columns.length > 2) {
    ElMessage.warning('最多只能选择2个时间列')
    return
  }
  
  if (!predictForm.target_fields || predictForm.target_fields.length === 0) {
    ElMessage.warning('请至少选择一个预测目标字段')
    return
  }
  
  if (!predictForm.prediction_length || predictForm.prediction_length <= 0) {
    ElMessage.warning('请输入有效的预测长度')
    return
  }
  
  // 验证分位数水平
  if (!predictForm.quantile_levels || predictForm.quantile_levels.length === 0) {
    ElMessage.warning('请至少选择一个分位数水平')
    return
  }
  
  if (predictForm.quantile_levels.length > 3) {
    ElMessage.warning('最多只能选择3个分位数水平')
    return
  }
  
  // 验证分位数范围
  for (const q of predictForm.quantile_levels) {
    if (q < 0.1 || q > 0.99) {
      ElMessage.warning('分位数必须在 0.1 到 0.99 之间')
      return
    }
  }
  
  predicting.value = true
  
  try {
    const predictRequest = {
      file_id: selectedFile.value.file_id,
      file_name: selectedFile.value.file_name,
      file_type: selectedFile.value.file_type,
      id_column: predictForm.id_column,
      timestamp_columns: predictForm.timestamp_columns,
      target_fields: predictForm.target_fields,
      related_target_fields: predictForm.related_target_fields,
      prediction_length: predictForm.prediction_length,
      prediction_start_time: predictForm.prediction_start_time || null,
      predict_strategy: predictForm.predict_strategy,
      quantile_levels: predictForm.quantile_levels,
      model_path: predictForm.model_path || null
    }
    
    const result = await predictAPI.execute(predictRequest)
    
    if (result.status === 'completed') {
      predictMessage.value = result.message || '预测成功完成'
      currentStep.value = 2
      ElMessage.success('预测完成')
    }
  } catch (error) {
    ElMessage.error('预测失败：' + (error.response?.data?.detail || error.message))
  } finally {
    predicting.value = false
  }
}

// 重置预测
const resetPrediction = () => {
  currentStep.value = 0
  selectedFile.value = null
  headers.value = []
  predictForm.target_fields = []
  predictForm.related_target_fields = []
  predictForm.prediction_length = 96
  predictForm.prediction_start_time = ''
  loadAvailableFiles()
}

// 跳转到下载页面
const goToDownload = () => {
  router.push('/timeseries/sample-set')
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i]
}

// 格式化日期时间
const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

onMounted(() => {
  loadAvailableFiles()
  loadModels()
})
</script>

<style scoped>
.predict-view {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
}

.step-content {
  margin-top: 20px;
}

.step-content h3 {
  margin-bottom: 10px;
  color: #eaf3ff;
}

.step-content h4 {
  margin-bottom: 10px;
  color: #aebdda;
}

.hint {
  color: #8aa0c8;
  margin-bottom: 20px;
}

.form-hint {
  color: #8aa0c8;
  font-size: 12px;
  margin-top: 5px;
}

.empty-tip {
  margin-top: 40px;
}

.step-actions {
  margin-top: 30px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 模型目录浏览器 */
.browser-path {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(20, 48, 96, 0.5);
  border: 1px solid rgba(56, 132, 235, 0.24);
  border-radius: 8px;
  font-size: 13px;
  color: #dbe7ff;
  word-break: break-all;
}
.browser-toolbar {
  display: flex;
  gap: 8px;
  margin: 12px 0;
}
.browser-list {
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid rgba(56, 132, 235, 0.2);
  border-radius: 8px;
  padding: 6px;
  background: rgba(8, 20, 44, 0.4);
}
.browser-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.18s ease;
}
.browser-item:hover {
  background: rgba(32, 168, 255, 0.14);
}
.browser-item.is-model {
  background: rgba(47, 214, 160, 0.12);
}
.browser-item-icon {
  color: #ffb454;
  font-size: 18px;
}
.browser-item-name {
  flex: 1;
  font-size: 14px;
  color: #dbe7ff;
  word-break: break-all;
}
.browser-empty {
  text-align: center;
  color: #7f9ac4;
  padding: 24px 0;
  font-size: 13px;
}
</style>
