<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import {
  getLabelTaskDetail, getLabelTaskSamples, getLabelSample,
  saveLabelContent, type LabelTaskDetail, type LabelSampleRow
} from '@/api/label'
import { getImageUrl } from '@/api/sample'
import { ElMessage } from 'element-plus'
import * as fabric from 'fabric'

const router = useRouter()
const route = useRoute()
const taskNo = (route.query.taskNo as string) || ''

// ==================== 状态 ====================
const taskDetail = ref<LabelTaskDetail | null>(null)
const samples = ref<LabelSampleRow[]>([])
const currentPage = ref(1)
const pageSize = 50
const totalSamples = ref(0)
const samplesLoading = ref(false)
const currentIndex = ref(-1)
const currentSample = computed(() => samples.value[currentIndex.value] || null)

// 标签列表（从 taskDetail.sampleLabels 解析）
const labelNames = computed(() => {
  if (!taskDetail.value?.sampleLabels) return []
  return taskDetail.value.sampleLabels.split('\n').map(s => s.trim()).filter(Boolean)
})

// 标注颜色（复用 SampleDetail.vue 的色板）
const boxColors = [
  '#00d4ff', '#00ff88', '#ff5555', '#ffaa00', '#a855f7',
  '#ff6b9d', '#45ffbc', '#ffd93d', '#6c5ce7', '#fd79a8'
]

// ==================== Fabric.js 画布 ====================
const canvasContainerRef = ref<HTMLDivElement | null>(null)
let canvas: fabric.Canvas | null = null
let bgImage: fabric.FabricImage | null = null // 当前图片对象
let resizeObserver: ResizeObserver | null = null
let pendingLabelContent: string | null = null // 容器未布局时暂存的DB标注，待首次适配后恢复
// 图片在画布（场景坐标）中的显示尺寸与偏移
let imgWidth = 0   // 图片显示宽度（场景像素）
let imgHeight = 0  // 图片显示高度（场景像素）
let imgOffsetX = 0 // 图片左边缘在场景中的 X
let imgOffsetY = 0 // 图片上边缘在场景中的 Y

// 绘制状态
let isDrawing = false
let drawStartX = 0
let drawStartY = 0
let tempRect: fabric.Rect | null = null
const drawMode = ref(false) // 绘制模式（默认关闭，关闭时可拖动平移图片）

// 平移状态
let isSpaceDown = false
let isPanning = false
let panLastX = 0
let panLastY = 0

// 撤销/重做
interface AnnotationSnapshot {
  classId: number
  className: string
  left: number
  top: number
  width: number
  height: number
}
const undoStack: AnnotationSnapshot[][] = []
const redoStack: AnnotationSnapshot[][] = []
const canUndo = ref(false)
const canRedo = ref(false)

// 标签选择浮层
const labelPopupVisible = ref(false)
const labelPopupX = ref(0)
const labelPopupY = ref(0)
let pendingRect: fabric.Rect | null = null

// 右侧标注列表
const annotations = ref<AnnotationSnapshot[]>([])
const selectedAnnoIndex = ref<number | null>(null)

// 保存状态
const isSaving = ref(false)
const imageLoading = ref(false)
const noDefectMode = ref(false) // 无缺陷模式

// ==================== 工具函数 ====================

function updateUndoRedoState() {
  canUndo.value = undoStack.length > 0
  canRedo.value = redoStack.length > 0
}

function getCurrentSnapshot(): AnnotationSnapshot[] {
  if (!canvas) return []
  const result: AnnotationSnapshot[] = []
  canvas.getObjects().forEach((obj) => {
    if (obj instanceof fabric.Rect && (obj as any).classId !== undefined) {
      result.push({
        classId: (obj as any).classId,
        className: (obj as any).className,
        left: obj.left || 0,
        top: obj.top || 0,
        width: obj.width || 0,
        height: obj.height || 0,
      })
    }
  })
  return result
}

function pushUndoStack() {
  undoStack.push(getCurrentSnapshot())
  if (undoStack.length > 50) undoStack.shift()
  redoStack.length = 0
  updateUndoRedoState()
}

function restoreSnapshot(snap: AnnotationSnapshot[]) {
  if (!canvas) return
  // 移除所有标注 Rect（保留背景图片 FabricImage）
  getAnnotationRects().slice().forEach((rect) => {
    canvas!.remove(rect)
  })
  // 重新创建
  snap.forEach((a) => {
    const rect = new fabric.Rect({
      originX: 'left',
      originY: 'top',
      left: a.left,
      top: a.top,
      width: a.width,
      height: a.height,
      fill: 'transparent',
      stroke: boxColors[a.classId % boxColors.length],
      strokeWidth: 2,
      strokeUniform: true,
      cornerColor: boxColors[a.classId % boxColors.length],
      cornerSize: 8,
      transparentCorners: false,
      selectable: true,
      evented: true,
      hasControls: true,
      hasBorders: true,
    })
    ;(rect as any).classId = a.classId
    ;(rect as any).className = a.className
    canvas!.add(rect)
  })
  canvas.renderAll()
  updateAnnotationsList()
}

function updateAnnotationsList() {
  annotations.value = getCurrentSnapshot()
  // 新增了标注时，自动退出无缺陷模式
  if (noDefectMode.value && annotations.value.length > 0) {
    noDefectMode.value = false
  }
}

// YOLO 格式序列化（坐标相对图片左上角，归一化）
function serializeToYolo(): string {
  if (!canvas || imgWidth === 0 || imgHeight === 0) return ''
  const lines: string[] = []
  getAnnotationRects().forEach((obj) => {
    const left = (obj.left || 0) - imgOffsetX
    const top = (obj.top || 0) - imgOffsetY
    const w = obj.width || 0
    const h = obj.height || 0
    const cx = (left + w / 2) / imgWidth
    const cy = (top + h / 2) / imgHeight
    const nw = w / imgWidth
    const nh = h / imgHeight
    lines.push(`${(obj as any).classId} ${cx.toFixed(6)} ${cy.toFixed(6)} ${nw.toFixed(6)} ${nh.toFixed(6)}`)
  })
  return lines.join('\n')
}

// YOLO 格式解析（还原为画布场景坐标，需加上图片偏移）
function parseFromYolo(labelContent: string | null | undefined): AnnotationSnapshot[] {
  if (!labelContent) return []
  const result: AnnotationSnapshot[] = []
  const labels = labelNames.value
  for (const line of labelContent.split('\n')) {
    const parts = line.trim().split(/\s+/)
    if (parts.length >= 5) {
      const classId = parseInt(parts[0])
      const cx = parseFloat(parts[1])
      const cy = parseFloat(parts[2])
      const w = parseFloat(parts[3])
      const h = parseFloat(parts[4])
      if (imgWidth > 0 && imgHeight > 0) {
        result.push({
          classId,
          className: labels[classId] || String(classId),
          left: (cx - w / 2) * imgWidth + imgOffsetX,
          top: (cy - h / 2) * imgHeight + imgOffsetY,
          width: w * imgWidth,
          height: h * imgHeight,
        })
      }
    }
  }
  return result
}

// ==================== 画布初始化 ====================

function getCanvasContainerSize(): { width: number; height: number } {
  const container = canvasContainerRef.value
  if (!container) return { width: 0, height: 0 }
  // 优先使用 offsetWidth/offsetHeight（更可靠）
  const w = container.offsetWidth || 0
  const h = container.offsetHeight || 0
  if (w > 0 && h > 0) {
    return { width: w, height: h }
  }
  // 降级使用 getBoundingClientRect
  const rect = container.getBoundingClientRect()
  if (rect.width > 0 && rect.height > 0) {
    return { width: Math.floor(rect.width), height: Math.floor(rect.height) }
  }
  // 最后降级：使用窗口尺寸减去估计的侧边栏和顶部栏尺寸
  const estimatedWidth = window.innerWidth - 240 - 280 // sidebar-left + sidebar-right
  const estimatedHeight = window.innerHeight - 60 - 50 // header + topbar
  return { 
    width: Math.max(estimatedWidth, 800), 
    height: Math.max(estimatedHeight, 600) 
  }
}

/** 将当前图片缩放并居中放入画布（画布尺寸 = 容器尺寸，图片完整展示） */
function fitImageToCanvas() {
  if (!canvas || !bgImage) return
  const { width: cw, height: ch } = getCanvasContainerSize()
  if (cw <= 0 || ch <= 0) return
  const naturalW = bgImage.width || 1
  const naturalH = bgImage.height || 1
  // 允许放大（移除 1 的上限），让小图片也能填充画布
  const scale = Math.min(cw / naturalW, ch / naturalH)
  imgWidth = Math.round(naturalW * scale)
  imgHeight = Math.round(naturalH * scale)
  imgOffsetX = Math.round((cw - imgWidth) / 2)
  imgOffsetY = Math.round((ch - imgHeight) / 2)
  bgImage.set({
    left: imgOffsetX,
    top: imgOffsetY,
    scaleX: scale,
    scaleY: scale,
  })
  bgImage.setCoords()
  canvas.renderAll()
  // 若此前因容器未布局而暂存了DB标注，此时几何已就绪，恢复之
  if (pendingLabelContent !== null) {
    const content = pendingLabelContent
    pendingLabelContent = null
    restoreSnapshot(parseFromYolo(content))
  }
}

/** 画布尺寸与容器同步（容器尺寸变化时调用），并按新图片几何重定位标注框 */
function syncCanvasSize() {
  if (!canvas) return
  const { width: cw, height: ch } = getCanvasContainerSize()
  if (cw <= 0 || ch <= 0) return
  const sizeChanged = canvas.width !== cw || canvas.height !== ch
  // 记录旧图片几何（用于重定位标注框）
  const oldW = imgWidth, oldH = imgHeight, oldOX = imgOffsetX, oldOY = imgOffsetY
  if (sizeChanged) {
    canvas.setDimensions({ width: cw, height: ch })
    // 确保 canvas-container 的 CSS 尺寸与内部尺寸一致
    const container = (canvas as any).wrapperEl
    if (container) {
      container.style.width = cw + 'px'
      container.style.height = ch + 'px'
    }
  }
  canvas.setViewportTransform([1, 0, 0, 1, 0, 0])
  fitImageToCanvas()
  // 尺寸变化且已有标注时，按归一化坐标重定位标注框
  if (sizeChanged && oldW > 0 && oldH > 0) {
    getAnnotationRects().forEach((rect) => {
      const nx = ((rect.left || 0) - oldOX) / oldW
      const ny = ((rect.top || 0) - oldOY) / oldH
      const nw = (rect.width || 0) / oldW
      const nh = (rect.height || 0) / oldH
      rect.set({
        left: nx * imgWidth + imgOffsetX,
        top: ny * imgHeight + imgOffsetY,
        width: nw * imgWidth,
        height: nh * imgHeight,
      })
      rect.setCoords()
    })
    canvas.renderAll()
    updateAnnotationsList()
  }
}

/** 获取画布上所有标注矩形（排除背景图片和临时绘制框）*/
function getAnnotationRects(): fabric.Rect[] {
  if (!canvas) return []
  return canvas.getObjects().filter(
    (obj): obj is fabric.Rect => obj instanceof fabric.Rect && (obj as any).classId !== undefined
  )
}

function initCanvas() {
  const canvasEl = document.getElementById('label-canvas') as HTMLCanvasElement
  if (!canvasEl) return
  // 初始尺寸用容器实际尺寸（若尚未布局则为0，ResizeObserver 会在布局后修正）
  const { width, height } = getCanvasContainerSize()
  canvas = new fabric.Canvas(canvasEl, {
    backgroundColor: '#1a1a2e',
    selection: false,
    preserveObjectStacking: true,
    width: width || 800,
    height: height || 600,
  })
  // 默认平移模式，光标为 grab
  canvas.defaultCursor = 'grab'

  // 监听容器尺寸变化，自动同步画布尺寸并重新适配图片
  if (canvasContainerRef.value) {
    resizeObserver = new ResizeObserver(() => {
      syncCanvasSize()
    })
    resizeObserver.observe(canvasContainerRef.value)
  }

  // 鼠标按下 — 根据模式决定平移或绘制
  canvas.on('mouse:down', (opt) => {
    // 如果有弹窗未关闭，不开始新操作
    if (labelPopupVisible.value) return
    // 点击了已有标注对象，让 Fabric 处理选中（两种模式下都支持）
    if (opt.target) return

    if (isSpaceDown || !drawMode.value) {
      // 平移模式（默认模式或按住空格）
      isPanning = true
      panLastX = opt.e.clientX
      panLastY = opt.e.clientY
      if (canvas) canvas.defaultCursor = 'grabbing'
      return
    }

    // 绘制模式
    isDrawing = true
    // 使用事件自带的场景坐标（v7 推荐，等价于 getScenePoint）
    const pointer = opt.scenePoint
    drawStartX = pointer.x
    drawStartY = pointer.y
    tempRect = new fabric.Rect({
      originX: 'left',
      originY: 'top',
      left: drawStartX,
      top: drawStartY,
      width: 0,
      height: 0,
      fill: 'rgba(0, 212, 255, 0.1)',
      stroke: '#00d4ff',
      strokeWidth: 2,
      strokeUniform: true,
      selectable: false,
      evented: false,
      hasControls: false,
      hasBorders: false,
    })
    canvas!.add(tempRect)
  })

  // 鼠标移动 — 更新矩形大小
  canvas.on('mouse:move', (opt) => {
    if (isPanning) {
      const vpt = canvas!.viewportTransform
      if (vpt) {
        vpt[4] += opt.e.clientX - panLastX
        vpt[5] += opt.e.clientY - panLastY
        canvas!.requestRenderAll()
      }
      panLastX = opt.e.clientX
      panLastY = opt.e.clientY
      return
    }
    if (!isDrawing || !tempRect) return
    const pointer = opt.scenePoint
    const w = Math.abs(pointer.x - drawStartX)
    const h = Math.abs(pointer.y - drawStartY)
    const left = Math.min(drawStartX, pointer.x)
    const top = Math.min(drawStartY, pointer.y)
    tempRect.set({ left, top, width: w, height: h })
    canvas!.requestRenderAll()
  })

  // 鼠标抬起 — 完成绘制，弹出标签选择
  canvas.on('mouse:up', (opt) => {
    if (isPanning) {
      isPanning = false
      // 恢复光标
      if (canvas) canvas.defaultCursor = drawMode.value ? 'crosshair' : 'grab'
      return
    }
    if (!isDrawing || !tempRect) return
    isDrawing = false

    // 如果矩形太小，删除
    if ((tempRect.width || 0) < 3 || (tempRect.height || 0) < 3) {
      canvas!.remove(tempRect)
      tempRect = null
      return
    }

    // 显示标签选择浮层（在鼠标释放位置附近）
    pendingRect = tempRect
    const canvasEl2 = canvas!.getElement()
    const canvasRect = canvasEl2?.getBoundingClientRect()
    if (canvasRect) {
      const vpt = canvas!.viewportTransform
      const zoom = canvas!.getZoom()
      // 矩形右下角在屏幕上的位置
      const screenX = canvasRect.left + (tempRect.left! + tempRect.width!) * zoom + (vpt?.[4] || 0)
      const screenY = canvasRect.top + (tempRect.top! + tempRect.height!) * zoom + (vpt?.[5] || 0)
      // 确保浮层在视口内
      labelPopupX.value = Math.min(Math.max(screenX + 10, 10), window.innerWidth - 220)
      labelPopupY.value = Math.min(Math.max(screenY + 10, 10), window.innerHeight - 320)
    } else {
      // 降级：在屏幕中央显示
      labelPopupX.value = window.innerWidth / 2 - 100
      labelPopupY.value = window.innerHeight / 2 - 150
    }
    labelPopupVisible.value = true
    tempRect = null
  })

  // 对象修改（移动/调整大小后）
  canvas.on('object:modified', () => {
    pushUndoStack()
    updateAnnotationsList()
  })

  // 对象选中
  canvas.on('selection:created', (opt) => {
    const idx = findAnnoIndex(opt.selected?.[0])
    selectedAnnoIndex.value = idx
  })
  canvas.on('selection:updated', (opt) => {
    const idx = findAnnoIndex(opt.selected?.[0])
    selectedAnnoIndex.value = idx
  })
  canvas.on('selection:cleared', () => {
    selectedAnnoIndex.value = null
    // 恢复所有标注框透明度
    getAnnotationRects().forEach(obj => obj.set({ opacity: 1 }))
    canvas?.renderAll()
  })

  // 滚轮缩放（以图片中心为原点，类似 Windows 看图功能）
  canvas.on('mouse:wheel', (opt) => {
    const delta = opt.e.deltaY
    let zoom = canvas!.getZoom()
    zoom *= 0.999 ** delta
    zoom = Math.max(0.1, Math.min(5, zoom))
    // 计算图片中心在画布像素坐标系中的位置
    const vpt = canvas!.viewportTransform
    if (imgWidth > 0 && imgHeight > 0 && vpt) {
      const sceneCenterX = imgOffsetX + imgWidth / 2
      const sceneCenterY = imgOffsetY + imgHeight / 2
      const canvasCenterX = sceneCenterX * vpt[0] + vpt[4]
      const canvasCenterY = sceneCenterY * vpt[3] + vpt[5]
      canvas!.zoomToPoint(new fabric.Point(canvasCenterX, canvasCenterY), zoom)
    } else {
      // 图片未加载时，以画布中心为原点
      const { width: cw, height: ch } = getCanvasContainerSize()
      canvas!.zoomToPoint(new fabric.Point(cw / 2, ch / 2), zoom)
    }
    opt.e.preventDefault()
    opt.e.stopPropagation()
  })

  // 文档级 mouseup 兜底（防止 Fabric mouse:up 未触发时矩形残留）
  document.addEventListener('mouseup', handleDocMouseUp)
}

// 文档级 mouseup — 兜底处理
function handleDocMouseUp() {
  if (isPanning) {
    isPanning = false
    if (canvas) canvas.defaultCursor = drawMode.value ? 'crosshair' : 'grab'
  }
}

function findAnnoIndex(obj: fabric.Object | undefined): number | null {
  if (!obj || !canvas) return null
  const annos = getAnnotationRects()
  for (let i = 0; i < annos.length; i++) {
    if (annos[i] === obj) return i
  }
  return null
}

// ==================== 标签选择 ====================

function handleSelectLabel(classId: number) {
  if (!pendingRect || !canvas) return
  const className = labelNames.value[classId] || String(classId)
  const color = boxColors[classId % boxColors.length]

  pushUndoStack()

  pendingRect.set({
    fill: 'transparent',
    stroke: color,
    strokeWidth: 2,
    cornerColor: color,
    cornerSize: 8,
    transparentCorners: false,
    selectable: true,
    evented: true,
    hasControls: true,
    hasBorders: true,
  })
  ;(pendingRect as any).classId = classId
  ;(pendingRect as any).className = className
  canvas.renderAll()

  pendingRect = null
  labelPopupVisible.value = false
  updateAnnotationsList()
}

function handleCancelLabel() {
  if (pendingRect && canvas) {
    canvas.remove(pendingRect)
    pendingRect = null
  }
  labelPopupVisible.value = false
}

// ==================== 标注列表操作 ====================

function handleAnnoClick(index: number) {
  if (!canvas) return
  const annos = getAnnotationRects()
  if (index < 0 || index >= annos.length) return
  // 高亮选中的，其他半透明
  annos.forEach((obj, i) => {
    if (i === index) {
      obj.set({ opacity: 1 })
      canvas!.setActiveObject(obj)
    } else {
      obj.set({ opacity: 0.3 })
    }
  })
  canvas.renderAll()
  selectedAnnoIndex.value = index
}

function handleAnnoDelete(index: number) {
  if (!canvas) return
  const annos = getAnnotationRects()
  if (index < 0 || index >= annos.length) return
  pushUndoStack()
  canvas.remove(annos[index])
  // 恢复其他标注框的透明度
  getAnnotationRects().forEach(obj => obj.set({ opacity: 1 }))
  canvas.renderAll()
  selectedAnnoIndex.value = null
  updateAnnotationsList()
}

// ==================== 撤销/重做 ====================

function handleUndo() {
  if (undoStack.length === 0) return
  redoStack.push(getCurrentSnapshot())
  const snap = undoStack.pop()!
  restoreSnapshot(snap)
  updateUndoRedoState()
}

function handleRedo() {
  if (redoStack.length === 0) return
  undoStack.push(getCurrentSnapshot())
  const snap = redoStack.pop()!
  restoreSnapshot(snap)
  updateUndoRedoState()
}

// ==================== 绘制模式切换 ====================

function toggleDrawMode() {
  drawMode.value = !drawMode.value
  if (canvas) {
    canvas.defaultCursor = drawMode.value ? 'crosshair' : 'grab'
    canvas.selection = false // 始终禁用框选（只允许点击选中单个标注）
  }
}

// ==================== 无缺陷按钮切换 ====================
function toggleNoDefect() {
  if (!noDefectMode.value) {
    // 进入无缺陷模式：清空所有标注框
    if (canvas) {
      // 移除所有标注 Rect（保留背景图片）
      const rects = canvas.getObjects().filter(obj => obj instanceof fabric.Rect && (obj as any).classId !== undefined)
      rects.forEach(obj => canvas.remove(obj))
      canvas.renderAll()
    }
    annotations.value = []
    noDefectMode.value = true
  } else {
    // 退出无缺陷模式
    noDefectMode.value = false
  }
}

// ==================== 删除键 ====================

function handleKeyDown(e: KeyboardEvent) {
  // W 键切换绘制模式（忽略输入框中的按键）
  if ((e.key === 'w' || e.key === 'W') && !isDrawing && !isPanning) {
    const target = e.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
    toggleDrawMode()
    e.preventDefault()
    return
  }
  if (e.code === 'Space' && !isSpaceDown) {
    isSpaceDown = true
    if (canvas) canvas.defaultCursor = 'grab'
    e.preventDefault()
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
    handleUndo()
    e.preventDefault()
  }
  if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
    handleRedo()
    e.preventDefault()
  }
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (canvas && !isDrawing && !isPanning) {
      const active = canvas.getActiveObject()
      if (active && active instanceof fabric.Rect) {
        pushUndoStack()
        canvas.remove(active)
        canvas.renderAll()
        updateAnnotationsList()
        e.preventDefault()
      }
    }
  }
  if (e.key === 'Escape') {
    handleCancelLabel()
  }
}

function handleKeyUp(e: KeyboardEvent) {
  if (e.code === 'Space') {
    isSpaceDown = false
    if (canvas) canvas.defaultCursor = drawMode.value ? 'crosshair' : 'grab'
  }
}

// ==================== 图片加载与标注 ====================

async function loadImageAndAnnotations(sample: LabelSampleRow) {
  if (!canvas || !sample.filePath) return
  imageLoading.value = true

  try {
    // 清空画布上所有对象（包括旧图片和标注框）
    canvas.getObjects().slice().forEach((obj) => {
      canvas!.remove(obj)
    })
    canvas.discardActiveObject()
    undoStack.length = 0
    redoStack.length = 0
    updateUndoRedoState()
    annotations.value = []
    selectedAnnoIndex.value = null
    labelPopupVisible.value = false
    pendingRect = null
    pendingLabelContent = null

    // 等待容器布局完成
    await nextTick()

    // 加载图片（不用 crossOrigin，同源请求）
    const img = await fabric.FabricImage.fromURL(getImageUrl(sample.filePath))

    // 图片不可交互，仅作底图
    // originX/originY 设为 left/top，与坐标计算逻辑一致（v7 默认是 center）
    img.set({
      originX: 'left',
      originY: 'top',
      selectable: false,
      evented: false,
      hasControls: false,
      hasBorders: false,
      hoverCursor: 'default',
    })
    bgImage = img

    // 先将图片添加到画布
    canvas.add(img)
    canvas.sendObjectToBack(img)

    // 强制同步画布尺寸到容器（等待容器有尺寸后同步）
    await nextTick()
    // 重试机制：等待容器有实际尺寸
    let retries = 0
    while (retries < 10) {
      const { width, height } = getCanvasContainerSize()
      if (width > 0 && height > 0) {
        syncCanvasSize()
        break
      }
      await new Promise(resolve => setTimeout(resolve, 50))
      retries++
    }
    if (retries >= 10) {
      syncCanvasSize()
    }

    // 加载已有标注（若容器已布局，几何就绪可直接恢复；否则暂存待首次适配后恢复）
    const detail = await getLabelSample(sample.recordId)
    if (detail?.labelContent) {
      if (imgWidth > 0 && imgHeight > 0) {
        restoreSnapshot(parseFromYolo(detail.labelContent))
      } else {
        pendingLabelContent = detail.labelContent
      }
    }
    // 根据已保存的 labelFlag 恢复无缺陷模式
    if (detail?.labelFlag === 2) {
      noDefectMode.value = true
    }
  } catch (e) {
    console.error('加载图片失败:', e)
    ElMessage.error('加载图片失败')
  } finally {
    imageLoading.value = false
  }
}

// ==================== 自动保存 ====================

async function autoSave() {
  if (!currentSample.value || !canvas) return
  const yolo = serializeToYolo()
  // label_flag: 0未标注 / 1有标签 / 2无缺陷
  let labelFlag: number
  if (noDefectMode.value) {
    labelFlag = 2
  } else {
    labelFlag = yolo ? 1 : 0
  }
  isSaving.value = true
  try {
    await saveLabelContent(currentSample.value.recordId, yolo, labelFlag)
    // 更新本地状态
    if (currentSample.value) {
      currentSample.value.labelFlag = labelFlag
      currentSample.value.labelContent = yolo
    }
  } catch (e: any) {
    ElMessage.error('自动保存失败: ' + (e.message || ''))
  } finally {
    isSaving.value = false
  }
}

// ==================== 图片切换 ====================

async function selectSample(index: number) {
  if (index < 0 || index >= samples.value.length) return
  if (index === currentIndex.value) return

  // 自动保存当前图片
  if (currentIndex.value >= 0) {
    await autoSave()
  }

  currentIndex.value = index
  // 切换图片时重置无缺陷模式
  noDefectMode.value = false
  await loadImageAndAnnotations(samples.value[index])
}

async function handlePrev() {
  if (currentIndex.value > 0) {
    await selectSample(currentIndex.value - 1)
  }
}

async function handleNext() {
  if (currentIndex.value < samples.value.length - 1) {
    await selectSample(currentIndex.value + 1)
  } else {
    // 尝试加载更多
    if (samples.value.length < totalSamples.value) {
      await loadMoreSamples()
      if (currentIndex.value < samples.value.length - 1) {
        await selectSample(currentIndex.value + 1)
      }
    }
  }
}

// ==================== 数据加载 ====================

async function loadTaskDetail() {
  try {
    taskDetail.value = await getLabelTaskDetail(taskNo)
  } catch (e: any) {
    ElMessage.error('加载任务详情失败: ' + (e.message || ''))
  }
}

async function loadMoreSamples() {
  if (samplesLoading.value) return
  if (samples.value.length >= totalSamples.value && totalSamples.value > 0) return
  samplesLoading.value = true
  try {
    const result = await getLabelTaskSamples(taskNo, currentPage.value, pageSize)
    if (currentPage.value === 1) {
      totalSamples.value = result.total
    }
    samples.value.push(...result.rows)
    currentPage.value++
  } catch (e: any) {
    ElMessage.error('加载样本列表失败: ' + (e.message || ''))
  } finally {
    samplesLoading.value = false
  }
}

// 左侧列表滚动加载
function handleListScroll(e: Event) {
  const el = e.target as HTMLElement
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 50) {
    loadMoreSamples()
  }
}

// ==================== 生命周期 ====================

onMounted(async () => {
  document.addEventListener('keydown', handleKeyDown)
  document.addEventListener('keyup', handleKeyUp)

  await loadTaskDetail()
  await loadMoreSamples()

  // 等待 DOM 完全渲染后再初始化画布
  await nextTick()
  initCanvas()

  // 加载第一张图片
  if (samples.value.length > 0) {
    currentIndex.value = 0
    await loadImageAndAnnotations(samples.value[0])
  }
})

onBeforeUnmount(async () => {
  document.removeEventListener('keydown', handleKeyDown)
  document.removeEventListener('keyup', handleKeyUp)
  document.removeEventListener('mouseup', handleDocMouseUp)
  // 保存当前图片
  if (currentIndex.value >= 0) {
    await autoSave()
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (canvas) {
    canvas.dispose()
    canvas = null
  }
  bgImage = null
})

function goBack() {
  router.push('/label-task')
}
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="标注工作台" />
    <div class="main-content">
      <Sidebar />
      <main class="workbench-area">
        <!-- 顶部栏 -->
        <div class="workbench-topbar">
          <div class="topbar-left">
            <el-button size="small" @click="goBack" class="back-btn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
              返回
            </el-button>
            <span class="task-name">{{ taskDetail?.taskName || '-' }}</span>
          </div>
          <div class="topbar-center">
            共 {{ totalSamples }} 张，当前第 {{ currentIndex + 1 }} 张
          </div>
          <div class="topbar-right">
            <el-button
              size="small"
              :class="['mode-btn', { 'mode-btn-active': drawMode }]"
              @click="toggleDrawMode"
              :title="drawMode ? '绘制模式（按 W 切换为平移）' : '平移模式（按 W 切换为绘制）'"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="1" stroke-dasharray="4 2"/>
                <path d="M3 3l6 6" v-if="!drawMode"/>
              </svg>
              {{ drawMode ? '绘制中' : '绘制标注' }}
            </el-button>
            <el-button size="small" :disabled="!canUndo" @click="handleUndo" title="撤销 (Ctrl+Z)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-15-6.7L3 13"/></svg>
              撤销
            </el-button>
            <el-button size="small" :disabled="!canRedo" @click="handleRedo" title="重做 (Ctrl+Shift+Z)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 15-6.7L21 13"/></svg>
              重做
            </el-button>
          </div>
        </div>

        <!-- 主体三栏布局 -->
        <div class="workbench-body">
          <!-- 左侧文件列表 -->
          <div class="sidebar-left">
            <div class="sidebar-header">文件列表</div>
            <div class="file-list" @scroll="handleListScroll" v-loading="samplesLoading && samples.length === 0">
              <div
                v-for="(sample, i) in samples"
                :key="sample.recordId"
                class="file-item"
                :class="{ active: i === currentIndex }"
                @click="selectSample(i)"
              >
                <span v-if="sample.labelFlag === 2" class="file-check" title="无缺陷">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <circle cx="6" cy="6" r="6" fill="#00d4ff"/>
                    <path d="M3 6l2.5 2.5L9 4" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </span>
                <span v-else class="file-dot" :class="{ labeled: sample.labelFlag === 1 }"></span>
                <span class="file-name" :title="sample.sampleName">{{ sample.sampleName }}</span>
              </div>
              <div v-if="samplesLoading && samples.length > 0" class="loading-more">加载中...</div>
              <div v-if="!samplesLoading && samples.length >= totalSamples && samples.length > 0" class="load-end">已加载全部</div>
            </div>
          </div>

          <!-- 中央画布 -->
          <div class="canvas-area" ref="canvasContainerRef" v-loading="imageLoading" element-loading-text="加载图片...">
            <canvas id="label-canvas"></canvas>
            <div v-if="!currentSample" class="canvas-empty">请从左侧选择图片</div>
            <!-- 保存提示 -->
            <div v-if="isSaving" class="save-indicator">保存中...</div>
            <!-- 缩放提示 -->
            <div class="zoom-hint">W 切换绘制/平移 | 滚轮缩放 | 拖动平移 | Delete删除选中</div>
          </div>

          <!-- 右侧标注列表 -->
          <div class="sidebar-right">
            <div class="sidebar-header">
              <span>已标注标签 ({{ annotations.length }})</span>
              <button
                class="no-defect-btn"
                :class="{ active: noDefectMode }"
                @click="toggleNoDefect"
                :title="noDefectMode ? '点击取消无缺陷状态' : '标记为无缺陷样本'"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                无缺陷
              </button>
            </div>
            <div class="anno-list">
              <div
                v-for="(anno, i) in annotations"
                :key="i"
                class="anno-item"
                :class="{ active: selectedAnnoIndex === i }"
                @click="handleAnnoClick(i)"
              >
                <span class="anno-dot" :style="{ backgroundColor: boxColors[anno.classId % boxColors.length] }"></span>
                <span class="anno-name">{{ anno.className }}</span>
                <span class="anno-index">#{{ i + 1 }}</span>
                <button class="anno-delete" @click.stop="handleAnnoDelete(i)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </div>
              <div v-if="annotations.length === 0" class="anno-empty">暂无标注</div>
            </div>
            <!-- 标签列表展示 -->
            <div class="label-list-section">
              <div class="sidebar-header">标签列表</div>
              <div class="label-list">
                <div v-for="(label, i) in labelNames" :key="i" class="label-item">
                  <span class="label-dot" :style="{ backgroundColor: boxColors[i % boxColors.length] }"></span>
                  <span class="label-name">{{ label }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部导航 -->
        <div class="workbench-bottombar">
          <el-button :disabled="currentIndex <= 0" @click="handlePrev">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
            上一张
          </el-button>
          <span class="nav-info">{{ currentIndex + 1 }} / {{ totalSamples }}</span>
          <el-button :disabled="currentIndex >= totalSamples - 1" @click="handleNext">
            下一张
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
          </el-button>
        </div>
      </main>
    </div>

    <!-- 标签选择浮层 -->
    <div
      v-if="labelPopupVisible"
      class="label-popup"
      :style="{ left: labelPopupX + 'px', top: labelPopupY + 'px' }"
    >
      <div class="popup-header">选择标签</div>
      <div class="popup-list">
        <button
          v-for="(label, i) in labelNames"
          :key="i"
          class="popup-label-btn"
          @click="handleSelectLabel(i)"
        >
          <span class="popup-label-dot" :style="{ backgroundColor: boxColors[i % boxColors.length] }"></span>
          {{ label }}
        </button>
      </div>
      <button class="popup-cancel" @click="handleCancelLabel">取消</button>
    </div>
  </div>
</template>

<style scoped lang="scss">
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
}

.workbench-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

// 顶部栏
.workbench-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
}

.back-btn {
  background: rgba(0, 212, 255, 0.1) !important;
  border: 1px solid rgba(0, 212, 255, 0.3) !important;
  color: #00d4ff !important;
}

.task-name {
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  font-weight: 500;
}

.topbar-center {
  font-size: 16px;
  color: #fff;
  font-weight: 500;
}

.topbar-right {
  display: flex;
  gap: 8px;
  min-width: 200px;
  justify-content: flex-end;
}

// 绘制模式按钮
.mode-btn {
  background: rgba(0, 212, 255, 0.08) !important;
  border: 1px solid rgba(0, 212, 255, 0.3) !important;
  color: rgba(0, 212, 255, 0.8) !important;

  &:hover {
    background: rgba(0, 212, 255, 0.15) !important;
    color: #00d4ff !important;
  }

  &.mode-btn-active {
    background: rgba(0, 255, 136, 0.15) !important;
    border-color: rgba(0, 255, 136, 0.5) !important;
    color: #00ff88 !important;
    box-shadow: 0 0 12px rgba(0, 255, 136, 0.2);
  }
}

// 主体三栏
.workbench-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

// 左侧文件列表
.sidebar-left {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(0, 212, 255, 0.15);
}

.sidebar-header {
  padding: 10px 16px;
  font-size: 13px;
  color: rgba(0, 212, 255, 0.8);
  font-weight: 500;
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.no-defect-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid rgba(0, 255, 136, 0.4);
  background: rgba(0, 255, 136, 0.08);
  color: rgba(0, 255, 136, 0.7);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  line-height: 1;

  &:hover {
    background: rgba(0, 255, 136, 0.15);
    color: #00ff88;
  }

  &.active {
    background: rgba(0, 255, 136, 0.2);
    color: #00ff88;
    box-shadow: 0 0 8px rgba(0, 255, 136, 0.3);
  }

  svg {
    flex-shrink: 0;
  }
}

.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.file-item {
  display: flex;
  align-items: center;
  padding: 6px 16px;
  cursor: pointer;
  gap: 8px;
  transition: background 0.15s;

  &:hover {
    background: rgba(0, 212, 255, 0.08);
  }

  &.active {
    background: rgba(0, 212, 255, 0.15);
  }
}

.file-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  flex-shrink: 0;

  &.labeled {
    background: #00ff88;
  }
}

.file-check {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

.file-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.loading-more, .load-end {
  padding: 8px 16px;
  text-align: center;
  color: rgba(255, 255, 255, 0.3);
  font-size: 12px;
}

// 中央画布
.canvas-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: #1a1a2e;
}

.canvas-empty {
  position: absolute;
  color: rgba(255, 255, 255, 0.3);
  font-size: 16px;
}

.save-indicator {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
}

.zoom-hint {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.55);
  font-size: 11px;
  pointer-events: none;
}

// 右侧标注列表
.sidebar-right {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid rgba(0, 212, 255, 0.15);
}

.anno-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.anno-item {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  cursor: pointer;
  gap: 8px;
  transition: background 0.15s;

  &:hover {
    background: rgba(0, 212, 255, 0.08);
  }

  &.active {
    background: rgba(0, 212, 255, 0.15);
  }
}

.anno-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.anno-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.anno-index {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  flex-shrink: 0;
}

.anno-delete {
  background: none;
  border: none;
  color: rgba(255, 85, 85, 0.6);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;

  &:hover {
    color: #ff5555;
  }
}

.anno-empty {
  padding: 24px 16px;
  text-align: center;
  color: rgba(255, 255, 255, 0.25);
  font-size: 13px;
}

.label-list-section {
  border-top: 1px solid rgba(0, 212, 255, 0.15);
  flex-shrink: 0;
}

.label-list {
  padding: 4px 0;
  max-height: 200px;
  overflow-y: auto;
}

.label-item {
  display: flex;
  align-items: center;
  padding: 6px 16px;
  gap: 8px;
}

.label-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.label-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

// 底部栏
.workbench-bottombar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 24px;
  border-top: 1px solid rgba(0, 212, 255, 0.15);
  gap: 24px;
  flex-shrink: 0;
}

.nav-info {
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  min-width: 80px;
  text-align: center;
}

// 标签选择浮层
.label-popup {
  position: fixed;
  z-index: 10000;
  background: #1a2332;
  border: 1px solid rgba(0, 212, 255, 0.3);
  border-radius: 8px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.5);
  padding: 8px;
  min-width: 160px;
}

.popup-header {
  font-size: 12px;
  color: rgba(0, 212, 255, 0.8);
  padding: 4px 8px 8px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
}

.popup-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 0;
  max-height: 240px;
  overflow-y: auto;
}

.popup-label-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  border-radius: 4px;
  font-size: 13px;
  text-align: left;

  &:hover {
    background: rgba(0, 212, 255, 0.15);
    color: #00d4ff;
  }
}

.popup-label-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.popup-cancel {
  width: 100%;
  padding: 6px;
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  font-size: 12px;
  margin-top: 4px;

  &:hover {
    background: rgba(255, 255, 255, 0.05);
    color: rgba(255, 255, 255, 0.8);
  }
}
</style>
