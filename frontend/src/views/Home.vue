<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { dashboardApi } from '@/api/models'
import type { DashboardStats, InvokeTrendPoint, SceneInfo } from '@/data/models'

const router = useRouter()
const stats = ref<DashboardStats | null>(null)
const scenes = ref<SceneInfo[]>([])
const trend = ref<InvokeTrendPoint[]>([])
const loading = ref(true)
const errorMsg = ref('')

const statCards = [
  { key: 'scene_count', label: '业务场景', unit: '个', color: '#00d4ff' },
  { key: 'model_count', label: '小模型总数', unit: '个', color: '#00ff88' },
  { key: 'running_models', label: '运行中', unit: '个', color: '#ffaa00' },
  { key: 'training_tasks', label: '训练任务', unit: '个', color: '#ff66cc' },
  { key: 'mcp_services', label: 'MCP 服务', unit: '个', color: '#9b6cff' },
  { key: 'today_calls', label: '今日调用', unit: '次', color: '#ff5555' }
] as const

async function loadAll() {
  loading.value = true
  errorMsg.value = ''
  try {
    const [s, sc, tr] = await Promise.all([
      dashboardApi.stats(),
      dashboardApi.sceneSummary(),
      dashboardApi.invokeTrend(24, 60)
    ])
    stats.value = s
    scenes.value = sc
    trend.value = tr
  } catch (err: any) {
    errorMsg.value = err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goScene(code: string) {
  router.push({ path: '/models', query: { scene: code } })
}

onMounted(loadAll)
</script>

<template>
  <div class="home">
    <header class="page-header">
      <div>
        <h1>模型能力展示与体验工作台</h1>
        <p class="subtitle">6 大业务场景 · 20 个小模型 · 统一推理与体验</p>
      </div>
      <button class="refresh-btn" @click="loadAll">刷新</button>
    </header>

    <div v-if="errorMsg" class="error-bar">⚠ {{ errorMsg }}</div>

    <section class="stat-grid">
      <div
        v-for="card in statCards"
        :key="card.key"
        class="stat-card"
        :style="{ borderColor: card.color }"
      >
        <div class="stat-label">{{ card.label }}</div>
        <div class="stat-value" :style="{ color: card.color }">
          {{ loading ? '--' : (stats?.[card.key] ?? 0) }}
          <span class="unit">{{ card.unit }}</span>
        </div>
      </div>
    </section>

    <section class="scene-section">
      <h2>业务场景概览</h2>
      <div class="scene-grid">
        <div
          v-for="scene in scenes"
          :key="scene.code"
          class="scene-card"
          @click="goScene(scene.code)"
        >
          <div class="scene-head">
            <span class="scene-code">{{ scene.code }}</span>
            <span class="scene-name">{{ scene.name }}</span>
          </div>
          <p class="scene-desc">{{ scene.description }}</p>
          <div class="scene-meta">
            <span>模型 {{ scene.count ?? 0 }}</span>
            <span class="running">运行 {{ scene.running ?? 0 }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="trend-section">
      <h2>近 24 小时调用趋势</h2>
      <div class="trend-summary">
        <span>共 {{ trend.length }} 个时间桶</span>
        <span>累计调用 {{ trend.reduce((s, p) => s + p.count, 0) }} 次</span>
      </div>
      <div class="trend-bar-wrap">
        <div
          v-for="(p, i) in trend"
          :key="i"
          class="trend-bar"
          :style="{ height: Math.max(2, p.count * 4) + 'px' }"
          :title="`${p.time} : ${p.count}`"
        ></div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home { padding: 24px; color: #e4e7ed; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h1 { font-size: 22px; margin: 0; color: #00d4ff; }
.subtitle { margin: 4px 0 0; color: rgba(255,255,255,0.5); font-size: 13px; }
.refresh-btn {
  padding: 8px 18px; background: rgba(0,212,255,0.15); border: 1px solid #00d4ff;
  color: #00d4ff; border-radius: 6px; cursor: pointer; font-size: 13px;
}
.refresh-btn:hover { background: rgba(0,212,255,0.25); }

.error-bar { padding: 10px 16px; background: rgba(255,80,80,0.15); border: 1px solid #ff5555; border-radius: 6px; margin-bottom: 16px; }

.stat-grid {
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 16px; margin-bottom: 28px;
}
.stat-card {
  background: rgba(17,24,39,0.6); border: 1px solid; border-left-width: 3px;
  border-radius: 8px; padding: 16px;
}
.stat-label { color: rgba(255,255,255,0.6); font-size: 13px; }
.stat-value { font-size: 28px; font-weight: 600; margin-top: 6px; }
.unit { font-size: 13px; color: rgba(255,255,255,0.4); margin-left: 4px; }

.scene-section, .trend-section { margin-bottom: 28px; }
.scene-section h2, .trend-section h2 { font-size: 16px; color: #00d4ff; margin: 0 0 12px; }

.scene-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.scene-card {
  background: rgba(17,24,39,0.6); border: 1px solid rgba(0,212,255,0.2);
  border-radius: 8px; padding: 14px; cursor: pointer; transition: all 0.2s;
}
.scene-card:hover { border-color: #00d4ff; transform: translateY(-2px); }
.scene-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.scene-code {
  display: inline-block; padding: 2px 8px; background: rgba(0,212,255,0.15);
  color: #00d4ff; border-radius: 4px; font-size: 12px; font-weight: 600;
}
.scene-name { font-size: 15px; font-weight: 600; }
.scene-desc { color: rgba(255,255,255,0.55); font-size: 12px; margin: 0 0 8px; }
.scene-meta { display: flex; gap: 12px; font-size: 12px; color: rgba(255,255,255,0.6); }
.scene-meta .running { color: #00ff88; }

.trend-summary { display: flex; gap: 20px; color: rgba(255,255,255,0.6); font-size: 12px; margin-bottom: 8px; }
.trend-bar-wrap {
  display: flex; align-items: flex-end; gap: 2px; height: 120px;
  padding: 8px; background: rgba(17,24,39,0.4); border-radius: 6px;
}
.trend-bar { flex: 1; background: linear-gradient(180deg, #00d4ff, rgba(0,212,255,0.2)); border-radius: 2px 2px 0 0; min-width: 4px; }
</style>
