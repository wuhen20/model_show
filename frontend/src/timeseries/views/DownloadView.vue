<template>
  <div class="download-view">
    <StatStrip :items="stats" />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>文件下载</span>
          <el-button type="primary" @click="refreshCurrentTab">
            刷新列表
          </el-button>
        </div>
      </template>
      
      <el-tabs v-model="activeTab" @tab-click="handleTabClick">
        <!-- 预处理文件下载 -->
        <el-tab-pane label="预处理文件下载" name="processed">
          <div v-if="processedFiles.length === 0" class="empty-state">
            <el-empty description="暂无预处理文件" />
          </div>
          
          <div v-else>
            <el-table :data="processedFiles" border style="width: 100%">
              <el-table-column prop="new_name" label="文件名" />
              <el-table-column prop="file_size" label="文件大小" width="120">
                <template #default="scope">
                  {{ formatFileSize(scope.row.file_size) }}
                </template>
              </el-table-column>
              <el-table-column prop="processed_time" label="处理时间" width="180">
                <template #default="scope">
                  {{ formatDate(scope.row.processed_time) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200">
                <template #default="scope">
                  <el-button type="primary" size="small" @click="handleDownloadProcessed(scope.row)">
                    下载
                  </el-button>
                  <el-button type="danger" size="small" @click="handleDeleteProcessed(scope.row)">
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
        
        <!-- 整合文件下载 -->
        <el-tab-pane label="整合文件下载" name="merged">
          <div v-if="mergedFiles.length === 0" class="empty-state">
            <el-empty description="暂无整合文件" />
          </div>
          
          <div v-else>
            <el-table :data="mergedFiles" border style="width: 100%">
              <el-table-column prop="merged_name" label="文件名" />
              <el-table-column prop="main_table_name" label="主表" width="200" />
              <el-table-column prop="file_size" label="文件大小" width="120">
                <template #default="scope">
                  {{ formatFileSize(scope.row.file_size) }}
                </template>
              </el-table-column>
              <el-table-column prop="merge_time" label="整合时间" width="180">
                <template #default="scope">
                  {{ formatDate(scope.row.merge_time) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200">
                <template #default="scope">
                  <el-button type="primary" size="small" @click="handleDownloadMerged(scope.row)">
                    下载
                  </el-button>
                  <el-button type="danger" size="small" @click="handleDeleteMerged(scope.row)">
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
        
        <!-- 预测文件下载 -->
        <el-tab-pane label="预测文件下载" name="predicted">
          <div v-if="predictedFiles.length === 0" class="empty-state">
            <el-empty description="暂无预测文件" />
          </div>
          
          <div v-else>
            <el-table :data="predictedFiles" border style="width: 100%">
              <el-table-column prop="predict_name" label="文件名" />
              <el-table-column prop="source_file" label="源文件" width="200" />
              <el-table-column prop="file_size" label="文件大小" width="120">
                <template #default="scope">
                  {{ formatFileSize(scope.row.file_size) }}
                </template>
              </el-table-column>
              <el-table-column label="预测时间" width="180">
                <template #default="scope">
                  {{ formatPredictTime(scope.row.predict_time) }}
                </template>
              </el-table-column>
              <el-table-column label="处理时间" width="180">
                <template #default="scope">
                  {{ formatDate(scope.row.generate_time) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200">
                <template #default="scope">
                  <el-button type="primary" size="small" @click="handleDownloadPredicted(scope.row)">
                    下载
                  </el-button>
                  <el-button type="danger" size="small" @click="handleDeletePredicted(scope.row)">
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StatStrip from '@/timeseries/components/StatStrip.vue'
import { downloadAPI, predictAPI } from '@/timeseries/api'

const activeTab = ref('processed')
const processedFiles = ref([])
const mergedFiles = ref([])
const predictedFiles = ref([])

const stats = computed(() => {
  const all = [...processedFiles.value, ...mergedFiles.value, ...predictedFiles.value]
  const totalSize = all.reduce((s, f) => s + (f.file_size || 0), 0)
  return [
    { label: '预处理文件', value: processedFiles.value.length, icon: 'Document', color: '#00d4ff' },
    { label: '整合文件', value: mergedFiles.value.length, icon: 'Connection', color: '#7c5cff' },
    { label: '预测文件', value: predictedFiles.value.length, icon: 'TrendCharts', color: '#2fd6a0' },
    { label: '总大小', value: formatFileSize(totalSize), icon: 'Coin', color: '#ffb454' }
  ]
})

onMounted(() => {
  loadProcessedFiles()
  loadMergedFiles()
  loadPredictedFiles()
})

const loadProcessedFiles = async () => {
  try {
    const response = await downloadAPI.getProcessedFiles()
    processedFiles.value = response.files || []
  } catch (error) {
    console.error('加载预处理文件列表失败:', error)
  }
}

const loadMergedFiles = async () => {
  try {
    const response = await downloadAPI.getMergedFiles()
    mergedFiles.value = response.files || []
  } catch (error) {
    console.error('加载整合文件列表失败:', error)
  }
}

const loadPredictedFiles = async () => {
  try {
    const response = await predictAPI.getList()
    predictedFiles.value = response.files || []
  } catch (error) {
    console.error('加载预测文件列表失败:', error)
  }
}

const handleTabClick = (tab) => {
  // 可以在这里添加tab切换时的逻辑
  console.log('切换到:', tab.props.name)
}

const refreshCurrentTab = () => {
  if (activeTab.value === 'processed') {
    loadProcessedFiles()
    ElMessage.success('预处理文件列表已刷新')
  } else if (activeTab.value === 'merged') {
    loadMergedFiles()
    ElMessage.success('整合文件列表已刷新')
  } else if (activeTab.value === 'predicted') {
    loadPredictedFiles()
    ElMessage.success('预测文件列表已刷新')
  }
}

const handleDownloadProcessed = (file) => {
  const downloadUrl = downloadAPI.downloadProcessed(file.file_id)
  window.open(downloadUrl, '_blank')
  ElMessage.success('开始下载预处理文件')
}

const handleDownloadMerged = (file) => {
  const downloadUrl = downloadAPI.downloadMerged(file.file_id)
  window.open(downloadUrl, '_blank')
  ElMessage.success('开始下载整合文件')
}

const handleDeleteProcessed = async (file) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除预处理文件 "${file.new_name}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await downloadAPI.deleteProcessedFile(file.new_name)
    ElMessage.success('预处理文件删除成功')
    loadProcessedFiles()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除预处理文件失败:', error)
    }
  }
}

const handleDeleteMerged = async (file) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除整合文件 "${file.merged_name}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await downloadAPI.deleteMergedFile(file.merged_name)
    ElMessage.success('整合文件删除成功')
    loadMergedFiles()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除整合文件失败:', error)
    }
  }
}

const handleDownloadPredicted = (file) => {
  const downloadUrl = predictAPI.download(file.file_id)
  window.open(downloadUrl, '_blank')
  ElMessage.success('开始下载预测文件')
}

const handleDeletePredicted = async (file) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除预测文件 "${file.predict_name}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await predictAPI.delete(file.predict_name)
    ElMessage.success('预测文件删除成功')
    loadPredictedFiles()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除预测文件失败:', error)
    }
  }
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i]
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const formatTimestamp = (timestamp) => {
  if (!timestamp) return '-'
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN')
}

// 格式化预测时间（支持字符串格式的时间）
const formatPredictTime = (timeStr) => {
  if (!timeStr) return '-'
  // 如果已经是字符串格式（YYYY-MM-DD HH:mm:ss），直接返回或格式化
  if (typeof timeStr === 'string') {
    return timeStr
  }
  // 如果是时间戳，转换为日期字符串
  const date = new Date(timeStr * 1000)
  return date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.download-view {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

.empty-state {
  padding: 40px 0;
}
</style>
