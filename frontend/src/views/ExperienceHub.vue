<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { modelsApi } from '@/api/models'
import { ioTypeLabels, sceneCatalog, type ModelBrief } from '@/data/smModels'

const router = useRouter()
const list = ref<ModelBrief[]>([])
const loading = ref(false)
const errorMsg = ref('')

async function load() {
  loading.value = true
  try {
    list.value = await modelsApi.list()
  } catch (e: any) {
    errorMsg.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function groupOf(code: string) {
  return list.value.filter((m) => m.scene === code)
}

function go(code: string) {
  router.push(`/experience/${code}`)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>小模型展示与体验</h1>
        <p class="sub">按业务场景浏览全部 20 个小模型，点击进入交互体验</p>
      </div>
    </header>

    <div v-if="errorMsg" class="error-bar">⚠ {{ errorMsg }}</div>
    <div v-if="loading" class="loading">加载中…</div>

    <section v-for="sc in sceneCatalog" :key="sc.code" class="scene">
      <h2>
        <span class="badge">{{ sc.code }}</span>
        {{ sc.name }}
        <small>{{ sc.description }}</small>
      </h2>
      <div class="grid">
        <div v-for="m in groupOf(sc.code)" :key="m.code" class="exp-card" @click="go(m.code)">
          <div class="head">
            <span class="code">{{ m.code }}</span>
            <span class="io">{{ ioTypeLabels[m.io_type] }}</span>
          </div>
          <h3>{{ m.name }}</h3>
          <button class="enter">立即体验 →</button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page { padding: 24px; color: #e4e7ed; }
.page-header { margin-bottom: 20px; }
.page-header h1 { font-size: 20px; color: #00d4ff; margin: 0; }
.sub { color: rgba(255,255,255,0.5); font-size: 13px; margin: 4px 0 0; }
.error-bar { padding: 10px; background: rgba(255,80,80,0.15); border: 1px solid #ff5555; border-radius: 6px; margin-bottom: 16px; }
.loading { padding: 30px; text-align: center; color: rgba(255,255,255,0.5); }

.scene { margin-bottom: 26px; }
.scene h2 { font-size: 15px; display: flex; align-items: center; gap: 8px; margin: 0 0 10px; }
.scene h2 small { color: rgba(255,255,255,0.4); font-weight: 400; margin-left: 6px; }
.badge { padding: 2px 8px; background: rgba(0,212,255,0.2); color: #00d4ff; border-radius: 4px; font-size: 12px; }

.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.exp-card {
  background: linear-gradient(135deg, rgba(0,212,255,0.08), rgba(155,108,255,0.08));
  border: 1px solid rgba(0,212,255,0.2); border-radius: 10px;
  padding: 16px; cursor: pointer; transition: all 0.2s;
}
.exp-card:hover { border-color: #00d4ff; transform: translateY(-3px); box-shadow: 0 4px 16px rgba(0,212,255,0.2); }
.head { display: flex; justify-content: space-between; margin-bottom: 8px; }
.code { font-family: monospace; color: #00d4ff; font-weight: 600; }
.io { padding: 2px 8px; background: rgba(255,255,255,0.08); border-radius: 4px; font-size: 11px; }
.exp-card h3 { font-size: 14px; margin: 0 0 12px; color: #fff; min-height: 36px; }
.enter { background: transparent; border: none; color: #00d4ff; font-size: 12px; cursor: pointer; padding: 0; }
</style>
