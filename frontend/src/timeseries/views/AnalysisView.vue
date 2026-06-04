<template>
  <div class="analysis-view">
    <StatStrip :items="stats" />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据分析</span>
        </div>
      </template>

      <!-- 步骤指示器 -->
      <el-steps :active="currentStep" finish-status="success" style="margin-bottom: 30px">
        <el-step title="选择数据源" />
        <el-step title="配置数据列" />
        <el-step title="查看图表" />
      </el-steps>

      <!-- 步骤1：选择数据源 -->
      <div v-if="currentStep === 0" class="step-content">
        <h3>选择真实数据源</h3>
        <p class="hint">请选择已上传、已处理或已整合的文件作为真实数据</p>
        
        <!-- 已上传文件 -->
        <h4 style="margin-top: 20px">已上传文件</h4>
        <el-table 
          :data="uploadedFiles" 
          @row-click="selectRealFile"
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
                @click.stop="selectRealFile(scope.row)"
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
          @row-click="selectRealFile"
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
                @click.stop="selectRealFile(scope.row)"
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
          @row-click="selectRealFile"
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
                @click.stop="selectRealFile(scope.row)"
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

      <!-- 步骤2：配置数据列 -->
      <div v-if="currentStep === 1" class="step-content">
        <h3>配置数据列</h3>
        
        <el-alert 
          v-if="realFile" 
          :title="`真实数据源：${realFile.file_name}`" 
          type="success" 
          :closable="false"
          style="margin-bottom: 20px"
        />

        <el-form :model="analysisForm" label-width="150px" style="max-width: 900px">
          <!-- 真实数据列配置 -->
          <el-divider content-position="left">真实数据配置</el-divider>
          
          <el-form-item label="时间列">
            <el-select 
              v-model="analysisForm.real_time_column" 
              placeholder="请选择时间列"
              style="width: 100%"
              @change="onRealTimeColumnChange"
            >
              <el-option
                v-for="col in realHeaders"
                :key="col"
                :label="col"
                :value="col"
              />
            </el-select>
            <div class="form-hint">如果数据包含日期和时间两列，请选择日期列</div>
          </el-form-item>

          <el-form-item v-if="hasRealDateTimeColumns" label="时间列">
            <el-select 
              v-model="analysisForm.real_time_column_2" 
              placeholder="请选择时间列（时分秒）"
              style="width: 100%"
            >
              <el-option
                v-for="col in realTimeColumns"
                :key="col"
                :label="col"
                :value="col"
              />
            </el-select>
            <div class="form-hint">选择包含时分秒的时间列，将与日期列合并</div>
          </el-form-item>

          <el-form-item v-if="realTimeValues.length > 0" label="时间范围">
            <el-date-picker
              v-model="analysisForm.real_time_range"
              type="datetimerange"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              format="YYYY-MM-DD HH:mm:ss"
              value-format="YYYY-MM-DD HH:mm:ss"
              :disabled-date="(time) => disableRealDate(time)"
              style="width: 100%"
            />
            <div class="form-hint">可选：筛选特定时间范围的数据（{{ realTimeRangeMin }} 至 {{ realTimeRangeMax }}）</div>
          </el-form-item>

          <el-form-item label="数值列">
            <el-select 
              v-model="analysisForm.real_value_columns" 
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="请选择真实数值列（支持多选）"
              style="width: 100%"
            >
              <el-option
                v-for="col in realValueColumns"
                :key="col"
                :label="col"
                :value="col"
              />
            </el-select>
            <div class="form-hint">选择需要展示的真实数据数值列</div>
          </el-form-item>

          <!-- 预测数据文件选择 -->
          <el-divider content-position="left">预测数据配置（可选）</el-divider>
          
          <el-form-item label="选择预测文件">
            <el-select 
              v-model="predictFile" 
              placeholder="请选择预测文件（可选）"
              style="width: 100%"
              @change="onPredictFileChange"
            >
              <el-option
                v-for="file in predictedFiles"
                :key="file.file_id"
                :label="file.file_name"
                :value="file"
              />
            </el-select>
            <div class="form-hint">选择需要对比的预测数据文件</div>
          </el-form-item>

          <template v-if="predictFile">
            <el-form-item label="预测时间列">
              <el-select 
                v-model="analysisForm.predict_time_column" 
                placeholder="请选择预测时间列"
                style="width: 100%"
                @change="onPredictTimeColumnChange"
              >
                <el-option
                  v-for="col in predictHeaders"
                  :key="col"
                  :label="col"
                  :value="col"
                />
              </el-select>
            </el-form-item>

            <el-form-item v-if="predictTimeValues.length > 0" label="预测时间范围">
              <el-date-picker
                v-model="analysisForm.predict_time_range"
                type="datetimerange"
                start-placeholder="开始时间"
                end-placeholder="结束时间"
                format="YYYY-MM-DD HH:mm:ss"
                value-format="YYYY-MM-DD HH:mm:ss"
                :disabled-date="(time) => disablePredictDate(time)"
                style="width: 100%"
              />
              <div class="form-hint">可选：筛选特定时间范围的预测数据（{{ predictTimeRangeMin }} 至 {{ predictTimeRangeMax }}）</div>
            </el-form-item>

            <el-form-item label="预测数值列">
              <el-select 
                v-model="analysisForm.predict_value_columns" 
                multiple
                collapse-tags
                collapse-tags-tooltip
                placeholder="请选择预测数值列（支持多分位多选）"
                style="width: 100%"
              >
                <el-option
                  v-for="col in predictValueColumns"
                  :key="col"
                  :label="col"
                  :value="col"
                />
              </el-select>
              <div class="form-hint">选择需要展示的预测数据数值列（支持多分位数）</div>
            </el-form-item>
          </template>
        </el-form>

        <div class="step-actions">
          <el-button @click="currentStep = 0">上一步</el-button>
          <el-button type="primary" @click="loadAndShowChart" :loading="loading">
            生成图表
          </el-button>
        </div>
      </div>

      <!-- 步骤3：查看图表 -->
      <div v-if="currentStep === 2" class="step-content">
        <h3>数据对比分析</h3>
        
        <div class="chart-container">
          <div ref="chartRef" style="width: 100%; height: 600px;"></div>
        </div>

        <!-- 准确率指标 -->
        <div v-if="metrics.length > 0 || metricsLoading" class="metrics-container">
          <el-divider content-position="left">准确率指标</el-divider>
          
          <el-table :data="metrics" border style="width: 100%" stripe v-loading="metricsLoading" element-loading-text="正在计算指标...">
            <el-table-column prop="real_column" label="真实数据列" min-width="180" />
            <el-table-column prop="predict_column" label="预测数据列" min-width="180" />
              <el-table-column label="R²" width="140" align="center">
                <template #default="scope">
                  <template v-if="scope.row.r2 !== null && scope.row.r2 !== undefined">
                    <el-tag :type="scope.row.r2 >= 0.8 ? 'success' : scope.row.r2 >= 0.5 ? 'warning' : 'danger'" effect="dark">
                      {{ scope.row.r2.toFixed(4) }}
                    </el-tag>
                  </template>
                  <span v-else style="color: #c0c4cc;">N/A</span>
                </template>
              </el-table-column>
              <el-table-column label="MAPE (%)" width="160" align="center">
                <template #default="scope">
                  <template v-if="scope.row.mape !== null && scope.row.mape !== undefined">
                    <el-tag :type="scope.row.mape <= 10 ? 'success' : scope.row.mape <= 30 ? 'warning' : 'danger'" effect="dark">
                      {{ scope.row.mape.toFixed(2) }}%
                    </el-tag>
                  </template>
                  <span v-else style="color: #c0c4cc;">N/A</span>
                </template>
              </el-table-column>
              <el-table-column prop="sample_count" label="匹配样本数" width="120" align="center" />
            </el-table>
            
            <div class="metrics-legend">
              <span class="legend-item"><el-tag type="success" effect="dark" size="small">优良</el-tag> R² ≥ 0.8 或 MAPE ≤ 10%</span>
              <span class="legend-item"><el-tag type="warning" effect="dark" size="small">一般</el-tag> 0.5 ≤ R² < 0.8 或 10% < MAPE ≤ 30%</span>
              <span class="legend-item"><el-tag type="danger" effect="dark" size="small">较差</el-tag> R² < 0.5 或 MAPE > 30%</span>
            </div>
        </div>

        <div class="step-actions">
          <el-button @click="currentStep = 1">返回配置</el-button>
          <el-button type="primary" @click="resetAnalysis">重新分析</el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import StatStrip from '@/timeseries/components/StatStrip.vue'
import { analysisAPI } from '@/timeseries/api'

const currentStep = ref(0)
const uploadedFiles = ref([])
const processedFiles = ref([])
const mergedFiles = ref([])
const predictedFiles = ref([])

const stats = computed(() => [
  { label: '已上传', value: uploadedFiles.value.length, icon: 'Upload', color: '#20a8ff' },
  { label: '已处理', value: processedFiles.value.length, icon: 'Operation', color: '#34e1ff' },
  { label: '已整合', value: mergedFiles.value.length, icon: 'Connection', color: '#7c5cff' },
  { label: '已预测', value: predictedFiles.value.length, icon: 'TrendCharts', color: '#2fd6a0' }
])

const realFile = ref(null)
const predictFile = ref(null)

const realHeaders = ref([])
const predictHeaders = ref([])
const realTimeValues = ref([])
const predictTimeValues = ref([])
const realValueColumns = ref([])
const predictValueColumns = ref([])
const realRawData = ref([])
const predictRawData = ref([])
const realTimeColumns = ref([])

// 计算真实数据的时间范围
const realTimeRangeMin = ref('')
const realTimeRangeMax = ref('')

// 计算预测数据的时间范围
const predictTimeRangeMin = ref('')
const predictTimeRangeMax = ref('')

const loading = ref(false)
const metricsLoading = ref(false)
const metrics = ref([])
const chartRef = ref(null)
let chart = null

const analysisForm = reactive({
  real_time_column: '',
  real_time_column_2: '',
  real_time_range: null,
  real_value_columns: [],
  predict_time_column: '',
  predict_time_range: null,
  predict_value_columns: []
})

// 颜色配置
const colorPalette = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', 
  '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#28a0e3'
]

// 加载可用文件
const loadAvailableFiles = async () => {
  try {
    const result = await analysisAPI.getAvailableFiles()
    uploadedFiles.value = result.uploaded_files || []
    processedFiles.value = result.processed_files || []
    mergedFiles.value = result.merged_files || []
    predictedFiles.value = result.predicted_files || []
  } catch (error) {
    ElMessage.error('加载文件列表失败')
  }
}

// 判断是否同时有日期和时间列
const hasRealDateTimeColumns = ref(false)

// 选择真实数据文件
const selectRealFile = async (file) => {
  realFile.value = file
  
  try {
    const identifier = file.file_type === 'uploaded' ? file.file_id : file.file_name
    const headerResult = await analysisAPI.getHeaders(file.file_type, identifier)
    realHeaders.value = headerResult.headers || []
    
    // 检测是否同时有日期和时间列
    const dateCols = realHeaders.value.filter(col => 
      col.toLowerCase().includes('date') || col.includes('日期')
    )
    const timeCols = realHeaders.value.filter(col => 
      col.toLowerCase().includes('time') || col.includes('TIME') || col.includes('时间')
    )
    
    hasRealDateTimeColumns.value = dateCols.length > 0 && timeCols.length > 0
    realTimeColumns.value = timeCols
    
    // 智能推荐
    if (dateCols.length > 0) {
      analysisForm.real_time_column = dateCols[0]
      if (hasRealDateTimeColumns.value && timeCols.length > 0) {
        analysisForm.real_time_column_2 = timeCols[0]
      }
      await onRealTimeColumnChange(analysisForm.real_time_column)
    } else if (headerResult.suggested_time_columns?.length > 0) {
      // 单时间列场景（如 timestamp）
      analysisForm.real_time_column = headerResult.suggested_time_columns[0]
      await onRealTimeColumnChange(analysisForm.real_time_column)
    }
    if (headerResult.suggested_value_columns?.length > 0) {
      // 排除已选为时间列的列，避免重复
      realValueColumns.value = headerResult.suggested_value_columns.filter(
        col => col !== analysisForm.real_time_column && col !== analysisForm.real_time_column_2
      )
      analysisForm.real_value_columns = realValueColumns.value.slice(0, 3)
    }
    
    currentStep.value = 1
  } catch (error) {
    ElMessage.error('获取文件表头失败')
  }
}

// 真实时间列变化时，加载时间值
const onRealTimeColumnChange = async (columnName) => {
  if (!realFile.value || !columnName) return
  
  try {
    const identifier = realFile.value.file_type === 'uploaded' ? realFile.value.file_id : realFile.value.file_name
    const dataResult = await analysisAPI.getData({
      file_id: realFile.value.file_id,
      file_name: identifier,
      file_type: realFile.value.file_type,
      time_column: columnName,
      time_column_2: analysisForm.real_time_column_2 || '',
      value_columns: []
    })
    
    realRawData.value = dataResult.data || []
    // 使用合并后的时间字段
    const timeField = hasRealDateTimeColumns.value ? 'datetime' : columnName
    const times = dataResult.data.map(row => row[timeField]).filter(t => t)
    realTimeValues.value = times
    
    // 计算时间范围
    if (times.length > 0) {
      const normalizeTime = (timeStr) => {
        if (!timeStr) return ''
        let normalized = timeStr.replace(/\//g, '-')
        if (!normalized.includes(':')) {
          normalized += ' 00:00:00'
        }
        const parts = normalized.split(' ')
        if (parts.length === 2) {
          const timeParts = parts[1].split(':')
          if (timeParts.length === 3) {
            timeParts[0] = timeParts[0].padStart(2, '0')
            timeParts[1] = timeParts[1].padStart(2, '0')
            timeParts[2] = timeParts[2].padStart(2, '0')
            parts[1] = timeParts.join(':')
            normalized = parts.join(' ')
          }
        }
        return normalized
      }
      
      const normalizedTimes = times.map(t => normalizeTime(t)).sort()
      realTimeRangeMin.value = normalizedTimes[0]
      realTimeRangeMax.value = normalizedTimes[normalizedTimes.length - 1]
      
      // 自动填充默认时间范围
      analysisForm.real_time_range = [realTimeRangeMin.value, realTimeRangeMax.value]
      
      console.log('[数据分析] 真实数据时间范围:', realTimeRangeMin.value, '至', realTimeRangeMax.value)
    } else {
      realTimeRangeMin.value = ''
      realTimeRangeMax.value = ''
      analysisForm.real_time_range = null
    }
  } catch (error) {
    console.error('加载时间值失败:', error)
  }
}

// 预测文件选择变化
const onPredictFileChange = async (file) => {
  if (!file) {
    predictHeaders.value = []
    predictTimeValues.value = []
    predictValueColumns.value = []
    analysisForm.predict_time_column = ''
    analysisForm.predict_value_columns = []
    return
  }
  
  try {
    const identifier = file.file_type === 'uploaded' ? file.file_id : file.file_name
    const headerResult = await analysisAPI.getHeaders(file.file_type, identifier)
    predictHeaders.value = headerResult.headers || []
    
    // 智能推荐
    if (headerResult.suggested_time_columns?.length > 0) {
      analysisForm.predict_time_column = headerResult.suggested_time_columns[0]
      await onPredictTimeColumnChange(analysisForm.predict_time_column)
    }
    
    // 使用后端推荐的数值列（已排除非数值列）
    if (headerResult.suggested_value_columns?.length > 0) {
      predictValueColumns.value = headerResult.suggested_value_columns
      // 默认选择前3个
      analysisForm.predict_value_columns = predictValueColumns.value.slice(0, 3)
    }
  } catch (error) {
    ElMessage.error('获取预测文件表头失败')
  }
}

// 预测时间列变化时，加载时间值
const onPredictTimeColumnChange = async (columnName) => {
  if (!predictFile.value || !columnName) return
  
  try {
    const identifier = predictFile.value.file_type === 'uploaded' ? predictFile.value.file_id : predictFile.value.file_name
    const dataResult = await analysisAPI.getData({
      file_id: predictFile.value.file_id,
      file_name: identifier,
      file_type: predictFile.value.file_type,
      time_column: columnName,
      value_columns: []
    })
    
    predictRawData.value = dataResult.data || []
    predictTimeValues.value = dataResult.data.map(row => row[columnName]).filter(t => t)
    
    // 计算预测数据时间范围
    if (predictTimeValues.value.length > 0) {
      const normalizeTime = (timeStr) => {
        if (!timeStr) return ''
        let normalized = timeStr.replace(/\//g, '-')
        if (!normalized.includes(':')) {
          normalized += ' 00:00:00'
        }
        const parts = normalized.split(' ')
        if (parts.length === 2) {
          const timeParts = parts[1].split(':')
          if (timeParts.length === 3) {
            timeParts[0] = timeParts[0].padStart(2, '0')
            timeParts[1] = timeParts[1].padStart(2, '0')
            timeParts[2] = timeParts[2].padStart(2, '0')
            parts[1] = timeParts.join(':')
            normalized = parts.join(' ')
          }
        }
        return normalized
      }
      
      const normalizedTimes = predictTimeValues.value.map(t => normalizeTime(t)).sort()
      predictTimeRangeMin.value = normalizedTimes[0]
      predictTimeRangeMax.value = normalizedTimes[normalizedTimes.length - 1]
      
      // 自动填充默认预测时间范围
      analysisForm.predict_time_range = [predictTimeRangeMin.value, predictTimeRangeMax.value]
      
      console.log('[数据分析] 预测数据时间范围:', predictTimeRangeMin.value, '至', predictTimeRangeMax.value)
    } else {
      predictTimeRangeMin.value = ''
      predictTimeRangeMax.value = ''
      analysisForm.predict_time_range = null
    }
    
    // 数值列已由 onPredictFileChange 中使用后端 suggested_value_columns 设置
    // 这里只需要排除当前选择的时间列
    if (predictValueColumns.value.length > 0) {
      predictValueColumns.value = predictValueColumns.value.filter(col => col !== columnName)
    } else {
      // 兜底：如果没有后端推荐，用简单过滤
      predictValueColumns.value = predictHeaders.value.filter(col => 
        col !== columnName && 
        !col.toLowerCase().includes('id') && 
        !col.toLowerCase().includes('series')
      )
    }
  } catch (error) {
    console.error('加载预测时间值失败:', error)
  }
}

// 加载数据并显示图表
const loadAndShowChart = async () => {
  // 验证表单
  if (!analysisForm.real_time_column) {
    ElMessage.warning('请选择真实时间列')
    return
  }
  
  if (!analysisForm.real_value_columns || analysisForm.real_value_columns.length === 0) {
    ElMessage.warning('请至少选择一个真实数值列')
    return
  }
  
  loading.value = true
  
  try {
    // 加载真实数据
    const realDataRequest = {
      file_id: realFile.value.file_id,
      file_name: realFile.value.file_name,
      file_type: realFile.value.file_type,
      time_column: analysisForm.real_time_column,
      time_column_2: analysisForm.real_time_column_2 || '',
      value_columns: analysisForm.real_value_columns
    }
    
    const realDataResult = await analysisAPI.getData(realDataRequest)
    
    // 加载预测数据（如果选择了）
    let predictDataResult = null
    if (predictFile.value && analysisForm.predict_time_column && analysisForm.predict_value_columns.length > 0) {
      const predictDataRequest = {
        file_id: predictFile.value.file_id,
        file_name: predictFile.value.file_name,
        file_type: predictFile.value.file_type,
        time_column: analysisForm.predict_time_column,
        value_columns: analysisForm.predict_value_columns
      }
      predictDataResult = await analysisAPI.getData(predictDataRequest)
    }
    
    // 先切换到图表步骤，让DOM挂载
    currentStep.value = 2
    
    // 等待DOM更新后再渲染图表
    await nextTick()
    renderChart(realDataResult, predictDataResult)
    
    // 计算准确率指标（如果有预测数据）
    if (predictDataResult) {
      loadMetrics()
    } else {
      metrics.value = []
    }
    
    ElMessage.success('图表生成成功')
  } catch (error) {
    ElMessage.error('加载数据失败：' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

// 渲染图表
const renderChart = (realData, predictData) => {
  console.log('[数据分析] renderChart 调用, chartRef:', chartRef.value, 'realData:', realData, 'predictData:', predictData)
  
  if (!chartRef.value) {
    console.error('[数据分析] chartRef 不存在，无法渲染图表')
    return
  }
  
  if (chart) {
    chart.dispose()
  }
  
  chart = echarts.init(chartRef.value)
  
  const series = []
  let colorIndex = 0
  
  // 辅助函数：将时间字符串转换为可比较的格式
  const normalizeTime = (timeStr) => {
    if (!timeStr) return ''
    // 将 2025/1/1 或 2025/1/1 0:15:00 转换为 2025-01-01 00:15:00
    let normalized = timeStr.replace(/\//g, '-')
    
    // 如果只有日期没有时间，添加 00:00:00
    if (!normalized.includes(':')) {
      normalized += ' 00:00:00'
    }
    
    // 如果时间部分少于8位（如 0:15:00），补零
    const parts = normalized.split(' ')
    if (parts.length === 2) {
      const timeParts = parts[1].split(':')
      if (timeParts.length === 3) {
        timeParts[0] = timeParts[0].padStart(2, '0')
        timeParts[1] = timeParts[1].padStart(2, '0')
        timeParts[2] = timeParts[2].padStart(2, '0')
        parts[1] = timeParts.join(':')
        normalized = parts.join(' ')
      }
    }
    
    return normalized
  }
  
  // 筛选真实数据（根据时间范围）
  let filteredRealData = realData.data
  // 确定时间字段名 - 双时间列合并时后端返回字段名为 datetime
  const realTimeField = hasRealDateTimeColumns.value ? 'datetime' : analysisForm.real_time_column
  
  if (analysisForm.real_time_range && analysisForm.real_time_range.length === 2) {
    const [startTime, endTime] = analysisForm.real_time_range
    filteredRealData = realData.data.filter(row => {
      const time = row[realTimeField]
      const normalizedTime = normalizeTime(time)
      return normalizedTime >= startTime && normalizedTime <= endTime
    })
    
    console.log('[数据分析] 真实数据筛选：原始', realData.data.length, '条，筛选后', filteredRealData.length, '条')
  }
  
  // 添加真实数据系列
  analysisForm.real_value_columns.forEach((colName, idx) => {
    const data = filteredRealData.map(row => ({
      time: row[realTimeField],
      value: parseFloat(row[colName])
    })).filter(item => !isNaN(item.value))
    
    console.log(`[数据分析] 真实数据系列 '${colName}': ${data.length} 条数据, timeField='${realTimeField}', 示例:`, data.slice(0, 2))
    
    series.push({
      name: `真实-${colName}`,
      type: 'line',
      data: data.map(item => [item.time, item.value]),
      smooth: true,
      lineStyle: { width: 2 },
      itemStyle: { color: colorPalette[colorIndex] },
      symbol: 'circle',
      symbolSize: 4
    })
    colorIndex++
  })
  
  // 筛选预测数据（根据时间范围）
  let filteredPredictData = predictData?.data || []
  if (predictData && analysisForm.predict_time_range && analysisForm.predict_time_range.length === 2) {
    const [startTime, endTime] = analysisForm.predict_time_range
    filteredPredictData = predictData.data.filter(row => {
      const time = row[analysisForm.predict_time_column]
      const normalizedTime = normalizeTime(time)
      return normalizedTime >= startTime && normalizedTime <= endTime
    })
    
    console.log('[数据分析] 预测数据筛选：原始', predictData.data.length, '条，筛选后', filteredPredictData.length, '条')
  }
  
  // 添加预测数据系列
  if (predictData) {
    analysisForm.predict_value_columns.forEach((colName, idx) => {
      const data = filteredPredictData.map(row => ({
        time: row[analysisForm.predict_time_column],
        value: parseFloat(row[colName])
      })).filter(item => !isNaN(item.value))
      
      console.log(`[数据分析] 预测数据系列 '${colName}': ${data.length} 条数据, 示例:`, data.slice(0, 2))
      
      // 判断是否为分位数列（包含小数点）
      const isQuantile = colName.includes('.')
      
      series.push({
        name: `预测-${colName}`,
        type: 'line',
        data: data.map(item => [item.time, item.value]),
        smooth: true,
        lineStyle: { 
          width: isQuantile ? 1 : 2,
          type: isQuantile ? 'dashed' : 'solid'
        },
        itemStyle: { color: colorPalette[colorIndex % colorPalette.length] },
        symbol: 'circle',
        symbolSize: isQuantile ? 3 : 4
      })
      colorIndex++
    })
  }
  
  const option = {
    title: {
      text: '数据对比分析',
      left: 'center',
      textStyle: { fontSize: 18, fontWeight: 'bold', color: '#eaf3ff' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: { backgroundColor: '#1b3a6b' }
      },
      backgroundColor: 'rgba(10, 25, 54, 0.94)',
      borderColor: 'rgba(52, 225, 255, 0.4)',
      textStyle: { color: '#dbe7ff' },
      formatter: function(params) {
        let result = `<strong>${params[0]?.value[0]}</strong><br/>`
        params.forEach(param => {
          result += `${param.marker} ${param.seriesName}: ${param.value[1]?.toFixed(2) || '-'}<br/>`
        })
        return result
      }
    },
    legend: {
      data: series.map(s => s.name),
      top: 40,
      type: 'scroll',
      textStyle: { color: '#aebdda' },
      pageTextStyle: { color: '#aebdda' },
      inactiveColor: '#4a5d80'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: series[0]?.data.map(item => item[0]) || [],
      axisLine: { lineStyle: { color: 'rgba(56, 132, 235, 0.4)' } },
      axisLabel: {
        color: '#8aa0c8',
        rotate: 45,
        formatter: function(value) {
          // 简化时间显示
          if (value && value.includes(' ')) {
            return value.split(' ')[1] || value
          }
          return value
        }
      }
    },
    yAxis: {
      type: 'value',
      name: '数值',
      nameTextStyle: { color: '#8aa0c8' },
      axisLabel: { color: '#8aa0c8' },
      axisLine: { lineStyle: { color: 'rgba(56, 132, 235, 0.4)' } },
      splitLine: { lineStyle: { type: 'dashed', color: 'rgba(56, 132, 235, 0.14)' } }
    },
    series: series,
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100
      },
      {
        start: 0,
        end: 100,
        bottom: 10
      }
    ]
  }
  
  chart.setOption(option)
}

// 加载准确率指标
const loadMetrics = async () => {
  if (!predictFile.value || !analysisForm.predict_time_column || analysisForm.predict_value_columns.length === 0) {
    metrics.value = []
    return
  }
  
  metricsLoading.value = true
  try {
    const request = {
      real_file_id: realFile.value.file_id,
      real_file_name: realFile.value.file_name,
      real_file_type: realFile.value.file_type,
      real_time_column: analysisForm.real_time_column,
      real_time_column_2: analysisForm.real_time_column_2 || '',
      real_time_range: analysisForm.real_time_range || null,
      real_value_columns: analysisForm.real_value_columns,
      predict_file_id: predictFile.value.file_id,
      predict_file_name: predictFile.value.file_name,
      predict_file_type: predictFile.value.file_type,
      predict_time_column: analysisForm.predict_time_column,
      predict_time_range: analysisForm.predict_time_range || null,
      predict_value_columns: analysisForm.predict_value_columns
    }
    const result = await analysisAPI.calculateMetrics(request)
    metrics.value = result.metrics || []
  } catch (error) {
    console.error('计算指标失败:', error)
    ElMessage.warning('指标计算失败，但图表仍可正常查看')
    metrics.value = []
  } finally {
    metricsLoading.value = false
  }
}

// 重置分析
const resetAnalysis = () => {
  currentStep.value = 0
  realFile.value = null
  predictFile.value = null
  realHeaders.value = []
  predictHeaders.value = []
  realTimeValues.value = []
  predictTimeValues.value = []
  realValueColumns.value = []
  predictValueColumns.value = []
  realRawData.value = []
  predictRawData.value = []
  realTimeColumns.value = []
  hasRealDateTimeColumns.value = false
  realTimeRangeMin.value = ''
  realTimeRangeMax.value = ''
  predictTimeRangeMin.value = ''
  predictTimeRangeMax.value = ''
  metrics.value = []
  metricsLoading.value = false
  analysisForm.real_time_column = ''
  analysisForm.real_time_column_2 = ''
  analysisForm.real_time_range = null
  analysisForm.real_value_columns = []
  analysisForm.predict_time_column = ''
  analysisForm.predict_time_range = null
  analysisForm.predict_value_columns = []
  loadAvailableFiles()
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i]
}

// 禁用真实数据日期范围外的日期
const disableRealDate = (time) => {
  if (!realTimeRangeMin.value || !realTimeRangeMax.value) return false
  
  // 使用本地时间格式化，避免时区问题
  const y = time.getFullYear()
  const m = String(time.getMonth() + 1).padStart(2, '0')
  const d = String(time.getDate()).padStart(2, '0')
  const timeStr = `${y}-${m}-${d}`
  
  const minDate = realTimeRangeMin.value.substring(0, 10)
  const maxDate = realTimeRangeMax.value.substring(0, 10)
  return timeStr < minDate || timeStr > maxDate
}

// 禁用预测数据日期范围外的日期
const disablePredictDate = (time) => {
  if (!predictTimeRangeMin.value || !predictTimeRangeMax.value) return false
  
  const y = time.getFullYear()
  const m = String(time.getMonth() + 1).padStart(2, '0')
  const d = String(time.getDate()).padStart(2, '0')
  const timeStr = `${y}-${m}-${d}`
  
  const minDate = predictTimeRangeMin.value.substring(0, 10)
  const maxDate = predictTimeRangeMax.value.substring(0, 10)
  return timeStr < minDate || timeStr > maxDate
}

// 窗口大小变化时重新调整图表
const handleResize = () => {
  if (chart) {
    chart.resize()
  }
}

onMounted(() => {
  loadAvailableFiles()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chart) {
    chart.dispose()
  }
})
</script>

<style scoped>
.analysis-view {
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

.chart-container {
  margin-top: 20px;
  padding: 20px;
  background: linear-gradient(160deg, rgba(16, 38, 78, 0.7), rgba(11, 26, 56, 0.78));
  border: 1px solid rgba(56, 132, 235, 0.24);
  border-radius: 10px;
  box-shadow: 0 0 22px rgba(20, 80, 180, 0.25);
}

.metrics-container {
  margin-top: 20px;
  padding: 20px;
  background: linear-gradient(160deg, rgba(16, 38, 78, 0.7), rgba(11, 26, 56, 0.78));
  border: 1px solid rgba(56, 132, 235, 0.24);
  border-radius: 10px;
  box-shadow: 0 0 22px rgba(20, 80, 180, 0.25);
}

.metrics-legend {
  margin-top: 12px;
  display: flex;
  gap: 24px;
  font-size: 12px;
  color: #8aa0c8;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
