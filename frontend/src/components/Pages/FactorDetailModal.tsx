import React, { useState, useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { Modal, Card, CardContent, CardHeader, CardTitle, Button, Loading, Error, Empty } from '@/components/UI'
import { useFactorAnalysis } from '@/hooks/useFactorApi'
import { useNewsDetail } from '@/hooks/useNewsApi'
import { formatDate, getDirectionColor, truncateText } from '@/utils/helpers'
import type { FactorDefinition, FactorNewsItem } from '@/types'
import NewsCard from './NewsCard'

interface FactorDetailModalProps {
  factor: FactorDefinition
  isOpen: boolean
  onClose: () => void
}

const DIRECTION_LABEL: Record<string, string> = {
  positive: '看涨',
  negative: '看跌',
  neutral: '中性',
}
const DIRECTION_COLOR: Record<string, string> = {
  positive: '#34d399',
  negative: '#fb7185',
  neutral: '#fbbf24',
  unknown: '#94a3b8',
}

const FactorDetailModal: React.FC<FactorDetailModalProps> = ({ factor, isOpen, onClose }) => {
  const [selectedNewsId, setSelectedNewsId] = useState<number | null>(null)
  const [modelFilter, setModelFilter] = useState<string>('best')

  const selectedModel = modelFilter === 'best' ? undefined : modelFilter
  const analysis = useFactorAnalysis(factor.code, selectedModel)
  const newsDetailQuery = useNewsDetail(selectedNewsId || 0, selectedModel)

  // 时间线聚合：按日期 × 方向统计新闻数量
  const timeline = useMemo(() => {
    const news = analysis.news?.news || []
    const byDate = new Map<string, Record<string, number>>()
    for (const item of news) {
      const date = item.publish_date || String(item.publish_time || '').slice(0, 10)
      if (!date) continue
      const dir = DIRECTION_LABEL[item.factor_direction] || item.factor_direction || '中性'
      const entry = byDate.get(date) || {}
      entry[dir] = (entry[dir] || 0) + 1
      byDate.set(date, entry)
    }
    return { dates: Array.from(byDate.keys()).sort(), byDate }
  }, [analysis.news])

  const timelineOption: EChartsOption = useMemo(() => {
    const dirKeys = ['看涨', '看跌', '中性']
    const series = dirKeys.map((dir) => ({
      name: dir,
      type: 'bar' as const,
      stack: 'total',
      data: timeline.dates.map((d) => timeline.byDate.get(d)?.[dir] || 0),
      itemStyle: { color: DIRECTION_COLOR[dir] },
      barMaxWidth: 22,
    }))
    return {
      backgroundColor: 'transparent',
      grid: { left: '2%', right: '3%', top: 40, bottom: 60, containLabel: true },
      legend: {
        top: 8,
        textStyle: { color: '#e2e8f0', fontSize: 12 },
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.92)',
        borderColor: 'rgba(148, 163, 184, 0.28)',
        textStyle: { color: '#f8fafc', fontSize: 12 },
      },
      xAxis: {
        type: 'category',
        data: timeline.dates,
        axisLabel: { color: '#94a3b8', fontSize: 10, rotate: timeline.dates.length > 20 ? 45 : 0 },
        axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.45)' } },
      },
      yAxis: {
        type: 'value',
        name: '新闻数',
        nameTextStyle: { color: '#94a3b8', fontSize: 11 },
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.16)', type: 'dashed' } },
      },
      series,
    }
  }, [timeline])

  const NewsItemCard: React.FC<{ news: FactorNewsItem }> = ({ news }) => (
    <div
      className={`p-4 border border-gray-700 rounded-lg transition-colors cursor-pointer ${
        selectedNewsId === news.id ? 'bg-purple-500/20 border-purple-500' : 'hover:bg-gray-800/50'
      }`}
      onClick={() => setSelectedNewsId(news.id)}
    >
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-medium text-white flex-1 mr-3 line-clamp-2">{news.title}</h4>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <span className="text-xs text-gray-400">{formatDate(news.publish_time, 'HH:mm')}</span>
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

  // 选中新闻时的详情视图
  if (selectedNewsId) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title={`${factor.name} (${factor.code})`} size="xl">
        {newsDetailQuery.isLoading ? (
          <Loading text="加载新闻详情..." />
        ) : newsDetailQuery.data ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-semibold text-white">新闻详情</h4>
              <Button variant="outline" size="sm" onClick={() => setSelectedNewsId(null)}>
                返回列表
              </Button>
            </div>
            <NewsCard
              news={newsDetailQuery.data}
              onClose={() => setSelectedNewsId(null)}
              onNewsSelect={(newsId) => setSelectedNewsId(newsId)}
            />
          </div>
        ) : (
          <Empty title="加载失败" message="无法获取新闻详情" />
        )}
      </Modal>
    )
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`${factor.name} (${factor.code})`} size="xl">
      <div className="space-y-6">
        {/* 模型切换 */}
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

        {/* 紧凑概览 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <label className="text-xs text-gray-400 block mb-1">因子代码</label>
              <p className="text-white font-mono text-sm">{factor.code}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <label className="text-xs text-gray-400 block mb-1">分类</label>
              <p className="text-white text-sm">{factor.category}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <label className="text-xs text-gray-400 block mb-1">总新闻数</label>
              <p className="text-white text-2xl font-bold">{analysis.newsStats?.total ?? '-'}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <label className="text-xs text-gray-400 block mb-1">近30天活跃</label>
              <p className="text-white text-sm">{factor.recent_news_count ?? '-'} 条</p>
            </CardContent>
          </Card>
        </div>

        {/* 方向 / 期限 / 时间范围概览 */}
        {analysis.newsStats && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">影响方向分布</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.keys(analysis.newsStats.byDirection).length === 0 ? (
                    <p className="text-sm text-gray-500">暂无</p>
                  ) : (
                    Object.entries(analysis.newsStats.byDirection).map(([direction, count]) => (
                      <div key={direction} className="flex items-center justify-between">
                        <span className={`px-2 py-1 rounded text-xs ${getDirectionColor(direction)}`}>{direction}</span>
                        <span className="text-sm text-gray-400">{String(count)} 条</span>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">分析期限分布</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.keys(analysis.newsStats.byHorizon).length === 0 ? (
                    <p className="text-sm text-gray-500">暂无</p>
                  ) : (
                    Object.entries(analysis.newsStats.byHorizon).map(([horizon, count]) => (
                      <div key={horizon} className="flex items-center justify-between">
                        <span className="text-sm text-gray-400">{horizon}</span>
                        <span className="text-sm text-gray-400">{String(count)} 条</span>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">数据时间范围</CardTitle>
              </CardHeader>
              <CardContent>
                {analysis.dateRange ? (
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-white">{formatDate(analysis.dateRange.start, 'YYYY-MM-DD')}</span>
                    <span className="text-gray-400">→</span>
                    <span className="text-sm text-white">{formatDate(analysis.dateRange.end, 'YYYY-MM-DD')}</span>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">暂无数据</p>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* 时间线：X=时间，Y=新闻数量（按方向堆叠） */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">新闻时间线（按方向）</CardTitle>
          </CardHeader>
          <CardContent>
            {analysis.isLoading ? (
              <Loading text="加载新闻数据..." />
            ) : analysis.error ? (
              <Error title="加载失败" message={analysis.error.message} />
            ) : timeline.dates.length === 0 ? (
              <Empty title="暂无新闻" message="该因子暂无相关新闻" />
            ) : (
              <ReactECharts option={timelineOption} style={{ height: 280, width: '100%' }} opts={{ renderer: 'svg' }} />
            )}
          </CardContent>
        </Card>

        {/* 相关新闻列表 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">相关新闻 ({analysis.newsStats?.total ?? 0} 条)</CardTitle>
          </CardHeader>
          <CardContent>
            {analysis.isLoading ? (
              <Loading text="加载相关新闻..." />
            ) : analysis.error ? (
              <Error title="加载失败" message={analysis.error.message} />
            ) : analysis.newsStats && analysis.newsStats.recentNews.length > 0 ? (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {analysis.newsStats.recentNews.map((news: FactorNewsItem) => (
                  <NewsItemCard key={news.id} news={news} />
                ))}
              </div>
            ) : (
              <Empty title="暂无新闻" message="该因子暂无相关新闻" />
            )}
          </CardContent>
        </Card>
      </div>
    </Modal>
  )
}

export default FactorDetailModal
