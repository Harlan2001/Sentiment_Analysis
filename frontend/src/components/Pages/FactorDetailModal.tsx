import React, { useState } from 'react'
import { Modal, Card, CardContent, CardHeader, CardTitle, Button, Loading, Error, Empty } from '../UI'
import { useFactorAnalysis } from '../../hooks/useFactorApi'
import { useNewsDetail } from '../../hooks/useNewsApi'
import { formatDate, getDirectionColor, truncateText } from '../../utils/helpers'
import NewsCard from './NewsCard'
import type { FactorDefinition, FactorNewsItem } from '../../types'

interface FactorDetailModalProps {
  factor: FactorDefinition
  isOpen: boolean
  onClose: () => void
}


const FactorDetailModal: React.FC<FactorDetailModalProps> = ({
  factor,
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'news' | 'timeline'>('overview')
  const [selectedNewsId, setSelectedNewsId] = useState<number | null>(null)
  const [modelFilter, setModelFilter] = useState<string>('best')
  
  const selectedModel = modelFilter === 'best' ? undefined : modelFilter
  const analysis = useFactorAnalysis(factor.code, selectedModel)
  const newsDetailQuery = useNewsDetail(selectedNewsId || 0, selectedModel)
  
  const NewsItemCard: React.FC<{ news: FactorNewsItem }> = ({ news }) => (
    <div
      className={`p-4 border border-gray-700 rounded-lg transition-colors cursor-pointer ${
        selectedNewsId === news.id
          ? 'bg-purple-500/20 border-purple-500'
          : 'hover:bg-gray-800/50'
      }`}
      onClick={() => setSelectedNewsId(news.id)}
    >
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-medium text-white flex-1 mr-3 line-clamp-2">
          {news.title}
        </h4>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <span className="text-xs text-gray-400">
            {formatDate(news.publish_time, 'HH:mm')}
          </span>
          <span className={`text-xs px-2 py-1 rounded ${getDirectionColor(news.factor_direction)}`}>
            {news.factor_direction}
          </span>
        </div>
      </div>
      
      <div className="flex items-center gap-3 text-xs text-gray-400 mb-2">
        <span>{formatDate(news.publish_time, 'YYYY-MM-DD')}</span>
        <span>{news.horizon}</span>
        <span>{news.direction}</span>
      </div>
      
      {news.factor_direction && (
        <div className="text-xs text-gray-300">
          因子影响: <span className="font-medium">{news.factor_direction}</span>
        </div>
      )}
    </div>
  )
  
  const OverviewTab = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <label className="text-sm text-gray-400">模型:</label>
        <select
          value={modelFilter}
          onChange={(e) => setModelFilter(e.target.value)}
          className="px-3 py-1.5 text-sm bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-purple-500 outline-none"
        >
          <option value="best">优先级(best)</option>
          <option value="doubao">doubao</option>
          <option value="deepseek">deepseek</option>
          <option value="qwen">qwen</option>
          <option value="default">default</option>
        </select>
      </div>

      {/* 基本信息 */}
      <Card>
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-400">因子代码</label>
                <p className="text-white font-mono">{factor.code}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-400">因子名称</label>
                <p className="text-white">{factor.name}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-400">分类</label>
                <p className="text-white">{factor.category}</p>
              </div>
            </div>
            
            <div className="space-y-4">
              {factor.last_updated && (
                <div>
                  <label className="text-sm font-medium text-gray-400">最后更新</label>
                  <p className="text-white">{formatDate(factor.last_updated, 'YYYY-MM-DD HH:mm')}</p>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* 新闻统计 */}
      {analysis.newsStats && (
        <Card>
          <CardHeader>
            <CardTitle>新闻统计</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-white">{analysis.newsStats.total}</p>
                <p className="text-sm text-gray-400">总新闻数</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-white">
                  {Object.keys(analysis.newsStats.byDirection).length}
                </p>
                <p className="text-sm text-gray-400">影响方向</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-white">
                  {Object.keys(analysis.newsStats.byHorizon).length}
                </p>
                <p className="text-sm text-gray-400">分析期限</p>
              </div>
            </div>
            
            {/* 方向分布 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="text-sm font-medium text-white mb-3">影响方向分布</h4>
              <div className="space-y-2">
                {Object.entries(analysis.newsStats.byDirection).map(([direction, count]) => (
                  <div key={direction} className="flex items-center justify-between">
                    <span className={`px-2 py-1 rounded text-xs ${getDirectionColor(direction)}`}>
                      {direction}
                    </span>
                    <span className="text-sm text-gray-400">{String(count)} 条</span>
                  </div>
                ))}
              </div>
              </div>
              
              <div>
                <h4 className="text-sm font-medium text-white mb-3">分析期限分布</h4>
              <div className="space-y-2">
                {Object.entries(analysis.newsStats.byHorizon).map(([horizon, count]) => (
                  <div key={horizon} className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">{horizon}</span>
                    <span className="text-sm text-gray-400">{String(count)} 条</span>
                  </div>
                ))}
              </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* 时间范围 */}
      {analysis.dateRange && (
        <Card>
          <CardHeader>
            <CardTitle>数据时间范围</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-6">
              <div>
                <label className="text-sm font-medium text-gray-400">开始日期</label>
                <p className="text-white">{formatDate(analysis.dateRange.start, 'YYYY-MM-DD')}</p>
              </div>
              <div className="text-gray-400">→</div>
              <div>
                <label className="text-sm font-medium text-gray-400">结束日期</label>
                <p className="text-white">{formatDate(analysis.dateRange.end, 'YYYY-MM-DD')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
  
  const NewsTab = () => {
    if (analysis.isLoading) {
      return <Loading text="加载相关新闻..." />
    }
    
    if (analysis.error) {
      return <Error title="加载失败" message={analysis.error.message} />
    }
    
    if (!analysis.newsStats) {
      return <Empty title="暂无新闻数据" message="该因子暂无相关新闻" />
    }
    
    // 如果有选中的新闻，显示 NewsCard
    if (selectedNewsId && newsDetailQuery.data) {
      return (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-lg font-semibold text-white">新闻详情</h4>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedNewsId(null)}
            >
              返回列表
            </Button>
          </div>
          <NewsCard
            news={newsDetailQuery.data}
            onClose={() => setSelectedNewsId(null)}
            onNewsSelect={(newsId) => setSelectedNewsId(newsId)}
          />
        </div>
      )
    }
    
    if (selectedNewsId && newsDetailQuery.isLoading) {
      return <Loading text="加载新闻详情..." />
    }
    
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="text-lg font-semibold text-white">
            相关新闻 ({analysis.newsStats.total} 条)
          </h4>
          {analysis.newsStats.recentNews && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                // 这里可以实现导出功能
                console.log('Export news data')
              }}
            >
              导出数据
            </Button>
          )}
        </div>
        
        {analysis.newsStats.recentNews.length > 0 ? (
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {analysis.newsStats.recentNews.map((news: FactorNewsItem) => (
              <NewsItemCard key={news.id} news={news} />
            ))}
          </div>
        ) : (
          <Empty title="暂无新闻" message="该因子暂无相关新闻" />
        )}
      </div>
    )
  }
  
  const TimelineTab = () => (
    <div className="space-y-4">
      <h4 className="text-lg font-semibold text-white">时间线视图</h4>
      <div className="text-center py-8 text-gray-400">
        <svg className="w-16 h-16 mx-auto mb-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <p>时间线图表功能开发中...</p>
        <p className="text-sm mt-2">将显示因子与收益率的相关性图表</p>
      </div>
    </div>
  )
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`${factor.name} (${factor.code})`}
      size="xl"
    >
      {/* 标签页导航 */}
      <div className="flex space-x-1 mb-6 p-1 bg-gray-800 rounded-lg">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'overview'
              ? 'bg-purple-500 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-700'
          }`}
        >
          概览
        </button>
        <button
          onClick={() => setActiveTab('news')}
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'news'
              ? 'bg-purple-500 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-700'
          }`}
        >
          相关新闻
        </button>
        <button
          onClick={() => setActiveTab('timeline')}
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'timeline'
              ? 'bg-purple-500 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-700'
          }`}
        >
          时间线
        </button>
      </div>
      
      {/* 内容区域 */}
      <div className="min-h-[400px]">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'news' && <NewsTab />}
        {activeTab === 'timeline' && <TimelineTab />}
      </div>
    </Modal>
  )
}

export default FactorDetailModal