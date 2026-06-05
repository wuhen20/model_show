<script setup lang="ts">
import { ref } from 'vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import UploadView from '@/timeseries/views/UploadView.vue'
import ProcessView from '@/timeseries/views/ProcessView.vue'
import MergeView from '@/timeseries/views/MergeView.vue'
import DownloadView from '@/timeseries/views/DownloadView.vue'

const activeTab = ref('upload')
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="时序样本集管理" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area ts-content">
        <el-tabs v-model="activeTab" class="ts-tabs">
          <el-tab-pane label="数据上传" name="upload" lazy>
            <UploadView />
          </el-tab-pane>
          <el-tab-pane label="数据预处理" name="process" lazy>
            <ProcessView />
          </el-tab-pane>
          <el-tab-pane label="样本整合" name="merge" lazy>
            <MergeView />
          </el-tab-pane>
          <el-tab-pane label="文件下载与管理" name="download" lazy>
            <DownloadView />
          </el-tab-pane>
        </el-tabs>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: auto;
  padding: 12px 16px;
  min-height: 0;
}

.ts-tabs {
  flex: 1;
  min-height: 0;
}

/* 让集成进来的页面铺满容器，覆盖其原有的居中 max-width */
.ts-content :deep(.upload-view),
.ts-content :deep(.process-view),
.ts-content :deep(.merge-view),
.ts-content :deep(.download-view) {
  max-width: none !important;
}
</style>
