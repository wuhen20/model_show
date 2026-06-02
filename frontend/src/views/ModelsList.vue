<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { modelsApi } from '@/api/models'
import {
  ioTypeLabels,
  sceneCatalog,
  statusLabels,
  type ModelBrief,
  type ModelStatus,
  type SceneCode
} from '@/data/models'

const route = useRoute()
const router = useRouter()

const list = ref<ModelBrief[]>([])
const loading = ref(false)
const errorMsg = ref('')
const sceneFilter = ref<SceneCode | ''>('')
const statusFilter = ref<ModelStatus | ''>('')

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    list.value = await modelsApi.list({
      scene: sceneFilter.value || undefined,
      status: statusFilter.value || undefined
    })
  } catch (e: any) {
    errorMsg.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function applyQueryFilter() {
  const s = route.query.scene as string | undefined
  if (s && sceneCatalog.find((x) => x.code === s)) {
    sceneFilter.value = s as SceneCode
  }
}

const grouped = computed(() => {
  const map: Record<string, ModelBrief[]> = {}
  for (const m of list.value) {
    if (!map[m.scene]) map[m.scene] = []
    map[m.scene].push(m)
  }
  return sceneCatalog
    .filter((sc) => map[sc.code]?.length)
    .map((sc) => ({ scene: sc, items: map[sc.code] }))
})

function goDetail(code: string) {
  router.push(`/models/${code}`)
}

async function toggleStatus(m: ModelBrief, evt: Event) {
  evt.stopPropagation()
  try {
    if (m.status === 'running') await modelsApi.offline(m.code)
    else await modelsApi.online(m.code)
    await load()
  } catch (e: any) {
    errorMsg.value = e?.message || '操作失败'
  }
}

watch([sceneFilter, statusFilter], load)
onMounted(() => {
  applyQueryFilter()
  load()
})
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1>小模型管理</h1>
      <div class="filters">
        <select v-model="sceneFilter">
          <option value="">全部场景</option>
          <option v-for="s in sceneCatalog" :key="s.code" :value="s.code">
            {{ s.code }} · {{ s.name }}
          </option>
        </select>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option value="running">运行中</option>
          <option value="planned">待训练</option>
          <option value="offline">已下线</option>
          <option value="error">异常</option>
        </select>
        <button class="btn" @click="load">刷新</button>
      </div>
    </header>

    <div v-if="errorMsg" class="error-bar">⚠ {{ errorMsg }}</div>
    <div v-if="loading" class="loading">加载中…</div>

    <section v-for="g in grouped" :key="g.scene.code" class="scene-block">
      <h2>
        <span class="badge">{{ g.scene.code }}</span>
        {{ g.scene.name }}
        <small>共 {{ g.items.length }} 个</small>
      </h2>
      <div class="card-grid">
        <div
          v-for="m in g.items"
          :key="m.code"
          class="model-card"
          @click="goDetail(m.code)"
        >
          <div class="card-head">
            <span class="code">{{ m.code }}</span>
            <span class="status" :class="m.status">
              {{ statusLabels[m.status].text }}
            </span>
          </div>
          <h3>{{ m.name }}</h3>
          <div class="card-meta">
            <span class="tag">{{ ioTypeLabels[m.io_type] }}</span>
            <span class="tag">{{ m.backend_type }}</span>
            <span v-if="m.current_version" class="ver">v{{ m.current_version }}</span>
          </div>
          <div class="card-actions">
            <button class="btn-sm" @click="toggleStatus(m, $event)">
              {{ m.status === 'running' ? '下线' : '上线' }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <div v-if="!loading && !grouped.length" class="empty">暂无模型</div>
  </div>
</template>

<style scoped>
.page { padding: 24px; color: #e4e7ed; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h1 { font-size: 20px; color: #00d4ff; margin: 0; }
.filters { display: flex; gap: 10px; }
.filters select, .btn {
  background: rgba(17,24,39,0.8); color: #e4e7ed;
  border: 1px solid rgba(0,212,255,0.3); border-radius: 6px;
  padding: 6px 12px; cursor: pointer;
}
.btn:hover { border-color: #00d4ff; }
.error-bar { padding: 10px; background: rgba(255,80,80,0.15); border: 1px solid #ff5555; border-radius: 6px; margin-bottom: 16px; }
.loading, .empty { padding: 30px; text-align: center; color: rgba(255,255,255,0.5); }

.scene-block { margin-bottom: 28px; }
.scene-block h2 { font-size: 15px; color: #fff; display: flex; align-items: center; gap: 8px; margin: 0 0 12px; }
.scene-block h2 small { color: rgba(255,255,255,0.4); font-weight: 400; }
.badge { display: inline-block; padding: 2px 8px; background: rgba(0,212,255,0.2); color: #00d4ff; border-radius: 4px; font-size: 12px; }

.card-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.model-card {
  background: rgba(17,24,39,0.6); border: 1px solid rgba(0,212,255,0.2);
  border-radius: 8px; padding: 14px; cursor: pointer; transition: all 0.2s;
}
.model-card:hover { border-color: #00d4ff; transform: translateY(-2px); }
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.code { font-family: monospace; color: #00d4ff; font-weight: 600; }
.status { padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.status.running { background: rgba(0,255,136,0.2); color: #00ff88; }
.status.planned { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.6); }
.status.offline { background: rgba(255,170,0,0.2); color: #ffaa00; }
.status.error { background: rgba(255,80,80,0.2); color: #ff5555; }
.model-card h3 { font-size: 14px; margin: 0 0 10px; color: #fff; }
.card-meta { display: flex; gap: 6px; flex-wrap: wrap; }
.tag {
  padding: 2px 6px; background: rgba(255,255,255,0.08);
  border-radius: 4px; font-size: 11px; color: rgba(255,255,255,0.7);
}
.ver { color: #ffaa00; font-size: 11px; }
.card-actions { margin-top: 12px; }
.btn-sm {
  padding: 4px 10px; background: rgba(0,212,255,0.15); color: #00d4ff;
  border: 1px solid rgba(0,212,255,0.3); border-radius: 4px;
  cursor: pointer; font-size: 12px;
}
.btn-sm:hover { background: rgba(0,212,255,0.25); }
</style>
