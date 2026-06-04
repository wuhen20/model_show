<template>
  <div class="file-list">
    <el-table :data="files" style="width: 100%">
      <el-table-column prop="original_name" label="原始文件名" />
      <el-table-column prop="new_name" label="处理后文件名" />
      <el-table-column prop="file_size" label="文件大小" width="150">
        <template #default="scope">
          {{ formatFileSize(scope.row.file_size) }}
        </template>
      </el-table-column>
      <el-table-column prop="processed_time" label="处理时间" width="200">
        <template #default="scope">
          {{ formatDate(scope.row.processed_time) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="scope">
          <el-button 
            size="small" 
            type="primary" 
            @click="handleDownload(scope.row)"
          >
            下载
          </el-button>
          <el-button 
            size="small" 
            type="danger" 
            @click="handleDelete(scope.row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
defineProps({
  files: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['download', 'delete'])

const handleDownload = (file) => {
  emit('download', file)
}

const handleDelete = (file) => {
  emit('delete', file)
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.file-list {
  margin-top: 20px;
}
</style>
