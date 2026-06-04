import axios from 'axios'
import { ElMessage } from 'element-plus'

// 创建axios实例
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    return config
  },
  error => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    const message = error.response?.data?.detail || '请求失败'
    ElMessage.error(message)
    console.error('响应错误:', error)
    return Promise.reject(error)
  }
)

// 上传相关API
export const uploadAPI = {
  // 上传文件
  uploadFile(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/upload/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  
  // 获取文件表头
  getHeaders(fileId) {
    return api.post(`/upload/${fileId}/headers`)
  },
  
  // 预览文件数据
  previewData(fileId) {
    return api.post(`/upload/${fileId}/preview`)
  },
  
  // 获取上传文件列表
  getUploadList() {
    return api.get('/upload/list')
  }
}

// 处理相关API
export const processAPI = {
  // 配置处理规则
  configure(config) {
    return api.post('/process/configure', config)
  },
  
  // 执行处理
  execute(fileId) {
    return api.post(`/process/${fileId}/execute`)
  },
  
  // 批量处理
  batchExecute(fileIds) {
    return api.post('/process/batch-execute', { file_ids: fileIds })
  },
  
  // 获取处理状态
  getStatus(fileId) {
    return api.get(`/process/${fileId}/status`)
  }
}

// 下载相关API
export const downloadAPI = {
  // 获取预处理文件列表
  getProcessedFiles() {
    return api.get('/download/processed')
  },
  
  // 获取整合文件列表
  getMergedFiles() {
    return api.get('/download/merged')
  },
  
  // 下载预处理文件
  downloadProcessed(fileId) {
    return `/api/download/download/${fileId}`
  },
  
  // 下载整合文件
  downloadMerged(fileId) {
    return `/api/merge/download/${fileId}`
  },
  
  // 删除预处理文件
  deleteProcessedFile(fileName) {
    return api.delete(`/download/processed/${fileName}`)
  },
  
  // 删除整合文件
  deleteMergedFile(fileName) {
    return api.delete(`/download/merged/${fileName}`)
  },
  
  // 删除文件（兼容旧接口）
  deleteFile(fileId) {
    return api.delete(`/files/${fileId}`)
  }
}

// 样本整合相关API
export const mergeAPI = {
  // 获取可用文件列表（已处理文件）
  getAvailableFiles() {
    return api.get('/merge/available-files')
  },
  
  // 获取文件表头
  getHeaders(fileId) {
    return api.post(`/merge/${fileId}/headers`)
  },
  
  // 执行整合
  execute(mergeRequest) {
    return api.post('/merge/execute', mergeRequest)
  },
  
  // 获取整合文件列表
  getMergedList() {
    return api.get('/merge/list')
  },
  
  // 下载整合文件
  downloadMerged(fileId) {
    return `/api/merge/download/${fileId}`
  }
}

// 数据预测相关API
export const predictAPI = {
  // 获取可用文件列表（已处理和已整合文件）
  getAvailableFiles() {
    return api.get('/predict/available-files')
  },

  // 获取本机可选模型列表（扫描模型根目录；可传 root 指定目录）
  getModels(root) {
    return api.get('/predict/models', { params: root ? { root } : {} })
  },

  // 浏览本机文件系统目录（用于选择模型目录；path 为空时返回盘符/根）
  browseModels(path) {
    return api.post('/predict/models/browse', { path: path || '' })
  },
  
  // 获取文件表头
  getHeaders(fileType, fileName) {
    return api.post(`/predict/${fileType}/${fileName}/headers`)
  },
  
  // 执行预测
  execute(predictRequest) {
    return api.post('/predict/execute', predictRequest, {
      timeout: 600000
    })
  },
  
  // 获取预测文件列表
  getList() {
    return api.get('/predict/list')
  },
  
  // 下载预测文件
  download(fileId) {
    return `/api/predict/download/${fileId}`
  },
  
  // 删除预测文件
  delete(fileName) {
    return api.delete(`/predict/${fileName}`)
  }
}

// 数据分析相关API
export const analysisAPI = {
  // 获取可用文件列表（已上传、已处理、已整合、已预测）
  getAvailableFiles() {
    return api.get('/analysis/available-files')
  },
  
  // 获取文件表头
  getHeaders(fileType, fileId) {
    return api.post(`/analysis/${fileType}/${fileId}/headers`)
  },
  
  // 获取文件数据
  getData(request) {
    return api.post('/analysis/get-data', request)
  },
  
  // 计算准确率指标(R2, MAPE)
  calculateMetrics(request) {
    return api.post('/analysis/calculate-metrics', request, {
      timeout: 60000
    })
  }
}

export default api
