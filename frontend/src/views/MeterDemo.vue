<script setup lang="ts">
import DemoShowcase, { type DemoConfig } from '@/components/DemoShowcase.vue'

const config: DemoConfig = {
  apiBase: '/api/demo/meter',
  theme: { primary: '#7c3aed', primaryDark: '#6d28d9', gradient: 'linear-gradient(120deg,#7c3aed,#a78bfa)' },
  title: '电表异常研判功能展示 - CNN+LSTM多标签分类系统',
  subtitle: '基于CNN+LSTM · 24点时序+静态特征 · 5类电表异常检测 · 多标签分类',
  flowTitle: 'CNN + BiLSTM 多标签分类',
  flowInputDesc: '输入（双通道）',
  flowInputItems: [
    '<b>时序通道</b>：24个时间点 × 4个测量量（电压、电流、有功功率、功率因数）= 96维',
    '<b>静态通道</b>：6项基础特征 + 24项自动统计特征（均值/方差/峰度/偏度/波峰因子等）= 30维'
  ],
  flowMechDesc: '模型结构',
  flowMechItems: [
    '<b>CNN编码</b>：2层Conv1D(32→64) + BatchNorm + MaxPool → 提取局部时序模式',
    '<b>BiLSTM</b>：双向LSTM(hidden=64) → 捕捉长期依赖关系',
    '<b>静态MLP</b>：2层全连接(64→32) → 编码静态特征',
    '<b>融合分类</b>：Concat → 2层全连接(128→5) → Sigmoid输出'
  ],
  nFeaturesLabel: '时序特征维度',
  nFeaturesValue: '96',
  anomalyTableCols: [
    { key: 'OFFSET_TIME', label: '时钟偏差' },
    { key: 'RUN_YEARS', label: '建档年限' },
    { key: 'COLL_FAIL_U_7D', label: '采集失败率' },
    { key: 'TEMP_ERR_RATE', label: '温度异常率' },
    { key: 'COLL_COMPLETE_U', label: '采集完整率' },
    { key: 'DEPTH', label: '深度' }
  ],
  detailFeatureKeys: [
    'OFFSET_TIME', 'RUN_YEARS', 'COLL_FAIL_U_7D', 'TEMP_ERR_RATE', 'COLL_COMPLETE_U', 'DEPTH'
  ],
  hasFeatureImportance: false,
  footer: '电表异常研判 CNN+LSTM 多标签分类系统 · PyTorch 模型 · © 2026',
  labelColors: ['#5470c6','#91cc75','#fac858','#ee6666','#73c0de']
}
</script>

<template>
  <DemoShowcase :config="config" />
</template>