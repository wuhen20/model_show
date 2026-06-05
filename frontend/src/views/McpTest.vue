<script setup lang="ts">
// M1 占位页：MCP 服务测试（M4 接入）
</script>

<template>
  <div class="page">
    <h1>小模型 MCP 服务测试</h1>
    <p class="sub">M4 里程碑提供：以 MCP 客户端调用已上线服务 / tools 列表 / 工具调用测试</p>
    <div class="placeholder">
      <div class="ph-icon">🔌</div>
      <div class="ph-text">该模块将在 M4 阶段开放</div>
      <ul class="ph-list">
        <li>选择目标 MCP 服务（按模型 code）</li>
        <li>列出 tools / resources / prompts</li>
        <li>表单化构造工具调用参数并查看响应</li>
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
