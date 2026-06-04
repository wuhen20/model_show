<template>
  <div class="column-mapper">
    <el-form :model="form" label-width="120px">
      <el-form-item label="时间类型">
        <el-select v-model="form.timeType" @change="handleTimeTypeChange">
          <el-option label="日期类型 (YYYY-MM-DD)" value="date" />
          <el-option label="小时类型 (X0000, T0100, P0200等)" value="hour" />
          <el-option label="日期时间类型 (YYYY-MM-DD HH:MM:SS)" value="datetime" />
        </el-select>
      </el-form-item>
      
      <!-- 日期类型配置 -->
      <el-form-item v-if="form.timeType === 'date'" label="日期列">
        <el-select v-model="form.timeColumn" filterable>
          <el-option
            v-for="header in headers"
            :key="header"
            :label="header"
            :value="header"
          />
        </el-select>
      </el-form-item>
      
      <!-- 小时类型配置 -->
      <el-form-item v-if="form.timeType === 'hour'" label="小时列">
        <el-select v-model="form.hourColumns" multiple filterable>
          <el-option
            v-for="header in suggestedHourColumns"
            :key="header"
            :label="header"
            :value="header"
          />
        </el-select>
        <div class="tip">系统已自动识别可能的小时列，您也可以手动选择</div>
      </el-form-item>
      
      <!-- 日期时间类型配置 -->
      <el-form-item v-if="form.timeType === 'datetime'" label="日期时间列">
        <el-select v-model="form.timeColumn" filterable>
          <el-option
            v-for="header in headers"
            :key="header"
            :label="header"
            :value="header"
          />
        </el-select>
      </el-form-item>
      
      <el-form-item label="公共字段">
        <el-select v-model="form.commonColumns" multiple filterable>
          <el-option
            v-for="header in headers"
            :key="header"
            :label="header"
            :value="header"
          />
        </el-select>
        <div class="tip">选择在所有行中保持不变的字段（非时间相关列）</div>
      </el-form-item>
      
      <el-form-item>
        <el-button type="primary" @click="handleConfirm" :disabled="!isValid">
          确认配置
        </el-button>
        <el-button @click="loadHeaders">重新加载</el-button>
      </el-form-item>
    </el-form>
    
    <!-- 预览信息 -->
    <el-alert
      v-if="headers.length > 0"
      title="配置说明"
      type="info"
      :closable="false"
      style="margin-top: 20px"
    >
      <div>
        <p>• 日期类型：适用于包含YYYY-MM-DD格式的时间列</p>
        <p>• 小时类型：适用于X0000-X2345、T0000-T2345、P0000-P2345、H0000-H2345等格式的小时列</p>
        <p>• 日期时间类型：适用于YYYY-MM-DD HH:MM:SS、YYYY/MM/DD HH:MM:SS等格式，会自动拆分为日期和时间</p>
        <p>• 公共字段：在数据扩展时会在每行中重复保留</p>
        <p>• 系统会自动识别T、P、H、X等前缀的小时列</p>
        <p style="color: #E6A23C; font-weight: bold;">• 中文表头处理：中文表头会保持原样，不会转换为VALUE字段。只有英文数字格式的小时列才会被转换</p>
      </div>
    </el-alert>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadAPI } from '@/timeseries/api'

const props = defineProps({
  fileId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['config-ready'])

const headers = ref([])
const suggestedHourColumns = ref([])
const form = ref({
  timeType: 'hour',
  timeColumn: '',
  hourColumns: [],
  commonColumns: []
})

onMounted(() => {
  loadHeaders()
})

const loadHeaders = async () => {
  try {
    const response = await uploadAPI.getHeaders(props.fileId)
    headers.value = response.headers
    suggestedHourColumns.value = response.suggested_hour_columns
    
    // 自动填充建议的小时列
    if (response.suggested_hour_columns.length > 0) {
      form.value.hourColumns = response.suggested_hour_columns
    }
  } catch (error) {
    console.error('加载表头失败:', error)
  }
}

const handleTimeTypeChange = () => {
  // 切换时间类型时清空相关配置
  form.value.timeColumn = ''
  form.value.hourColumns = []
}

const isValid = computed(() => {
  if (form.value.timeType === 'date' && !form.value.timeColumn) return false
  if (form.value.timeType === 'hour' && form.value.hourColumns.length === 0) return false
  if (form.value.timeType === 'datetime' && !form.value.timeColumn) return false
  return true
})

const handleConfirm = () => {
  const config = {
    file_id: props.fileId,
    time_type: form.value.timeType,
    time_column: form.value.timeColumn,
    hour_columns: form.value.hourColumns,
    common_columns: form.value.commonColumns,
    value_columns: []  // 自动识别
  }
  
  emit('config-ready', config)
  ElMessage.success('配置已确认')
}
</script>

<style scoped>
.column-mapper {
  padding: 20px;
}

.tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.el-alert p {
  margin: 5px 0;
  line-height: 1.6;
}
</style>
