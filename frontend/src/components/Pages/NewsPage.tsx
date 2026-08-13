import React, { useState, useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { format, subDays } from 'date-fns'
import { useQuery } from '@tanstack/react-query'
import { Button, Input, Card, CardContent, CardHeader, CardTitle, Loading } from '@/components/UI'
import {
  useMultiYields,
  useNewsByDateRange,
  useNewsSources,
  useNewsDetail,
  useSearchNews,
  useLatestTradingDay,
} from '@/hooks/useNewsApi'
import { storage, maskSource } from '@/utils/helpers'
import { API_PREFIX } from '@/constants'
import type { YieldPoint, NewsItem } from '@/types'
import YieldChart from './YieldChart'
import NewsList from './NewsList'
import NewsDetail from './NewsDetail'

// 固定展示的重要期限
const YIELD_PERIODS = ['1年', '5年', '10年', '30年']
// 默认信息流时间窗口（天）
const FEED_DAYS = 7

const NewsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  // 状态管理
  const [selectedNewsId, setSelectedNewsId] = useState<number | null>(null)
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [modelFilter, setModelFilter] = useState<string>('best')
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchInput, setSearchInput] = useState('')
  // 自定义时间范围；null 表示使用默认「最近 7 天」（跟随 latestDate 自动伸缩）
  const [feedRange, setFeedRange] = useState<{ start: string; end: string } | null>(null)
  const [dateRangeOpen, setDateRangeOpen] = useState(false)
  const [draftStart, setDraftStart] = useState('')
  const [draftEnd, setDraftEnd] = useState('')

  React.useEffect(() => {
    const newsId = Number(searchParams.get('newsId'))
    setSelectedNewsId(Number.isSafeInteger(newsId) && newsId > 0 ? newsId : null)
  }, [searchParams])

  const closeNewsDetail = useCallback(() => {
    setSelectedNewsId(null)
    if (searchParams.has('newsId')) {
      const nextSearchParams = new URLSearchParams(searchParams)
      nextSearchParams.delete('newsId')
      setSearchParams(nextSearchParams, { replace: true })
    }
  }, [searchParams, setSearchParams])

  const modelOptions = ['doubao', 'deepseek', 'qwen', 'default']

  const newsView: 'best' | 'single' | 'all' = modelFilter === 'all' ? 'all' : modelFilter === 'best' ? 'best' : 'single'
  const selectedModel = newsView === 'single' ? modelFilter : undefined

  // 获取最新的有新闻数据的交易日，作为信息流与收益率曲线的基准
  const { data: latestData } = useLatestTradingDay()
  const latestDate = latestData?.latest_date || format(new Date(), 'yyyy-MM-dd')

  // 收益率日期范围：最近30天
  const yieldStartDate = format(subDays(new Date(latestDate), 30), 'yyyy-MM-dd')
  const yieldEndDate = latestDate

  // 多期限收益率（固定 1年/5年/10年/30年）
  const {
    data: multiYields,
    isLoading: yieldsLoading,
    error: yieldsError,
  } = useMultiYields(YIELD_PERIODS, yieldStartDate, yieldEndDate)

  // 新闻信息流：默认最近 FEED_DAYS 天，终点为最新交易日；用户可选自定义时间范围
  const defaultStart = format(subDays(new Date(latestDate), FEED_DAYS), 'yyyy-MM-dd')
  const {
    data: news,
    isLoading: newsLoading,
    error: newsError,
  } = useNewsByDateRange(
    feedRange?.start ?? defaultStart,
    feedRange?.end ?? latestDate,
    selectedSources.length > 0 ? selectedSources : undefined,
    selectedModel,
    newsView
  )

  const { data: sourcesData } = useNewsSources()
  const { data: selectedNewsDetail, isLoading: detailLoading } = useNewsDetail(
    selectedNewsId || 0,
    selectedModel,
    newsView === 'all'
  )

  // 新闻搜索
  const { data: searchResults, isLoading: searchLoading, error: searchError } = useSearchNews(searchKeyword, 20)

  const handleNewsSelect = useCallback((newsItem: NewsItem) => {
    setSelectedNewsId(newsItem.id)
  }, [])

  // 计算选中新闻前后10个交易日的收益率数据
  const {
    data: newsYields,
    isLoading: newsYieldsLoading,
    error: newsYieldsError,
  } = useQuery({
    queryKey: ['news', 'yield_features', selectedNewsId, '10年'],
    queryFn: async () => {
      if (!selectedNewsId) return null
      const token = storage.get<string>('auth_token')
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const response = await fetch(
        `${API_PREFIX}/news/${selectedNewsId}/yield?period=10%E5%B9%B4&window_before=10&window_after=10`,
        { headers }
      )
      if (!response.ok) throw new Error('获取收益率特征失败')
      return response.json()
    },
    enabled: !!selectedNewsId,
    staleTime: 10 * 60 * 1000,
  })

  const handleSourceToggle = useCallback((sourceKey: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceKey) ? prev.filter((s) => s !== sourceKey) : [...prev, sourceKey]
    )
  }, [])

  const handleSearch = useCallback(() => {
    if (searchInput.trim()) {
      setSearchKeyword(searchInput.trim())
      setSelectedNewsId(null)
    }
  }, [searchInput])

  const handleClearSearch = useCallback(() => {
    setSearchInput('')
    setSearchKeyword('')
  }, [])

  // 打开时间范围弹层时，用当前生效范围初始化草稿值
  const openDateRange = useCallback(() => {
    setDraftStart(feedRange?.start ?? format(subDays(new Date(latestDate), FEED_DAYS), 'yyyy-MM-dd'))
    setDraftEnd(feedRange?.end ?? latestDate)
    setDateRangeOpen(true)
  }, [feedRange, latestDate])

  // 应用手动选择的开始/结束日期
  const applyCustomRange = useCallback(() => {
    if (draftStart && draftEnd) setFeedRange({ start: draftStart, end: draftEnd })
    setDateRangeOpen(false)
  }, [draftStart, draftEnd])

  // 快捷预设：null=默认(最近7天)，或指定天数
  const applyPreset = useCallback(
    (days: number | null) => {
      setFeedRange(days ? { start: format(subDays(new Date(latestDate), days), 'yyyy-MM-dd'), end: latestDate } : null)
      setDateRangeOpen(false)
    },
    [latestDate]
  )

  // 组装多期限曲线数据
  const yieldSeries = useMemo(() => multiYields?.map((s) => ({ label: s.label, data: s.data })) || [], [multiYields])

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div className="page-header">
        <h1 className="text-3xl font-bold text-white mb-2">📰 新闻分析</h1>
        <p className="text-gray-400 text-sm">查看国债收益率走势、分析新闻事件对债市的影响</p>
      </div>

      {/* 工具栏 */}
      <Card className="relative z-30">
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4 items-center">
            {/* 新闻源选择（脱敏名） */}
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-400">新闻源:</label>
              <div className="flex gap-2">
                {sourcesData?.sources?.map((source) => (
                  <Button
                    key={source.key}
                    size="sm"
                    variant={selectedSources.includes(source.key) ? 'primary' : 'outline'}
                    onClick={() => handleSourceToggle(source.key)}
                  >
                    {maskSource(source.name) || source.name}
                  </Button>
                ))}
              </div>
            </div>

            {/* 模型视图选择 */}
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-400">模型:</label>
              <select
                value={modelFilter}
                onChange={(e) => setModelFilter(e.target.value)}
                className="px-3 py-1.5 text-sm bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-purple-500 outline-none"
              >
                <option value="best">优先级(best)</option>
                <option value="all">全部模型(all)</option>
                {modelOptions.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            {/* 时间范围选择 */}
            <div className="relative flex items-center gap-2">
              <label className="text-sm text-gray-400">时间:</label>
              <Button size="sm" variant="outline" onClick={openDateRange}>
                📅 {feedRange ? `${feedRange.start} ~ ${feedRange.end}` : `最近 ${FEED_DAYS} 天`}
              </Button>
              {dateRangeOpen && (
                <div className="absolute top-full left-0 mt-1 z-50 bg-gray-800 border border-gray-600 rounded-lg p-3 shadow-xl">
                  {/* 快捷预设 */}
                  <div className="flex gap-2 mb-3">
                    {[3, 7, 15, 30].map((d) => (
                      <button
                        key={d}
                        onClick={() => applyPreset(d)}
                        className="text-xs px-3 py-1 rounded bg-gray-700 text-gray-300 hover:text-white"
                      >
                        最近{d}天
                      </button>
                    ))}
                    <button
                      onClick={() => applyPreset(null)}
                      className="text-xs px-3 py-1 rounded bg-gray-700 text-gray-300 hover:text-white"
                    >
                      默认
                    </button>
                  </div>
                  {/* 开始/结束日期 */}
                  <div className="flex gap-3">
                    <div>
                      <div className="text-[11px] text-gray-400 mb-1">开始日期</div>
                      <input
                        type="date"
                        value={draftStart}
                        onChange={(e) => setDraftStart(e.target.value)}
                        className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1.5 w-36"
                      />
                    </div>
                    <div>
                      <div className="text-[11px] text-gray-400 mb-1">结束日期</div>
                      <input
                        type="date"
                        value={draftEnd}
                        onChange={(e) => setDraftEnd(e.target.value)}
                        className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1.5 w-36"
                      />
                    </div>
                  </div>
                  {/* 操作按钮 */}
                  <div className="flex justify-end gap-2 mt-3">
                    <button
                      onClick={() => setDateRangeOpen(false)}
                      className="text-xs px-3 py-1 rounded bg-gray-700 text-gray-400 hover:text-gray-300"
                    >
                      取消
                    </button>
                    <button
                      onClick={applyCustomRange}
                      className="text-xs px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-500"
                    >
                      应用
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* 搜索框 */}
            <div className="flex items-center gap-2 ml-auto">
              <Input
                type="text"
                placeholder="输入关键词搜索新闻..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                icon="🔍"
                className="w-64"
              />
              <Button size="sm" variant="primary" onClick={handleSearch} loading={searchLoading}>
                搜索
              </Button>
              {searchKeyword && (
                <Button size="sm" variant="outline" onClick={handleClearSearch}>
                  清除
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 主要内容区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：多期限收益率走势 */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>收益率走势 </CardTitle>
            </CardHeader>
            <CardContent>
              {yieldsLoading ? (
                <Loading text="加载收益率数据..." />
              ) : yieldsError ? (
                <div className="text-red-400 text-sm">加载收益率数据失败: {yieldsError.message}</div>
              ) : yieldSeries.length > 0 && yieldSeries.some((s) => s.data.length > 0) ? (
                <YieldChart data={yieldSeries[0].data} series={yieldSeries} height={400} />
              ) : (
                <div className="text-gray-400 text-center py-8">暂无收益率数据</div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 右侧：新闻信息流 */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle>
                {searchKeyword
                  ? `搜索结果: "${searchKeyword}"`
                  : `最新新闻（${feedRange ? `${feedRange.start} ~ ${feedRange.end}` : `最近 ${FEED_DAYS} 天`}）`}
                {searchKeyword
                  ? searchResults?.news && (
                      <span className="ml-2 text-sm font-normal text-gray-400">({searchResults.news.length}条)</span>
                    )
                  : news && <span className="ml-2 text-sm font-normal text-gray-400">({news.length}条)</span>}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {searchKeyword ? (
                searchLoading ? (
                  <Loading text="搜索中..." />
                ) : searchError ? (
                  <div className="text-red-400 text-sm">搜索失败: {searchError.message}</div>
                ) : searchResults?.news && searchResults.news.length > 0 ? (
                  <NewsList news={searchResults.news} selectedNewsId={selectedNewsId} onNewsSelect={handleNewsSelect} />
                ) : (
                  <div className="text-gray-400 text-center py-8">没有找到包含 "{searchKeyword}" 的新闻</div>
                )
              ) : newsLoading ? (
                <Loading text="加载新闻..." />
              ) : newsError ? (
                <div className="text-red-400 text-sm">加载新闻失败: {newsError.message}</div>
              ) : news && news.length > 0 ? (
                <NewsList news={news} selectedNewsId={selectedNewsId} onNewsSelect={handleNewsSelect} />
              ) : (
                <div className="text-gray-400 text-center py-8">暂无新闻</div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 新闻详情及相关收益率走势 */}
      {selectedNewsId && (
        <div className="space-y-6">
          {/* 新闻事件前后收益率走势 */}
          {selectedNewsDetail && (
            <Card>
              <CardHeader>
                <CardTitle>
                  新闻事件前后收益率走势
                  <span className="ml-2 text-sm font-normal text-gray-400">
                    {newsYields?.window_start && newsYields?.window_end
                      ? `(${newsYields.window_start} 至 ${newsYields.window_end})`
                      : '（前后10个交易日）'}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {newsYieldsLoading ? (
                  <Loading text="加载收益率数据..." />
                ) : newsYieldsError ? (
                  <div className="text-red-400 text-sm">加载收益率数据失败: {newsYieldsError.message}</div>
                ) : newsYields?.data && newsYields.data.length > 0 ? (
                  <YieldChart data={newsYields.data} type="10年" height={300} />
                ) : (
                  <div className="text-gray-400 text-center py-8">暂无该时间段的收益率数据</div>
                )}
              </CardContent>
            </Card>
          )}

          {/* 新闻详情 */}
          <Card>
            <CardHeader>
              <CardTitle>新闻详情</CardTitle>
            </CardHeader>
            <CardContent>
              {detailLoading ? (
                <Loading text="加载新闻详情..." />
              ) : selectedNewsDetail ? (
                <NewsDetail
                  news={selectedNewsDetail}
                  onClose={closeNewsDetail}
                  onNewsSelect={(newsId) => setSelectedNewsId(newsId)}
                  selectedModelName={selectedModel}
                />
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

export default NewsPage
