<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { fetchModels, sendChat, sendChatStream, sendChatWithFile, type ModelInfo, type ChatResponse } from '@/api/chat'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  suggestions?: string[]
  tokens?: number
  file?: { name: string; size: number; url: string }
  timestamp: string
}

const models = ref<ModelInfo[]>([])
const selectedModel = ref('')
const inputText = ref('')
const messages = ref<Message[]>([])
const loading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadedFile = ref<File | null>(null)
const modelDropdownOpen = ref(false)

const selectedModelName = ref('选择模型')
const modelSelectorRef = ref<HTMLElement | null>(null)

function handleClickOutside(e: MouseEvent) {
  if (modelSelectorRef.value && !modelSelectorRef.value.contains(e.target as Node)) {
    modelDropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  loadModels()
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

async function loadModels() {
  try {
    const list = await fetchModels()
    models.value = list
    if (list.length > 0) {
      selectedModel.value = list[0].id
      selectedModelName.value = list[0].name
    }
  } catch {
    models.value = [
      { id: 'qwen-plus', name: 'Qwen2-72B', type: '语言模型', description: '通义千问2 72B，高性能语言模型，支持复杂对话与分析' },
      { id: 'qwen-vl-plus', name: 'Qwen-VL-Plus', type: '视觉模型', description: '通义千问VL Plus，多模态视觉理解与图像分析' }
    ]
    selectedModel.value = models.value[0].id
    selectedModelName.value = models.value[0].name
  }
}

function selectModel(model: ModelInfo) {
  selectedModel.value = model.id
  selectedModelName.value = model.name
  modelDropdownOpen.value = false
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function triggerFileUpload() {
  fileInput.value?.click()
}

function handleFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    uploadedFile.value = target.files[0]
  }
}

function removeFile() {
  uploadedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1048576).toFixed(1) + 'MB'
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text && !uploadedFile.value) return

  const userMsg: Message = {
    id: Date.now().toString(),
    role: 'user',
    content: text || '[图片/文件]',
    timestamp: new Date().toLocaleTimeString()
  }
  if (uploadedFile.value) {
    userMsg.file = {
      name: uploadedFile.value.name,
      size: uploadedFile.value.size,
      url: ''
    }
  }

  messages.value.push(userMsg)
  inputText.value = ''
  scrollToBottom()

  loading.value = true
  try {
    if (uploadedFile.value) {
      // 带文件上传的请求仍使用普通方式
      const result = await sendChatWithFile(selectedModel.value, text, uploadedFile.value)
      
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: result.content,
        suggestions: result.suggestions,
        tokens: result.tokens,
        timestamp: new Date().toLocaleTimeString(),
        file: result.file
      }
      messages.value.push(assistantMsg)
    } else {
        // 文本请求使用流式输出
        const assistantMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: '',
          suggestions: [],
          tokens: 0,
          timestamp: new Date().toLocaleTimeString()
        }
        messages.value.push(assistantMsg)
        
        console.log('[Home] 开始送ChatStream, modelId:', selectedModel.value, 'question:', text)
        await sendChatStream(
          { modelId: selectedModel.value, question: text },
          (chunk) => {
            console.log('[Home] 收到chunk:', chunk)
            assistantMsg.content += chunk
            // 触发Vue更新：通过替换整个数组来强制刷新
            messages.value = [...messages.value]
            scrollToBottom()
          },
          (meta) => {
            console.log('[Home] 收到meta:', meta)
            assistantMsg.tokens = meta.tokens
            assistantMsg.timestamp = new Date().toLocaleTimeString()
            // 触发Vue更新
            messages.value = [...messages.value]
            scrollToBottom()
          },
          (error) => {
            console.log('[Home] 收到error:', error)
            assistantMsg.content = `请求失败: ${error}`
            // 触发Vue更新
            messages.value = [...messages.value]
            scrollToBottom()
          }
        )
      }
  } catch (error: any) {
    const errorMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: error.message || '抱歉，服务暂时不可用，请稍后重试。如持续遇到此问题，请检查后端服务是否已启动。',
      timestamp: new Date().toLocaleTimeString()
    }
    messages.value.push(errorMsg)
  } finally {
    loading.value = false
    uploadedFile.value = null
    if (fileInput.value) fileInput.value.value = ''
    scrollToBottom()
  }
}

function autoResize(e: Event) {
  const target = e.target as HTMLTextAreaElement
  target.style.height = 'auto'
  target.style.height = Math.min(target.scrollHeight, 120) + 'px'
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function useSuggestion(text: string) {
  inputText.value = text
  sendMessage()
}
</script>

<template>
  <div class="app-layout">
    <Header title="人工智能分部 · 模型微调组" subtitle="智能问答工作台" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="chat-header">
          <div ref="modelSelectorRef" class="model-selector">
            <button class="model-select-btn" @click="modelDropdownOpen = !modelDropdownOpen">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
              </svg>
              <span class="model-name">{{ selectedModelName }}</span>
              <svg
                width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                :class="{ rotated: modelDropdownOpen }"
              >
                <path d="M6 9l6 6 6-6"/>
              </svg>
            </button>
            <div v-if="modelDropdownOpen" class="model-dropdown">
              <div
                v-for="model in models" :key="model.id"
                class="model-option"
                :class="{ active: selectedModel === model.id }"
                @click="selectModel(model)"
              >
                <div class="model-option-info">
                  <span class="model-option-name">{{ model.name }}</span>
                  <span class="model-option-type">{{ model.type }}</span>
                </div>
                <svg v-if="selectedModel === model.id" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="3">
                  <path d="M20 6L9 17l-5-5"/>
                </svg>
              </div>
            </div>
          </div>
          <span class="chat-subtitle">基于大模型的电力业务智能问答</span>
        </div>

        <div ref="chatContainer" class="chat-messages">
          <div v-if="messages.length === 0" class="empty-state">
            <div class="empty-icon">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="1" opacity="0.4">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                <line x1="9" y1="10" x2="15" y2="10" stroke="#00d4ff" stroke-width="1.5" opacity="0.6"/>
                <line x1="12" y1="7" x2="12" y2="13" stroke="#00d4ff" stroke-width="1.5" opacity="0.6"/>
              </svg>
            </div>
            <h3 class="empty-title">你好，我是阿良</h3>
            <p class="empty-desc">选择一个模型，输入您的问题，即可获得AI驱动的业务智能分析</p>
            <div class="quick-prompts">
              <button
                v-for="prompt in ['台区线损异常分析', '设备缺陷智能识别', '负荷预测与优化', '采集自愈诊断']"
                :key="prompt"
                class="prompt-btn"
                @click="useSuggestion(prompt)"
              >
                {{ prompt }}
              </button>
            </div>
          </div>

          <div v-for="msg in messages" :key="msg.id" class="message" :class="msg.role">
            <div class="message-avatar">
              <svg v-if="msg.role === 'user'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
              <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
              </svg>
            </div>
            <div class="message-body">
              <div class="message-header">
                <span class="message-role">{{ msg.role === 'user' ? '我' : selectedModelName }}</span>
                <span class="message-time">{{ msg.timestamp }}</span>
              </div>
              <div v-if="msg.file" class="message-file">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span>{{ msg.file.name }}</span>
              </div>
              <div class="message-content" v-html="msg.content.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')"></div>
              <div v-if="msg.tokens" class="message-footer">
                <span class="token-info">{{ msg.tokens }} tokens</span>
              </div>
              <div v-if="msg.suggestions && msg.suggestions.length > 0" class="message-suggestions">
                <span class="suggestions-label">推荐操作</span>
                <div class="suggestions-list">
                  <button
                    v-for="s in msg.suggestions"
                    :key="s"
                    class="suggestion-btn"
                    @click="useSuggestion(s)"
                  >
                    {{ s }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="loading" class="message assistant">
            <div class="message-avatar">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
              </svg>
            </div>
            <div class="message-body">
              <div class="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <div v-if="uploadedFile" class="file-preview">
            <div class="file-info">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <span class="file-name">{{ uploadedFile.name }}</span>
              <span class="file-size">{{ formatFileSize(uploadedFile.size) }}</span>
            </div>
            <button class="file-remove" @click="removeFile">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="input-row">
            <button class="upload-btn" @click="triggerFileUpload" title="上传图片或文件">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
            </button>
            <input
              ref="fileInput"
              type="file"
              accept="image/*,.pdf,.doc,.docx,.txt,.csv,.json"
              style="display: none"
              @change="handleFileChange"
            />
            <textarea
              v-model="inputText"
              class="chat-input"
              placeholder="输入您的问题，例如：请分析台区本月线损异常原因..."
              rows="1"
              @keydown="handleKeydown"
              @input="autoResize"
            ></textarea>
            <button
              class="send-btn"
              :class="{ disabled: !inputText.trim() && !uploadedFile }"
              :disabled="!inputText.trim() && !uploadedFile"
              @click="sendMessage"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  background: radial-gradient(circle at 50% 30%, rgba(0, 212, 255, 0.03) 0%, transparent 60%);
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
  flex-shrink: 0;
}

.model-selector {
  position: relative;
}

.model-select-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.25);
  border-radius: 8px;
  color: #00d4ff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.model-select-btn:hover {
  background: rgba(0, 212, 255, 0.2);
  border-color: rgba(0, 212, 255, 0.4);
}

.model-select-btn svg.rotated {
  transform: rotate(180deg);
}

.model-name {
  font-weight: 500;
}

.model-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  min-width: 260px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.98) 0%, rgba(26, 35, 50, 0.98) 100%);
  border: 1px solid rgba(0, 212, 255, 0.25);
  border-radius: 10px;
  padding: 6px;
  z-index: 100;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.model-option:hover {
  background: rgba(0, 212, 255, 0.1);
}

.model-option.active {
  background: rgba(0, 212, 255, 0.15);
}

.model-option-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.model-option-name {
  font-size: 13px;
  color: #fff;
  font-weight: 500;
}

.model-option-type {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.chat-subtitle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.empty-icon {
  margin-bottom: 8px;
}

.empty-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

.empty-desc {
  margin: 0;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  max-width: 400px;
  text-align: center;
}

.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-top: 8px;
}

.prompt-btn {
  padding: 8px 18px;
  background: rgba(0, 212, 255, 0.08);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 20px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.prompt-btn:hover {
  background: rgba(0, 212, 255, 0.18);
  border-color: rgba(0, 212, 255, 0.4);
  color: #00d4ff;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 80%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant {
  align-self: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.message.assistant .message-avatar {
  background: rgba(0, 255, 136, 0.15);
  color: #00ff88;
}

.message-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 18px;
  border-radius: 12px;
}

.message.user .message-body {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.2) 0%, rgba(0, 170, 255, 0.1) 100%);
  border: 1px solid rgba(0, 212, 255, 0.3);
}

.message.assistant .message-body {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.15);
}

.message-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.message-role {
  font-size: 12px;
  font-weight: 600;
  color: #00d4ff;
}

.message-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.message-file {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(0, 212, 255, 0.08);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
}

.message-content {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.7;
}

.message-content :deep(strong) {
  color: #fff;
  font-weight: 600;
}

.message-footer {
  display: flex;
  align-items: center;
}

.token-info {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.message-suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 212, 255, 0.1);
}

.suggestions-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.suggestions-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.suggestion-btn {
  padding: 6px 14px;
  background: rgba(0, 212, 255, 0.08);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 16px;
  color: #00d4ff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.suggestion-btn:hover {
  background: rgba(0, 212, 255, 0.18);
  border-color: rgba(0, 212, 255, 0.4);
}

.typing-indicator {
  display: flex;
  gap: 5px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 7px;
  height: 7px;
  background: #00d4ff;
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1.1); }
}

.chat-input-area {
  padding: 16px 24px;
  border-top: 1px solid rgba(0, 212, 255, 0.1);
  flex-shrink: 0;
}

.file-preview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  margin-bottom: 10px;
  background: rgba(0, 212, 255, 0.08);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 8px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.file-name {
  color: #fff;
}

.file-size {
  color: rgba(255, 255, 255, 0.5);
}

.file-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: rgba(255, 85, 85, 0.15);
  border: 1px solid rgba(255, 85, 85, 0.3);
  border-radius: 50%;
  color: #ff5555;
  cursor: pointer;
  transition: all 0.3s ease;
}

.file-remove:hover {
  background: rgba(255, 85, 85, 0.3);
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 8px 14px;
  background: rgba(17, 24, 39, 0.8);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
}

.upload-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 8px;
  color: #00d4ff;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.upload-btn:hover {
  background: rgba(0, 212, 255, 0.2);
  border-color: rgba(0, 212, 255, 0.4);
}

.chat-input {
  flex: 1;
  padding: 8px 0;
  background: transparent;
  border: none;
  outline: none;
  color: #fff;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  max-height: 120px;
  line-height: 1.5;
}

.chat-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.send-btn:hover:not(.disabled) {
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.4);
  transform: scale(1.05);
}

.send-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
  background: rgba(255, 255, 255, 0.1);
}
</style>