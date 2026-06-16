import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, Button, Loading } from '../UI'
import { useNewsAnalysis, useSimilarNews } from '../../hooks/useNewsApi'
import { useGraphAugmentJob, useGraphAugment } from '../../hooks/useGraphAugment'
import GraphAugmentViewer from './GraphAugmentViewer'
import type { NewsItem } from '../../types'
import NewsContentBlocks from './NewsContentBlocks'
import YieldChart from './YieldChart'

interface NewsCardProps {
  news: NewsItem
  yieldData?: any
  yieldLoading?: boolean
  yieldError?: Error | null
  yieldType?: string
  onClose?: () => void
  onNewsSelect?: (newsId: number) => void
  className?: string
}

const NewsCard: React.FC<NewsCardProps> = ({
  news,
  yieldData,
  yieldLoading,
  yieldError,
  yieldType = '10年',
  onClose,
  onNewsSelect,
  className = ''
}) => {
  // 如果新闻已经被分析过（有direction, horizon等分析结果），自动展开分析
  const hasExistingAnalysis = !!(news.direction || news.horizon || news.reason);
  const [showAnalysis, setShowAnalysis] = useState(hasExistingAnalysis);
  const [showSimilar, setShowSimilar] = useState(false);
  const [showGraphAugment, setShowGraphAugment] = useState(false);
  
  const { 
    mutate: analyzeNews, 
    isPending: isAnalyzing, 
    data: analysisResult 
  } = useNewsAnalysis()
  
  const { 
    data: similarNews, 
    isLoading: isLoadingSimilar, 
    error: similarError 
  } = useSimilarNews(showSimilar ? news.id : 0)

  // 图谱补全 - 检查是否有内容
  const hasContent = !!(news.content || (news.content_blocks && news.content_blocks.length > 0))
  const newsText = news.content || 
    (news.content_blocks || []).map(b => b.content).filter(Boolean).join('\n')

  // 获取已有任务
  const { job: existingJob } = useGraphAugmentJob(news.id)
  
  // 图谱补全 hook
  const graphAugment = useGraphAugment({
    newsId: news.id,
    newsContent: newsText,
  })

  // 如果有已有任务，加载它
  useEffect(() => {
    if (existingJob && existingJob.result_json) {
      graphAugment.loadFromJob(existingJob)
      if (existingJob.status === 'WAITING_REVIEW' || existingJob.status === 'COMPLETED') {
        setShowGraphAugment(true)
      }
    }
  }, [existingJob])
  
  const handleAnalyze = () => {
    setShowAnalysis(true)
    if (!analysisResult) {
      analyzeNews({ newsId: news.id })
    }
  }
  
  const handleSimilarNewsClick = (newsId: number) => {
    if (onNewsSelect) {
      onNewsSelect(newsId)
    }
  }
  
  const getDirectionColor = (direction?: string) => {
    switch (direction) {
      case 'positive':
      case '看涨':
        return 'text-green-400 bg-green-400/20'
      case 'negative':
      case '看跌':
        return 'text-red-400 bg-red-400/20'
      case 'neutral':
      case '中性':
        return 'text-yellow-400 bg-yellow-400/20'
      default:
        return 'text-gray-400 bg-gray-400/20'
    }
  }
  
  const formatDateTime = (dateString?: string) => {
    if (!dateString) return ''
    try {
      const date = new Date(dateString)
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return dateString
    }
  }

  return (
    <Card className={`max-w-4xl w-full mx-auto ${className}`}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <CardTitle className="text-lg">
            {news.title}
          </CardTitle>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </Button>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm text-gray-400 mt-2">
          <span>发布时间: {formatDateTime(news.publish_time)}</span>
          {news.source && <span>来源: {news.source}</span>}
          {news.publisher && <span>发布者: {news.publisher}</span>}
        </div>
        {/* 标签 */}
        <div className="flex flex-wrap gap-2 mt-2">
          {news.direction && (
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${getDirectionColor(news.direction)}`}>
              {news.direction}
            </span>
          )}
          {news.horizon && (
            <span className="px-3 py-1 bg-gray-700 text-gray-300 rounded-full text-xs">
              {news.horizon}
            </span>
          )}
          {news.model && (
            <span className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-xs">
              模型: {news.model}
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 已有分析结果信息 */}
        {(news.direction || news.horizon || news.factors) && (
          <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
            <h4 className="text-sm font-medium text-white mb-3">分析结果</h4>
            <div className="flex flex-wrap gap-3 mb-3">
              {news.direction && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">影响方向:</span>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${getDirectionColor(news.direction)}`}>
                    {news.direction}
                  </span>
                </div>
              )}
              {news.horizon && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">分析期限:</span>
                  <span className="px-3 py-1 bg-gray-700 text-gray-300 rounded-full text-xs">
                    {news.horizon}
                  </span>
                </div>
              )}
            </div>
            
            {news.reason && (
              <div className="mb-3">
                <span className="text-sm text-gray-400 block mb-2">影响逻辑:</span>
                <p className="text-sm text-gray-300 leading-relaxed bg-gray-900/50 p-3 rounded">
                  {news.reason}
                </p>
              </div>
            )}
            
            {news.factors && news.factors.length > 0 && (
              <div>
                <span className="text-sm text-gray-400 block mb-2">相关因子:</span>
                <div className="flex flex-wrap gap-2">
                  {news.factors.map((factor, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 bg-purple-500/20 text-purple-300 rounded text-xs"
                    >
                      {factor.name} ({factor.code})
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 新闻内容 */}
        <div>
          {news.content_blocks && news.content_blocks.length > 0 ? (
            <div className="prose prose-invert max-w-none text-base">
              <NewsContentBlocks blocks={news.content_blocks} />
            </div>
          ) : news.content && (
            <div className="prose prose-invert max-w-none text-base">
              <div className="text-gray-300 leading-relaxed whitespace-pre-wrap">
                {news.content}
              </div>
            </div>
          )}
          {news.summary && (
            <div className="mt-4 p-4 bg-gray-800/50 rounded-lg border border-gray-700">
              <h4 className="text-sm font-medium text-gray-400 mb-2">摘要</h4>
              <p className="text-sm text-gray-300 leading-relaxed">
                {news.summary}
              </p>
            </div>
          )}
        </div>

        {/* 收益率走势图 */}
        {yieldData && (
          <div className="border-t border-gray-700 pt-4">
            <h4 className="text-sm font-medium text-white mb-3">
              新闻发布前后收益率走势
              <span className="ml-2 text-xs font-normal text-gray-400">
                {yieldData?.window_start && yieldData?.window_end
                  ? `(${yieldData.window_start} 至 ${yieldData.window_end})`
                  : '（前后10个交易日）'}
              </span>
            </h4>
            {yieldLoading ? (
              <Loading text="加载收益率数据..." size="sm" />
            ) : yieldError ? (
              <div className="text-red-400 text-xs">
                加载失败: {yieldError.message}
              </div>
            ) : yieldData?.relative_changes && yieldData.relative_changes.length > 0 ? (
              <YieldChart
                data={yieldData.relative_changes.map((item: { date: string; change: number }) => ({
                  date: item.date,
                  value: item.change,
                }))}
                type={yieldType}
                height={200}
              />
            ) : (
            <div className="text-gray-400 text-center py-4 text-sm">
              暂无收益率数据
            </div>
          )}
          </div>
        )}

         {/* 操作按钮 */}
         <div className="flex flex-wrap gap-2 border-t border-gray-700 pt-4">
           <Button
             size="sm"
             onClick={handleAnalyze}
             loading={isAnalyzing}
           >
             {showAnalysis ? '重新分析' : '智能分析'}
           </Button>
           <Button
             size="sm"
             variant="outline"
             onClick={() => setShowSimilar(!showSimilar)}
           >
             相似新闻
           </Button>
           {hasContent && (
             <Button
               size="sm"
               variant="outline"
               onClick={() => setShowGraphAugment(!showGraphAugment)}
             >
               🔮 图谱补全
             </Button>
           )}
         </div>

        {/* 分析结果（手动触发） */}
        {showAnalysis && (
          <div className="border-t border-gray-700 pt-4">
            <h4 className="text-sm font-medium text-white mb-3">智能分析结果</h4>
            {isAnalyzing ? (
              <Loading text="分析中..." size="sm" />
            ) : analysisResult ? (
              <div className="space-y-3">
                {analysisResult.error && (
                  <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg">
                    <p className="text-red-400 text-sm">{analysisResult.error}</p>
                  </div>
                )}
                
                {analysisResult.analysis && (
                  <div className="text-sm text-gray-300 max-h-96 overflow-y-auto">
                    <pre className="whitespace-pre-wrap">
                      {typeof analysisResult.analysis === 'string'
                        ? analysisResult.analysis
                        : JSON.stringify(analysisResult.analysis, null, 2)
                      }
                    </pre>
                  </div>
                )}
                
                {analysisResult.message && (
                  <div className="p-3 bg-green-500/20 border border-green-500/50 rounded-lg">
                    <p className="text-green-400 text-sm">{analysisResult.message}</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center text-gray-400 py-3 text-sm">
                点击"智能分析"按钮开始分析
              </div>
            )}
          </div>
        )}

         {/* 相似新闻 */}
         {showSimilar && (
           <div className="border-t border-gray-700 pt-4">
             <h4 className="text-sm font-medium text-white mb-3">相似新闻</h4>
             {isLoadingSimilar ? (
               <Loading text="加载相似新闻..." size="sm" />
             ) : similarError ? (
               <div className="text-red-400 text-sm">
                 加载失败: {similarError.message}
               </div>
             ) : similarNews && similarNews.length > 0 ? (
               <div className="space-y-3 max-h-96 overflow-y-auto">
                 {similarNews.map((item: any) => (
                   <div
                     key={item.news_id}
                     onClick={() => handleSimilarNewsClick(item.news_id)}
                     className="p-3 border border-gray-700 rounded-lg hover:bg-gray-800/50 transition-colors cursor-pointer"
                   >
                     <h5 className="text-sm font-medium text-white mb-1 line-clamp-2">
                       {item.title}
                     </h5>
                     <div className="flex items-center gap-4 text-sm text-gray-400">
                       <span>相似度: {(item.score * 100).toFixed(1)}%</span>
                       <span>ID: {item.news_id}</span>
                     </div>
                   </div>
                 ))}
               </div>
             ) : (
               <div className="text-center text-gray-400 py-3 text-xs">
                 暂无相似新闻
               </div>
             )}
           </div>
         )}

         {/* 图谱补全 - 在相似新闻下方显示 */}
         {showGraphAugment && (
           <div className="border-t border-gray-700 pt-4">
             <GraphAugmentViewer
               result={graphAugment.result}
               extract={graphAugment.extract}
               isLoading={graphAugment.isLoading}
               status={graphAugment.status}
               stage={graphAugment.stage}
               progressMessages={graphAugment.progressMessages}
               error={graphAugment.error}
               onStart={graphAugment.start}
               canStart={hasContent}
             />
           </div>
         )}
       </CardContent>
     </Card>
   )
 }

export default NewsCard
