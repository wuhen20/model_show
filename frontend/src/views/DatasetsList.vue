<script setup lang="ts">
// M1 占位页：训练数据集管理（M2 接入）
</script>

<template>
  <div class="page">
    <h1>训练数据集管理</h1>
    <p class="sub">M2 里程碑提供：数据集上传 / 版本管理 / 样本预览 / 与模型/训练任务关联</p>
    <div class="placeholder">
      <div class="ph-icon">📦</div>
      <div class="ph-text">该模块将在 M2 阶段开放</div>
      <ul class="ph-list">
        <li>按场景组织数据集（采集自愈 / 现场作业 / 负荷资源管理 / 台区四精 / 用电异常 / 资产管理）</li>
        <li>支持 csv / parquet / image / multimodal 多类型</li>
        <li>校验 schema 与模型 input_spec 对齐</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 24px; color: #e4e7ed; }
.page h1 { font-size: 20px; color: #00d4ff; margin: 0 0 6px; }
.sub { color: rgba(255,255,255,0.5); font-size: 13px; margin: 0 0 20px; }
.placeholder { background: rgba(17,24,39,0.6); border: 1px dashed rgba(0,212,255,0.3); border-radius: 10px; padding: 40px; text-align: center; }
.ph-icon { font-size: 48px; margin-bottom: 12px; }
.ph-text { font-size: 16px; color: rgba(255,255,255,0.7); margin-bottom: 18px; }
.ph-list { text-align: left; max-width: 500px; margin: 0 auto; color: rgba(255,255,255,0.6); font-size: 13px; line-height: 1.9; }
</style>
