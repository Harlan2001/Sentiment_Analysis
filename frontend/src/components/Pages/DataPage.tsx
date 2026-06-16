import React, { useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle, Button, Loading, Empty } from '../UI'
import { useNewsSources } from '../../hooks/useNewsApi'
import { cn, formatDate } from '../../utils/helpers'

interface DataSource {
  id: string
  name: string
  type: 'commercial' | 'crawler'
  category: string
  description: string
  status: 'active' | 'inactive' | 'planned'
  coverage?: string
  updateFrequency?: string
  icon: string
}

const DataPage: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set())
  
  const { data: sourcesData, isLoading: sourcesLoading, error: sourcesError } = useNewsSources()
  
  // 数据源列表
  const dataSources: DataSource[] = useMemo(() => [
    // 商用数据库
    {
      id: 'wind',
      name: 'Wind（万得）',
      type: 'commercial',
      category: 'commercial',
      description: '国内领先的金融数据服务商，提供全面的债券市场数据、宏观经济数据、行业数据等。覆盖中债、上清所等全市场债券行情。',
      status: 'inactive',
      coverage: '全市场债券、宏观数据、研报',
      updateFrequency: '实时',
      icon: '💨'
    },
    {
      id: 'bloomberg',
      name: 'Bloomberg（彭博）',
      type: 'commercial',
      category: 'commercial',
      description: '全球顶级金融数据平台，提供国际市场债券数据、外汇、大宗商品等多资产类别数据。强大的分析工具和新闻系统。',
      status: 'inactive',
      coverage: '全球债券、外汇、商品',
      updateFrequency: '实时',
      icon: '🌐'
    },
    {
      id: 'refinitiv',
      name: 'Refinitiv（路孚特）',
      type: 'commercial',
      category: 'commercial',
      description: '前身为汤森路透金融与风险部门，提供全球金融市场数据、债券定价、衍生品数据等。强大的Eikon终端。',
      status: 'inactive',
      coverage: '全球债券、股票、外汇',
      updateFrequency: '实时',
      icon: '📡'
    },
    {
      id: 'choice',
      name: 'Choice（东方财富）',
      type: 'commercial',
      category: 'commercial',
      description: '东方财富旗下金融数据服务平台，提供股票、债券、基金等全市场数据。性价比高，适合机构和个人投资者。',
      status: 'inactive',
      coverage: 'A股、债券、基金',
      updateFrequency: '实时',
      icon: '📊'
    },
    {
      id: 'ifind',
      name: 'iFind（同花顺）',
      type: 'commercial',
      category: 'commercial',
      description: '同花顺旗下专业金融数据终端，提供全面的金融数据、行情分析、研报等功能。',
      status: 'inactive',
      coverage: 'A股、债券、基金',
      updateFrequency: '实时',
      icon: '📈'
    },
    // 智能信息采集
    {
      id: 'cls',
      name: '财联社',
      type: 'crawler',
      category: 'crawler',
      description: '国内领先的财经新闻媒体，提供实时债券市场新闻、政策解读、市场分析等内容。',
      status: 'active',
      coverage: '债券新闻、政策解读',
      updateFrequency: '实时',
      icon: '📰'
    },
    {
      id: 'wechat',
      name: '微信公众号',
      type: 'crawler',
      category: 'crawler',
      description: '采集各大金融机构、研究机构的微信公众号文章，获取深度市场分析和观点。',
      status: 'active',
      coverage: '机构研报、市场观点',
      updateFrequency: '每日更新',
      icon: '💬'
    },
    {
      id: 'eastmoney',
      name: '东方财富网',
      type: 'crawler',
      category: 'crawler',
      description: '采集东方财富网的债券市场新闻、数据公告、研报等内容。',
      status: 'planned',
      coverage: '债券新闻、数据公告',
      updateFrequency: '每日更新',
      icon: '🔍'
    },
    {
      id: '10jqka',
      name: '同花顺财经',
      type: 'crawler',
      category: 'crawler',
      description: '采集同花顺财经的债券市场资讯、行情数据、机构研报等内容。',
      status: 'planned',
      coverage: '债券资讯、行情数据',
      updateFrequency: '每日更新',
      icon: '📊'
    },
    {
      id: 'hexun',
      name: '和讯网',
      type: 'crawler',
      category: 'crawler',
      description: '采集和讯网的债券市场新闻、深度分析、投资策略等内容。',
      status: 'planned',
      coverage: '债券新闻、投资分析',
      updateFrequency: '每日更新',
      icon: '💹'
    },
    {
      id: 'yicai',
      name: '第一财经',
      type: 'crawler',
      category: 'crawler',
      description: '权威财经媒体，提供债券市场相关的新闻报道、深度分析、专家观点等内容。',
      status: 'active',
      coverage: '财经新闻、市场分析',
      updateFrequency: '实时',
      icon: '📺'
    },
    {
      id: 'wallstreetcn',
      name: '华尔街见闻',
      type: 'crawler',
      category: 'crawler',
      description: '全球金融资讯平台，提供国际国内债券市场新闻、宏观经济数据、政策解读等。',
      status: 'active',
      coverage: '全球财经、债券市场',
      updateFrequency: '实时',
      icon: '🌍'
    },
    {
      id: 'stats',
      name: '国家统计局',
      type: 'crawler',
      category: 'official',
      description: '国家统计局官方网站，获取宏观经济数据、CPI、PPI、GDP等重要经济指标。',
      status: 'active',
      coverage: '宏观经济数据',
      updateFrequency: '按月/季度更新',
      icon: '🏛️'
    },
    {
      id: 'pbc',
      name: '中国人民银行',
      type: 'crawler',
      category: 'official',
      description: '中国人民银行官方网站，获取货币政策、利率政策、金融统计数据等权威信息。',
      status: 'planned',
      coverage: '货币政策、利率数据',
      updateFrequency: '不定期更新',
      icon: '🏦'
    },
    {
      id: 'mof',
      name: '财政部',
      type: 'crawler',
      category: 'official',
      description: '财政部官方网站，获取财政政策、国债发行、地方政府债券发行等信息。',
      status: 'planned',
      coverage: '财政政策、债券发行信息',
      updateFrequency: '不定期更新',
      icon: '💰'
    },
    {
      id: 'csrc',
      name: '中国证监会',
      type: 'crawler',
      category: 'official',
      description: '中国证监会官方网站，获取资本市场监管政策、债券市场监管规则等信息。',
      status: 'planned',
      coverage: '监管政策、市场规则',
      updateFrequency: '不定期更新',
      icon: '📜'
    },
    {
      id: 'chinabond',
      name: '中国债券信息网',
      type: 'crawler',
      category: 'official',
      description: '中央结算公司官方网站，获取债券发行、登记、托管、结算等权威数据。',
      status: 'planned',
      coverage: '债券市场核心数据',
      updateFrequency: '每日更新',
      icon: '📈'
    },
    {
      id: 'shanghai_exchange',
      name: '上海证券交易所',
      type: 'crawler',
      category: 'exchange',
      description: '上海证券交易所官方网站，获取上交所债券发行、上市、交易、信息披露等数据。',
      status: 'planned',
      coverage: '上交所债券市场数据',
      updateFrequency: '实时',
      icon: '📊'
    },
    {
      id: 'shenzhen_exchange',
      name: '深圳证券交易所',
      type: 'crawler',
      category: 'exchange',
      description: '深圳证券交易所官方网站，获取深交所债券发行、上市、交易、信息披露等数据。',
      status: 'planned',
      coverage: '深交所债券市场数据',
      updateFrequency: '实时',
      icon: '📉'
    },
    {
      id: 'cfets',
      name: '中国外汇交易中心',
      type: 'crawler',
      category: 'exchange',
      description: '中国外汇交易中心暨全国银行间同业拆借中心，获取银行间债券市场交易数据。',
      status: 'planned',
      coverage: '银行间债券市场数据',
      updateFrequency: '实时',
      icon: '💱'
    },
    {
      id: '21jingjing',
      name: '21世纪经济报道',
      type: 'crawler',
      category: 'media',
      description: '权威财经媒体，提供深度的债券市场报道、行业分析、政策解读等内容。',
      status: 'planned',
      coverage: '深度财经报道',
      updateFrequency: '每日更新',
      icon: '📰'
    },
    {
      id: 'economicobserver',
      name: '经济观察网',
      type: 'crawler',
      category: 'media',
      description: '专业财经新闻网站，提供宏观经济、金融市场、债券领域的深度分析。',
      status: 'planned',
      coverage: '财经分析、市场评论',
      updateFrequency: '每日更新',
      icon: '🔍'
    },
    {
      id: 'caixin',
      name: '财新网',
      type: 'crawler',
      category: 'media',
      description: '知名财经媒体，提供高质量的财经新闻、深度报道、政策分析等内容。',
      status: 'planned',
      coverage: '财经新闻、深度报道',
      updateFrequency: '每日更新',
      icon: '📰'
    },
    {
      id: 'ceic',
      name: 'CEIC数据库',
      type: 'crawler',
      category: 'research',
      description: '全球领先的经济数据库，提供中国及全球宏观经济数据、行业数据等。',
      status: 'planned',
      coverage: '宏观经济、行业数据',
      updateFrequency: '每月更新',
      icon: '📚'
    },
    {
      id: 'zhihu',
      name: '知乎',
      type: 'crawler',
      category: 'crawler',
      description: '采集知乎平台上金融、债券相关的专业分析、行业讨论和专家观点。',
      status: 'planned',
      coverage: '专业观点、行业讨论',
      updateFrequency: '每日更新',
      icon: '💡'
    },
    {
      id: 'xueqiu',
      name: '雪球',
      type: 'crawler',
      category: 'crawler',
      description: '采集雪球平台上投资者对债券市场的分析、讨论和投资策略分享。',
      status: 'planned',
      coverage: '投资者观点、策略分享',
      updateFrequency: '每日更新',
      icon: '❄️'
    },
  ], [])
  
  // 分类筛选
  const categories = [
    { id: 'all', name: '全部数据源', icon: '📊' },
    { id: 'commercial', name: '商用数据库', icon: '💼' },
    { id: 'crawler', name: '智能信息采集', icon: '🔍' },
    { id: 'official', name: '官方发布', icon: '🏛️' },
    { id: 'exchange', name: '交易所', icon: '📈' },
    { id: 'media', name: '财经媒体', icon: '📰' },
    { id: 'research', name: '研究机构', icon: '📚' },
  ]
  
  // 过滤数据源
  const filteredSources = useMemo(() => {
    if (selectedCategory === 'all') return dataSources
    return dataSources.filter(source => source.category === selectedCategory)
  }, [dataSources, selectedCategory])
  
  // 统计信息
  const stats = useMemo(() => ({
    total: dataSources.length,
    active: dataSources.filter(s => s.status === 'active').length,
    inactive: dataSources.filter(s => s.status === 'inactive').length,
    planned: dataSources.filter(s => s.status === 'planned').length,
  }), [dataSources])
  
  const handleSourceToggle = (sourceId: string) => {
    setSelectedSources(prev => {
      const newSet = new Set(prev)
      if (newSet.has(sourceId)) {
        newSet.delete(sourceId)
      } else {
        newSet.add(sourceId)
      }
      return newSet
    })
  }
  
  const handleClearSelection = () => {
    setSelectedSources(new Set())
  }
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'text-green-400 bg-green-400/20 border-green-400/50'
      case 'inactive':
        return 'text-gray-400 bg-gray-400/20 border-gray-400/50'
      case 'planned':
        return 'text-blue-400 bg-blue-400/20 border-blue-400/50'
      default:
        return 'text-gray-400 bg-gray-400/20 border-gray-400/50'
    }
  }
  
  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'active':
        return '已启用'
      case 'inactive':
        return '未启用'
      case 'planned':
        return '计划中'
      default:
        return status
    }
  }
  
  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div className="page-header">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
          💾 数据源配置
        </h1>
        <p className="text-gray-400 text-sm">选择和管理债券市场数据来源</p>
      </div>
      
      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">总数据源</p>
                <p className="text-2xl font-bold text-white">{stats.total}</p>
              </div>
              <div className="w-12 h-12 bg-purple-500/20 rounded-lg flex items-center justify-center">
                <span className="text-purple-400 text-xl">📊</span>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">已启用</p>
                <p className="text-2xl font-bold text-green-400">{stats.active}</p>
              </div>
              <div className="w-12 h-12 bg-green-500/20 rounded-lg flex items-center justify-center">
                <span className="text-green-400 text-xl">✓</span>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">未启用</p>
                <p className="text-2xl font-bold text-gray-400">{stats.inactive}</p>
              </div>
              <div className="w-12 h-12 bg-gray-500/20 rounded-lg flex items-center justify-center">
                <span className="text-gray-400 text-xl">○</span>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">计划中</p>
                <p className="text-2xl font-bold text-blue-400">{stats.planned}</p>
              </div>
              <div className="w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center">
                <span className="text-blue-400 text-xl">🚧</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* 分类筛选 */}
      <Card>
        <CardHeader>
          <CardTitle>数据源分类</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {categories.map(category => (
              <button
                key={category.id}
                onClick={() => setSelectedCategory(category.id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-2 rounded-lg border transition-all',
                  selectedCategory === category.id
                    ? 'bg-purple-500/20 border-purple-500 text-purple-400'
                    : 'bg-gray-800 border-gray-600 text-gray-400 hover:border-gray-500'
                )}
              >
                <span>{category.icon}</span>
                <span className="text-sm font-medium">{category.name}</span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
      
      {/* 数据源列表 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>
              数据源列表
              <span className="ml-2 text-sm font-normal text-gray-400">
                ({filteredSources.length} 个)
              </span>
            </CardTitle>
            {selectedSources.size > 0 && (
              <Button variant="outline" size="sm" onClick={handleClearSelection}>
                清除选择 ({selectedSources.size})
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {sourcesLoading ? (
            <Loading text="加载数据源..." />
          ) : sourcesError ? (
            <div className="text-red-400 text-center py-8">
              加载失败: {sourcesError.message}
            </div>
          ) : filteredSources.length === 0 ? (
            <Empty title="没有找到数据源" message="尝试选择其他分类" />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredSources.map(source => (
                <div
                  key={source.id}
                  onClick={() => handleSourceToggle(source.id)}
                  className={cn(
                    'p-4 rounded-lg border cursor-pointer transition-all',
                    selectedSources.has(source.id)
                      ? 'border-purple-500 bg-purple-500/10'
                      : 'border-gray-700 hover:border-gray-600 hover:bg-gray-800/50'
                  )}
                >
                  {/* 头部 */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        'w-12 h-12 rounded-lg flex items-center justify-center text-2xl',
                        source.type === 'commercial' ? 'bg-orange-500/20' : 'bg-blue-500/20'
                      )}>
                        {source.icon}
                      </div>
                      <div>
                        <h3 className="font-semibold text-white text-sm">{source.name}</h3>
                        <span className={cn(
                          'text-xs px-2 py-0.5 rounded',
                          source.type === 'commercial' ? 'bg-orange-500/20 text-orange-400' : 'bg-blue-500/20 text-blue-400'
                        )}>
                          {source.type === 'commercial' ? '商用数据库' : '智能采集'}
                        </span>
                      </div>
                    </div>
                    {selectedSources.has(source.id) && (
                      <div className="w-6 h-6 bg-purple-500 rounded-full flex items-center justify-center">
                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                    )}
                  </div>
                  
                  {/* 描述 */}
                  <p className="text-xs text-gray-400 leading-relaxed mb-3 line-clamp-3">
                    {source.description}
                  </p>
                  
                  {/* 状态 */}
                  <div className="flex items-center justify-between">
                    <span className={cn('text-xs px-2 py-1 rounded border', getStatusColor(source.status))}>
                      {getStatusLabel(source.status)}
                    </span>
                    {source.updateFrequency && (
                      <span className="text-xs text-gray-500">{source.updateFrequency}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* 已选择的数据源 */}
      {selectedSources.size > 0 && (
        <Card className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-50 max-w-2xl w-full mx-4">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-sm text-white font-medium">
                  已选择 {selectedSources.size} 个数据源
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {Array.from(selectedSources).map(id => dataSources.find(s => s.id === id)?.name).join(', ')}
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleClearSelection}>
                  清空
                </Button>
                <Button size="sm">
                  确认选择
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default DataPage
