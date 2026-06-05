<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import type { BoundingBox } from '@/api/chat'

interface Transform {
  scale: number
  translateX: number
  translateY: number
}

const props = defineProps<{
  imageSrc: string | null
  annotations?: BoundingBox[]
  labelColors?: Record<string, string>
  highlightIndex?: number
}>()

const emit = defineEmits<{
  (e: 'update:transform', val: Transform): void
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)

const transform = ref<Transform>({ scale: 1, translateX: 0, translateY: 0 })
const image = ref<HTMLImageElement | null>(null)
const isDragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })

function loadImage(src: string) {
  const img = new Image()
  img.onload = () => {
    image.value = img
    resetView()
    render()
  }
  img.src = src
}

watch(() => props.imageSrc, (src) => {
  if (src) loadImage(src)
  else { image.value = null; render() }
})

watch(() => [props.annotations, props.highlightIndex], () => render(), { deep: true })

watch(transform, (val) => {
  emit('update:transform', { ...val })
  render()
}, { deep: true })

// 外部同步 transform
function applyTransform(t: Transform) {
  if (t.scale !== transform.value.scale || t.translateX !== transform.value.translateX || t.translateY !== transform.value.translateY) {
    transform.value = { ...t }
  }
}

defineExpose({ resetView, zoomIn, zoomOut, applyTransform, getTransform: () => ({ ...transform.value }) })

function resetView() {
  const canvas = canvasRef.value
  if (!canvas || !image.value) {
    transform.value = { scale: 1, translateX: 0, translateY: 0 }
    return
  }
  const cw = canvas.width
  const ch = canvas.height
  const iw = image.value.naturalWidth
  const ih = image.value.naturalHeight
  const scale = Math.min(cw / iw, ch / ih, 1)
  const tx = (cw - iw * scale) / 2
  const ty = (ch - ih * scale) / 2
  transform.value = { scale, translateX: tx, translateY: ty }
}

function zoomIn() {
  const canvas = canvasRef.value
  if (!canvas) return
  const cx = canvas.width / 2
  const cy = canvas.height / 2
  zoomAt(cx, cy, 1.25)
}

function zoomOut() {
  const canvas = canvasRef.value
  if (!canvas) return
  const cx = canvas.width / 2
  const cy = canvas.height / 2
  zoomAt(cx, cy, 0.8)
}

function zoomAt(cx: number, cy: number, factor: number) {
  const t = transform.value
  const newScale = Math.max(0.05, Math.min(20, t.scale * factor))
  const ratio = newScale / t.scale
  transform.value = {
    scale: newScale,
    translateX: cx - (cx - t.translateX) * ratio,
    translateY: cy - (cy - t.translateY) * ratio
  }
}

function render() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Resize canvas to container
  const container = containerRef.value
  if (container) {
    const rect = container.getBoundingClientRect()
    if (canvas.width !== rect.width || canvas.height !== rect.height) {
      canvas.width = rect.width
      canvas.height = rect.height
    }
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.save()
  ctx.translate(transform.value.translateX, transform.value.translateY)
  ctx.scale(transform.value.scale, transform.value.scale)

  // 绘制图像
  if (image.value) {
    ctx.drawImage(image.value, 0, 0)
  }

  // 绘制标注
  if (props.annotations && props.annotations.length > 0) {
    props.annotations.forEach((det, idx) => {
      if (!det.bbox || det.bbox.length < 4) return
      const [x1, y1, x2, y2] = det.bbox
      const color = props.labelColors?.[det.label] || getDefaultColor(idx)
      const isHighlighted = props.highlightIndex === idx

      ctx.strokeStyle = color
      ctx.lineWidth = isHighlighted ? 3 / transform.value.scale : 2 / transform.value.scale
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

      if (isHighlighted) {
        ctx.fillStyle = color.replace(')', ', 0.15)').replace('rgb', 'rgba').replace('#', '')
        ctx.globalAlpha = 0.2
        ctx.fillRect(x1, y1, x2 - x1, y2 - y1)
        ctx.globalAlpha = 1.0
      }

      // 标签背景
      const fontSize = Math.max(12, 14 / transform.value.scale)
      ctx.font = `${fontSize}px sans-serif`
      const label = det.confidence ? `${det.label} ${(det.confidence * 100).toFixed(0)}%` : det.label
      const textWidth = ctx.measureText(label).width
      const labelHeight = fontSize + 4

      ctx.fillStyle = color
      ctx.fillRect(x1, y1 - labelHeight, textWidth + 8, labelHeight)
      ctx.fillStyle = '#fff'
      ctx.fillText(label, x1 + 4, y1 - 4)
    })
  }

  ctx.restore()
}

function getDefaultColor(idx: number): string {
  const colors = ['#ff4444', '#00d4ff', '#00ff88', '#ffaa00', '#aa44ff', '#ff44aa', '#44aaff', '#ffcc00']
  return colors[idx % colors.length]
}

// 鼠标事件
function onWheel(e: WheelEvent) {
  e.preventDefault()
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const cx = e.clientX - rect.left
  const cy = e.clientY - rect.top
  const factor = e.deltaY < 0 ? 1.15 : 0.87
  zoomAt(cx, cy, factor)
}

function onMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
  isDragging.value = true
  dragStart.value = { x: e.clientX - transform.value.translateX, y: e.clientY - transform.value.translateY }
}

function onMouseMove(e: MouseEvent) {
  if (!isDragging.value) return
  transform.value = {
    ...transform.value,
    translateX: e.clientX - dragStart.value.x,
    translateY: e.clientY - dragStart.value.y
  }
}

function onMouseUp() {
  isDragging.value = false
}

// ResizeObserver
let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  nextTick(() => render())
  if (containerRef.value) {
    resizeObserver = new ResizeObserver(() => render())
    resizeObserver.observe(containerRef.value)
  }
  if (props.imageSrc) loadImage(props.imageSrc)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
})
</script>

<template>
  <div ref="containerRef" class="image-viewer-container">
    <canvas
      ref="canvasRef"
      class="image-viewer-canvas"
      :class="{ dragging: isDragging }"
      @wheel.prevent="onWheel"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
    />
    <div v-if="!imageSrc" class="empty-placeholder">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="1">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        <circle cx="8.5" cy="8.5" r="1.5"/>
        <polyline points="21 15 16 10 5 21"/>
      </svg>
      <span>暂无图像</span>
    </div>
  </div>
</template>

<style scoped>
.image-viewer-container {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background: rgba(10, 14, 20, 0.9);
  border-radius: 6px;
}

.image-viewer-canvas {
  display: block;
  width: 100%;
  height: 100%;
  cursor: grab;
}

.image-viewer-canvas.dragging {
  cursor: grabbing;
}

.empty-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: rgba(255, 255, 255, 0.25);
  font-size: 13px;
  pointer-events: none;
}
</style>
