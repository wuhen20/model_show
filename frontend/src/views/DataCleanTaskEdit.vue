<script setup lang="ts">
import { ref, reactive, computed, onMounted, markRaw, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { ElMessage } from 'element-plus'
import { VueFlow, useVueFlow, Handle, Position, type Node, type Edge, type Connection } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'

import {
  getCleanTaskDetail,
  saveCleanTaskNodes,
  queryDatabaseTables,
  queryCleanTableColumns,
  type CleanTaskDetail,
  type TableColumnInfo,
} from '@/api/clean'

const router = useRouter()
const route = useRoute()
const taskNo = ref<string>((route.query.taskNo as string) || '')

// ========== 基础信息 ==========
const taskInfo = reactive({ taskName: '', remark: '' })

// ========== Vue Flow 画布 ==========
const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])
const loading = ref(false)
const saving = ref(false)

// useVueFlow 不需要传入参数，通过 v-model 自动同步
const {
  onConnect,
  addEdges,
  addNodes,
  project,
  vueFlowRef,
  onNodeClick,
  onPaneClick,
  getNodes,
  getEdges,
} = useVueFlow()

let nodeIdCounter = 0
function genNodeId(type: string): string {
  nodeIdCounter++
  return `${type}_${Date.now()}_${nodeIdCounter}`
}

// 选中节点
const selectedNode = ref<Node | null>(null)

// ========== 算子面板拖拽 ==========
const operators = [
  { type: 'source', name: '数据源', icon: 'database', color: '#00d4ff' },
  { type: 'dedup', name: '去重', icon: 'filter', color: '#00ff88' },
  { type: 'nullfill', name: '空值处理', icon: 'null', color: '#ffaa00' },
]

function onDragStart(event: DragEvent, opType: string) {
  if (!event.dataTransfer) return
  event.dataTransfer.setData('application/vueflow', opType)
  event.dataTransfer.effectAllowed = 'move'
}

function onDragOver(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

function onDrop(event: DragEvent) {
  event.preventDefault()
  const opType = event.dataTransfer?.getData('application/vueflow') || ''
  if (!opType) return

  const vueFlowEl = vueFlowRef.value
  if (!vueFlowEl) return

  const bounds = vueFlowEl.getBoundingClientRect()
  const position = project({
    x: event.clientX - bounds.left,
    y: event.clientY - bounds.top,
  })

  addOperatorNode(opType, position)
}

function addOperatorNode(opType: string, position: { x: number; y: number }) {
  const op = operators.find(o => o.type === opType)
  if (!op) return

  const id = genNodeId(opType)
  const node: Node = {
    id,
    type: opType,
    position,
    data: {
      label: op.name,
      nodeType: opType,
      config: opType === 'source'
        ? { tableName: '' }
        : opType === 'dedup'
          ? { fields: [] }
          : { fields: [], strategy: 'drop', fillValue: '' },
    },
  }
  nodes.value.push(node)
}

// ========== 连线 ==========
onConnect((connection: Connection) => {
  const newEdge: Edge = {
    id: `edge_${connection.source}_${connection.target}`,
    source: connection.source,
    target: connection.target,
    animated: true,
    style: { stroke: '#00d4ff', strokeWidth: 2 },
  }
  edges.value.push(newEdge)
})

// ========== 节点选中 ==========
onPaneClick(() => {
  selectedNode.value = null
})

// ========== 右侧配置面板 ==========
const tableList = ref<string[]>([])
const tableLoading = ref(false)
const columnList = ref<TableColumnInfo[]>([])
const columnLoading = ref(false)

async function loadTableList() {
  tableLoading.value = true
  try {
    tableList.value = await queryDatabaseTables()
  } catch (e: any) {
    ElMessage.error(e.message || '查询表列表失败')
  } finally {
    tableLoading.value = false
  }
}

async function loadColumns(tableName: string) {
  if (!tableName) {
    columnList.value = []
    return
  }
  columnLoading.value = true
  try {
    columnList.value = await queryCleanTableColumns(tableName)
  } catch (e: any) {
    ElMessage.error(e.message || '查询字段失败')
  } finally {
    columnLoading.value = false
  }
}

// 沿连线向上递归查找 source 节点（支持 source → dedup → nullfill 多级链路）
// 同时从 v-model 本地 refs 和 Vue Flow store 中查找，避免同步时序问题
function findUpstreamSourceNode(nodeId: string): Node | null {
  const allEdges = [...edges.value, ...getEdges.value]
  const allNodes = [...nodes.value, ...getNodes.value]

  const visited = new Set<string>()
  let currentId = nodeId
  while (currentId && !visited.has(currentId)) {
    visited.add(currentId)
    const incomingEdge = allEdges.find(e => e.target === currentId)
    if (!incomingEdge) break
    const upstreamNode = allNodes.find(n => n.id === incomingEdge.source)
    if (!upstreamNode) break
    if (upstreamNode.data?.nodeType === 'source') {
      return upstreamNode
    }
    currentId = upstreamNode.id
  }
  return null
}

// 当选中 dedup 或 nullfill 节点时，从上游 source 节点获取表名并加载字段
function onNodeSelectedForConfig() {
  const nodeType = selectedNode.value?.data?.nodeType
  if (nodeType === 'dedup' || nodeType === 'nullfill') {
    const sourceNode = findUpstreamSourceNode(selectedNode.value!.id)
    if (sourceNode?.data?.config?.tableName) {
      loadColumns(sourceNode.data.config.tableName)
    }
  }
}

// 监听选中节点变化
function handleNodeSelect(node: Node) {
  selectedNode.value = node
  if (node.data?.nodeType === 'source') {
    if (tableList.value.length === 0) {
      loadTableList()
    }
  } else if (node.data?.nodeType === 'dedup' || node.data?.nodeType === 'nullfill') {
    onNodeSelectedForConfig()
  }
}

// 重写 onNodeClick 以加载配置数据
onNodeClick(({ node }) => {
  handleNodeSelect(node)
})

// 监听 selectedNode 变化，确保选中 dedup/nullfill 节点时一定触发字段加载
// 使用 nextTick 等待 edges/nodes 的响应式更新完成后再查找上游 source 节点
watch(selectedNode, (newNode) => {
  if (newNode?.data?.nodeType === 'dedup' || newNode?.data?.nodeType === 'nullfill') {
    nextTick(() => {
      if (selectedNode.value?.id === newNode.id) {
        onNodeSelectedForConfig()
      }
    })
  }
})

// 统一更新选中节点的配置（同时更新 nodes 数组和 selectedNode 引用）
function updateSelectedNodeConfig(configUpdate: Record<string, any>) {
  if (!selectedNode.value) return
  const nodeId = selectedNode.value.id
  nodes.value = nodes.value.map(n => {
    if (n.id === nodeId) {
      return {
        ...n,
        data: {
          ...n.data,
          config: { ...n.data?.config, ...configUpdate },
        },
      }
    }
    return n
  })
  selectedNode.value = nodes.value.find(n => n.id === nodeId) || null
}

// 当 source 节点的表名变化时，更新配置
function onSourceTableChange(tableName: string) {
  updateSelectedNodeConfig({ tableName })
}

// 当 dedup 节点的字段变化时，更新配置
function onDedupFieldsChange(fields: string[]) {
  updateSelectedNodeConfig({ fields })
}

// 当 nullfill 节点的字段变化时，更新配置
function onNullFillFieldsChange(fields: string[]) {
  updateSelectedNodeConfig({ fields })
}

// 空值处理：区间选择器（手动输入起止字段名，自动匹配同前缀+数字的区间字段）
const nullFillRangeStart = ref('')
const nullFillRangeEnd = ref('')

// 解析字段名：返回 {prefix, num} 或 null
function parseFieldName(name: string): { prefix: string; num: number } | null {
  const match = name.match(/^([^\d]*?)(\d+)$/)
  if (!match) return null
  return { prefix: match[1], num: parseInt(match[2]) }
}

// 添加区间选择：根据起止字段名，自动勾选同前缀+数字区间内的所有字段
function onAddNullFillRange() {
  const startRaw = nullFillRangeStart.value.trim()
  const endRaw = nullFillRangeEnd.value.trim()
  if (!startRaw || !endRaw) {
    ElMessage.warning('请输入起始和结束字段名')
    return
  }
  const startParsed = parseFieldName(startRaw)
  const endParsed = parseFieldName(endRaw)
  if (!startParsed || !endParsed) {
    ElMessage.warning('字段名必须以数字结尾（如 time0000、P0015）')
    return
  }
  if (startParsed.prefix !== endParsed.prefix) {
    ElMessage.warning(`前缀不一致："${startParsed.prefix}" 与 "${endParsed.prefix}"`)
    return
  }
  let start = startParsed.num
  let end = endParsed.num
  if (start > end) { [start, end] = [end, start] }
  if (columnList.value.length === 0) {
    ElMessage.warning('请先点击"刷新字段"加载字段列表')
    return
  }
  const prefix = startParsed.prefix
  const fieldsToAdd: string[] = []
  for (const col of columnList.value) {
    const parsed = parseFieldName(col.fieldName)
    if (parsed && parsed.prefix === prefix && parsed.num >= start && parsed.num <= end) {
      fieldsToAdd.push(col.fieldName)
    }
  }
  if (fieldsToAdd.length === 0) {
    ElMessage.warning(`未找到前缀为 "${prefix}" 且数字在 ${start}~${end} 之间的字段`)
    return
  }
  const currentFields = new Set(selectedNode.value?.data?.config?.fields || [])
  fieldsToAdd.forEach(f => currentFields.add(f))
  onNullFillFieldsChange(Array.from(currentFields))
  ElMessage.success(`已添加 ${fieldsToAdd.length} 个字段`)
}

// 清空空值处理已选字段
function onClearNullFillFields() {
  onNullFillFieldsChange([])
}

// 当 nullfill 节点的策略变化时，更新配置
function onNullFillStrategyChange(strategy: string) {
  updateSelectedNodeConfig({ strategy })
}

// 当 nullfill 节点的填充值变化时，更新配置
function onNullFillValueChange(fillValue: string) {
  updateSelectedNodeConfig({ fillValue })
}

// nullfill 策略显示名称
const strategyNameMap: Record<string, string> = {
  drop: '删除行',
  fill: '固定值',
  ffill: '前向填充',
  bfill: '后向填充',
  interpolate: '线性插值',
  mean: '均值',
  median: '中位数',
  hfill_forward: '横向向前',
  hfill_backward: '横向向后',
  hinterpolate: '横向插值',
}
function nullfillStrategyName(strategy: string): string {
  return strategyNameMap[strategy] || strategy
}

// ========== 保存流程 ==========
async function handleSave() {
  if (!taskNo.value) {
    ElMessage.warning('缺少任务编号')
    return
  }

  const currentNodes = nodes.value
  const currentEdges = edges.value

  if (currentNodes.length === 0) {
    ElMessage.warning('请至少添加一个节点')
    return
  }

  // 检查 source 节点是否配置了表名
  const sourceNode = currentNodes.find(n => n.data?.nodeType === 'source')
  if (!sourceNode) {
    ElMessage.warning('请添加数据源节点')
    return
  }
  if (!sourceNode.data?.config?.tableName) {
    ElMessage.warning('请为数据源节点选择数据表')
    return
  }

  // 检查 dedup 节点是否配置了字段
  const dedupNode = currentNodes.find(n => n.data?.nodeType === 'dedup')
  if (dedupNode && (!dedupNode.data?.config?.fields || dedupNode.data.config.fields.length === 0)) {
    ElMessage.warning('请为去重节点配置去重字段')
    return
  }

  // 检查 nullfill 节点是否配置了字段
  const nullfillNode = currentNodes.find(n => n.data?.nodeType === 'nullfill')
  if (nullfillNode) {
    if (!nullfillNode.data?.config?.fields || nullfillNode.data.config.fields.length === 0) {
      ElMessage.warning('请为空值处理节点配置处理字段')
      return
    }
    if (nullfillNode.data.config.strategy === 'fill' && !nullfillNode.data.config.fillValue && nullfillNode.data.config.fillValue !== 0) {
      ElMessage.warning('请为空值处理节点配置填充值')
      return
    }
  }

  // 构建保存数据
  const nodesToSave = currentNodes.map(n => {
    const incomingEdge = currentEdges.find(e => e.target === n.id)
    return {
      nodeId: n.id,
      nodeType: n.data?.nodeType || '',
      nodeName: n.data?.label || '',
      nodeConfig: n.data?.config || {},
      posX: Math.round(n.position.x),
      posY: Math.round(n.position.y),
      prevNodeId: incomingEdge ? incomingEdge.source : null,
    }
  })

  saving.value = true
  try {
    await saveCleanTaskNodes(taskNo.value, nodesToSave)
    ElMessage.success('流程保存成功')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// ========== 加载已有流程 ==========
async function loadTaskDetail() {
  if (!taskNo.value) {
    ElMessage.warning('缺少任务编号，请从任务列表进入')
    router.push('/clean-task')
    return
  }
  loading.value = true
  try {
    const data: CleanTaskDetail = await getCleanTaskDetail(taskNo.value)
    taskInfo.taskName = data.taskName
    taskInfo.remark = data.remark || ''

    // 将节点数据转为 Vue Flow 格式
    const loadedNodes: Node[] = (data.nodes || []).map(n => {
      let defaultLabel = '数据源'
      let defaultConfig: any = { tableName: '' }
      if (n.nodeType === 'dedup') {
        defaultLabel = '去重'
        defaultConfig = { fields: [] }
      } else if (n.nodeType === 'nullfill') {
        defaultLabel = '空值处理'
        defaultConfig = { fields: [], strategy: 'drop', fillValue: '' }
      }
      return {
        id: n.nodeId,
        type: n.nodeType,
        position: { x: n.posX, y: n.posY },
        data: {
          label: n.nodeName || defaultLabel,
          nodeType: n.nodeType,
          config: n.nodeConfig || defaultConfig,
        },
      }
    })

    // 根据 prevNodeId 生成 edges
    const loadedEdges: Edge[] = []
    for (const n of data.nodes || []) {
      if (n.prevNodeId) {
        loadedEdges.push({
          id: `edge_${n.prevNodeId}_${n.nodeId}`,
          source: n.prevNodeId,
          target: n.nodeId,
          animated: true,
          style: { stroke: '#00d4ff', strokeWidth: 2 },
        })
      }
    }

    nodes.value = loadedNodes
    edges.value = loadedEdges
  } catch (e: any) {
    ElMessage.error(e.message || '加载任务详情失败')
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/clean-task')
}

// 删除选中节点（同时清理相关连线）
function deleteSelectedNode() {
  if (!selectedNode.value) return
  const nodeId = selectedNode.value.id
  nodes.value = nodes.value.filter(n => n.id !== nodeId)
  edges.value = edges.value.filter(e => e.source !== nodeId && e.target !== nodeId)
  selectedNode.value = null
}

onMounted(() => {
  loadTaskDetail()
})
</script>

<template>
  <div class="app-layout">
    <Header title="模型能力展示与体验工作台" subtitle="清洗任务编排" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <!-- 顶部：基础信息 + 操作 -->
        <div class="top-bar">
          <div class="top-left">
            <el-button class="back-btn" @click="goBack">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
              返回
            </el-button>
            <div class="task-info">
              <span class="task-no">任务编号：{{ taskNo }}</span>
            </div>
          </div>
          <div class="top-right">
            <el-button type="primary" :loading="saving" @click="handleSave">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                <polyline points="17 21 17 13 7 13 7 21" />
                <polyline points="7 3 7 8 15 8" />
              </svg>
              保存流程
            </el-button>
          </div>
        </div>

        <!-- 基础信息 -->
        <div class="basic-info">
          <div class="info-item">
            <label>任务名称</label>
            <el-input v-model="taskInfo.taskName" placeholder="任务名称" disabled />
          </div>
          <div class="info-item">
            <label>任务说明</label>
            <el-input v-model="taskInfo.remark" placeholder="任务说明" disabled />
          </div>
        </div>

        <!-- 画布区域 -->
        <div class="canvas-area">
          <!-- 左侧算子面板 -->
          <div class="operator-palette">
            <div class="palette-title">算子面板</div>
            <div class="palette-tip">拖拽到画布</div>
            <div
              v-for="op in operators"
              :key="op.type"
              class="operator-card"
              :style="{ borderColor: op.color + '40' }"
              draggable="true"
              @dragstart="onDragStart($event, op.type)"
            >
              <div class="operator-icon" :style="{ background: op.color + '20', color: op.color }">
                <svg v-if="op.icon === 'database'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <ellipse cx="12" cy="5" rx="9" ry="3" />
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                </svg>
                <svg v-else-if="op.icon === 'filter'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
                </svg>
                <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="8" y1="12" x2="16" y2="12" stroke-dasharray="2 2" />
                </svg>
              </div>
              <span class="operator-name" :style="{ color: op.color }">{{ op.name }}</span>
            </div>
          </div>

          <!-- 中间画布 -->
          <div class="flow-canvas" @drop="onDrop" @dragover="onDragOver">
            <div v-if="loading" class="canvas-loading">加载中...</div>
            <VueFlow
              v-model:nodes="nodes"
              v-model:edges="edges"
              :default-viewport="{ zoom: 1 }"
              fit-view-on-init
              class="vue-flow-container"
            >
              <Background :gap="20" :size="1" pattern-color="rgba(0, 212, 255, 0.1)" />
              <Controls />

              <!-- 数据源节点 -->
              <template #node-source="props">
                <div class="custom-node source-node" :class="{ selected: selectedNode?.id === props.id }">
                  <div class="node-header">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                      <ellipse cx="12" cy="5" rx="9" ry="3" />
                      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                    </svg>
                    <span>数据源</span>
                  </div>
                  <div class="node-body">
                    {{ props.data?.config?.tableName || '未选择表' }}
                  </div>
                  <Handle type="source" :position="Position.Right" />
                </div>
              </template>

              <!-- 去重节点 -->
              <template #node-dedup="props">
                <div class="custom-node dedup-node" :class="{ selected: selectedNode?.id === props.id }">
                  <Handle type="target" :position="Position.Left" />
                  <div class="node-header">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00ff88" stroke-width="2">
                      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
                    </svg>
                    <span>去重</span>
                  </div>
                  <div class="node-body">
                    {{ props.data?.config?.fields?.length ? `${props.data.config.fields.length} 个字段` : '未配置字段' }}
                  </div>
                  <Handle type="source" :position="Position.Right" />
                </div>
              </template>

              <!-- 空值处理节点 -->
              <template #node-nullfill="props">
                <div class="custom-node nullfill-node" :class="{ selected: selectedNode?.id === props.id }">
                  <Handle type="target" :position="Position.Left" />
                  <div class="node-header">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ffaa00" stroke-width="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="8" y1="12" x2="16" y2="12" stroke-dasharray="2 2" />
                    </svg>
                    <span>空值处理</span>
                  </div>
                  <div class="node-body">
                    <template v-if="props.data?.config?.fields?.length">
                      {{ props.data.config.fields.length }} 个字段 · {{ nullfillStrategyName(props.data.config.strategy) }}
                    </template>
                    <template v-else>未配置字段</template>
                  </div>
                  <Handle type="source" :position="Position.Right" />
                </div>
              </template>
            </VueFlow>
          </div>

          <!-- 右侧配置面板 -->
          <div class="config-panel">
            <template v-if="selectedNode">
              <div class="panel-title">
                {{ selectedNode.data?.nodeType === 'source' ? '数据源配置' : selectedNode.data?.nodeType === 'dedup' ? '去重配置' : '空值处理配置' }}
              </div>

              <!-- 数据源配置 -->
              <template v-if="selectedNode.data?.nodeType === 'source'">
                <div class="config-item">
                  <label>选择数据表</label>
                  <el-select
                    :model-value="selectedNode.data?.config?.tableName || ''"
                    placeholder="请选择数据表"
                    filterable
                    :loading="tableLoading"
                    style="width: 100%"
                    @change="onSourceTableChange"
                  >
                    <el-option v-for="t in tableList" :key="t" :label="t" :value="t" />
                  </el-select>
                </div>
              </template>

              <!-- 去重配置 -->
              <template v-if="selectedNode.data?.nodeType === 'dedup'">
                <div class="config-item">
                  <label>去重判定字段（多选）</label>
                  <div class="field-select-header">
                    <el-button size="small" :loading="columnLoading" @click="onNodeSelectedForConfig">
                      刷新字段
                    </el-button>
                    <span v-if="columnList.length === 0 && !columnLoading" class="field-tip">
                      请先配置上游数据源并连线
                    </span>
                  </div>
                  <el-select
                    :model-value="selectedNode.data?.config?.fields || []"
                    placeholder="请选择去重字段"
                    multiple
                    filterable
                    :collapse-tags="(selectedNode.data?.config?.fields || []).length > 5"
                    collapse-tags-tooltip
                    :loading="columnLoading"
                    style="width: 100%"
                    @change="onDedupFieldsChange"
                  >
                    <el-option
                      v-for="col in columnList"
                      :key="col.fieldName"
                      :label="`${col.fieldName} (${col.fieldType})`"
                      :value="col.fieldName"
                    />
                  </el-select>
                  <div class="config-tip">按所选字段组合去重，保留每组第一条数据</div>
                </div>
              </template>

              <!-- 空值处理配置 -->
              <template v-if="selectedNode.data?.nodeType === 'nullfill'">
                <div class="config-item">
                  <label>处理字段（多选）</label>
                  <div class="field-select-header">
                    <el-button size="small" :loading="columnLoading" @click="onNodeSelectedForConfig">
                      刷新字段
                    </el-button>
                    <span v-if="columnList.length === 0 && !columnLoading" class="field-tip">
                      请先配置上游数据源并连线
                    </span>
                  </div>
                  <!-- 字段区间选择器 -->
                  <div class="range-selector">
                    <div class="range-selector-row">
                      <el-input
                        v-model="nullFillRangeStart"
                        size="small"
                        placeholder="起始字段名"
                        style="width: 140px"
                      />
                      <span class="range-separator">~</span>
                      <el-input
                        v-model="nullFillRangeEnd"
                        size="small"
                        placeholder="结束字段名"
                        style="width: 140px"
                      />
                      <el-button size="small" type="primary" @click="onAddNullFillRange">
                        添加区间
                      </el-button>
                    </div>
                    <div class="config-tip">
                      输入起止字段名（如 time0000 ~ time2300），自动勾选同前缀+数字区间内所有字段
                    </div>
                  </div>
                  <el-select
                    :model-value="selectedNode.data?.config?.fields || []"
                    placeholder="请选择需要处理空值的字段"
                    multiple
                    filterable
                    :collapse-tags="(selectedNode.data?.config?.fields || []).length > 5"
                    collapse-tags-tooltip
                    :loading="columnLoading"
                    style="width: 100%"
                    @change="onNullFillFieldsChange"
                  >
                    <el-option
                      v-for="col in columnList"
                      :key="col.fieldName"
                      :label="`${col.fieldName} (${col.fieldType})`"
                      :value="col.fieldName"
                    />
                  </el-select>
                  <div v-if="(selectedNode.data?.config?.fields || []).length > 0" class="field-count-bar">
                    <span>已选 {{ (selectedNode.data?.config?.fields || []).length }} 个字段</span>
                    <el-button size="small" link type="danger" @click="onClearNullFillFields">清空</el-button>
                  </div>
                </div>
                <div class="config-item">
                  <label>处理方式</label>
                  <el-select
                    :model-value="selectedNode.data?.config?.strategy || 'drop'"
                    placeholder="请选择处理方式"
                    style="width: 100%"
                    @change="onNullFillStrategyChange"
                  >
                    <el-option value="drop" label="删除空值行" />
                    <el-option value="fill" label="填充固定值" />
                    <el-option value="ffill" label="前向填充（用上一行同字段值）" />
                    <el-option value="bfill" label="后向填充（用下一行同字段值）" />
                    <el-option value="interpolate" label="线性插值（上下行插值）" />
                    <el-option value="mean" label="均值填充" />
                    <el-option value="median" label="中位数填充" />
                    <el-option value="hfill_forward" label="横向向前填充（用同一行前一字段值）" />
                    <el-option value="hfill_backward" label="横向向后填充（用同一行后一字段值）" />
                    <el-option value="hinterpolate" label="横向插值（同一行前后字段插值）" />
                  </el-select>
                </div>
                <div v-if="selectedNode.data?.config?.strategy === 'fill'" class="config-item">
                  <label>填充值</label>
                  <el-input
                    :model-value="selectedNode.data?.config?.fillValue || ''"
                    placeholder="请输入填充值"
                    style="width: 100%"
                    @input="onNullFillValueChange"
                  />
                  <div class="config-tip">空值将被替换为该值</div>
                </div>
              </template>

              <!-- 删除节点按钮 -->
              <div class="panel-footer">
                <el-button
                  type="danger"
                  size="small"
                  class="delete-node-btn"
                  @click="deleteSelectedNode"
                >删除节点</el-button>
              </div>
            </template>

            <template v-else>
              <div class="panel-empty">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="rgba(0,212,255,0.3)" stroke-width="1.5">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 8v4M12 16h.01" />
                </svg>
                <p>点击节点进行配置</p>
                <p class="panel-tip">从左侧拖拽算子到画布</p>
              </div>
            </template>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped lang="scss">
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0d1117;
  overflow: hidden;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: rgba(17, 24, 39, 0.6);
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
}

.top-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  background: rgba(0, 212, 255, 0.1) !important;
  border: 1px solid rgba(0, 212, 255, 0.3) !important;
  color: #00d4ff !important;
  display: flex;
  align-items: center;
  gap: 4px;

  &:hover {
    background: rgba(0, 212, 255, 0.2) !important;
  }
}

.task-no {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

.top-right {
  .el-button--primary {
    background: linear-gradient(135deg, #00d4ff, #0099cc) !important;
    border: none !important;
    color: #0d1117 !important;
    font-weight: 600;
    display: flex;
    align-items: center;
  }
}

.basic-info {
  display: flex;
  gap: 20px;
  padding: 12px 24px;
  background: rgba(17, 24, 39, 0.4);
  border-bottom: 1px solid rgba(0, 212, 255, 0.1);
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;

  label {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.5);
    white-space: nowrap;
  }

  .el-input {
    width: 240px;
  }
}

.canvas-area {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.operator-palette {
  width: 160px;
  flex-shrink: 0;
  background: rgba(17, 24, 39, 0.6);
  border-right: 1px solid rgba(0, 212, 255, 0.15);
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.palette-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.palette-tip {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: -8px;
}

.operator-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(0, 212, 255, 0.05);
  border: 1px solid;
  border-radius: 8px;
  cursor: grab;
  transition: all 0.2s;

  &:hover {
    background: rgba(0, 212, 255, 0.1);
    transform: translateY(-1px);
  }

  &:active {
    cursor: grabbing;
  }
}

.operator-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.operator-name {
  font-size: 13px;
  font-weight: 600;
}

.flow-canvas {
  flex: 1;
  position: relative;
  background: #0a0e14;
  overflow: hidden;
}

.vue-flow-container {
  width: 100%;
  height: 100%;
}

.canvas-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
}

.config-panel {
  width: 280px;
  flex-shrink: 0;
  background: rgba(17, 24, 39, 0.6);
  border-left: 1px solid rgba(0, 212, 255, 0.15);
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 8px;

  label {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.7);
  }
}

.config-tip {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1.5;
}

.field-select-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.field-tip {
  font-size: 12px;
  color: #ff6b6b;
}

.range-selector {
  padding: 10px 12px;
  background: rgba(0, 212, 255, 0.06);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  margin-bottom: 8px;
}

.range-selector-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.range-label {
  font-size: 14px;
  color: #00d4ff;
  font-weight: 600;
}

.range-separator {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.field-count-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
  padding: 4px 8px;
  background: rgba(0, 212, 255, 0.05);
  border-radius: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.panel-footer {
  margin-top: auto;
  padding-top: 16px;
}

.delete-node-btn {
  width: 100%;
  background: rgba(255, 85, 85, 0.1) !important;
  border: 1px solid rgba(255, 85, 85, 0.3) !important;
  color: #ff5555 !important;

  &:hover {
    background: rgba(255, 85, 85, 0.2) !important;
  }
}

.panel-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;

  p {
    color: rgba(255, 255, 255, 0.4);
    font-size: 13px;
    margin: 0;
  }

  .panel-tip {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.3);
  }
}
</style>

<style lang="scss">
// Vue Flow 自定义节点样式
.custom-node {
  min-width: 160px;
  border-radius: 8px;
  border: 2px solid;
  background: rgba(17, 24, 39, 0.95);
  overflow: hidden;
  transition: box-shadow 0.2s;

  &.selected {
    box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.4);
  }
}

.source-node {
  border-color: #00d4ff;
}

.dedup-node {
  border-color: #00ff88;
}

.nullfill-node {
  border-color: #ffaa00;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;

  .source-node & {
    background: rgba(0, 212, 255, 0.15);
    color: #00d4ff;
  }

  .dedup-node & {
    background: rgba(0, 255, 136, 0.15);
    color: #00ff88;
  }

  .nullfill-node & {
    background: rgba(255, 170, 0, 0.15);
    color: #ffaa00;
  }
}

.node-body {
  padding: 8px 12px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

// Vue Flow 通用样式覆盖
.vue-flow__edge-path {
  stroke: #00d4ff;
  stroke-width: 2;
}

.vue-flow__edge.animated .vue-flow__edge-path {
  stroke-dasharray: 5;
  animation: dashdraw 0.5s linear infinite;
}

.vue-flow__handle {
  width: 10px;
  height: 10px;
  background: #00d4ff;
  border: 2px solid #0d1117;
}

.vue-flow__controls {
  background: rgba(17, 24, 39, 0.9);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  overflow: hidden;

  .vue-flow__controls-button {
    background: transparent;
    border-bottom: 1px solid rgba(0, 212, 255, 0.15);
    fill: rgba(255, 255, 255, 0.7);

    &:hover {
      background: rgba(0, 212, 255, 0.15);
    }
  }
}
</style>
