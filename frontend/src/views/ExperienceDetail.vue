<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { modelsApi, predictApi, type PredictResult } from '@/api/models'
import { ioTypeLabels, type ModelDetail } from '@/data/models'
import TerminalDemo from '@/views/TerminalDemo.vue'
import MeterDemo from '@/views/MeterDemo.vue'
import MeterHealthDemo from '@/views/MeterHealthDemo.vue'

const route = useRoute()
const router = useRouter()

const detail = ref<ModelDetail | null>(null)
const inputText = ref('{}')
const result = ref<PredictResult | null>(null)
const invoking = ref(false)
const errorMsg = ref('')
const activeTab = ref('terminal')

const demoTable = [
  { key: 'terminal', label: '终端异常研判演示' },
  { key: 'meter', label: '电表异常研判演示' },
]

async function load() {
  const code = route.params.code as string
  if (!code) return
  try {
    detail.value = await modelsApi.detail(code)
    inputText.value = buildSample(detail.value)
    result.value = null
    activeTab.value = 'terminal'
  } catch (e: any) {
    errorMsg.value = e?.message || '加载失败'
  }
}

function buildSample(d: ModelDetail): string {
  const obj: Record<string, any> = {}
  for (const f of d.input_spec || []) {
    if (f.type === 'array') obj[f.field] = []
    else if (f.type === 'number' || f.type === 'float') obj[f.field] = 0
    else if (f.type === 'boolean') obj[f.field] = false
    else obj[f.field] = ''
  }
  return JSON.stringify(obj, null, 2)
}

async function invoke() {
  if (!detail.value) return
  invoking.value = true
  errorMsg.value = ''
  result.value = null
  try {
    const input = JSON.parse(inputText.value)
    result.value = await predictApi.invoke(detail.value.code, input)
  } catch (e: any) {
    errorMsg.value = e?.message || '推理失败'
  } finally {
    invoking.value = false
  }
}

watch(() => route.params.code, load)
onMounted(load)
</script>

<template>
  <div class="page">
    <a class="back" @click="router.back()">← 返回</a>

    <template v-if="detail">
      <header class="head">
        <h1>
          <span class="code">{{ detail.code }}</span>
          {{ detail.name }}
          <small>{{ ioTypeLabels[detail.io_type] }} · {{ detail.backend_type }}</small>
        </h1>
        <button class="btn-link" @click="router.push(`/models/${detail.code}`)">查看详情</button>
      </header>

      <!-- ZJ-05 演示 Tab 布局 -->
      <template v-if="detail.code === 'ZJ-05'">
        <nav class="tabs">
          <button
            v-for="t in demoTable" :key="t.key"
            class="tab-btn"
            :class="{ active: activeTab === t.key }"
            @click="activeTab = t.key"
          >{{ t.label }}</button>
        </nav>

        <!-- Tab: 终端异常研判演示 -->
        <KeepAlive>
          <TerminalDemo v-if="activeTab === 'terminal'" />
        </KeepAlive>

        <!-- Tab: 电表异常研判演示 -->
        <KeepAlive>
          <MeterDemo v-if="activeTab === 'meter'" />
        </KeepAlive>
      </template>

      <!-- ZJ-02 电表健康评价 -->
      <template v-else-if="detail.code === 'ZJ-02'">
        <MeterHealthDemo />
      </template>

      <!-- 非 ZJ-05 模型：保持原有布局 -->
      <template v-else>
        <section class="panel grid-2">
          <div class="card">
            <div class="card-title">输入参数（JSON）</div>
            <textarea v-model="inputText" rows="14" class="json-editor"></textarea>
            <button class="btn" :disabled="invoking" @click="invoke">
              {{ invoking ? '推理中…' : '运行推理' }}
            </button>
          </div>
          <div class="card">
            <div class="card-title">
              推理结果
              <span v-if="result?.mock" class="mock-tag">MOCK</span>
            </div>
            <div v-if="errorMsg" class="error">⚠ {{ errorMsg }}</div>
            <div v-else-if="!result" class="placeholder">点击「运行推理」查看输出</div>
            <div v-else>
              <div class="result-meta">
                <span>延时 {{ result.latency_ms }} ms</span>
                <span v-if="result.trace_id">trace: {{ result.trace_id }}</span>
              </div>
              <pre class="output">{{ JSON.stringify(result.output, null, 2) }}</pre>
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="card">
            <div class="card-title">字段说明</div>
            <div class="spec-grid">
              <div>
                <h4>输入</h4>
                <ul>
                  <li v-for="(f, i) in detail.input_spec" :key="i">
                    <code>{{ f.field }}</code> {{ f.type || '' }} {{ f.required ? '(必填)' : '' }}
                  </li>
                </ul>
              </div>
              <div>
                <h4>输出</h4>
                <ul>
                  <li v-for="(f, i) in detail.output_spec" :key="i">
                    <code>{{ f.field }}</code> — {{ f.description || '' }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped>
.page { padding: 24px; color: #e4e7ed; }
.back { color: #00d4ff; cursor: pointer; font-size: 13px; }
.head { display: flex; justify-content: space-between; align-items: center; margin: 16px 0; }
.head h1 { font-size: 20px; margin: 0; display: flex; align-items: center; gap: 10px; }
.head h1 small { font-size: 12px; color: rgba(255,255,255,0.5); font-weight: 400; }
.code { font-family: monospace; padding: 3px 10px; background: rgba(0,212,255,0.15); color: #00d4ff; border-radius: 4px; font-size: 14px; }
.btn-link { background: transparent; border: 1px solid rgba(0,212,255,0.3); color: #00d4ff; padding: 6px 14px; border-radius: 6px; cursor: pointer; }

.panel { margin-bottom: 16px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.card { background: rgba(17,24,39,0.6); border: 1px solid rgba(0,212,255,0.15); border-radius: 8px; padding: 16px; }
.card-title { font-size: 14px; color: #00d4ff; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
.mock-tag { padding: 1px 6px; background: rgba(255,170,0,0.2); color: #ffaa00; border-radius: 4px; font-size: 10px; }

.json-editor {
  width: 100%; background: rgba(0,0,0,0.4); color: #e4e7ed;
  border: 1px solid rgba(255,255,255,0.1); border-radius: 6px;
  padding: 10px; font-family: monospace; font-size: 12px; resize: vertical;
}
.btn {
  margin-top: 10px; padding: 8px 18px; background: #00d4ff; color: #0d1117;
  border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.error { color: #ff5555; padding: 12px; background: rgba(255,80,80,0.1); border-radius: 6px; }
.placeholder { color: rgba(255,255,255,0.4); padding: 30px; text-align: center; }
.result-meta { display: flex; gap: 14px; font-size: 12px; color: rgba(255,255,255,0.5); margin-bottom: 8px; }
.output {
  background: rgba(0,0,0,0.4); padding: 12px; border-radius: 6px;
  font-size: 12px; max-height: 320px; overflow: auto;
}

.spec-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.spec-grid h4 { font-size: 13px; color: rgba(255,255,255,0.6); margin: 0 0 8px; }
.spec-grid ul { margin: 0; padding-left: 18px; font-size: 12px; line-height: 1.9; }
.spec-grid code { color: #00d4ff; background: rgba(0,212,255,0.1); padding: 1px 5px; border-radius: 3px; }

/* Tab 导航 */
.tabs {
  display: flex; gap: 0;
  border-bottom: 1px solid rgba(0,212,255,0.15);
  margin-bottom: 16px;
}
.tab-btn {
  background: transparent; border: none; color: rgba(255,255,255,0.5);
  padding: 10px 20px; cursor: pointer; font-size: 14px;
  border-bottom: 2px solid transparent; transition: all 0.2s;
}
.tab-btn:hover { color: #00d4ff; }
.tab-btn.active {
  color: #00d4ff;
  border-bottom-color: #00d4ff;
}


</style>
