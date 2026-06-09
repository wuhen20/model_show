<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { datasetsApi } from '@/api/datasets'
import type { YoloPreviewItem } from '@/data/models'

const props = defineProps<{
  dsId: number
}>()

const items = ref<YoloPreviewItem[]>([])
const loading = ref(false)
const errorMsg = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)

// 放大查看
const enlarged = ref<YoloPreviewItem | null>(null)

// 预定义 10 种颜色
const COLORS = [
  '#00d4ff', '#00ff88', '#ffaa00', '#ff5555', '#a855f7',
  '#f97316', '#06b6d4', '#ec4899', '#84cc16', '#f43f5e',
]

function getColor(classId: number): string {
  return COLORS[classId % COLORS.length]
}

async function loadPage() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await datasetsApi.yoloPreview(props.dsId, page.value, pageSize)
    items.value = res.items
    total.value = res.total
  } catch (e: any) {
    errorMsg.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goPage(p: number) {
  page.value = p
  loadPage()
}

function drawBoxesOnCanvas(canvas: HTMLCanvasElement, imageUrl: string, objects: YoloPreviewItem['objects']) {
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    if (!canvas.classList.contains('yolo-canvas-enlarged')) {
      canvas.style.width = '100%'
      canvas.style.maxWidth = '400px'
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.drawImage(img, 0, 0)

    for (const obj of objects) {
      const color = getColor(obj.class_id)
      const x = (obj.cx - obj.w / 2) * img.naturalWidth
      const y = (obj.cy - obj.h / 2) * img.naturalHeight
      const w = obj.w * img.naturalWidth
      const h = obj.h * img.naturalHeight

      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.strokeRect(x, y, w, h)

      const label = `${obj.class_name} (${obj.class_id})`
      ctx.font = '12px monospace'
      const textWidth = ctx.measureText(label).width
      const textHeight = 16
      ctx.fillStyle = color
      ctx.fillRect(x, y - textHeight - 2, textWidth + 6, textHeight + 4)
      ctx.fillStyle = '#000'
      ctx.fillText(label, x + 3, y - 4)
    }
  }
  img.src = imageUrl
}

function drawBoxes(item: YoloPreviewItem, canvasId: string) {
  const canvas = document.getElementById(canvasId) as HTMLCanvasElement | null
  if (!canvas) return
  drawBoxesOnCanvas(canvas, item.image_url, item.objects)
}

function openEnlarged(item: YoloPreviewItem) {
  enlarged.value = item
  // 等 DOM 渲染后绘制
  setTimeout(() => {
    const canvas = document.getElementById('yolo-canvas-enlarged') as HTMLCanvasElement | null
    if (canvas && enlarged.value) {
      drawBoxesOnCanvas(canvas, enlarged.value.image_url, enlarged.value.objects)
    }
  }, 50)
}

const totalPages = ref(0)

watch(() => items.value, () => {
  totalPages.value = Math.ceil(total.value / pageSize)
  // 延迟绘制 Canvas（等待 DOM 渲染）
  setTimeout(() => {
    for (let i = 0; i < items.value.length; i++) {
      drawBoxes(items.value[i], `yolo-canvas-${page.value}-${i}`)
    }
  }, 100)
})

onMounted(loadPage)
</script>

<template>
  <div class="yolo-preview">
    <div v-if="errorMsg" class="error-bar">⚠ {{ errorMsg }}</div>
    <div v-if="loading" class="loading">加载中…</div>

    <div v-if="!loading && items.length" class="preview-grid">
      <div v-for="(item, idx) in items" :key="item.image_file" class="preview-card">
        <canvas
          :id="`yolo-canvas-${page}-${idx}`"
          class="yolo-canvas"
          @click="openEnlarged(item)"
        />
        <div class="card-info">
          <span class="img-name">{{ item.image_file }}</span>
          <span class="box-count">{{ item.objects.length }} 个框</span>
        </div>
      </div>
    </div>

    <div v-if="!loading && !items.length" class="empty">暂无标注图片</div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="pagination">
      <button :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <span class="page-info">{{ page }} / {{ totalPages }}</span>
      <button :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
    </div>

    <!-- 放大查看 -->
    <div v-if="enlarged" class="enlarge-overlay" @click="enlarged = null">
      <div class="enlarge-box" @click.stop>
        <canvas
          id="yolo-canvas-enlarged"
          class="yolo-canvas-enlarged"
        />
        <button class="close-btn" @click="enlarged = null">✕</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.yolo-preview { min-height: 200px; }
.error-bar { padding: 10px; background: rgba(255,80,80,0.15); border: 1px solid #ff5555; border-radius: 6px; margin-bottom: 16px; }
.loading, .empty { padding: 40px; text-align: center; color: rgba(255,255,255,0.5); }

.preview-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.preview-card {
  background: rgba(17,24,39,0.4); border: 1px solid rgba(0,212,255,0.15);
  border-radius: 8px; overflow: hidden; cursor: pointer; transition: all 0.2s;
}
.preview-card:hover { border-color: #00d4ff; }

.yolo-canvas { display: block; width: 100%; max-width: 400px; margin: 0 auto; }

.card-info { display: flex; justify-content: space-between; padding: 8px 12px; }
.img-name { font-size: 12px; color: rgba(255,255,255,0.7); max-width: 70%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.box-count { font-size: 12px; color: #00d4ff; }

/* 分页 */
.pagination { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px; }
.pagination button {
  padding: 6px 16px; background: rgba(0,212,255,0.15); color: #00d4ff;
  border: 1px solid rgba(0,212,255,0.3); border-radius: 6px;
  cursor: pointer; font-size: 13px;
}
.pagination button:disabled { opacity: 0.3; cursor: not-allowed; }
.pagination button:hover:not(:disabled) { background: rgba(0,212,255,0.25); }
.page-info { color: rgba(255,255,255,0.7); font-size: 13px; }

/* 放大查看 */
.enlarge-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.8);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
}
.enlarge-box { position: relative; max-width: 90vw; max-height: 90vh; }
.yolo-canvas-enlarged { max-width: 90vw; max-height: 90vh; }
.close-btn {
  position: absolute; top: -12px; right: -12px;
  width: 32px; height: 32px; border-radius: 50%;
  background: rgba(255,80,80,0.8); color: #fff;
  border: none; cursor: pointer; font-size: 16px; display: flex; align-items: center; justify-content: center;
}
.close-btn:hover { background: #ff5555; }
</style>