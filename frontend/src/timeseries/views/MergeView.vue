<template>
  <div class="merge-view">
    <StatStrip :items="stats" />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>样本整合</span>
        </div>
      </template>

      <!-- 步骤指示器 -->
      <el-steps :active="currentStep" finish-status="success" style="margin-bottom: 30px">
        <el-step title="选择主表" />
        <el-step title="配置关联表" />
        <el-step title="执行整合" />
      </el-steps>

      <!-- 步骤1：选择主表 -->
      <div v-if="currentStep === 0" class="step-content">
        <h3>选择主表</h3>
        <p class="hint">请选择一个已处理的CSV文件作为主表</p>
        
        <el-table 
          :data="processedFiles" 
          @row-click="selectMainTable"
          highlight-current-row
          border
          style="width: 100%"
        >
          <el-table-column prop="new_name" label="文件名" />
          <el-table-column prop="file_size" label="文件大小" width="120">
            <template #default="scope">
              {{ formatFileSize(scope.row.file_size) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="scope">
              <el-button 
                type="primary" 
                size="small"
                @click.stop="selectMainTable(scope.row)"
              >
                选择为主表
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="processedFiles.length === 0" class="empty-tip">
          <el-empty description="暂无已处理文件，请先进行数据处理" />
        </div>
      </div>

      <!-- 步骤2：配置关联表 -->
      <div v-if="currentStep === 1" class="step-content">
        <h3>配置关联表</h3>
        
        <el-alert 
          v-if="mainTable" 
          :title="`主表：${mainTable.new_name}`" 
          type="success" 
          :closable="false"
          style="margin-bottom: 20px"
        />

        <!-- 关联方式选择 -->
        <div class="config-section">
          <h4>关联方式</h4>
          <el-radio-group v-model="joinType">
            <el-radio label="left">LEFT JOIN（左连接 - 保留主表所有记录）</el-radio>
            <el-radio label="inner">INNER JOIN（内连接 - 只保留匹配记录）</el-radio>
          </el-radio-group>
        </div>

        <!-- 添加关联表按钮 -->
        <div class="config-section">
          <el-button type="primary" @click="addSecondaryTable">
            <el-icon><Plus /></el-icon>
            添加关联表
          </el-button>
        </div>

        <!-- 关联表配置列表 -->
        <div v-for="(table, index) in secondaryTables" :key="index" class="table-config">
          <el-card shadow="hover">
            <template #header>
              <div class="table-config-header">
                <span>关联表 {{ index + 1 }}</span>
                <el-button type="danger" size="small" @click="removeSecondaryTable(index)">
                  删除
                </el-button>
              </div>
            </template>

            <!-- 选择关联表文件 -->
            <el-form label-width="120px">
              <el-form-item label="选择文件">
                <el-select 
                  v-model="table.file_id" 
                  placeholder="请选择关联表"
                  @change="onSecondaryTableChange(table)"
                  style="width: 100%"
                >
                  <el-option
                    v-for="file in getAvailableSecondaryFiles()"
                    :key="file.file_id"
                    :label="file.new_name"
                    :value="file.file_id"
                  />
                </el-select>
              </el-form-item>

              <!-- 主表关联字段 -->
              <el-form-item label="主表关联字段">
                <el-select 
                  v-model="table.main_join_columns" 
                  multiple
                  placeholder="请选择主表关联字段"
                  style="width: 100%"
                >
                  <el-option
                    v-for="col in mainTableHeaders"
                    :key="col"
                    :label="col"
                    :value="col"
                  />
                </el-select>
              </el-form-item>

              <!-- 次表关联字段 -->
              <el-form-item label="次表关联字段">
                <el-select 
                  v-model="table.secondary_join_columns" 
                  multiple
                  placeholder="请选择次表关联字段"
                  style="width: 100%"
                >
                  <el-option
                    v-for="col in table.headers"
                    :key="col"
                    :label="col"
                    :value="col"
                  />
                </el-select>
              </el-form-item>
            </el-form>
          </el-card>
        </div>

        <div v-if="secondaryTables.length === 0" class="empty-tip">
          <el-empty description="请添加关联表" />
        </div>
      </div>

      <!-- 步骤3：执行整合 -->
      <div v-if="currentStep === 2" class="step-content">
        <h3>执行整合</h3>
        
        <el-alert 
          title="整合配置确认" 
          type="info" 
          :closable="false"
          style="margin-bottom: 20px"
        >
          <template #default>
            <p><strong>主表：</strong>{{ mainTable?.new_name }}</p>
            <p><strong>关联表数量：</strong>{{ secondaryTables.length }}</p>
            <p><strong>关联方式：</strong>{{ joinType === 'left' ? 'LEFT JOIN' : 'INNER JOIN' }}</p>
          </template>
        </el-alert>

        <div class="action-buttons">
          <el-button @click="currentStep = 1">返回修改</el-button>
          <el-button 
            type="primary" 
            @click="executeMerge" 
            :loading="merging"
            :disabled="!canExecute"
          >
            开始整合
          </el-button>
        </div>

        <!-- 进度显示 -->
        <div v-if="merging" class="progress-section">
          <el-progress :percentage="progress" :status="progressStatus" />
          <p class="progress-text">{{ progressText }}</p>
        </div>

        <!-- 整合结果 -->
        <div v-if="mergeResult" class="result-section">
          <el-alert 
            :title="mergeResult.message" 
            type="success" 
            :closable="false"
          />
        </div>
      </div>

      <!-- 底部操作按钮 -->
      <div class="footer-actions">
        <el-button v-if="currentStep > 0" @click="currentStep--">上一步</el-button>
        <el-button 
          v-if="currentStep < 2" 
          type="primary" 
          @click="nextStep"
          :disabled="!canProceed"
        >
          下一步
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import StatStrip from '@/timeseries/components/StatStrip.vue'
import { mergeAPI } from '@/timeseries/api'

const currentStep = ref(0)
const processedFiles = ref([])
const mainTable = ref(null)
const mainTableHeaders = ref([])
const secondaryTables = ref([])
const joinType = ref('left')

const stats = computed(() => [
  { label: '可整合文件', value: processedFiles.value.length, icon: 'FolderOpened', color: '#20a8ff' },
  { label: '已选主表', value: mainTable.value ? 1 : 0, icon: 'CircleCheck', color: '#34e1ff' },
  { label: '关联表数', value: secondaryTables.value.length, icon: 'Connection', color: '#7c5cff' },
  { label: '关联方式', value: joinType.value === 'left' ? 'LEFT' : 'INNER', icon: 'Setting', color: '#2fd6a0' }
])
const merging = ref(false)
const progress = ref(0)
const progressStatus = ref('')
const progressText = ref('')
const mergeResult = ref(null)

// 是否可以继续下一步
const canProceed = computed(() => {
  if (currentStep.value === 0) {
    return mainTable.value !== null
  }
  if (currentStep.value === 1) {
    return secondaryTables.value.length > 0 && secondaryTables.value.every(t => 
      t.file_id && t.main_join_columns.length > 0 && t.secondary_join_columns.length > 0
    )
  }
  return true
})

// 是否可以执行整合
const canExecute = computed(() => {
  return mainTable.value && 
         secondaryTables.value.length > 0 && 
         secondaryTables.value.every(t => 
           t.file_id && t.main_join_columns.length > 0 && t.secondary_join_columns.length > 0
         )
})

// 加载已处理文件列表
const loadProcessedFiles = async () => {
  try {
    const response = await mergeAPI.getAvailableFiles()
    processedFiles.value = response.files || []
  } catch (error) {
    ElMessage.error('加载文件列表失败')
  }
}

// 选择主表
const selectMainTable = async (row) => {
  mainTable.value = row
  ElMessage.success(`已选择主表：${row.new_name}`)
  
  // 加载主表表头
  try {
    const headersResponse = await mergeAPI.getHeaders(row.file_id)
    mainTableHeaders.value = headersResponse.headers || []
  } catch (error) {
    ElMessage.error('加载主表表头失败')
  }
}

// 获取可用的次表（排除已选主表）
const getAvailableSecondaryFiles = () => {
  return processedFiles.value.filter(f => f.file_id !== mainTable.value?.file_id)
}

// 添加关联表
const addSecondaryTable = () => {
  secondaryTables.value.push({
    file_id: '',
    file_name: '',
    headers: [],
    main_join_columns: [],
    secondary_join_columns: []
  })
}

// 删除关联表
const removeSecondaryTable = (index) => {
  secondaryTables.value.splice(index, 1)
}

// 次表选择变化
const onSecondaryTableChange = async (table) => {
  const selectedFile = processedFiles.value.find(f => f.file_id === table.file_id)
  if (selectedFile) {
    table.file_name = selectedFile.new_name
    
    // 加载次表表头
    try {
      const headersResponse = await mergeAPI.getHeaders(table.file_id)
      table.headers = headersResponse.headers || []
    } catch (error) {
      ElMessage.error('加载次表表头失败')
    }
  }
}

// 下一步
const nextStep = () => {
  if (canProceed.value) {
    currentStep.value++
  }
}

// 执行整合
const executeMerge = async () => {
  if (!canExecute.value) {
    ElMessage.warning('请完成所有配置')
    return
  }

  merging.value = true
  progress.value = 0
  progressText.value = '准备整合...'
  mergeResult.value = null

  try {
    progress.value = 20
    progressText.value = '读取数据...'

    // 构建请求数据
    const mergeRequest = {
      main_table: {
        file_id: mainTable.value.file_id,
        file_name: mainTable.value.new_name,
        role: 'main',
        join_columns: [],
        main_join_columns: [],
        secondary_join_columns: []
      },
      secondary_tables: secondaryTables.value.map(t => ({
        file_id: t.file_id,
        file_name: t.file_name,
        role: 'secondary',
        join_columns: [],
        main_join_columns: t.main_join_columns,
        secondary_join_columns: t.secondary_join_columns
      })),
      join_type: joinType.value
    }

    progress.value = 50
    progressText.value = '执行关联...'

    // 发送请求
    const response = await mergeAPI.execute(mergeRequest)

    progress.value = 100
    progressStatus.value = 'success'
    progressText.value = '整合完成！'
    
    mergeResult.value = response
    ElMessage.success('样本整合完成')

    // 3秒后自动跳转到下载页面
    setTimeout(() => {
      window.location.href = '/download'
    }, 3000)

  } catch (error) {
    progressStatus.value = 'exception'
    progressText.value = '整合失败'
    ElMessage.error('样本整合失败：' + (error.message || '未知错误'))
  } finally {
    merging.value = false
  }
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i]
}

onMounted(() => {
  loadProcessedFiles()
})
</script>

<style scoped>
.merge-view {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.step-content {
  min-height: 400px;
}

.hint {
  color: #909399;
  margin-bottom: 20px;
}

.config-section {
  margin-bottom: 20px;
}

.table-config {
  margin-bottom: 20px;
}

.table-config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-tip {
  padding: 40px 0;
}

.action-buttons {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.progress-section {
  margin-top: 20px;
}

.progress-text {
  text-align: center;
  color: #606266;
  margin-top: 10px;
}

.result-section {
  margin-top: 20px;
}

.footer-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid rgba(56, 132, 235, 0.2);
}

.hint { color: #8aa0c8; }
h3 { color: #34e1ff; }
h4 { color: #aebdda; }
</style>
