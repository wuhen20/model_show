<template>
  <div class="process-view">
    <StatStrip :items="stats" />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据处理配置</span>
        </div>
      </template>
      
      <el-steps :active="currentStep" finish-status="success" style="margin-bottom: 30px">
        <el-step title="选择文件" />
        <el-step title="配置规则" />
        <el-step title="执行处理" />
      </el-steps>
      
      <!-- 步骤1: 选择文件 -->
      <div v-if="currentStep === 0">
        <h3>选择要处理的文件</h3>
        <el-alert
          title="提示"
          type="info"
          :closable="false"
          style="margin-bottom: 15px"
        >
          可以选择多个文件进行批量处理，所有文件将使用相同的处理规则。支持CSV、XLSX、XLS格式，处理后统一输出为CSV格式
        </el-alert>
        <el-table
          :data="uploadedFiles"
          style="width: 100%"
          max-height="360"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column prop="original_name" label="文件名" />
          <el-table-column prop="status" label="状态" width="120">
            <template #default="scope">
              <el-tag :type="getStatusType(scope.row.status)">
                {{ scope.row.status }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top: 15px">
          <el-button 
            type="primary" 
            @click="currentStep = 1" 
            :disabled="selectedFiles.length === 0"
          >
            下一步 (已选择 {{ selectedFiles.length }} 个文件)
          </el-button>
          <el-button 
            type="success" 
            @click="batchProcess" 
            :disabled="selectedFiles.length <= 1 || !hasAllConfigured"
          >
            批量处理
          </el-button>
        </div>
      </div>
      
      <!-- 步骤2: 配置规则 -->
      <div v-if="currentStep === 1">
        <h3>配置处理规则</h3>
        <el-alert
          v-if="selectedFiles.length > 1"
          :title="`将为 ${selectedFiles.length} 个文件应用相同的处理规则`"
          type="warning"
          :closable="false"
          style="margin-bottom: 15px"
        />
        <ColumnMapper 
          v-if="selectedFiles.length > 0"
          :file-id="selectedFiles[0].file_id"
          @config-ready="handleConfigReady"
        />
      </div>
      
      <!-- 步骤3: 执行处理 -->
      <div v-if="currentStep === 2">
        <h3>执行数据处理</h3>
        <div v-if="processing" class="processing-status">
          <el-progress :percentage="progress" :status="progressStatus" />
          <p>{{ statusMessage }}</p>
        </div>
        <el-button 
          type="primary" 
          @click="executeProcess" 
          :loading="processing"
          :disabled="!processConfig"
        >
          开始处理
        </el-button>
        <el-button @click="resetProcess">重置</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import ColumnMapper from '@/timeseries/components/ColumnMapper.vue'
import StatStrip from '@/timeseries/components/StatStrip.vue'
import { uploadAPI, processAPI } from '@/timeseries/api'

const currentStep = ref(0)
const uploadedFiles = ref([])
const selectedFiles = ref([])

const stats = computed(() => {
  const files = uploadedFiles.value
  return [
    { label: '待处理文件', value: files.length, icon: 'Files', color: '#00d4ff' },
    { label: '已配置', value: files.filter(f => f.status === 'configured').length, icon: 'Setting', color: '#5ee7ff' },
    { label: '已完成', value: files.filter(f => f.status === 'completed').length, icon: 'CircleCheck', color: '#2fd6a0' },
    { label: '已选择', value: selectedFiles.value.length, icon: 'Document', color: '#ffb454' }
  ]
})
const processConfig = ref(null)
const processing = ref(false)
const progress = ref(0)
const progressStatus = ref('')
const statusMessage = ref('')

onMounted(() => {
  loadUploadedFiles()
})

const loadUploadedFiles = async () => {
  try {
    const response = await uploadAPI.getUploadList()
    uploadedFiles.value = response.files || []
  } catch (error) {
    console.error('加载文件列表失败:', error)
    uploadedFiles.value = []
    ElMessage.error('加载文件列表失败')
  }
}

const handleSelectionChange = (selection) => {
  selectedFiles.value = selection
}

const handleConfigReady = (config) => {
  processConfig.value = config
  currentStep.value = 2
}

const executeProcess = async () => {
  if (selectedFiles.value.length === 0 || !processConfig.value) {
    ElMessage.warning('请先配置处理规则')
    return
  }
  
  processing.value = true
  progress.value = 0
  statusMessage.value = '正在保存配置...'
  
  try {
    // 为所有选中的文件保存配置
    const configPromises = selectedFiles.value.map(file => {
      const config = {
        ...processConfig.value,
        file_id: file.file_id
      }
      return processAPI.configure(config)
    })
    await Promise.all(configPromises)
    
    progress.value = 30
    statusMessage.value = `配置保存成功，开始处理 ${selectedFiles.value.length} 个文件...`
    
    // 执行处理
    await processAPI.execute(selectedFiles.value[0].file_id)
    progress.value = 100
    progressStatus.value = 'success'
    statusMessage.value = '数据处理完成！'
    
    ElMessage.success('数据处理完成')
  } catch (error) {
    progressStatus.value = 'exception'
    statusMessage.value = '处理失败: ' + (error.response?.data?.detail || error.message)
    ElMessage.error('数据处理失败')
  } finally {
    processing.value = false
  }
}

const resetProcess = () => {
  currentStep.value = 0
  selectedFiles.value = []
  processConfig.value = null
  progress.value = 0
  progressStatus.value = ''
  statusMessage.value = ''
}

const hasAllConfigured = computed(() => {
  return selectedFiles.value.length > 1 && 
         selectedFiles.value.every(f => f.status === 'configured' || f.status === 'completed')
})

const batchProcess = async () => {
  if (selectedFiles.value.length <= 1) {
    ElMessage.warning('请选择至少2个文件进行批量处理')
    return
  }
  
  processing.value = true
  progress.value = 0
  statusMessage.value = `开始批量处理 ${selectedFiles.value.length} 个文件...`
  
  try {
    const fileIds = selectedFiles.value.map(f => f.file_id)
    const response = await processAPI.batchExecute(fileIds)
    
    progress.value = 100
    progressStatus.value = 'success'
    statusMessage.value = `批量处理完成！成功: ${response.success_count}, 失败: ${response.failed_count}`
    
    ElMessage.success(`批量处理完成！成功 ${response.success_count} 个，失败 ${response.failed_count} 个`)
    
    // 刷新文件列表
    await loadUploadedFiles()
  } catch (error) {
    progressStatus.value = 'exception'
    statusMessage.value = '批量处理失败: ' + (error.response?.data?.detail || error.message)
    ElMessage.error('批量处理失败')
  } finally {
    processing.value = false
  }
}

const getStatusType = (status) => {
  const types = {
    uploaded: 'info',
    configured: 'warning',
    processing: '',
    completed: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}
</script>

<style scoped>
.process-view {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

h3 {
  margin: 20px 0 15px;
  color: #5ee7ff;
}

.processing-status {
  margin: 20px 0;
  padding: 20px;
  background: rgba(20, 48, 96, 0.4);
  border: 1px solid rgba(56, 132, 235, 0.2);
  border-radius: 8px;
}

.processing-status p {
  margin-top: 10px;
  color: #aebdda;
}
</style>
