<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getCodeDict, getCollectTaskDet, saveCollectTaskDet, type CodeDictItem } from '@/api/sample'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()

const taskNo = ref<string>((route.query.taskNo as string) || '')

const dbTypeOptions = ref<{ value: string; label: string }[]>([])
const loading = ref(false)
const saving = ref(false)

const form = ref({
  sourceDbType: '',
  sourceDbHost: '',
  sourceDbPort: '',
  sourceDbUsr: '',
  sourceDbPwd: '',
  targetTable: '',
  collectSql: ''
})

// 执行结果信息
const execInfo = ref({
  lastExecuteTime: '',
  lastExecuteFlagName: ''
})

async function loadDbTypeDict() {
  try {
    const data = await getCodeDict(['DATABASE_TYPE'])
    if (data.DATABASE_TYPE && data.DATABASE_TYPE.length > 0) {
      dbTypeOptions.value = data.DATABASE_TYPE.map((item: CodeDictItem) => ({
        value: item.codeValue,
        label: item.codeName
      }))
    }
  } catch {
    // 字典加载失败时忽略
  }
}

async function loadTaskDet() {
  loading.value = true
  try {
    const det = await getCollectTaskDet(taskNo.value)
    if (det) {
      form.value = {
        sourceDbType: det.sourceDbType || '',
        sourceDbHost: det.sourceDbHost || '',
        sourceDbPort: det.sourceDbPort || '',
        sourceDbUsr: det.sourceDbUsr || '',
        sourceDbPwd: det.sourceDbPwd || '',
        targetTable: det.targetTable || '',
        collectSql: det.collectSql || ''
      }
      execInfo.value = {
        lastExecuteTime: det.lastExecuteTime || '',
        lastExecuteFlagName: det.lastExecuteFlagName || ''
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '查询明细失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!form.value.sourceDbType) {
    ElMessage.warning('请选择数据库类型')
    return
  }
  if (!form.value.sourceDbHost.trim()) {
    ElMessage.warning('请输入数据库地址')
    return
  }
  if (!form.value.sourceDbUsr.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!form.value.collectSql.trim()) {
    ElMessage.warning('请输入采集SQL')
    return
  }
  if (!form.value.targetTable.trim()) {
    ElMessage.warning('请输入目标表名')
    return
  }

  saving.value = true
  try {
    await saveCollectTaskDet({
      taskNo: taskNo.value,
      sourceDbType: form.value.sourceDbType,
      sourceDbHost: form.value.sourceDbHost.trim(),
      sourceDbPort: form.value.sourceDbPort.trim(),
      sourceDbUsr: form.value.sourceDbUsr.trim(),
      sourceDbPwd: form.value.sourceDbPwd,
      targetTable: form.value.targetTable.trim(),
      collectSql: form.value.collectSql.trim()
    })
    ElMessage.success('保存成功')
    router.push('/collect-task')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function goBack() {
  router.push('/collect-task')
}

onMounted(() => {
  if (!taskNo.value) {
    ElMessage.warning('缺少任务编号，请从任务列表进入')
    router.push('/collect-task')
    return
  }
  loadDbTypeDict()
  loadTaskDet()
})
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="采集任务明细" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="page-header">
          <div class="page-title-row">
            <div class="title-left">
              <span class="back-btn" @click="goBack">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M19 12H5M12 19l-7-7 7-7" />
                </svg>
                返回
              </span>
              <h2 class="page-title">采集任务明细</h2>
            </div>
            <span class="task-no-tag">任务编号：{{ taskNo }}</span>
          </div>
        </div>

        <div class="form-container">
          <div v-if="loading" class="loading-mask">
            <span>加载中...</span>
          </div>
          <div v-if="!loading && execInfo.lastExecuteTime" class="exec-info">
            <span class="exec-label">最近执行时间：</span>
            <span class="exec-value">{{ execInfo.lastExecuteTime }}</span>
            <span class="exec-label" style="margin-left: 24px;">执行结果：</span>
            <span class="exec-value" :style="{ color: execInfo.lastExecuteFlagName === '成功' ? '#00ff88' : execInfo.lastExecuteFlagName === '失败' ? '#ff5555' : 'rgba(255,255,255,0.5)' }">
              {{ execInfo.lastExecuteFlagName || '未执行' }}
            </span>
          </div>
          <el-form label-width="100px" label-position="right">
            <!-- 第一排：数据库类型、地址 -->
            <div class="form-row">
              <div class="form-col">
                <el-form-item label="数据库类型" required>
                  <el-select v-model="form.sourceDbType" placeholder="请选择" popper-class="detail-popper">
                    <el-option v-for="opt in dbTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                  </el-select>
                </el-form-item>
              </div>
              <div class="form-col">
                <el-form-item label="数据库地址" required>
                  <el-input v-model="form.sourceDbHost" placeholder="如 127.0.0.1" maxlength="100" />
                </el-form-item>
              </div>
            </div>
            <!-- 第二排：端口、用户名、密码 -->
            <div class="form-row">
              <div class="form-col form-col-small">
                <el-form-item label="端口">
                  <el-input v-model="form.sourceDbPort" placeholder="如 3306" maxlength="32" />
                </el-form-item>
              </div>
              <div class="form-col">
                <el-form-item label="用户名" required>
                  <el-input v-model="form.sourceDbUsr" placeholder="请输入用户名" maxlength="32" />
                </el-form-item>
              </div>
              <div class="form-col">
                <el-form-item label="密码">
                  <el-input v-model="form.sourceDbPwd" type="password" show-password placeholder="请输入密码" maxlength="32" />
                </el-form-item>
              </div>
            </div>
            <!-- 第三排：SQL（占满一行） -->
            <div class="form-row form-row-full">
              <el-form-item label="采集SQL" required class="full-width-item">
                <el-input v-model="form.collectSql" type="textarea" :rows="6" placeholder="请输入采集数据的SQL语句" />
              </el-form-item>
            </div>
            <!-- 第四排：目标表名 -->
            <div class="form-row">
              <div class="form-col">
                <el-form-item label="目标表名" required>
                  <el-input v-model="form.targetTable" placeholder="数据写入的目标表名" maxlength="32" />
                </el-form-item>
              </div>
            </div>
          </el-form>

          <div class="form-footer">
            <el-button @click="goBack">取消</el-button>
            <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped lang="scss">
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0d1117;
  overflow: hidden;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.content-area {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.page-header {
  margin-bottom: 20px;
}

.page-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  font-size: 13px;
  transition: color 0.2s;

  &:hover {
    color: #00d4ff;
  }
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #fff;
  margin: 0;
}

.task-no-tag {
  font-size: 13px;
  color: #00d4ff;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.25);
  padding: 4px 12px;
  border-radius: 6px;
}

.form-container {
  flex: 1;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 32px;
  position: relative;
}

.loading-mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(17, 24, 39, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  border-radius: 12px;

  span {
    color: rgba(255, 255, 255, 0.6);
    font-size: 14px;
  }
}

.exec-info {
  margin-bottom: 20px;
  padding: 12px 16px;
  background: rgba(0, 212, 255, 0.08);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  font-size: 13px;
}

.exec-label {
  color: rgba(255, 255, 255, 0.5);
}

.exec-value {
  color: rgba(255, 255, 255, 0.85);
}

.form-row {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  max-width: 1100px;
}

.form-row-full {
  display: block;
  max-width: 1100px;
}

.form-col {
  flex: 1;
  min-width: 200px;
  max-width: 300px;
}

.form-col-small {
  flex: 0 0 150px;
  max-width: 150px;
}

.full-width-item {
  width: 100%;

  .el-form-item__content {
    width: 100%;
  }
}

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(0, 212, 255, 0.12);
}
</style>

<style lang="scss">
.detail-popper {
  background: rgba(17, 24, 39, 0.98) !important;
  border: 1px solid rgba(0, 212, 255, 0.25) !important;

  .el-select-dropdown__item {
    color: rgba(255, 255, 255, 0.7) !important;

    &.is-selected {
      color: #00d4ff !important;
    }
  }
}

.form-container {
  .el-form-item__label {
    color: rgba(255, 255, 255, 0.7) !important;
  }

  .el-input__wrapper,
  .el-textarea__inner {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
    box-shadow: none !important;
  }

  .el-input__inner {
    color: rgba(255, 255, 255, 0.85) !important;

    &::placeholder {
      color: rgba(255, 255, 255, 0.3) !important;
    }
  }

  .el-textarea__inner {
    color: rgba(255, 255, 255, 0.85) !important;

    &::placeholder {
      color: rgba(255, 255, 255, 0.3) !important;
    }
  }

  .el-button--primary {
    background: linear-gradient(135deg, #00d4ff, #0099cc) !important;
    border: none !important;
    color: #0d1117 !important;
    font-weight: 600;
  }

  .el-button:not(.el-button--primary) {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
    color: rgba(255, 255, 255, 0.7) !important;
  }
}
</style>
