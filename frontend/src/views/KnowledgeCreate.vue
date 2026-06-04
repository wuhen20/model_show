<template>
  <div class="app-layout">
    <Header title="人工智能分部 · 模型微调组" subtitle="新建知识库" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="create-layout">
          <!-- Left: Step Nav -->
          <aside class="step-sidebar">
            <div class="step-nav">
              <div
                v-for="(s, idx) in steps"
                :key="idx"
                class="step-nav-item"
                :class="{ active: step === idx + 1, done: step > idx + 1 }"
                @click="step > idx + 1 && (step = idx + 1)"
              >
                <span class="step-nav-dot">{{ idx + 1 }}</span>
                <span class="step-nav-label">{{ s }}</span>
              </div>
            </div>
          </aside>

          <!-- Right: Form -->
          <section class="step-content">
            <div class="step-scroll">
              <!-- Step 1: Basic Info -->
              <div v-if="step === 1" class="step-body">
                <h2 class="step-title">基本信息</h2>
                <p class="step-desc">设置知识库的名称、描述、图标和颜色</p>
                <div class="form-grid">
                  <div class="form-group wide">
                    <label class="form-label">知识库名称 <span class="required">*</span></label>
                    <el-input v-model="form.name" placeholder="请输入知识库名称" maxlength="50" show-word-limit />
                  </div>
                  <div class="form-group wide">
                    <label class="form-label">描述</label>
                    <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入知识库描述" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">图标</label>
                    <IconSelector v-model="form.icon" :color="form.color" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">颜色</label>
                    <ColorSelector v-model="form.color" />
                  </div>
                </div>
              </div>

              <!-- Step 2: Tag System -->
              <div v-if="step === 2" class="step-body">
                <h2 class="step-title">标签体系</h2>
                <p class="step-desc">构建多级标签分类，上传文件时可按标签组织检索</p>
                <div class="tag-toolbar">
                  <el-button size="small" @click="addRootTag">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    添加根标签
                  </el-button>
                </div>
                <div class="tag-tree-area">
                  <TagNode
                    v-for="(tag, idx) in form.tags"
                    :key="idx"
                    :tag="tag"
                    :depth="1"
                    @remove="removeTag(idx)"
                    @add-child="addChildTag"
                  />
                  <div v-if="!form.tags.length" class="tag-empty">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1.5">
                      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01"/>
                    </svg>
                    <p>暂无标签</p>
                    <p class="sub">标签支持无限层级嵌套，子标签选中时自动关联父级</p>
                  </div>
                </div>
              </div>

              <!-- Step 3: Chunking Config -->
              <div v-if="step === 3" class="step-body">
                <h2 class="step-title">切片配置</h2>
                <p class="step-desc">设置文本切片策略与分隔符，影响向量化检索粒度</p>
                <div class="config-grid">
                  <div class="config-left">
                    <div class="form-group">
                      <label class="form-label">切片策略</label>
                      <div class="strategy-cards">
                        <div
                          class="strategy-card"
                          :class="{ active: form.chunking_strategy === 'basic' }"
                          @click="form.chunking_strategy = 'basic'"
                        >
                          <div class="strategy-icon">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                          </div>
                          <div class="strategy-name">基础切片</div>
                          <div class="strategy-desc">按固定大小切分文本</div>
                        </div>
                        <div
                          class="strategy-card"
                          :class="{ active: form.chunking_strategy === 'parent_child' }"
                          @click="form.chunking_strategy = 'parent_child'"
                        >
                          <div class="strategy-icon">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="6" rx="1"/><rect x="5" y="12" width="6" height="9" rx="1"/><rect x="13" y="12" width="6" height="9" rx="1"/></svg>
                          </div>
                          <div class="strategy-name">父子切片</div>
                          <div class="strategy-desc">大段保留上下文，小段精准检索</div>
                        </div>
                      </div>
                    </div>

                    <div class="form-group">
                      <label class="form-label">切片分隔符</label>
                      <p class="form-hint">文本将按分隔符优先切分，再按大小二次切分</p>
                      <div class="separator-grid">
                        <div
                          v-for="opt in separatorOptions"
                          :key="opt.value"
                          class="separator-option"
                          :class="{ active: form.chunk_separator === opt.value }"
                          @click="form.chunk_separator = opt.value"
                        >
                          <span class="sep-preview">{{ opt.preview }}</span>
                          <span class="sep-label">{{ opt.label }}</span>
                        </div>
                      </div>
                      <div class="custom-separator">
                        <el-input
                          v-model="customSeparator"
                          placeholder="自定义分隔符（如：===、---、## 等）"
                          size="small"
                          @input="onCustomSeparatorInput"
                        />
                      </div>
                    </div>

                    <div class="form-row">
                      <div class="form-group half">
                        <label class="form-label">切片大小</label>
                        <el-input-number v-model="form.chunk_size" :min="100" :max="3000" :step="100" size="small" />
                      </div>
                      <div class="form-group half">
                        <label class="form-label">切片重叠</label>
                        <el-input-number v-model="form.chunk_overlap" :min="0" :max="500" :step="10" size="small" />
                      </div>
                    </div>
                    <div v-if="form.chunking_strategy === 'parent_child'" class="form-group">
                      <label class="form-label">父切片大小（保留更大上下文）</label>
                      <el-input-number v-model="form.parent_chunk_size" :min="500" :max="5000" :step="100" size="small" />
                    </div>
                  </div>

                  <div class="config-right">
                    <div class="summary-card">
                      <div class="summary-title">创建预览</div>
                      <div class="summary-row">
                        <span class="summary-key">名称</span>
                        <strong>{{ form.name || '—' }}</strong>
                      </div>
                      <div class="summary-row">
                        <span class="summary-key">图标</span>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" :stroke="form.color" stroke-width="2">
                          <path :d="getIconPath(form.icon)"/>
                        </svg>
                      </div>
                      <div class="summary-row">
                        <span class="summary-key">颜色</span>
                        <span class="color-dot" :style="{ background: form.color }"></span>
                        <span style="font-size:12px;color:rgba(255,255,255,0.5)">{{ form.color }}</span>
                      </div>
                      <div class="summary-row">
                        <span class="summary-key">标签</span>
                        <div class="summary-tags" v-if="form.tags.length">
                          <span v-for="t in flattenTags(form.tags)" :key="t" class="sum-tag">{{ t }}</span>
                        </div>
                        <span v-else style="color:rgba(255,255,255,0.35)">无</span>
                      </div>
                      <div class="summary-divider"></div>
                      <div class="summary-row">
                        <span class="summary-key">切片策略</span>
                        <strong>{{ form.chunking_strategy === 'basic' ? '基础切片' : '父子切片' }}</strong>
                      </div>
                      <div class="summary-row">
                        <span class="summary-key">分隔符</span>
                        <strong class="sep-display">{{ displaySeparator(form.chunk_separator) }}</strong>
                      </div>
                      <div class="summary-row">
                        <span class="summary-key">切片大小</span>
                        <strong>{{ form.chunk_size }}</strong>
                      </div>
                      <div class="summary-row">
                        <span class="summary-key">重叠</span>
                        <strong>{{ form.chunk_overlap }}</strong>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Bottom action bar -->
            <div class="step-footer">
              <el-button v-if="step > 1" @click="step--">上一步</el-button>
              <el-button v-if="step === 1" @click="router.push('/knowledge-management?tab=management')">取消</el-button>
              <div class="footer-spacer"></div>
              <el-button v-if="step < 3" type="primary" :disabled="step === 1 && !form.name" @click="step++">下一步</el-button>
              <el-button v-if="step === 3" type="primary" :loading="saving" @click="handleCreate">创建知识库</el-button>
            </div>
          </section>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import IconSelector from '@/components/IconSelector.vue'
import ColorSelector from '@/components/ColorSelector.vue'
import TagNode from '@/components/TagNode.vue'
import { createKnowledgeBase, type TagCreatePayload } from '@/api/knowledge'
import { ElMessage } from 'element-plus'

const router = useRouter()
const step = ref(1)
const saving = ref(false)
const customSeparator = ref('')
const steps = ['基本信息', '标签体系', '切片配置']

interface TagFormNode {
  name: string
  children: TagFormNode[]
}

const form = reactive({
  name: '',
  description: '',
  icon: 'brain',
  color: '#00d4ff',
  chunking_strategy: 'basic' as string,
  chunk_size: 500,
  chunk_overlap: 50,
  parent_chunk_size: 1500,
  chunk_separator: '\n\n',
  tags: [] as TagFormNode[],
})

const separatorOptions = [
  { value: '\n\n', preview: '¶¶', label: '双换行' },
  { value: '\n', preview: '¶', label: '单换行' },
  { value: '。', preview: '。', label: '句号' },
  { value: '！', preview: '！', label: '叹号' },
  { value: '？', preview: '？', label: '问号' },
  { value: '；', preview: '；', label: '分号' },
  { value: '---', preview: '---', label: '三横线' },
  { value: '###', preview: '###', label: '三级标题' },
  { value: '##', preview: '##', label: '二级标题' },
]

function onCustomSeparatorInput(val: string) {
  if (val) form.chunk_separator = val
}

function displaySeparator(sep: string): string {
  const opt = separatorOptions.find(o => o.value === sep)
  if (opt) return `${opt.label} (${JSON.stringify(sep)})`
  return JSON.stringify(sep)
}

function addRootTag() { form.tags.push({ name: '', children: [] }) }
function removeTag(idx: number) { form.tags.splice(idx, 1) }
function addChildTag(parent: TagFormNode) { parent.children.push({ name: '', children: [] }) }

function flattenTags(tags: TagFormNode[], prefix = ''): string[] {
  const result: string[] = []
  for (const t of tags) {
    const path = prefix ? `${prefix} > ${t.name || '(未命名)'}` : (t.name || '(未命名)')
    result.push(path)
    if (t.children.length) result.push(...flattenTags(t.children, t.name || '(未命名)'))
  }
  return result
}

function buildTagPayload(tags: TagFormNode[], level: number = 1): TagCreatePayload[] {
  return tags.filter(t => t.name.trim()).map(t => ({
    level,
    name: t.name.trim(),
    children: buildTagPayload(t.children, level + 1),
  }))
}

function getIconPath(iconName: string): string {
  const icons: Record<string, string> = {
    brain: 'M12 2a8 8 0 0 0-8 8c0 3.4 2.1 6.3 5 7.5V20h6v-2.5c2.9-1.2 5-4.1 5-7.5a8 8 0 0 0-8-8z',
    plug: 'M12 22V8M5 12H2a10 10 0 0 0 20 0h-3',
    database: 'M4 20h16v-2H4v2zm0-6h16v-2H4v2zm0-6h16V6H4v2z',
    scale: 'M12 3v18M3 12h18M5.5 5.5l13 13M18.5 5.5l-13 13',
    'trending-down': 'M23 18l-9.5-9.5-5 5L1 6',
    shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
    book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z',
    'file-text': 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8',
    layers: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
    cpu: 'M6 3v3M10 3v3M14 3v3M18 3v3M6 21v-3M10 21v-3M14 21v-3M18 21v-3M3 6h3M3 10h3M3 14h3M3 18h3M21 6h-3M21 10h-3M21 14h-3M21 18h-3M6 6h12v12H6z',
    globe: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z',
    zap: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
    target: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 6v6l4 2',
    search: 'M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM21 21l-4.35-4.35',
    code: 'M16 18l6-6-6-6M8 6l-6 6 6 6',
    box: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zM3.27 6.96L12 12.01l8.73-5.05M12 22.08V12',
    share: 'M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8M16 6l-4-4-4 4M12 2v13',
    cog: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z',
    link: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71',
    feather: 'M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5zM16 8L2 22M17.5 15H9',
    'git-branch': 'M6 3v6M6 21v-4a2 2 0 0 1 2-2h4M18 3a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM6 9a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM18 7v4a2 2 0 0 1-2 2H10',
  }
  return icons[iconName] || icons.brain
}

async function handleCreate() {
  saving.value = true
  try {
    const tags = buildTagPayload(form.tags)
    await createKnowledgeBase({
      name: form.name, description: form.description, icon: form.icon, color: form.color,
      chunk_size: form.chunk_size, chunk_overlap: form.chunk_overlap,
      chunking_strategy: form.chunking_strategy, parent_chunk_size: form.parent_chunk_size,
      chunk_separator: form.chunk_separator, tags,
    })
    ElMessage.success('知识库创建成功')
    router.push('/knowledge-management?tab=management')
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.app-layout { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
.main-content { display: flex; flex: 1; overflow: hidden; min-height: 0; }
.content-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 0; min-height: 0; }

/* --- Full-height layout --- */
.create-layout {
  flex: 1; display: flex; overflow: hidden;
}

/* Left sidebar: step nav */
.step-sidebar {
  width: 200px; flex-shrink: 0;
  background: linear-gradient(180deg, rgba(17,24,39,0.95) 0%, rgba(10,14,26,0.9) 100%);
  border-right: 1px solid rgba(0,212,255,0.12);
  padding: 28px 0; display: flex; flex-direction: column;
}
.step-nav { display: flex; flex-direction: column; gap: 4px; padding: 0 12px; }
.step-nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px; border-radius: 10px; cursor: default;
  transition: all 0.25s; position: relative;
}
.step-nav-item.done { cursor: pointer; }
.step-nav-item:hover.done { background: rgba(0,255,136,0.06); }
.step-nav-item.active { background: rgba(0,212,255,0.1); }
.step-nav-dot {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; flex-shrink: 0;
  background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.35);
  border: 2px solid rgba(255,255,255,0.1);
  transition: all 0.25s;
}
.step-nav-item.active .step-nav-dot {
  border-color: #00d4ff; color: #00d4ff; background: rgba(0,212,255,0.15);
  box-shadow: 0 0 12px rgba(0,212,255,0.25);
}
.step-nav-item.done .step-nav-dot {
  border-color: #00ff88; color: #00ff88; background: rgba(0,255,136,0.15);
}
.step-nav-label { font-size: 14px; color: rgba(255,255,255,0.45); font-weight: 500; }
.step-nav-item.active .step-nav-label { color: #fff; }
.step-nav-item.done .step-nav-label { color: rgba(255,255,255,0.7); }

/* Right: form area */
.step-content {
  flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0;
}
.step-scroll {
  flex: 1; overflow-y: auto; padding: 28px 32px 20px;
}
.step-body { animation: fadeIn 0.25s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

.step-title { font-size: 22px; font-weight: 600; color: #fff; margin: 0 0 6px; }
.step-desc { font-size: 13px; color: rgba(255,255,255,0.45); margin: 0 0 24px; line-height: 1.5; }

/* Form grid */
.form-grid { display: flex; flex-direction: column; gap: 4px; }
.form-group { margin-bottom: 20px; }
.form-group.wide { max-width: 600px; }
.form-label { display: block; font-size: 13px; font-weight: 500; color: rgba(255,255,255,0.7); margin-bottom: 8px; }
.form-hint { font-size: 12px; color: rgba(255,255,255,0.35); margin: 0 0 10px; line-height: 1.5; }
.required { color: #ff5555; }
.form-row { display: flex; gap: 16px; }
.form-group.half { flex: 1; }

/* Tag system */
.tag-toolbar { margin-bottom: 12px; }
.tag-tree-area {
  background: rgba(255,255,255,0.03); border-radius: 10px; padding: 18px;
  border: 1px solid rgba(0,212,255,0.1); min-height: 200px;
}
.tag-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 40px 20px; text-align: center;
  color: rgba(255,255,255,0.35); font-size: 14px;
}
.tag-empty .sub { font-size: 12px; color: rgba(255,255,255,0.25); margin-top: 4px; }

/* Config grid: left = form, right = summary */
.config-grid {
  display: grid; grid-template-columns: 1fr 320px; gap: 28px; align-items: start;
}
.config-left { min-width: 0; }

/* Strategy cards */
.strategy-cards { display: flex; gap: 12px; margin-bottom: 4px; }
.strategy-card {
  flex: 1; padding: 18px; border-radius: 10px; cursor: pointer;
  background: rgba(255,255,255,0.03); border: 1px solid rgba(0,212,255,0.12);
  transition: all 0.25s; text-align: center;
}
.strategy-card:hover { border-color: rgba(0,212,255,0.3); background: rgba(255,255,255,0.05); }
.strategy-card.active {
  border-color: #00d4ff; background: rgba(0,212,255,0.1);
  box-shadow: 0 0 16px rgba(0,212,255,0.12);
}
.strategy-icon { margin-bottom: 8px; color: rgba(255,255,255,0.5); }
.strategy-card.active .strategy-icon { color: #00d4ff; }
.strategy-name { font-size: 14px; font-weight: 600; color: rgba(255,255,255,0.7); margin-bottom: 4px; }
.strategy-card.active .strategy-name { color: #fff; }
.strategy-desc { font-size: 11px; color: rgba(255,255,255,0.35); }

/* Separator */
.separator-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.separator-option {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 10px 14px; border-radius: 8px; cursor: pointer;
  background: rgba(255,255,255,0.04); border: 1px solid rgba(0,212,255,0.12);
  transition: all 0.2s; min-width: 72px;
}
.separator-option:hover { border-color: rgba(0,212,255,0.35); background: rgba(255,255,255,0.06); }
.separator-option.active { border-color: #00d4ff; background: rgba(0,212,255,0.12); box-shadow: 0 0 12px rgba(0,212,255,0.15); }
.sep-preview { font-size: 16px; font-weight: 600; color: #00d4ff; font-family: 'Consolas','Monaco',monospace; }
.separator-option.active .sep-preview { color: #fff; }
.sep-label { font-size: 11px; color: rgba(255,255,255,0.5); }
.separator-option.active .sep-label { color: rgba(255,255,255,0.7); }
.custom-separator { max-width: 320px; }

/* Summary card */
.summary-card {
  background: rgba(0,212,255,0.04); border-radius: 10px; padding: 20px;
  border: 1px solid rgba(0,212,255,0.15); position: sticky; top: 0;
}
.summary-title { font-size: 14px; font-weight: 600; color: #00d4ff; margin-bottom: 14px; }
.summary-row { font-size: 13px; color: rgba(255,255,255,0.55); margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.summary-row strong { color: #fff; font-weight: 500; }
.summary-key { min-width: 56px; color: rgba(255,255,255,0.4); font-size: 12px; }
.summary-divider { height: 1px; background: rgba(0,212,255,0.12); margin: 12px 0; }
.color-dot { width: 14px; height: 14px; border-radius: 50%; display: inline-block; }
.sep-display { font-family: 'Consolas','Monaco',monospace; font-size: 11px; background: rgba(0,212,255,0.1); padding: 2px 8px; border-radius: 3px; }
.summary-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.sum-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.7); }

/* Footer bar */
.step-footer {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 32px; border-top: 1px solid rgba(0,212,255,0.1);
  background: rgba(17,24,39,0.6);
}
.footer-spacer { flex: 1; }
</style>
