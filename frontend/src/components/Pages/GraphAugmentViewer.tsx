import React, { useCallback, useMemo, useState, useEffect } from 'react'
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
  type Node,
  type Edge,
  Panel,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { Card, CardContent, CardHeader, CardTitle, Loading } from '@/components/UI'
import type { GraphAugmentResult, GraphAugmentExtractResult, GraphAugmentNode, GraphAugmentRelationship } from '@/types'

interface GraphAugmentViewerProps {
  result: GraphAugmentResult | null
  extract: GraphAugmentExtractResult | null
  isLoading: boolean
  status: string | null
  stage: string | null
  progressMessages: string[]
  error: string | null
  onStart: () => void
  canStart: boolean
}

const getNodeTypeLabel = (type: string): string => {
  const labels: Record<string, string> = {
    events: '事件',
    market_variables: '市场变量',
    variable_changes: '变量变化',
    valuation_outcomes: '估值结果',
  }
  return labels[type] || type
}

const getDirectionColor = (direction?: 'up' | 'down'): { bg: string, border: string, text: string } => {
  if (direction === 'up') return { 
    bg: 'rgba(248, 113, 113, 0.15)', 
    border: '#f87171', 
    text: '#fca5a5' 
  }
  if (direction === 'down') return { 
    bg: 'rgba(74, 222, 128, 0.15)', 
    border: '#4ade80', 
    text: '#86efac' 
  }
  return { 
    bg: 'rgba(148, 163, 184, 0.15)', 
    border: '#94a3b8', 
    text: '#cbd5e1' 
  }
}

const getNodeColors = (category: string): { bg: string, border: string } => {
  switch (category) {
    case 'events':
      return { bg: '#3b82f6', border: '#2563eb' }
    case 'market_variables':
      return { bg: '#22c55e', border: '#16a34a' }
    case 'variable_changes':
      return { bg: '#f97316', border: '#ea580c' }
    case 'valuation_outcomes':
      return { bg: '#a855f7', border: '#9333ea' }
    default:
      return { bg: '#6b7280', border: '#4b5563' }
  }
}

// 将图谱数据转换为 ReactFlow 格式
const convertToGraphFlow = (result: GraphAugmentResult): {
  nodes: Node[],
  edges: Edge[],
  marketVariables: Array<{id: string; label: string; direction?: 'up' | 'down'}>
} => {
  const nodes: Node[] = []
  const edges: Edge[] = []

  // 网格布局参数 - 按类型分列排列
  const gridSize = 140
  let x = 0
  let y = 0

  // 分类放置节点
  const categories: Array<{ type: keyof GraphAugmentResult, nodes: GraphAugmentNode[] }> = [
    { type: 'events', nodes: result.events },
    { type: 'market_variables', nodes: result.market_variables },
    { type: 'variable_changes', nodes: result.variable_changes },
    { type: 'valuation_outcomes', nodes: result.valuation_outcomes },
  ]

  // 单独分离出市场变量，不在图中显示，放到列表展示
  const marketVariables: Array<{id: string; label: string; direction?: 'up' | 'down'}> = []

  categories.forEach(({ type, nodes: categoryNodes }) => {
    if (type === 'market_variables') {
      // 市场变量收集起来不加入图布局
      marketVariables.push(...categoryNodes.map(node => ({
        id: node.id,
        label: node.label,
        direction: node.direction
      })))
      return
    }

    categoryNodes.forEach((node, idx) => {
      const colors = getNodeColors(type)
      nodes.push({
        id: node.id,
        type: 'custom',
        data: {
          label: node.label,
          direction: node.direction,
          category: type
        },
        position: { x: x, y: y },
        style: {
          background: colors.bg,
          border: `3px solid ${colors.border}`,
          color: 'white',
          borderRadius: '12px',
          padding: '12px 16px',
          fontSize: '13px',
          minWidth: '80px',
          maxWidth: '180px',
          textAlign: 'center',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.25)',
          transition: 'all 0.2s ease',
          cursor: 'pointer',
        },
      })
      y += gridSize
    })
    x += 260
    y = 0
  })

  // 创建节点 ID 集合用于验证
  const nodeIds = new Set(nodes.map(node => node.id))
  
  // 转换关系为边，只添加源节点和目标节点都存在的边
  result.relationships.forEach((rel: GraphAugmentRelationship) => {
    // 跳过不存在的节点
    if (
      !rel.source ||
      !rel.target ||
      !nodeIds.has(rel.source) ||
      !nodeIds.has(rel.target)
    ) {
      return;
    }
    
    // 根据关系类型判断颜色
    let strokeColor = '#94a3b8'
    if (rel.relation.includes('促进') || rel.relation.includes('上涨') || rel.relation.includes('提升') || rel.relation.includes('增加')) {
      strokeColor = '#f87171'
    } else if (rel.relation.includes('抑制') || rel.relation.includes('下跌') || rel.relation.includes('降低') || rel.relation.includes('减少')) {
      strokeColor = '#4ade80'
    }

    edges.push({
      id: `${rel.source}-${rel.target}-${rel.relation}`,
      source: rel.source,
      target: rel.target,
      animated: true,
      style: {
        stroke: strokeColor,
        strokeWidth: 2,
      },
    });
  })

  return { nodes, edges, marketVariables }
}

// 自定义节点组件
const CustomNode = ({ data }: { data: any }) => {
  const directionInfo = getDirectionColor(data.direction)
  
  return (
    <>
      {/* 左侧目标句柄 */}
      <Handle type="target" position={Position.Left} className="w-2 h-2 bg-gray-300" />
      
      <div className="flex flex-col items-center gap-1">
        <div className="font-medium leading-snug break-words">
          {data.label}
        </div>
        {data.direction && (
          <div
            className="text-xs px-2 py-0.5 rounded-full border mt-1 whitespace-nowrap"
            style={{
              backgroundColor: directionInfo.bg,
              borderColor: directionInfo.border,
              color: directionInfo.text,
            }}
          >
            {data.direction === 'up' ? '↑ 上涨' : '↓ 下跌'}
          </div>
        )}
      </div>
      
      {/* 右侧源句柄 */}
      <Handle type="source" position={Position.Right} className="w-2 h-2 bg-gray-300" />
    </>
  )
}

const nodeTypes = {
  custom: CustomNode,
};

// 在组件外部定义以避免重复创建
const edgeTypes = {};


// 需要包裹在 ReactFlowProvider 外，这里创建一个内部组件使用 useReactFlow
const GraphAugmentFlowInner: React.FC<{
  result: GraphAugmentResult
}> = ({ result }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [legendCollapsed, setLegendCollapsed] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [marketVariables, setMarketVariables] = useState<Array<{id: string; label: string; direction?: 'up' | 'down'}>>([])
  const reactFlow = useReactFlow()

  // 使用 ref 保持对最新 edges 的引用，避免闭包问题
  const edgesRef = React.useRef<Edge[]>(edges)
  React.useEffect(() => {
    edgesRef.current = edges
  }, [edges])

  // 当结果变化时更新图谱
  useEffect(() => {
    if (result) {
      const { nodes: graphNodes, edges: graphEdges, marketVariables: mvs } = convertToGraphFlow(result)
      setNodes(graphNodes)
      setEdges(graphEdges)
      setMarketVariables(mvs)
    } else {
      setNodes([])
      setEdges([])
    }
    setSelectedNodeId(null)
  }, [result, setNodes, setEdges])

  // 禁用节点点击交互，只保留拖拽移动
  const onNodeClick = undefined
  const onPaneClick = undefined

  // 节点搜索
  const filteredNodes = useMemo(() => {
    if (!searchQuery.trim()) return []
    return nodes.filter(n => 
      n.data.label?.toLowerCase().includes(searchQuery.toLowerCase())
    )
  }, [nodes, searchQuery])

  // 跳转到指定节点
  const goToNode = useCallback((nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId)
    if (!node) return
    
    reactFlow.setCenter(node.position.x, node.position.y, { zoom: 1.5, duration: 800 })
    setSearchQuery('')
  }, [nodes, reactFlow])

  // 快捷控制
  const handleFitView = useCallback(() => {
    reactFlow.fitView({ padding: 0.2, duration: 500 })
  }, [reactFlow])

  const handleZoomIn = useCallback(() => {
    reactFlow.zoomIn({ duration: 200 })
  }, [reactFlow])

  const handleZoomOut = useCallback(() => {
    reactFlow.zoomOut({ duration: 200 })
  }, [reactFlow])

  return (
    <>
      {/* 顶部搜索和控制栏 */}
      <div className="flex flex-col sm:flex-row gap-3 mb-3 items-center justify-between">
        {/* 节点搜索 */}
        <div className="relative w-full sm:w-64">
          <input
            type="text"
            placeholder="搜索节点..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
          {searchQuery && filteredNodes.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-10">
              {filteredNodes.map(node => (
                <button
                  key={node.id}
                  onClick={() => goToNode(node.id)}
                  className="w-full text-left px-3 py-2 text-sm text-white hover:bg-gray-700 transition-colors"
                >
                  {node.data.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 快捷缩放控制 */}
        <div className="flex items-center gap-1">
          <button
            onClick={handleZoomOut}
            className="px-2 py-1 bg-gray-800 border border-gray-700 rounded hover:bg-gray-700 text-white text-sm transition-colors"
            title="缩小"
          >
            −
          </button>
          <button
            onClick={handleFitView}
            className="px-2 py-1 bg-gray-800 border border-gray-700 rounded hover:bg-gray-700 text-white text-sm transition-colors"
            title="适应画布"
          >
            □
          </button>
          <button
            onClick={handleZoomIn}
            className="px-2 py-1 bg-gray-800 border border-gray-700 rounded hover:bg-gray-700 text-white text-sm transition-colors"
            title="放大"
          >
            +
          </button>
        </div>
      </div>

      <div className="p-2 bg-gray-800/30 rounded-lg border border-gray-700">
        <div className="h-[500px] w-full bg-gray-900/50 rounded">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            fitView
            proOptions={{ hideAttribution: true }}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            nodesDraggable={true}
            elementsSelectable={false}
          >
            <Background color="#374151" gap={16} />
            <MiniMap
              nodeStrokeWidth={3}
              zoomable
              pannable
              className="bg-gray-800/90 border border-gray-700 rounded"
              maskColor="rgba(15, 23, 42, 0.8)"
            />
            <Controls 
              className="bg-gray-800 border border-gray-700 overflow-hidden rounded-lg"
              position="bottom-right"
            />
            <Panel position="top-left" className="bg-gray-800/90 p-2 rounded-lg text-xs text-gray-300">
              <div className="flex items-center gap-2">
                <span className="font-medium">图例</span>
                <button
                  onClick={() => setLegendCollapsed(!legendCollapsed)}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  {legendCollapsed ? '▶' : '▼'}
                </button>
              </div>
              {!legendCollapsed && (
                <div className="flex flex-wrap gap-3 mt-2">
                  <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-500"></span>事件</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-500"></span>市场变量</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-500"></span>变量变化</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-purple-500"></span>估值结果</span>
                </div>
              )}
              {!legendCollapsed && (
                <div className="flex flex-wrap gap-3 mt-2 pt-2 border-t border-gray-700">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400"></span>正向/上涨</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-400"></span>负向/下跌</span>
                </div>
              )}
              {/* 市场变量列表 */}
              {marketVariables.length > 0 && !legendCollapsed && (
                <div className="mt-2 pt-2 border-t border-gray-700">
                  <div className="mb-1 font-medium text-gray-200">市场变量</div>
                  <div className="flex flex-wrap gap-1 mt-1 max-w-[220px]">
                    {marketVariables.map(mv => (
                      <span
                        key={mv.id}
                        className="inline-flex items-center gap-1 px-2 py-1 bg-gray-700 rounded text-xs"
                      >
                        {mv.direction === 'up' && <span className="text-red-400">↑</span>}
                        {mv.direction === 'down' && <span className="text-green-400">↓</span>}
                        {mv.label}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </Panel>
          </ReactFlow>
        </div>
      </div>
   </>
 )
}

const GraphAugmentFlow: React.FC<{
 result: GraphAugmentResult
}> = ({ result }) => {
 return (
   <ReactFlowProvider>
     <GraphAugmentFlowInner result={result} />
   </ReactFlowProvider>
 )
}

const GraphAugmentViewer: React.FC<GraphAugmentViewerProps> = ({
 result,
 extract,
 isLoading,
 status,
 stage,
 progressMessages,
 error,
 onStart,
 canStart,
}) => {
 const [viewMode, setViewMode] = useState<'graph' | 'list'>('graph')

 const stageLabels: Record<string, string> = {
   extract: '实体抽取',
   similarity: '相似度匹配',
   chains: '链路生成',
   augment: 'LLM补全',
   review: '等待审核',
   ttl: 'TTL转换',
   done: '完成',
 }

 const statusLabels: Record<string, string> = {
   RUNNING: '处理中',
   WAITING_REVIEW: '等待审核',
   COMPLETED: '已完成',
   FAILED: '失败',
   REJECTED: '已拒绝',
 }

 // 修复原来 getDirectionColor 返回类型问题在列表视图中
 const getListDirectionClass = (direction?: 'up' | 'down'): string => {
   if (direction === 'up') return 'text-red-400 bg-red-400/20'
   if (direction === 'down') return 'text-green-400 bg-green-400/20'
   return 'text-gray-400 bg-gray-400/20'
 }

 return (
   <Card>
     <CardHeader>
       <CardTitle className="flex items-center justify-between flex-wrap gap-2">
         <span>🔮 知识图谱补全</span>
         {status && (
           <span className={`text-sm font-normal px-3 py-1 rounded-full ${
             status === 'RUNNING' ? 'bg-blue-500/20 text-blue-300' :
             status === 'COMPLETED' || status === 'WAITING_REVIEW' ? 'bg-green-500/20 text-green-300' :
             status === 'FAILED' ? 'bg-red-500/20 text-red-300' :
             'bg-gray-500/20 text-gray-300'
           }`}>
             {statusLabels[status] || status}
             {stage && ` · ${stageLabels[stage] || stage}`}
           </span>
         )}
       </CardTitle>
     </CardHeader>
     <CardContent className="space-y-6">
       {/* 抽取摘要 */}
       {extract && (
         <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
           <h4 className="text-sm font-medium text-white mb-3">抽取摘要</h4>
           <p className="text-sm text-gray-300 mb-4">{extract.summary}</p>

           {extract.main_events.length > 0 && (
             <div className="mb-3">
               <span className="text-xs text-gray-400 block mb-2">主要事件:</span>
               <div className="flex flex-wrap gap-2">
                 {extract.main_events.map((event, idx) => (
                   <span key={idx} className="px-2 py-1 bg-blue-500/20 text-blue-300 rounded text-xs">
                     {event}
                   </span>
                 ))}
               </div>
             </div>
           )}

           {extract.main_variable_changes.length > 0 && (
             <div>
               <span className="text-xs text-gray-400 block mb-2">主要变量变化:</span>
               <div className="flex flex-wrap gap-2">
                 {extract.main_variable_changes.map((change, idx) => (
                   <span key={idx} className="px-2 py-1 bg-purple-500/20 text-purple-300 rounded text-xs">
                     {change}
                   </span>
                 ))}
               </div>
             </div>
           )}
         </div>
       )}

       {/* 实时进度 */}
       {isLoading && progressMessages.length > 0 && (
         <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
           <h4 className="text-sm font-medium text-white mb-3">处理进度</h4>
           <div className="max-h-48 overflow-y-auto space-y-1">
             {progressMessages.slice(-20).map((msg, idx) => (
               <div key={idx} className="text-xs text-gray-400 font-mono">
                 {msg}
               </div>
             ))}
           </div>
         </div>
       )}

       {/* 错误信息 */}
       {error && (
         <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg">
           <p className="text-red-400 text-sm">{error}</p>
         </div>
       )}

       {/* 图谱结果 */}
       {result && (
         <div className="space-y-4">
           {/* 视图切换 */}
           <div className="flex items-center justify-end gap-2">
             <span className="text-sm text-gray-400">显示模式：</span>
             <button
               onClick={() => setViewMode('graph')}
               className={`px-3 py-1 rounded text-sm ${
                 viewMode === 'graph'
                   ? 'bg-purple-500/20 text-purple-300 border border-purple-500/50'
                   : 'bg-gray-800/50 text-gray-400 border border-gray-700 hover:text-white'
               }`}
             >
               图形视图
             </button>
             <button
               onClick={() => setViewMode('list')}
               className={`px-3 py-1 rounded text-sm ${
                 viewMode === 'list'
                   ? 'bg-purple-500/20 text-purple-300 border border-purple-500/50'
                   : 'bg-gray-800/50 text-gray-400 border border-gray-700 hover:text-white'
               }`}
             >
               列表详情
             </button>
           </div>

           {/* 图形可视化视图 */}
           {viewMode === 'graph' && (
             <GraphAugmentFlow result={result} />
           )}

           {/* 列表详情视图 */}
           {viewMode === 'list' && (
             <div className="space-y-4">
               {/* 按类型分组显示节点 */}
               {(result.events.length > 0 ||
                 result.market_variables.length > 0 ||
                 result.variable_changes.length > 0 ||
                 result.valuation_outcomes.length > 0) && (
                 Object.entries({
                   events: result.events,
                   market_variables: result.market_variables,
                   variable_changes: result.variable_changes,
                   valuation_outcomes: result.valuation_outcomes,
                 }).map(([type, nodes]) => {
                   if (nodes.length === 0) return null
                   return (
                     <div key={type} className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                       <h4 className="text-sm font-medium text-white mb-3">
                         {getNodeTypeLabel(type)} ({nodes.length})
                       </h4>
                       <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                         {nodes.map((node) => (
                           <div
                             key={node.id}
                             className="p-3 border border-gray-700 rounded-lg bg-gray-900/30"
                           >
                             <div className="flex items-start justify-between mb-1">
                               <span className="text-sm font-medium text-white">
                                 {node.label}
                               </span>
                               {node.direction && (
                                 <span className={`text-xs px-2 py-0.5 rounded ${getListDirectionClass(node.direction)}`}>
                                   {node.direction}
                                 </span>
                               )}
                             </div>
                             <div className="text-xs text-gray-400 font-mono">
                               {node.id}
                               {node.for_variable && (
                                 <div className="mt-1">
                                   for: {node.for_variable}
                                 </div>
                               )}
                             </div>
                           </div>
                         ))}
                       </div>
                     </div>
                   )
                 })
               )}

               {/* 关系列表 */}
               {result.relationships.length > 0 && (
                 <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                   <h4 className="text-sm font-medium text-white mb-3">
                     影响关系 ({result.relationships.length})
                   </h4>
                   <div className="space-y-2 max-h-64 overflow-y-auto">
                     {result.relationships.map((rel, idx) => (
                       <div key={idx} className="flex items-center gap-2 p-2 border border-gray-700 rounded bg-gray-900/30">
                         <span className="text-sm text-white flex-1 truncate">{rel.source}</span>
                         <span className="px-2 py-1 bg-purple-500/20 text-purple-300 rounded text-xs">
                           {rel.relation}
                         </span>
                         <span className="text-sm text-white flex-1 truncate text-right">{rel.target}</span>
                       </div>
                     ))}
                   </div>
                 </div>
               )}
             </div>
           )}
         </div>
       )}

       {/* 开始按钮 */}
       {!isLoading && !result && canStart && (
         <div className="text-center py-6">
           <p className="text-gray-400 text-sm mb-4">
             点击下方按钮开始对这篇新闻进行知识图谱补全
           </p>
           <button
             onClick={onStart}
             className="px-4 py-2 bg-white text-black rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium"
           >
             🔮 开始图谱补全
           </button>
         </div>
       )}

       {/* 加载中 */}
       {isLoading && !progressMessages.length && (
         <Loading text="正在启动图谱补全任务..." />
       )}

       {!result && !isLoading && !canStart && (
         <div className="text-center py-6 text-gray-400 text-sm">
           新闻内容为空，无法进行图谱补全
         </div>
       )}
     </CardContent>
   </Card>
 )
}

export default GraphAugmentViewer
