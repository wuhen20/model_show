<template>
  <div class="file-uploader">
    <el-upload
      drag
      :auto-upload="false"
      :on-change="handleFileChange"
      :before-upload="beforeUpload"
      multiple
      accept=".csv,.xlsx,.xls"
    >
      <el-icon class="el-icon--upload">
        <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
          <path fill="currentColor" d="M512 692.8L326.4 507.2l45.2-45.2L480 570.4V256h64v314.4L652.4 462l45.2 45.2L512 692.8zM224 768h576v64H224z"/>
        </svg>
      </el-icon>
      <div class="el-upload__text">
        拖拽文件到此处或<em>点击上传</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">
          支持CSV、XLSX、XLS格式文件，支持多文件上传。处理后统一输出为CSV格式
        </div>
      </template>
    </el-upload>
    
    <div v-if="fileList.length > 0" class="file-list">
      <h4>待上传文件列表</h4>
      <el-button type="primary" @click="uploadFiles" :loading="uploading">
        开始上传
      </el-button>
      <ul>
        <li v-for="(file, index) in fileList" :key="index">
          {{ file.name }} ({{ formatFileSize(file.size) }})
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadAPI } from '@/timeseries/api'

const emit = defineEmits(['upload-success'])

const fileList = ref([])
const uploading = ref(false)

const handleFileChange = (file) => {
  // 添加到文件列表
  if (!fileList.value.find(f => f.name === file.name)) {
    fileList.value.push(file.raw)
  }
}

const beforeUpload = (file) => {
  const isSupported = file.name.endsWith('.csv') || file.name.endsWith('.xlsx') || file.name.endsWith('.xls')
  if (!isSupported) {
    ElMessage.error('只支持CSV、XLSX、XLS格式的文件!')
  }
  return isSupported
}

const uploadFiles = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  
  uploading.value = true
  
  try {
    const uploadPromises = fileList.value.map(file => uploadAPI.uploadFile(file))
    const results = await Promise.all(uploadPromises)
    
    ElMessage.success(`成功上传 ${results.length} 个文件`)
    fileList.value = []
    
    // 通知父组件上传成功
    emit('upload-success', results)
  } catch (error) {
    console.error('上传失败:', error)
  } finally {
    uploading.value = false
  }
}

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}
</script>

<style scoped>
.file-uploader {
  padding: 20px;
}

.file-list {
  margin-top: 20px;
  padding: 15px;
  background: rgba(20, 48, 96, 0.4);
  border: 1px solid rgba(56, 132, 235, 0.2);
  border-radius: 8px;
}

.file-list h4 {
  margin: 0 0 10px 0;
  color: #34e1ff;
}

.file-list ul {
  list-style: none;
  padding: 0;
  margin: 10px 0 0 0;
}

.file-list li {
  padding: 8px 10px;
  background: rgba(12, 31, 64, 0.6);
  border: 1px solid rgba(56, 132, 235, 0.16);
  margin-bottom: 5px;
  border-radius: 6px;
  color: #c2d2ef;
}

.el-button {
  margin-bottom: 10px;
}
</style>
