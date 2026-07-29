import React, { useState, useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { format, subDays, addDays } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { useQuery } from '@tanstack/react-query'
import { Button, Input, Card, CardContent, CardHeader, CardTitle, Loading } from '../UI'
import { useYields, useNewsByDate, useNewsSources, useNewsDetail, useSearchNews, useLatestTradingDay } from '../../hooks/useNewsApi'
import { storage } from '../../utils/helpers'
import YieldChart from './YieldChart'
import NewsList from './NewsList'
import NewsDetail from './NewsDetail'
import type { YieldPoint, NewsItem } from '../../types'

const NewsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  // 默认日期：使用当前日期作为初始值，获取最新交易日后会更新
  const today = format(new Date(), 'yyyy-MM-dd')
  const thirtyDaysAgo = format(subDays(new Date(), 30), 'yyyy-MM-dd')
  
  // 状态管理
  const [yieldEndDate, setYieldEndDate] = useState(today)
  const [yieldStartDate, setYieldStartDate] = useState(thirtyDaysAgo)
  const [selectedNewsId, setSelectedNewsId] = useState<number | null>(null)
  const [yieldsType, setYieldsType] = useState('10年')
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [modelFilter, setModelFilter] = useState<string>('best')
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [selectedDateForNews, setSelectedDateForNews] = useState<string | null>(null)

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
  
  // 收益率期限选项
  const yieldPeriods = ['3月', '6月', '1年', '2年', '3年', '5年', '7年', '10年', '30年']
  const modelOptions = ['doubao', 'deepseek', 'qwen', 'default']

  const newsView: 'best' | 'single' | 'all' =
    modelFilter === 'all' ? 'all' : modelFilter === 'best' ? 'best' : 'single'
  const selectedModel = newsView === 'single' ? modelFilter : undefined
  
  // 获取最新的有新闻数据的交易日
  const { data: latestData } = useLatestTradingDay()
  
  // 当获取到最新交易日数据后，更新日期范围
  React.useEffect(() => {
    if (latestData?.latest_date) {
      const latestDate = latestData.latest_date
      const startDate = format(subDays(new Date(latestDate), 30), 'yyyy-MM-dd')
      setYieldEndDate(latestDate)
      setYieldStartDate(startDate)
    }
  }, [latestData])
  
  // 数据获取
  const { data: yields, isLoading: yieldsLoading, error: yieldsError } = useYields(
    yieldStartDate,
    yieldEndDate,
    yieldsType
  )
  
  // 根据选中的日期获取新闻 - 修复：始终调用 hook，通过 enabled 控制
  const { data: news, isLoading: newsLoading, error: newsError, refetch: refetchNews } = useNewsByDate(
    selectedDateForNews || '',
    selectedSources.length > 0 ? selectedSources : undefined,
    selectedModel,
    newsView,
  )
  
  // 当没有选择日期时，提供默认值
  const safeNews = selectedDateForNews ? (news || []) : []
  
  const { data: sourcesData } = useNewsSources()
  const { data: selectedNewsDetail, isLoading: detailLoading } = useNewsDetail(
    selectedNewsId || 0,
    selectedModel,
    newsView === 'all',
  )
  
  // 新闻搜索
  const { data: searchResults, isLoading: searchLoading, error: searchError, refetch: refetchSearch } = useSearchNews(searchKeyword, 20)
  
  // 事件处理
  const handleDateClick = useCallback((date: string) => {
    // 点击图表日期时，显示该日期的新闻
    setSelectedDateForNews(date)
    setSelectedNewsId(null)
  }, [])
  
  const handleNewsSelect = useCallback((newsItem: NewsItem) => {
    console.log('Selected news item:', newsItem)
    setSelectedNewsId(newsItem.id)
  }, [])

  // 计算选中新闻前后10个交易日的收益率数据
  const { data: newsYields, isLoading: newsYieldsLoading, error: newsYieldsError } = useQuery({
    queryKey: ['news', 'yield_features', selectedNewsId, yieldsType],
    queryFn: async () => {
      if (!selectedNewsId) return null
      const token = storage.get<string>('auth_token')
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const response = await fetch(
        `/api/news/${selectedNewsId}/yield?period=${yieldsType}&window_before=10&window_after=10`,
        { headers }
      )
      if (!response.ok) throw new Error('获取收益率特征失败')
      return response.json()
    },
    enabled: !!selectedNewsId,
    staleTime: 10 * 60 * 1000,
  })


  // 调试信息
  console.log('selectedNewsId:', selectedNewsId)
  console.log('selectedNewsDetail:', selectedNewsDetail)
  console.log('detailLoading:', detailLoading)
  
  const handleSourceToggle = useCallback((sourceKey: string) => {
    setSelectedSources(prev => 
      prev.includes(sourceKey) 
        ? prev.filter(s => s !== sourceKey)
        : [...prev, sourceKey]
    )
  }, [])
  
  const handleRefresh = useCallback(() => {
    if (selectedDateForNews) {
      refetchNews()
    }
  }, [selectedDateForNews, refetchNews])
  
  const handleSearch = useCallback(() => {
    if (searchInput.trim()) {
      setSearchKeyword(searchInput.trim())
      setSelectedDateForNews(null) // 搜索时清空日期选择
      setSelectedNewsId(null)
    }
  }, [searchInput])
  
  const handleClearSearch = useCallback(() => {
    setSearchInput('')
    setSearchKeyword('')
  }, [])
  
  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div className="page-header">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
          📰 新闻分析
        </h1>
        <p className="text-gray-400 text-sm">
          查看国债收益率走势、分析新闻事件对债市的影响
        </p>
      </div>
      
      {/* 工具栏 */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4 items-center">
            {/* 收益率类型选择 */}
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-400">收益率:</label>
              <select
                value={yieldsType}
                onChange={(e) => setYieldsType(e.target.value)}
                className="px-3 py-1.5 text-sm bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-purple-500 outline-none"
              >
                {yieldPeriods.map((period) => (
                  <option key={period} value={period}>{period}</option>
                ))}
              </select>
            </div>
            {/* 日期范围选择 */}
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-400">收益率日期范围:</label>
              <Input
                type="date"
                value={yieldStartDate}
                onChange={(e) => setYieldStartDate(e.target.value)}
                className="w-40"
              />
              <span className="text-gray-400">至</span>
              <Input
                type="date"
                value={yieldEndDate}
                onChange={(e) => setYieldEndDate(e.target.value)}
                className="w-40"
              />
            </div>
            
            
            {/* 新闻源选择 */}
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
                    {source.name}
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
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
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
               <Button
                 size="sm"
                 variant="primary"
                 onClick={handleSearch}
                 loading={searchLoading}
               >
                 搜索
               </Button>
               {searchKeyword && (
                 <Button
                   size="sm"
                   variant="outline"
                   onClick={handleClearSearch}
                 >
                   清除
                 </Button>
               )}
             </div>
           </div>
        </CardContent>
      </Card>
      
      {/* 主要内容区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：收益率图表 */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>收益率走势</CardTitle>
            </CardHeader>
            <CardContent>
              {yieldsLoading ? (
                <Loading text="加载收益率数据..." />
              ) : yieldsError ? (
                <div className="text-red-400 text-sm">
                  加载收益率数据失败: {yieldsError.message}
                </div>
              ) : yields && yields.length > 0 ? (
                <YieldChart
                  data={yields}
                  type={yieldsType}
                  onClickDate={handleDateClick}
                  height={400}
                />
              ) : (
                <div className="text-gray-400 text-center py-8">
                  暂无收益率数据
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        
         {/* 右侧：新闻列表 */}
         <div className="lg:col-span-1">
           <Card>
             <CardHeader>
               <CardTitle>
                 {searchKeyword ? `搜索结果: "${searchKeyword}"` : (selectedDateForNews ? `${selectedDateForNews} 的新闻` : '请点击收益率图表选择日期')}
                 {searchKeyword ? (
                   searchResults?.news && (
                     <span className="ml-2 text-sm font-normal text-gray-400">
                       ({searchResults.news.length}条)
                     </span>
                   )
                 ) : (
                   safeNews && (
                     <span className="ml-2 text-sm font-normal text-gray-400">
                       ({safeNews.length}条)
                     </span>
                   )
                 )}
               </CardTitle>
             </CardHeader>
             <CardContent>
               {searchKeyword ? (
                 searchLoading ? (
                   <Loading text="搜索中..." />
                 ) : searchError ? (
                   <div className="text-red-400 text-sm">
                     搜索失败: {searchError.message}
                   </div>
                 ) : searchResults?.news && searchResults.news.length > 0 ? (
                   <NewsList
                     news={searchResults.news}
                     selectedNewsId={selectedNewsId}
                     onNewsSelect={handleNewsSelect}
                   />
                 ) : (
                   <div className="text-gray-400 text-center py-8">
                     没有找到包含 "{searchKeyword}" 的新闻
                   </div>
                 )
               ) : selectedDateForNews ? (
                 newsLoading ? (
                   <Loading text="加载新闻..." />
                 ) : newsError ? (
                   <div className="text-red-400 text-sm">
                     加载新闻失败: {newsError.message}
                   </div>
                 ) : safeNews && safeNews.length > 0 ? (
                   <NewsList
                     news={safeNews}
                     selectedNewsId={selectedNewsId}
                     onNewsSelect={handleNewsSelect}
                   />
                 ) : (
                   <div className="text-gray-400 text-center py-8">
                     {selectedDateForNews} 暂无新闻
                   </div>
                 )
               ) : (
                 <div className="text-gray-400 text-center py-8">
                   请点击图表上的收益率点查看当天的新闻，或使用上方搜索框搜索新闻
                 </div>
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
                  <div className="text-red-400 text-sm">
                    加载收益率数据失败: {newsYieldsError.message}
                  </div>
                ) : newsYields?.data && newsYields.data.length > 0 ? (
                  <YieldChart
                    data={newsYields.data}
                    type={yieldsType}
                    height={300}
                  />
                ) : (
                  <div className="text-gray-400 text-center py-8">
                    暂无该时间段的收益率数据
                  </div>
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
