<script setup lang="ts">
import { ref, reactive, computed, onMounted, markRaw, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { ElMessage } from 'element-plus'
import { VueFlow, useVueFlow, Handle, Position, type Node, type Edge, type Connection, type EdgeChange } from '@vue-flow/core'
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
  onEdgesChange,
  onEdgeClick,
  addEdges,
  addNodes,
  removeEdges,
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

// 选中连线
const selectedEdge = ref<Edge | null>(null)

// ========== 算子面板拖拽 ==========
const operators = [
  { type: 'source', name: '数据源', icon: 'database', color: '#00d4ff' },
  { type: 'dedup', name: '去重', icon: 'filter', color: '#00ff88' },
  { type: 'nullfill', name: '空值处理(统一处理)', icon: 'null', color: '#ffaa00' },
  { type: 'nullfill_short', name: '短期空值处理(1个点)', icon: 'null', color: '#ffcc44' },
  { type: 'nullfill_medium', name: '中期空值处理(2~4连续点)', icon: 'null', color: '#ff9966' },
  { type: 'nullfill_long', name: '长期空值处理(>4连续点且占比<50%)', icon: 'null', color: '#ff6600' },
  { type: 'outlier', name: '异常值处理', icon: 'alert', color: '#ff4488' },
  { type: 'dateformat', name: '日期格式标准化', icon: 'calendar', color: '#9b59ff' },
  { type: 'str2num', name: '字符替换', icon: 'hash', color: '#00ccaa' },
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
          : opType === 'outlier'
            ? { fields: [], checkNegative: true, absThreshold: null, strategy: 'setnull' }
            : opType === 'dateformat'
              ? { field: '', targetFormat: '%Y-%m-%d' }
              : opType === 'str2num'
                ? { fields: [], replaceFrom: '', replaceTo: '' }
              : { fields: [], strategy: 'drop', fillValue: '', treatZeroAsNull: false },
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

// 处理连线删除
onEdgesChange((changes: EdgeChange[]) => {
  for (const change of changes) {
    if (change.type === 'remove') {
      edges.value = edges.value.filter(e => e.id !== change.id)
      if (selectedEdge.value?.id === change.id) {
        selectedEdge.value = null
      }
    } else if (change.type === 'select') {
      // 更新选中状态
      const edge = edges.value.find(e => e.id === change.id)
      if (edge && change.selected) {
        selectedEdge.value = edge
      } else if (selectedEdge.value?.id === change.id && !change.selected) {
        selectedEdge.value = null
      }
    }
  }
})

// 连线点击事件
onEdgeClick(({ edge }) => {
  // 清除其他边的选中状态
  edges.value.forEach(e => {
    e.selected = false
  })
  // 设置当前边为选中状态
  const clickedEdge = edges.value.find(e => e.id === edge.id)
  if (clickedEdge) {
    clickedEdge.selected = true
  }
  selectedEdge.value = edge as Edge
  selectedNode.value = null
})

// ========== 节点选中 ==========
onPaneClick(() => {
  selectedNode.value = null
  selectedEdge.value = null
  // 清除所有边的选中状态
  edges.value.forEach(e => {
    e.selected = false
  })
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

// 当选中 dedup / nullfill / outlier / dateformat 节点时，从上游 source 节点获取表名并加载字段
function onNodeSelectedForConfig() {
  const nodeType = selectedNode.value?.data?.nodeType
  if (nodeType === 'dedup' || nodeType === 'nullfill' || nodeType === 'nullfill_short' || nodeType === 'nullfill_medium' || nodeType === 'nullfill_long' || nodeType === 'outlier' || nodeType === 'dateformat' || nodeType === 'str2num') {
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
  } else if (node.data?.nodeType === 'dedup' || node.data?.nodeType === 'nullfill' || node.data?.nodeType === 'nullfill_short' || node.data?.nodeType === 'nullfill_medium' || node.data?.nodeType === 'nullfill_long' || node.data?.nodeType === 'outlier' || node.data?.nodeType === 'dateformat' || node.data?.nodeType === 'str2num') {
    onNodeSelectedForConfig()
  }
}

// 重写 onNodeClick 以加载配置数据
onNodeClick(({ node }) => {
  handleNodeSelect(node)
  selectedEdge.value = null
  // 清除所有边的选中状态
  edges.value.forEach(e => {
    e.selected = false
  })
})

// 删除选中连线
function deleteSelectedEdge() {
  if (!selectedEdge.value) return
  const edgeId = selectedEdge.value.id
  edges.value = edges.value.filter(e => e.id !== edgeId)
  selectedEdge.value = null
  // 确保其他边的选中状态被清除
  edges.value.forEach(e => {
    e.selected = false
  })
}

// 键盘删除事件处理
function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Delete' || event.key === 'Backspace') {
    // 如果有选中的连线，删除连线
    if (selectedEdge.value) {
      deleteSelectedEdge()
      event.preventDefault()
    }
    // 如果有选中的节点，删除节点
    else if (selectedNode.value) {
      deleteSelectedNode()
      event.preventDefault()
    }
  }
}

// 监听 selectedNode 变化，确保选中 dedup/nullfill 节点时一定触发字段加载
// 使用 nextTick 等待 edges/nodes 的响应式更新完成后再查找上游 source 节点
watch(selectedNode, (newNode) => {
  if (newNode?.data?.nodeType === 'dedup' || newNode?.data?.nodeType === 'nullfill' || newNode?.data?.nodeType === 'nullfill_short' || newNode?.data?.nodeType === 'nullfill_medium' || newNode?.data?.nodeType === 'nullfill_long' || newNode?.data?.nodeType === 'outlier' || newNode?.data?.nodeType === 'dateformat' || newNode?.data?.nodeType === 'str2num') {
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

// 0视为空值复选框
function onTreatZeroAsNullChange(val: boolean) {
  updateSelectedNodeConfig({ treatZeroAsNull: val })
}

// 当 nullfill 节点的填充值变化时，更新配置
function onNullFillValueChange(fillValue: string) {
  updateSelectedNodeConfig({ fillValue })
}

// ========== 异常值处理 ==========
function onOutlierFieldsChange(fields: string[]) {
  updateSelectedNodeConfig({ fields })
}

function onOutlierCheckNegativeChange(val: boolean) {
  updateSelectedNodeConfig({ checkNegative: val })
}

function onOutlierAbsThresholdChange(val: number | null) {
  updateSelectedNodeConfig({ absThreshold: val })
}

function onOutlierStrategyChange(strategy: string) {
  updateSelectedNodeConfig({ strategy })
}

function onClearOutlierFields() {
  onOutlierFieldsChange([])
}

// 异常值处理字段区间选择
const outlierRangeStart = ref('')
const outlierRangeEnd = ref('')

function onAddOutlierRange() {
  const startRaw = outlierRangeStart.value.trim()
  const endRaw = outlierRangeEnd.value.trim()
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
  onOutlierFieldsChange(Array.from(currentFields))
  ElMessage.success(`已添加 ${fieldsToAdd.length} 个字段`)
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

// ========== 日期格式标准化 ==========
// 日期目标格式选项
const dateFormatOptions = [
  { label: 'YYYY-MM-DD（2024-01-31）', value: '%Y-%m-%d' },
  { label: 'YYYY-MM-DD HH:MM:SS（2024-01-31 12:30:45）', value: '%Y-%m-%d %H:%M:%S' },
]

function onDateFormatFieldChange(field: string) {
  updateSelectedNodeConfig({ field })
}

function onDateTargetFormatChange(targetFormat: string) {
  updateSelectedNodeConfig({ targetFormat })
}

// 简化格式显示（用于节点正文）
function dateFormatShort(fmt: string): string {
  if (!fmt) return ''
  const map: Record<string, string> = {
    '%Y-%m-%d': 'YYYY-MM-DD',
    '%Y-%m-%d %H:%M:%S': 'YYYY-MM-DD HH:MM:SS',
  }
  return map[fmt] || fmt
}

// ========== 字符替换 ==========
function onStr2NumFieldsChange(fields: string[]) {
  updateSelectedNodeConfig({ fields })
}

function onStrReplaceFromChange(replaceFrom: string) {
  updateSelectedNodeConfig({ replaceFrom })
}

function onStrReplaceToChange(replaceTo: string) {
  updateSelectedNodeConfig({ replaceTo })
}

function onClearStr2NumFields() {
  onStr2NumFieldsChange([])
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
  const nullfillTypes = ['nullfill', 'nullfill_short', 'nullfill_medium', 'nullfill_long']
  for (const nt of nullfillTypes) {
    const nfNode = currentNodes.find(n => n.data?.nodeType === nt)
    if (nfNode) {
      if (!nfNode.data?.config?.fields || nfNode.data.config.fields.length === 0) {
        const labelMap: Record<string, string> = {
          'nullfill': '空值处理(统一处理)',
          'nullfill_short': '短期空值处理',
          'nullfill_medium': '中期空值处理',
          'nullfill_long': '长期空值处理',
        }
        ElMessage.warning(`请为${labelMap[nt]}节点配置处理字段`)
        return
      }
      if (nfNode.data.config.strategy === 'fill' && !nfNode.data.config.fillValue && nfNode.data.config.fillValue !== 0) {
        ElMessage.warning(`请为${labelMap[nt]}节点配置填充值`)
        return
      }
    }
  }

  // 检查 outlier 节点是否配置了字段
  const outlierNode = currentNodes.find(n => n.data?.nodeType === 'outlier')
  if (outlierNode) {
    if (!outlierNode.data?.config?.fields || outlierNode.data.config.fields.length === 0) {
      ElMessage.warning('请为异常值处理节点配置处理字段')
      return
    }
    const cfg = outlierNode.data.config
    if (!cfg.checkNegative && (cfg.absThreshold === null || cfg.absThreshold === '' || cfg.absThreshold === undefined)) {
      ElMessage.warning('请为异常值处理节点启用负值检测或设置绝对值阈值')
      return
    }
  }

  // 检查 dateformat 节点是否配置完整
  const dateformatNode = currentNodes.find(n => n.data?.nodeType === 'dateformat')
  if (dateformatNode) {
    const cfg = dateformatNode.data.config
    if (!cfg.field) {
      ElMessage.warning('请为日期格式标准化节点选择日期字段')
      return
    }
    if (!cfg.targetFormat) {
      ElMessage.warning('请为日期格式标准化节点选择目标日期格式')
      return
    }
  }

  // 检查 str2num 节点是否配置了字段和替换字符
  const str2numNode = currentNodes.find(n => n.data?.nodeType === 'str2num')
  if (str2numNode) {
    if (!str2numNode.data?.config?.fields || str2numNode.data.config.fields.length === 0) {
      ElMessage.warning('请为字符替换节点配置处理字段')
      return
    }
    if (!str2numNode.data?.config?.replaceFrom) {
      ElMessage.warning('请为字符替换节点输入需替换字符')
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
        defaultLabel = '空值处理(统一处理)'
        defaultConfig = { fields: [], strategy: 'drop', fillValue: '', treatZeroAsNull: false }
      } else if (n.nodeType === 'nullfill_short') {
        defaultLabel = '短期空值处理(1个点)'
        defaultConfig = { fields: [], windowSize: 3, treatZeroAsNull: false }
      } else if (n.nodeType === 'nullfill_medium') {
        defaultLabel = '中期空值处理(2~4连续点)'
        defaultConfig = { fields: [], treatZeroAsNull: false }
      } else if (n.nodeType === 'nullfill_long') {
        defaultLabel = '长期空值处理(>4连续点且占比<50%)'
        defaultConfig = { fields: [], knnK: 5, maxNanRatio: 0.5, treatZeroAsNull: false }
      } else if (n.nodeType === 'outlier') {
        defaultLabel = '异常值处理'
        defaultConfig = { fields: [], checkNegative: true, absThreshold: null, strategy: 'setnull' }
      } else if (n.nodeType === 'dateformat') {
        defaultLabel = '日期格式标准化'
        defaultConfig = { field: '', targetFormat: '%Y-%m-%d' }
      } else if (n.nodeType === 'str2num') {
        defaultLabel = '字符替换'
        defaultConfig = { fields: [], replaceFrom: '', replaceTo: '' }
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
                <svg v-else-if="op.icon === 'null'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="8" y1="12" x2="16" y2="12" stroke-dasharray="2 2" />
                </svg>
                <svg v-else-if="op.icon === 'alert'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                <svg v-else-if="op.icon === 'calendar'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
                <svg v-else-if="op.icon === 'hash'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="4" y1="9" x2="20" y2="9" />
                  <line x1="4" y1="15" x2="20" y2="15" />
                  <line x1="10" y1="3" x2="8" y2="21" />
                  <line x1="16" y1="3" x2="14" y2="21" />
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
          <div class="flow-canvas" tabindex="0" @drop="onDrop" @dragover="onDragOver" @keydown="handleKeyDown">
            <div v-if="loading" class="canvas-loading">加载中...</div>
            <VueFlow
              v-model:nodes="nodes"
              v-model:edges="edges"
              :default-viewport="{ zoom: 1 }"
              :selection-on-drag="true"
              :pan-on-drag="[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]"
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
                      {{ props.data.config.fields.length }} 个字段 · {{ nullfillStrategyName(props.data.config.strategy) }}{{ props.data.config.treatZeroAsNull ? ' · 0视为空值' : '' }}
                    </template>
                    <template v-else>未配置字段</template>
                  </div>
                  <Handle type="source" :position="Position.Right" />
                </div>
              </template>

              <!-- 短期空值处理节点 -->
              <template #node-nullfill_short="props">
                <div class="custom-node nullfill-short-node" :class="{ selected: selectedNode?.id === props.id }">
                  <Handle type="target" :position="Position.Left" />
                  <div class="node-header">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ffcc44" stroke-width="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="8" y1="12" x2="16" y2="12" stroke-dasharray="2 2" />
                    </svg>
                    <span>短期空值处理</span>
                  </div>
                  <div class="node-body">
                    <template v-if="props.data?.config?.fields?.length">
                      {{ props.data.config.fields.length }} 个字段 · 窗口{{ props.data.config.windowSize ?? 3 }}{{ props.data.config.treatZeroAsNull ? ' · 0视为空值' : '' }}
                    </template>
                    <template v-else>未配置字段</template>
                  </div>
                  <Handle type="source" :position="Position.Right" />
                </div>
              </template>

              <!-- 中期空值处理节点 -->
              <template #node-nullfill_medium="props">
                <div class="custom-node nullfill-medium-node" :class="{ selected: selectedNode?.id === props.id }">
                  <Handle type="target" :position="Position.Left" />
                  <div class="node-header">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ff9966" stroke-width="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="8" y1="12" x2="16" y2="12" stroke-dasharray="4 2" />
                    </svg>
                    <span>中期空值处理</span>
                  </div>
                  <div class="node-body">
                    <template v-if="props.data?.config?.fields?.length">
                      {{ props.data.config.fields.length }} 个字段 · 拉格朗日插值{{ props.data.config.treatZeroAsNull ? ' · 0视为空值' : '' }}
                    </template>
                    <template v-else>未配置字段</template>
                  </div>
                  <Handle type="source" :position="Position.Right" />
                </div>
              </template>

              <!-- 长期空值处理节点 -->
              <template #node-nullfill_long="props">
                <div class="custom-node nullfill-long-node" :class="{ selected: selectedNode?.id === props.id }">
                  <Handle type="target" :position="Position.Left" />
                  <div class="node-header">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ff6600" stroke-width="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="8" y1="12" x2="16" y2="12" stroke-dasharray="6 2" />
                    </svg>
                    <span>长期空值处理</span>
                  </div>
                  <div class="node-body">
                    <template v-if="props.data?.config?.fields?.length">
                      {{ props.data.config.fields.length }} 个字段 · K={{ props.data.config.knnK ?? 5 }}{{ props.data.config.treatZeroAsNull ? ' · 0视为空值' : '' }}
                    </template>
                    <template v-else>未配置字段</template>
                  </div>
                  <Handle type="source" :position="Position.Right" />
                </div>
              </template>

              <!-- 异常值处理节点 -->
              <template #node-outlier="props">
                <div class="custom-node outlier-node" :class="{ selected: selectedNode?.id === props.id }">
                  <Handle type="target" :position="Position.Left" />
                  <div class="node-header">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ff4488" stroke-width="2">
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                      <line x1="12" y1="9" x2="12" y2="13" />
                      <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    <span>异常值处理</span>
                  </div>
                  <div class="node-body">
                    <template v-if="props.data?.config?.fields?.length">
                      {{ props.data.config.fields.length }} 个字段 · {{ props.data.config.strategy === 'setnull' ? '置空' : props.data.config.strategy }}
                    </template>
                    <template v-else>未配置字段</template>
                  </div>
                  <Handle type="source" :position="Position.Right" />
                </div>
              </template>

              <!-- 日期格式标准化节点 -->
              <template #node-dateformat="props">
                <div class="custom-node dateformat-node" :class="{ selected: selectedNode?.id === props.id }">
                  <Handle type="target" :position="Position.Left" />
                  <div class="node-header">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9b59ff" stroke-width="2">
                      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                      <line x1="16" y1="2" x2="16" y2="6" />
                      <line x1="8" y1="2" x2="8" y2="6" />
                      <line x1="3" y1="10" x2="21" y2="10" />
                    </svg>
                    <span>日期格式标准化</span>
                  </div>
                  <div class="node-body">
                    <template v-if="props.data?.config?.field">
                      {{ props.data.config.field }} · {{ dateFormatShort(props.data.config.targetFormat) || '未设置格式' }}
                    </template>
                    <template v-else>未配置字段</template>
                  </div>
                  <Handle type="source" :position="Position.Right" />
                </div>
              </template>

              <!-- 字符替换节点 -->
              <template #node-str2num="props">
                <div class="custom-node str2num-node" :class="{ selected: selectedNode?.id === props.id }">
                  <Handle type="target" :position="Position.Left" />
                  <div class="node-header">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00ccaa" stroke-width="2">
                      <line x1="4" y1="9" x2="20" y2="9" />
                      <line x1="4" y1="15" x2="20" y2="15" />
                      <line x1="10" y1="3" x2="8" y2="21" />
                      <line x1="16" y1="3" x2="14" y2="21" />
                    </svg>
                    <span>字符替换</span>
                  </div>
                  <div class="node-body">
                    <template v-if="props.data?.config?.fields?.length">
                      {{ props.data.config.fields.length }} 个字段 · "{{ props.data.config.replaceFrom || '?' }}" → "{{ props.data.config.replaceTo || '' }}"
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
                {{ selectedNode.data?.nodeType === 'source' ? '数据源配置' : selectedNode.data?.nodeType === 'dedup' ? '去重配置' : selectedNode.data?.nodeType === 'nullfill' ? '空值处理(统一处理)配置' : selectedNode.data?.nodeType === 'nullfill_short' ? '短期空值处理配置' : selectedNode.data?.nodeType === 'nullfill_medium' ? '中期空值处理配置' : selectedNode.data?.nodeType === 'nullfill_long' ? '长期空值处理配置' : selectedNode.data?.nodeType === 'outlier' ? '异常值处理配置' : selectedNode.data?.nodeType === 'dateformat' ? '日期格式标准化配置' : '字符替换配置' }}
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
                  <el-checkbox
                    :model-value="selectedNode.data?.config?.treatZeroAsNull || false"
                    @change="onTreatZeroAsNullChange"
                  >
                    0 视为空值
                  </el-checkbox>
                  <div class="config-tip">勾选后，数值列中的 0、0.0 等零值也将作为空值处理</div>
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

              <!-- 短期空值处理配置 -->
              <template v-if="selectedNode.data?.nodeType === 'nullfill_short'">
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
                  <div class="range-selector">
                    <div class="range-selector-row">
                      <el-input v-model="nullFillRangeStart" size="small" placeholder="起始字段名" style="width: 140px" />
                      <span class="range-separator">~</span>
                      <el-input v-model="nullFillRangeEnd" size="small" placeholder="结束字段名" style="width: 140px" />
                      <el-button size="small" type="primary" @click="onAddNullFillRange">添加区间</el-button>
                    </div>
                    <div class="config-tip">输入起止字段名（如 time0000 ~ time2300），自动勾选同前缀+数字区间内所有字段</div>
                  </div>
                  <el-select
                    :model-value="selectedNode.data?.config?.fields || []"
                    placeholder="请选择需要处理空值的字段"
                    multiple filterable
                    :collapse-tags="(selectedNode.data?.config?.fields || []).length > 5"
                    collapse-tags-tooltip
                    :loading="columnLoading"
                    style="width: 100%"
                    @change="onNullFillFieldsChange"
                  >
                    <el-option v-for="col in columnList" :key="col.fieldName" :label="`${col.fieldName} (${col.fieldType})`" :value="col.fieldName" />
                  </el-select>
                  <div v-if="(selectedNode.data?.config?.fields || []).length > 0" class="field-count-bar">
                    <span>已选 {{ (selectedNode.data?.config?.fields || []).length }} 个字段</span>
                    <el-button size="small" link type="danger" @click="onClearNullFillFields">清空</el-button>
                  </div>
                </div>
                <div class="config-item">
                  <el-checkbox :model-value="selectedNode.data?.config?.treatZeroAsNull || false" @change="onTreatZeroAsNullChange">
                    0 视为空值
                  </el-checkbox>
                  <div class="config-tip">勾选后，数值列中的 0、0.0 等零值也将作为空值处理</div>
                </div>
                <div class="config-item">
                  <label>处理方式</label>
                  <el-select
                    :model-value="selectedNode.data?.config?.strategy || 'sliding_window'"
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
                    <el-option value="sliding_window" label="滑动窗口均值" />
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
                <div v-if="selectedNode.data?.config?.strategy === 'sliding_window' || !selectedNode.data?.config?.strategy" class="config-item">
                  <label>滑动窗口大小</label>
                  <el-input-number
                    :model-value="selectedNode.data?.config?.windowSize ?? 3"
                    :min="1" :max="20" size="small"
                    @change="(val: number) => updateSelectedNodeConfig({ windowSize: val })"
                  />
                  <div class="config-tip">窗口大小决定前后取均值的数据范围（默认3，即前后各取3个点计算均值）</div>
                </div>
              </template>

              <!-- 中期空值处理配置 -->
              <template v-if="selectedNode.data?.nodeType === 'nullfill_medium'">
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
                  <div class="range-selector">
                    <div class="range-selector-row">
                      <el-input v-model="nullFillRangeStart" size="small" placeholder="起始字段名" style="width: 140px" />
                      <span class="range-separator">~</span>
                      <el-input v-model="nullFillRangeEnd" size="small" placeholder="结束字段名" style="width: 140px" />
                      <el-button size="small" type="primary" @click="onAddNullFillRange">添加区间</el-button>
                    </div>
                    <div class="config-tip">输入起止字段名（如 time0000 ~ time2300），自动勾选同前缀+数字区间内所有字段</div>
                  </div>
                  <el-select
                    :model-value="selectedNode.data?.config?.fields || []"
                    placeholder="请选择需要处理空值的字段"
                    multiple filterable
                    :collapse-tags="(selectedNode.data?.config?.fields || []).length > 5"
                    collapse-tags-tooltip
                    :loading="columnLoading"
                    style="width: 100%"
                    @change="onNullFillFieldsChange"
                  >
                    <el-option v-for="col in columnList" :key="col.fieldName" :label="`${col.fieldName} (${col.fieldType})`" :value="col.fieldName" />
                  </el-select>
                  <div v-if="(selectedNode.data?.config?.fields || []).length > 0" class="field-count-bar">
                    <span>已选 {{ (selectedNode.data?.config?.fields || []).length }} 个字段</span>
                    <el-button size="small" link type="danger" @click="onClearNullFillFields">清空</el-button>
                  </div>
                </div>
                <div class="config-item">
                  <el-checkbox :model-value="selectedNode.data?.config?.treatZeroAsNull || false" @change="onTreatZeroAsNullChange">
                    0 视为空值
                  </el-checkbox>
                  <div class="config-tip">勾选后，数值列中的 0、0.0 等零值也将作为空值处理</div>
                </div>
                <div class="config-item">
                  <label>处理方式</label>
                  <el-select
                    :model-value="selectedNode.data?.config?.strategy || 'lagrange'"
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
                    <el-option value="lagrange" label="拉格朗日插值" />
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
                <div v-if="selectedNode.data?.config?.strategy === 'lagrange' || !selectedNode.data?.config?.strategy" class="config-item">
                  <div class="config-tip" style="padding: 8px 12px; background: rgba(255,153,102,0.1); border-radius: 4px; border-left: 3px solid #ff9966;">
                    使用拉格朗日插值法补全连续 2~4 个点的缺失值，自动选取缺失段附近最近的 6 个有效点作为参考，失败时回退为线性插值
                  </div>
                </div>
              </template>

              <!-- 长期空值处理配置 -->
              <template v-if="selectedNode.data?.nodeType === 'nullfill_long'">
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
                  <div class="range-selector">
                    <div class="range-selector-row">
                      <el-input v-model="nullFillRangeStart" size="small" placeholder="起始字段名" style="width: 140px" />
                      <span class="range-separator">~</span>
                      <el-input v-model="nullFillRangeEnd" size="small" placeholder="结束字段名" style="width: 140px" />
                      <el-button size="small" type="primary" @click="onAddNullFillRange">添加区间</el-button>
                    </div>
                    <div class="config-tip">输入起止字段名（如 time0000 ~ time2300），自动勾选同前缀+数字区间内所有字段</div>
                  </div>
                  <el-select
                    :model-value="selectedNode.data?.config?.fields || []"
                    placeholder="请选择需要处理空值的字段"
                    multiple filterable
                    :collapse-tags="(selectedNode.data?.config?.fields || []).length > 5"
                    collapse-tags-tooltip
                    :loading="columnLoading"
                    style="width: 100%"
                    @change="onNullFillFieldsChange"
                  >
                    <el-option v-for="col in columnList" :key="col.fieldName" :label="`${col.fieldName} (${col.fieldType})`" :value="col.fieldName" />
                  </el-select>
                  <div v-if="(selectedNode.data?.config?.fields || []).length > 0" class="field-count-bar">
                    <span>已选 {{ (selectedNode.data?.config?.fields || []).length }} 个字段</span>
                    <el-button size="small" link type="danger" @click="onClearNullFillFields">清空</el-button>
                  </div>
                </div>
                <div class="config-item">
                  <el-checkbox :model-value="selectedNode.data?.config?.treatZeroAsNull || false" @change="onTreatZeroAsNullChange">
                    0 视为空值
                  </el-checkbox>
                  <div class="config-tip">勾选后，数值列中的 0、0.0 等零值也将作为空值处理</div>
                </div>
                <div class="config-item">
                  <label>处理方式</label>
                  <el-select
                    :model-value="selectedNode.data?.config?.strategy || 'knn'"
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
                    <el-option value="knn" label="KNN 补全" />
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
                <div v-if="selectedNode.data?.config?.strategy === 'knn' || !selectedNode.data?.config?.strategy" class="config-item">
                  <label>KNN 邻居数 (K)</label>
                  <el-input-number
                    :model-value="selectedNode.data?.config?.knnK ?? 5"
                    :min="1" :max="20" size="small"
                    @change="(val: number) => updateSelectedNodeConfig({ knnK: val })"
                  />
                  <div class="config-tip">KNN 补全时参考的最近邻居数量（默认5）</div>
                </div>
                <div v-if="selectedNode.data?.config?.strategy === 'knn' || !selectedNode.data?.config?.strategy" class="config-item">
                  <label>最大缺失占比</label>
                  <el-input-number
                    :model-value="selectedNode.data?.config?.maxNanRatio ?? 0.5"
                    :min="0.1" :max="0.9" :step="0.05" size="small"
                    @change="(val: number) => updateSelectedNodeConfig({ maxNanRatio: val })"
                  />
                  <div class="config-tip">连续缺失段占比超过此阈值时跳过补全（默认0.5，即50%）</div>
                </div>
                <div v-if="selectedNode.data?.config?.strategy === 'knn' || !selectedNode.data?.config?.strategy" class="config-item">
                  <div class="config-tip" style="padding: 8px 12px; background: rgba(255,102,0,0.1); border-radius: 4px; border-left: 3px solid #ff6600;">
                    使用 KNN 算法补全连续 >4 个点且占比 &lt;50% 的缺失值，利用数据集中所有数值列作为特征进行最近邻插补
                  </div>
                </div>
              </template>

              <!-- 异常值处理配置 -->
              <template v-if="selectedNode.data?.nodeType === 'outlier'">
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
                        v-model="outlierRangeStart"
                        size="small"
                        placeholder="起始字段名"
                        style="width: 140px"
                      />
                      <span class="range-separator">~</span>
                      <el-input
                        v-model="outlierRangeEnd"
                        size="small"
                        placeholder="结束字段名"
                        style="width: 140px"
                      />
                      <el-button size="small" type="primary" @click="onAddOutlierRange">
                        添加区间
                      </el-button>
                    </div>
                    <div class="config-tip">
                      输入起止字段名（如 time0000 ~ time2300），自动勾选同前缀+数字区间内所有字段
                    </div>
                  </div>
                  <el-select
                    :model-value="selectedNode.data?.config?.fields || []"
                    placeholder="请选择需要处理异常值的字段"
                    multiple
                    filterable
                    :collapse-tags="(selectedNode.data?.config?.fields || []).length > 5"
                    collapse-tags-tooltip
                    :loading="columnLoading"
                    style="width: 100%"
                    @change="onOutlierFieldsChange"
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
                    <el-button size="small" link type="danger" @click="onClearOutlierFields">清空</el-button>
                  </div>
                </div>
                <div class="config-item">
                  <label>检测条件</label>
                  <div class="outlier-condition">
                    <el-checkbox
                      :model-value="selectedNode.data?.config?.checkNegative !== false"
                      @change="onOutlierCheckNegativeChange"
                    >检测负值</el-checkbox>
                  </div>
                  <div class="outlier-condition" style="margin-top: 8px;">
                    <el-checkbox
                      :model-value="selectedNode.data?.config?.absThreshold !== null && selectedNode.data?.config?.absThreshold !== '' && selectedNode.data?.config?.absThreshold !== undefined"
                      @change="(val: boolean) => onOutlierAbsThresholdChange(val ? 0 : null)"
                    >绝对值超过阈值</el-checkbox>
                    <el-input-number
                      v-if="selectedNode.data?.config?.absThreshold !== null && selectedNode.data?.config?.absThreshold !== '' && selectedNode.data?.config?.absThreshold !== undefined"
                      :model-value="selectedNode.data?.config?.absThreshold"
                      :min="0"
                      :precision="2"
                      :step="1"
                      size="small"
                      style="width: 140px; margin-left: 8px;"
                      @change="onOutlierAbsThresholdChange"
                    />
                  </div>
                  <div class="config-tip">勾选需要检测的异常条件，满足任一条件的值将被处理</div>
                </div>
                <div class="config-item">
                  <label>处理方式</label>
                  <el-select
                    :model-value="selectedNode.data?.config?.strategy || 'setnull'"
                    placeholder="请选择处理方式"
                    style="width: 100%"
                    @change="onOutlierStrategyChange"
                  >
                    <el-option value="setnull" label="置空" />
                  </el-select>
                  <div class="config-tip">异常值将被置为空值（null）</div>
                </div>
              </template>

              <!-- 日期格式标准化配置 -->
              <template v-if="selectedNode.data?.nodeType === 'dateformat'">
                <div class="config-item">
                  <label>日期字段（单选）</label>
                  <div class="field-select-header">
                    <el-button size="small" :loading="columnLoading" @click="onNodeSelectedForConfig">
                      刷新字段
                    </el-button>
                    <span v-if="columnList.length === 0 && !columnLoading" class="field-tip">
                      请先配置上游数据源并连线
                    </span>
                  </div>
                  <el-select
                    :model-value="selectedNode.data?.config?.field || ''"
                    placeholder="请选择日期字段"
                    filterable
                    clearable
                    :loading="columnLoading"
                    style="width: 100%"
                    @change="onDateFormatFieldChange"
                  >
                    <el-option
                      v-for="col in columnList"
                      :key="col.fieldName"
                      :label="`${col.fieldName} (${col.fieldType})`"
                      :value="col.fieldName"
                    />
                  </el-select>
                  <div class="config-tip">选择数据表中存储日期的字段（支持 varchar 类型）</div>
                </div>
                <div class="config-item">
                  <label>目标日期格式</label>
                  <el-select
                    :model-value="selectedNode.data?.config?.targetFormat || '%Y-%m-%d'"
                    placeholder="请选择目标格式"
                    style="width: 100%"
                    @change="onDateTargetFormatChange"
                  >
                    <el-option
                      v-for="opt in dateFormatOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                  <div class="config-tip">标准化后输出的日期格式</div>
                </div>
              </template>

              <!-- 字符替换配置 -->
              <template v-if="selectedNode.data?.nodeType === 'str2num'">
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
                  <el-select
                    :model-value="selectedNode.data?.config?.fields || []"
                    placeholder="请选择需要替换的字段"
                    multiple
                    filterable
                    :collapse-tags="(selectedNode.data?.config?.fields || []).length > 5"
                    collapse-tags-tooltip
                    :loading="columnLoading"
                    style="width: 100%"
                    @change="onStr2NumFieldsChange"
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
                    <el-button size="small" link type="danger" @click="onClearStr2NumFields">清空</el-button>
                  </div>
                </div>
                <div class="config-item">
                  <label>需替换字符</label>
                  <el-input
                    :model-value="selectedNode.data?.config?.replaceFrom || ''"
                    placeholder="输入需替换的字符，如 °、%、$ 等"
                    clearable
                    style="width: 100%"
                    @input="onStrReplaceFromChange"
                  />
                </div>
                <div class="config-item">
                  <label>替换后字符</label>
                  <el-input
                    :model-value="selectedNode.data?.config?.replaceTo || ''"
                    placeholder="可为空，表示直接删除该字符"
                    clearable
                    style="width: 100%"
                    @input="onStrReplaceToChange"
                  />
                  <div class="config-tip">将字段值中的"需替换字符"替换为"替换后字符"，替换后字符为空则直接删除</div>
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
  overflow-y: auto;
  max-height: 100%;
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
  outline: none;

  &:focus {
    outline: none;
  }
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
  overflow-y: auto;
  max-height: 100%;
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

.outlier-condition {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
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

.nullfill-short-node {
  border-color: #ffcc44;
}

.nullfill-medium-node {
  border-color: #ff9966;
}

.nullfill-long-node {
  border-color: #ff6600;
}

.outlier-node {
  border-color: #ff4488;
}

.dateformat-node {
  border-color: #9b59ff;
}

.str2num-node {
  border-color: #00ccaa;
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

  .nullfill-short-node & {
    background: rgba(255, 204, 68, 0.15);
    color: #ffcc44;
  }

  .nullfill-medium-node & {
    background: rgba(255, 153, 102, 0.15);
    color: #ff9966;
  }

  .nullfill-long-node & {
    background: rgba(255, 102, 0, 0.15);
    color: #ff6600;
  }

  .outlier-node & {
    background: rgba(255, 68, 136, 0.15);
    color: #ff4488;
  }

  .dateformat-node & {
    background: rgba(155, 89, 255, 0.15);
    color: #9b59ff;
  }

  .str2num-node & {
    background: rgba(0, 204, 170, 0.15);
    color: #00ccaa;
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

.vue-flow__edge.selected .vue-flow__edge-path {
  stroke: #ff4488;
  stroke-width: 3;
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
