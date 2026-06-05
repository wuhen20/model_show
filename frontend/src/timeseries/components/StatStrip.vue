<template>
  <div class="stat-strip">
    <div
      v-for="(item, i) in items"
      :key="i"
      class="stat-card"
      :style="{ '--sc': item.color || '#00d4ff' }"
    >
      <div class="stat-icon">
        <el-icon><component :is="iconMap[item.icon] || iconMap.Document" /></el-icon>
      </div>
      <div class="stat-body">
        <div class="stat-value">
          {{ item.value }}<span v-if="item.unit" class="stat-unit">{{ item.unit }}</span>
        </div>
        <div class="stat-label">{{ item.label }}</div>
      </div>
      <span class="stat-corner"></span>
    </div>
  </div>
</template>

<script setup>
import { markRaw } from 'vue'
import {
  Document, Files, FolderOpened, Connection, TrendCharts, Histogram,
  Download, DataAnalysis, Coin, CircleCheck, Clock, PieChart, Upload,
  Cpu, MagicStick, Setting, Operation
} from '@element-plus/icons-vue'

defineProps({ items: { type: Array, default: () => [] } })

const iconMap = {
  Document: markRaw(Document),
  Files: markRaw(Files),
  FolderOpened: markRaw(FolderOpened),
  Connection: markRaw(Connection),
  TrendCharts: markRaw(TrendCharts),
  Histogram: markRaw(Histogram),
  Download: markRaw(Download),
  DataAnalysis: markRaw(DataAnalysis),
  Coin: markRaw(Coin),
  CircleCheck: markRaw(CircleCheck),
  Clock: markRaw(Clock),
  PieChart: markRaw(PieChart),
  Upload: markRaw(Upload),
  Cpu: markRaw(Cpu),
  MagicStick: markRaw(MagicStick),
  Setting: markRaw(Setting),
  Operation: markRaw(Operation)
}
</script>

<style scoped>
.stat-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.stat-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 15px 18px;
  border-radius: 12px;
  border: 1px solid rgba(56, 132, 235, 0.26);
  border-left: 3px solid var(--sc);
  background: linear-gradient(135deg, rgba(16, 38, 78, 0.85), rgba(11, 26, 56, 0.88));
  box-shadow: 0 0 20px rgba(20, 80, 180, 0.2);
  overflow: hidden;
  transition: border-color .25s ease, box-shadow .25s ease, transform .25s ease;
}
.stat-card:hover {
  transform: translateY(-2px);
  border-color: rgba(52, 225, 255, 0.5);
  box-shadow: 0 0 24px rgba(20, 80, 180, 0.32);
}
.stat-icon {
  width: 46px; height: 46px;
  flex-shrink: 0;
  border-radius: 11px;
  display: flex; align-items: center; justify-content: center;
  font-size: 23px;
  color: var(--sc);
  background: rgba(32, 168, 255, 0.12);
  box-shadow: inset 0 0 12px rgba(32, 168, 255, 0.1);
}
.stat-body { min-width: 0; }
.stat-value {
  font-size: 25px;
  font-weight: 700;
  color: #eaf3ff;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 12px rgba(52, 225, 255, 0.2);
  white-space: nowrap;
}
.stat-unit { font-size: 13px; font-weight: 500; margin-left: 3px; color: #8aa0c8; }
.stat-label { margin-top: 5px; font-size: 13px; color: #8aa0c8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stat-corner {
  position: absolute;
  top: -18px; right: -18px;
  width: 56px; height: 56px;
  border-radius: 50%;
  background: radial-gradient(circle, color-mix(in srgb, var(--sc) 35%, transparent) 0%, transparent 70%);
  pointer-events: none;
}
</style>
