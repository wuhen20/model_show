<template>
  <div class="upload-view">
    <StatStrip :items="stats" />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>CSV文件上传</span>
        </div>
      </template>
      
      <FileUploader @upload-success="handleUploadSuccess" />
      
      <el-divider />
      
      <div v-if="uploadedFiles.length > 0">
        <h3>已上传文件</h3>
        <el-table :data="uploadedFiles" style="width: 100%">
          <el-table-column prop="original_name" label="文件名" />
          <el-table-column label="文件类型" width="100">
            <template #default="scope">
              <el-tag :type="getFileTypeTag(scope.row.original_name)">
                {{ getFileType(scope.row.original_name) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="file_size" label="文件大小" width="150">
            <template #default="scope">
              {{ formatFileSize(scope.row.file_size) }}
            </template>
          </el-table-column>
          <el-table-column prop="upload_time" label="上传时间" width="200">
            <template #default="scope">
              {{ formatDate(scope.row.upload_time) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="scope">
              <el-button size="small" @click="handlePreview(scope.row)">
                预览
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
    
    <!-- 预览对话框 -->
    <el-dialog v-model="previewVisible" title="数据预览" width="80%">
      <el-table :data="previewData.data" border style="width: 100%">
        <el-table-column
          v-for="header in previewData.headers"
          :key="header"
          :prop="header"
          :label="header"
        />
      </el-table>
      <div style="margin-top: 10px; color: #909399">
        共 {{ previewData.total_rows }} 行数据，显示前5行
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import FileUploader from '@/timeseries/components/FileUploader.vue'
import StatStrip from '@/timeseries/components/StatStrip.vue'
import { uploadAPI } from '@/timeseries/api'

const router = useRouter()
const uploadedFiles = ref([])

const stats = computed(() => {
  const files = uploadedFiles.value
  const totalSize = files.reduce((s, f) => s + (f.file_size || 0), 0)
  const csv = files.filter(f => (f.original_name || '').toLowerCase().endsWith('.csv')).length
  const excel = files.filter(f => /\.(xlsx|xls)$/i.test(f.original_name || '')).length
  return [
    { label: '文件总数', value: files.length, icon: 'Files', color: '#20a8ff' },
    { label: '总大小', value: formatFileSize(totalSize), icon: 'Coin', color: '#34e1ff' },
    { label: 'CSV 文件', value: csv, icon: 'Document', color: '#2fd6a0' },
    { label: 'Excel 文件', value: excel, icon: 'Document', color: '#ffb454' }
  ]
})
const previewVisible = ref(false)
const previewData = ref({
  headers: [],
  data: [],
  total_rows: 0
})

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
  }
}

const handleUploadSuccess = (fileInfo) => {
  ElMessage.success('文件上传成功')
  loadUploadedFiles()
}

const handlePreview = async (file) => {
  try {
    const response = await uploadAPI.previewData(file.file_id)
    previewData.value = response
    previewVisible.value = true
  } catch (error) {
    console.error('预览数据失败:', error)
    ElMessage.error('预览数据失败，请重试')
  }
}

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN')
}

const getFileType = (filename) => {
  if (!filename) return '未知'
  const ext = filename.split('.').pop().toLowerCase()
  if (ext === 'csv') return 'CSV'
  if (ext === 'xlsx' || ext === 'xls') return 'Excel'
  return ext.toUpperCase()
}

const getFileTypeTag = (filename) => {
  const ext = filename.split('.').pop().toLowerCase()
  if (ext === 'csv') return 'success'
  if (ext === 'xlsx' || ext === 'xls') return 'warning'
  return 'info'
}
</script>

<style scoped>
.upload-view {
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
  margin: 20px 0 10px;
  color: #409eff;
}
</style>
