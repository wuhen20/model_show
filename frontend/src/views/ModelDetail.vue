<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { modelsApi } from '@/api/models'
import { ioTypeLabels, statusLabels, type ModelDetail } from '@/data/smModels'

const route = useRoute()
const router = useRouter()
const detail = ref<ModelDetail | null>(null)
const loading = ref(false)
const errorMsg = ref('')

async function load() {
  const code = route.params.code as string
  if (!code) return
  loading.value = true
  errorMsg.value = ''
  try {
    detail.value = await modelsApi.detail(code)
  } catch (e: any) {
    errorMsg.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

watch(() => route.params.code, load)
onMounted(load)
</script>

<template>
  <div class="page">
    <a class="back" @click="router.back()">← 返回</a>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="errorMsg" class="error-bar">⚠ {{ errorMsg }}</div>

    <template v-else-if="detail">
      <header class="detail-head">
        <div>
          <h1>
            <span class="code">{{ detail.code }}</span>
            {{ detail.name }}
          </h1>
          <div class="meta-row">
            <span class="status" :class="detail.status">
              {{ statusLabels[detail.status].text }}
            </span>
            <span class="tag">{{ ioTypeLabels[detail.io_type] }}</span>
            <span class="tag">{{ detail.backend_type }}</span>
            <span v-if="detail.current_version" class="ver">v{{ detail.current_version }}</span>
          </div>
        </div>
        <div class="actions">
          <button class="btn" @click="router.push(`/experience/${detail.code}`)">前往体验</button>
        </div>
      </header>

      <section class="block">
        <h2>模型描述</h2>
        <p class="desc">{{ detail.description || '暂无描述' }}</p>
      </section>

      <section class="block grid-2">
        <div>
          <h2>输入规范</h2>
          <table class="spec-table">
            <thead><tr><th>字段</th><th>类型</th><th>必填</th></tr></thead>
            <tbody>
              <tr v-for="(f, i) in detail.input_spec" :key="i">
                <td>{{ f.field }}</td>
                <td>{{ f.type || '-' }}</td>
                <td>{{ f.required ? '是' : '否' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div>
          <h2>输出规范</h2>
          <table class="spec-table">
            <thead><tr><th>字段</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="(f, i) in detail.output_spec" :key="i">
                <td>{{ f.field }}</td>
                <td>{{ f.description || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="detail.sub_scenes && detail.sub_scenes.length" class="block">
        <h2>子场景</h2>
        <div class="chips">
          <span v-for="s in detail.sub_scenes" :key="s" class="chip">{{ s }}</span>
        </div>
      </section>

      <section class="block">
        <small>更新时间：{{ detail.updated_at || '-' }}</small>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page { padding: 24px; color: #e4e7ed; }
.back { color: #00d4ff; cursor: pointer; font-size: 13px; }
.back:hover { text-decoration: underline; }
.loading, .error-bar { padding: 20px; text-align: center; }
.error-bar { background: rgba(255,80,80,0.15); border: 1px solid #ff5555; border-radius: 6px; }

.detail-head { display: flex; justify-content: space-between; align-items: flex-start; margin: 16px 0 24px; }
.detail-head h1 { font-size: 22px; margin: 0; display: flex; gap: 12px; align-items: center; }
.code { font-family: monospace; padding: 3px 10px; background: rgba(0,212,255,0.15); color: #00d4ff; border-radius: 4px; font-size: 14px; }
.meta-row { display: flex; gap: 8px; margin-top: 8px; }
.tag { padding: 2px 8px; background: rgba(255,255,255,0.08); border-radius: 4px; font-size: 12px; }
.ver { color: #ffaa00; font-size: 12px; }
.status { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.status.running { background: rgba(0,255,136,0.2); color: #00ff88; }
.status.planned { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.6); }
.status.offline { background: rgba(255,170,0,0.2); color: #ffaa00; }
.status.error { background: rgba(255,80,80,0.2); color: #ff5555; }
.btn { padding: 8px 18px; background: rgba(0,212,255,0.15); border: 1px solid #00d4ff; color: #00d4ff; border-radius: 6px; cursor: pointer; }

.block { background: rgba(17,24,39,0.5); border: 1px solid rgba(0,212,255,0.15); border-radius: 8px; padding: 16px; margin-bottom: 14px; }
.block h2 { font-size: 14px; color: #00d4ff; margin: 0 0 10px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; background: transparent; border: none; padding: 0; }
.grid-2 > div { background: rgba(17,24,39,0.5); border: 1px solid rgba(0,212,255,0.15); border-radius: 8px; padding: 16px; }
.desc { color: rgba(255,255,255,0.8); line-height: 1.7; margin: 0; }
.spec-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.spec-table th, .spec-table td { padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.08); text-align: left; }
.spec-table th { color: rgba(255,255,255,0.5); font-weight: 500; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { padding: 4px 10px; background: rgba(0,212,255,0.1); color: #00d4ff; border-radius: 14px; font-size: 12px; }
</style>
