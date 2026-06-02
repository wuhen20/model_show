<script setup lang="ts">
// M1 占位页：训练任务列表（M3 接入真实 API）
</script>

<template>
  <div class="page">
    <h1>小模型训练</h1>
    <p class="sub">M3 里程碑提供：训练任务发起 / 进度跟踪 / 评估指标 / 版本归档</p>
    <div class="placeholder">
      <div class="ph-icon">🛠</div>
      <div class="ph-text">该模块将在 M3 阶段开放</div>
      <ul class="ph-list">
        <li>支持按场景选择基线算法（XGBoost / LightGBM / TFT / YOLOv8 / TabTransformer）</li>
        <li>统一训练入口 + DVC/MLflow 跟踪（可选）</li>
        <li>训练完成自动生成 ModelVersion 并入注册表</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 24px; color: #e4e7ed; }
.page h1 { font-size: 20px; color: #00d4ff; margin: 0 0 6px; }
.sub { color: rgba(255,255,255,0.5); font-size: 13px; margin: 0 0 20px; }
.placeholder {
  background: rgba(17,24,39,0.6); border: 1px dashed rgba(0,212,255,0.3);
  border-radius: 10px; padding: 40px; text-align: center;
}
.ph-icon { font-size: 48px; margin-bottom: 12px; }
.ph-text { font-size: 16px; color: rgba(255,255,255,0.7); margin-bottom: 18px; }
.ph-list { text-align: left; max-width: 500px; margin: 0 auto; color: rgba(255,255,255,0.6); font-size: 13px; line-height: 1.9; }
</style>
