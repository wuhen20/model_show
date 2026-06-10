<script setup lang="ts">
import DemoShowcase, { type DemoConfig } from '@/components/DemoShowcase.vue'

const config: DemoConfig = {
  apiBase: '/api/demo/terminal',
  theme: { primary: '#2f6df3', primaryDark: '#1f54c7', gradient: 'linear-gradient(120deg,#2f6df3,#4f8bff)' },
  title: '终端异常研判功能展示 - XGBoost多标签分类系统',
  subtitle: '基于XGBoost · 12维特征 · 13类终端异常检测 · One-vs-Rest 多标签分类',
  flowTitle: 'XGBoost 多标签分类 — One-vs-Rest 策略',
  flowInputDesc: '输入特征（12维）',
  flowInputItems: [
    'SIG_STR（信号强度）· ONOFF_NUM（上下线次数）',
    'FLOW_STAT（流量饱和度）· OFFSET_TIME（时钟偏差）',
    'METER_NET_RATE（组网异常率）· CUST_NUM_FLAG（用户超阈值）',
    'RUN_YEARS（建档年限）· COLL_FAIL_RATE_7D（7天采集失败率）',
    'ONLINE_DUR（在线时长）· MSG_TIME（消息时间）',
    'TEMP_ERR_RATE（温度异常率）· METER_FAIL_RATE（采集失败占比）'
  ],
  flowMechDesc: '核心机制',
  flowMechItems: [
    '<b>样本不均衡处理</b>：scale_pos_weight 自动加权',
    '<b>F1 最优阈值</b>：验证集搜索最佳判定阈值（0.1~0.9）',
    '<b>XGBoost</b>：240棵树，max_depth=4，learning_rate=0.06'
  ],
  nFeaturesLabel: '特征维度',
  nFeaturesValue: '12',
  anomalyTableCols: [
    { key: 'SIG_STR', label: '信号强度' },
    { key: 'ONOFF_NUM', label: '上下线次数' },
    { key: 'FLOW_STAT', label: '流量饱和度' },
    { key: 'OFFSET_TIME', label: '时钟偏差' },
    { key: 'METER_NET_RATE', label: '组网异常率' },
    { key: 'COLL_FAIL_RATE_7D', label: '采集失败率' },
    { key: 'ONLINE_DUR', label: '在线时长' },
    { key: 'TEMP_ERR_RATE', label: '温度异常率' },
    { key: 'METER_FAIL_RATE', label: '电表失败率' }
  ],
  detailFeatureKeys: [
    'SIG_STR', 'ONOFF_NUM', 'FLOW_STAT', 'OFFSET_TIME',
    'METER_NET_RATE', 'CUST_NUM_FLAG', 'RUN_YEARS', 'COLL_FAIL_RATE_7D',
    'ONLINE_DUR', 'MSG_TIME', 'TEMP_ERR_RATE', 'METER_FAIL_RATE'
  ],
  hasFeatureImportance: true,
  footer: '终端异常研判 XGBoost 多标签分类系统 · © 2026',
  labelColors: ['#5470c6','#91cc75','#fac858','#ee6666','#73c0de','#3ba272','#fc8452','#9a60b4','#ea7ccc','#47a0e9','#b497c6','#6e7074','#e69b6d']
}
</script>

<template>
  <DemoShowcase :config="config" />
</template>