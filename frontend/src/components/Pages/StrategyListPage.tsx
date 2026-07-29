import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchAllStrategies } from '../../api'
import { Loading, Error, Empty, Card, CardContent, CardHeader, CardTitle, Input } from '../UI'
import type { StrategyItem } from '../../types'

// ============ 状态标签组件 ============
const StatusBadge: React.FC<{ status: string; type: string }> = ({ status, type }) => {
  let color = 'bg-gray-500/20 text-gray-300'
  if (type === 'quant_strategy') {
    if (status === '已发布') color = 'bg-green-500/20 text-green-300'
    else if (status === '研究中') color = 'bg-amber-500/20 text-amber-300'
  }
  return (
    <span className={`px-2 py-0.5 text-xs rounded-full ${color}`}>
      {status}
    </span>
  )
}

// ============ 详情展开面板 ============
const StrategyDetails: React.FC<{ item: StrategyItem }> = ({ item }) => {
  const d = item.details
  const isQuant = item.source_type === 'quant_strategy'
  
  const fields: { label: string; value: string }[] = isQuant
    ? [
        { label: '因子类型', value: d.factor_type_label || '-' },
        { label: '因子分类', value: d.factor_category_label || '-' },
        { label: '数据频率', value: d.frequency_label || '-' },
        { label: '数据源', value: d.data_source_label || '-' },
        { label: '品种代码', value: d.variety_code || '-' },
        { label: '考核区间', value: d.exam_interval || '-' },
        { label: 'IC窗口期', value: d.ic_window != null ? String(d.ic_window) : '-' },
        { label: '所属类别', value: d.subject_category || '-' },
        { label: '品种组', value: d.breed_code || '-' },
      ]
    : [
        { label: '策略类型', value: d.strategy_type_label || '-' },
        { label: '版本', value: d.version || '-' },
        { label: '范围', value: d.scope || '-' },
        { label: '参考标的', value: d.reference || '-' },
        { label: '产品类型', value: d.product_type || '-' },
        { label: '审批状态', value: d.approval_status || '-' },
      ]
  
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 pt-3 border-t border-gray-700/50">
      {fields.map(f => (
        <div key={f.label}>
          <div className="text-xs text-gray-500 mb-0.5">{f.label}</div>
          <div className="text-sm text-gray-200">{f.value}</div>
        </div>
      ))}
    </div>
  )
}

// ============ 策略卡片 ============
const StrategyCard: React.FC<{ item: StrategyItem; expanded: boolean; onToggle: () => void }> = ({ item, expanded, onToggle }) => {
  return (
    <div className="border border-gray-700 rounded-lg bg-gray-950/40 overflow-hidden">
      <button
        type="button"
        className="w-full p-4 text-left transition-colors hover:bg-gray-900/30"
        onClick={onToggle}
        data-track="strategy_click"
        data-target={`strategy_code:${item.id}`}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium text-gray-500 bg-gray-800 px-2 py-0.5 rounded">
                {item.source_type_label}
              </span>
              <StatusBadge status={item.status} type={item.source_type} />
            </div>
            <div className="text-sm font-semibold text-gray-100 truncate">{item.name}</div>
            <div className="text-xs text-gray-500 mt-1">
              {item.category}{item.sub_category ? ` · ${item.sub_category}` : ''}
              <span className="mx-1">·</span>
              ID: {item.id}
            </div>
          </div>
          <div className="flex-shrink-0 text-right">
            <div className="text-xs text-gray-400">
              {item.create_time ? new Date(item.create_time).toLocaleDateString('zh-CN') : '-'}
            </div>
            <div className={`text-sm mt-1 ${expanded ? 'text-blue-300' : 'text-gray-500'}`}>
              {expanded ? '收起' : '详情'}
            </div>
          </div>
        </div>
        {item.description && !expanded && (
          <div className="mt-2 text-xs text-gray-500 line-clamp-1">{item.description}</div>
        )}
      </button>
      {expanded && (
        <div className="px-4 pb-4">
          <StrategyDetails item={item} />
          {item.description && (
            <div className="mt-3 text-xs text-gray-400 leading-5">{item.description}</div>
          )}
        </div>
      )}
    </div>
  )
}

// ============ 策略列表页面 ============
const StrategyListPage: React.FC = () => {
  const [strategies, setStrategies] = useState<StrategyItem[]>([])
  const [quantCount, setQuantCount] = useState(0)
  const [tradingCount, setTradingCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'all' | 'quant' | 'trading'>('all')
  const navigate = useNavigate()
  const [searchText, setSearchText] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchAllStrategies()
      .then(res => {
        setStrategies(res.strategies || [])
        setQuantCount(res.quant_total || 0)
        setTradingCount(res.trading_total || 0)
      })
      .catch(err => setError((err as Error)?.message || '加载失败'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = strategies.filter(item => {
    // 按标签筛选
    if (activeTab === 'quant' && item.source_type !== 'quant_strategy') return false
    if (activeTab === 'trading' && item.source_type !== 'trading_strategy') return false
    // 按文字搜索
    if (searchText) {
      const q = searchText.toLowerCase()
      const matchName = item.name.toLowerCase().includes(q)
      const matchId = item.id.includes(q)
      const matchCategory = item.category.toLowerCase().includes(q)
      const matchDesc = item.description.toLowerCase().includes(q)
      if (!matchName && !matchId && !matchCategory && !matchDesc) return false
    }
    return true
  })

  const tabs = [
    { key: 'all' as const, label: '全部', count: strategies.length },
    { key: 'quant' as const, label: '量化策略', count: quantCount },
    { key: 'trading' as const, label: '交易策略', count: tradingCount },
    { key: 'ai' as const, label: 'AI策略', count: null },
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
          策略总览
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          统一浏览量化因子策略与交易策略，字段已自动转换为中文标签
        </p>
      </div>

      {error && <Error message={error} />}

      {loading ? (
        <Loading text="正在加载策略列表..." />
      ) : (
        <>
          {/* 搜索和标签栏 */}
          <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
            <div className="flex gap-1">
              {tabs.map(tab => (
                <button
                  key={tab.key}
                  type="button"
                  className={`px-4 py-2 text-sm rounded-lg transition-all ${
                    activeTab === tab.key
                      ? 'bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-lg shadow-purple-500/20'
                      : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
                  }`}
                  onClick={() => {
                    // AI标签特殊跳转逻辑
                    if (tab.key === 'ai') {
                      navigate('/ai-strategy-generation-preview');
                      // return 阻断后面通用逻辑，点ai只跳转，不切换tab
                      return;
                    }
                    // 所有标签通用逻辑：切换激活tab、收起展开面板
                    setActiveTab(tab.key);
                    setExpandedId(null);
                  }}
                  data-track="strategy_filter"
                  data-target={tab.key}
                >
                  {tab.label}
                  {typeof tab.count === 'number' && (
                    <span className="ml-1.5 text-xs opacity-75">({tab.count})</span>
                  )}
                </button>
              ))}
            </div>
            <div data-track="strategy_search">
              <Input
                placeholder="搜索策略名称/ID/分类..."
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                className="sm:w-64"
              />
            </div>
          </div>

          {/* 策略列表 */}
          {filtered.length === 0 ? (
            <Empty message={searchText ? '未找到匹配的策略' : '暂无策略数据'} />
          ) : (
            <div className="space-y-2">
              {filtered.map(item => (
                <StrategyCard
                  key={`${item.source_type}-${item.id}`}
                  item={item}
                  expanded={expandedId === `${item.source_type}-${item.id}`}
                  onToggle={() =>
                    setExpandedId(
                      expandedId === `${item.source_type}-${item.id}`
                        ? null
                        : `${item.source_type}-${item.id}`
                    )
                  }
                />
              ))}
            </div>
          )}

          {/* 统计摘要 */}
          <div className="text-xs text-gray-600 text-center pt-2">
            共 {strategies.length} 条策略
            （量化 {quantCount} 条 · 交易 {tradingCount} 条）
          </div>
        </>
      )}
    </div>
  )
}

export default StrategyListPage
