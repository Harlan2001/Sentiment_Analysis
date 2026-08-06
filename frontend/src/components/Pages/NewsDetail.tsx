import React, { useState, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Card, CardContent, CardHeader, CardTitle } from '@/components/UI'
import { useNewsAnalysis, useSimilarNews, useNewsDetail } from '@/hooks/useNewsApi'
import { useGraphAugmentJob, useGraphAugment } from '@/hooks/useGraphAugment'
import { Loading, Error } from '@/components/UI'
import { maskSource } from '@/utils/helpers'
import type { NewsItem } from '@/types'
import GraphAugmentViewer from './GraphAugmentViewer'
import NewsContentBlocks from './NewsContentBlocks'
import NewsCard from './NewsCard'

interface NewsDetailProps {
  news: NewsItem
  onClose?: () => void
  onNewsSelect?: (newsId: number) => void
  selectedModelName?: string
}

const NewsDetail: React.FC<NewsDetailProps> = ({ news, onClose, onNewsSelect, selectedModelName }) => {
  const [showAnalysis, setShowAnalysis] = useState(false)
  const [showSimilar, setShowSimilar] = useState(false)
  const [showGraphAugment, setShowGraphAugment] = useState(false)
  const [selectedSimilarNews, setSelectedSimilarNews] = useState<NewsItem | null>(null)
  const [activeAnalysisModel, setActiveAnalysisModel] = useState<string>('')

  const queryClient = useQueryClient()
  const { mutate: analyzeNews, isPending: isAnalyzing, data: analysisResult } = useNewsAnalysis()

  const {
    data: similarNews,
    isLoading: isLoadingSimilar,
    error: similarError,
  } = useSimilarNews(showSimilar ? news.id : 0)

  // 获取选中的相似新闻详情
  const { data: similarNewsDetail, isLoading: similarDetailLoading } = useNewsDetail(selectedSimilarNews?.id || 0)

  // 图谱补全 - 检查是否有内容
  const hasContent = !!(news.content || (news.content_blocks && news.content_blocks.length > 0))
  const newsText =
    news.content ||
    (news.content_blocks || [])
      .map((b) => b.content)
      .filter(Boolean)
      .join('\n')

  // 获取已有任务
  const { job: existingJob } = useGraphAugmentJob(news.id)

  // 图谱补全 hook
  const graphAugment = useGraphAugment({
    newsId: news.id,
    newsContent: newsText,
  })

  // 如果有已有任务，加载它
  React.useEffect(() => {
    if (existingJob && existingJob.result_json) {
      graphAugment.loadFromJob(existingJob)
      if (existingJob.status === 'WAITING_REVIEW' || existingJob.status === 'COMPLETED') {
        setShowGraphAugment(true)
      }
    }
  }, [existingJob])

  const analyses = news.analyses || []
  const hasMultiModelAnalyses = analyses.length > 0

  useEffect(() => {
    if (!hasMultiModelAnalyses) {
      setActiveAnalysisModel('')
      return
    }
    const defaultModel = news.selected_model || news.model || analyses[0].model
    setActiveAnalysisModel(defaultModel)
  }, [news.id, news.model, news.selected_model, hasMultiModelAnalyses, analyses])

  const activeAnalysis = hasMultiModelAnalyses
    ? analyses.find((a) => a.model === activeAnalysisModel) || analyses[0]
    : undefined

  const displayDirection = activeAnalysis?.direction || news.direction
  const displayHorizon = activeAnalysis?.horizon || news.horizon
  const displayReason = activeAnalysis?.reason || news.reason
  const displayModel = activeAnalysis?.model || news.model
  const displayFactors =
    activeAnalysis?.factors && activeAnalysis.factors.length > 0 ? activeAnalysis.factors : news.factors || []

  const handleAnalyze = () => {
    analyzeNews(
      { newsId: news.id, modelName: selectedModelName || activeAnalysisModel },
      {
        onSuccess: () => {
          // 分析成功后刷新新闻详情，获取最新的分析结果
          queryClient.invalidateQueries({ queryKey: ['news', 'detail', news.id] })
        },
      }
    )
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
    <div className="space-y-6">
      {/* 新闻基本信息 */}
      <div>
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-white mb-2">{news.title}</h2>
            <div className="flex flex-wrap items-center gap-3 text-sm text-gray-400">
              <span>发布时间: {formatDateTime(news.publish_time)}</span>
              {news.source && maskSource(news.source) && <span>来源: {maskSource(news.source)}</span>}
              {news.publisher && <span>发布者: {news.publisher}</span>}
            </div>
          </div>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </Button>
          )}
        </div>

        {/* 标签 */}
        <div className="flex flex-wrap gap-2 mb-4">
          {displayDirection && (
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getDirectionColor(displayDirection)}`}>
              {displayDirection}
            </span>
          )}
          {displayHorizon && (
            <span className="px-3 py-1 bg-gray-700 text-gray-300 rounded-full text-sm">{displayHorizon}</span>
          )}
          {displayModel && (
            <span className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-sm">模型: {displayModel}</span>
          )}
        </div>

        {/* 内容 */}
        {news.content_blocks && news.content_blocks.length > 0 ? (
          <div className="prose prose-invert max-w-none">
            <NewsContentBlocks blocks={news.content_blocks} />
          </div>
        ) : (
          news.content && (
            <div className="prose prose-invert max-w-none">
              <div className="text-gray-300 leading-relaxed whitespace-pre-wrap">{news.content}</div>
            </div>
          )
        )}

        {/* 摘要 */}
        {news.summary && (
          <div className="mt-4 p-4 bg-gray-800/50 rounded-lg border border-gray-700">
            <h4 className="text-sm font-medium text-gray-400 mb-2">摘要</h4>
            <p className="text-sm text-gray-300 leading-relaxed">{news.summary}</p>
          </div>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-3">
        <Button onClick={handleAnalyze} loading={isAnalyzing}>
          {showAnalysis ? '重新分析' : '智能分析'}
        </Button>
        <Button variant="outline" onClick={() => setShowSimilar(!showSimilar)}>
          相似新闻
        </Button>
        {hasContent && (
          <Button variant="outline" onClick={() => setShowGraphAugment(!showGraphAugment)}>
            🔮 图谱补全
          </Button>
        )}
      </div>

      {/* 分析结果提示 */}
      {showAnalysis && analysisResult?.message && (
        <div className="p-3 bg-green-500/20 border border-green-500/50 rounded-lg">
          <p className="text-green-400 text-sm">{analysisResult.message}</p>
        </div>
      )}

      {/* 分析错误提示 */}
      {showAnalysis && analysisResult?.error && (
        <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg">
          <p className="text-red-400 text-sm">{analysisResult.error}</p>
        </div>
      )}

      {/* 分析中加载状态 */}
      {showAnalysis && isAnalyzing && <Loading text="分析中..." />}

      {/* 多模型对比 */}
      {hasMultiModelAnalyses && (
        <Card>
          <CardHeader>
            <CardTitle>多模型对比</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2 mb-4">
              {analyses.map((analysis) => (
                <button
                  key={analysis.model}
                  type="button"
                  onClick={() => setActiveAnalysisModel(analysis.model)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-colors border ${
                    activeAnalysisModel === analysis.model
                      ? 'bg-blue-500/25 text-blue-200 border-blue-400/50'
                      : 'bg-gray-800 text-gray-300 border-gray-700 hover:bg-gray-700'
                  }`}
                >
                  {analysis.model}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
              {analyses.map((analysis) => (
                <div
                  key={`compare-${analysis.model}`}
                  className={`p-3 rounded-lg border ${
                    activeAnalysisModel === analysis.model
                      ? 'border-blue-400/60 bg-blue-500/10'
                      : 'border-gray-700 bg-gray-800/40'
                  }`}
                >
                  <div className="text-sm text-white font-medium mb-2">{analysis.model}</div>
                  <div className="flex flex-wrap gap-2 mb-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${getDirectionColor(analysis.direction)}`}>
                      {analysis.direction}
                    </span>
                    <span className="px-2 py-0.5 rounded text-xs bg-gray-700 text-gray-200">{analysis.horizon}</span>
                  </div>
                  <div className="text-xs text-gray-300 line-clamp-3">{analysis.reason || '待分析'}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 相似新闻 */}
      {showSimilar && (
        <Card>
          <CardHeader>
            <CardTitle>相似新闻</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingSimilar ? (
              <Loading text="加载相似新闻..." />
            ) : similarError ? (
              <Error title="加载失败" message={similarError.message} />
            ) : similarNews && similarNews.length > 0 ? (
              <div className="space-y-3">
                {similarNews.map((item: any) => (
                  <div
                    key={item.news_id}
                    onClick={() => setSelectedSimilarNews({ id: item.news_id, title: item.title } as NewsItem)}
                    className="p-3 border border-gray-700 rounded-lg hover:bg-gray-800/50 transition-colors cursor-pointer"
                  >
                    <h4 className="text-sm font-medium text-white mb-2">{item.title}</h4>
                    <div className="flex items-center gap-4 text-xs text-gray-400">
                      <span>相似度: {(item.score * 100).toFixed(1)}%</span>
                      <span>ID: {item.news_id}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-gray-400 py-4">暂无相似新闻</div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 分析结论 */}
      {displayReason && (
        <Card>
          <CardHeader>
            <CardTitle>影响逻辑链</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-2 justify-center py-4">
              {displayReason.split('→').map((step, index, array) => (
                <React.Fragment key={index}>
                  <div className="flex items-center px-4 py-3 bg-gray-800/60 border border-gray-700 rounded-lg shadow-lg">
                    <span className="text-sm font-medium text-blue-100">{step.trim().replace(/【|】/g, '')}</span>
                  </div>
                  {index < array.length - 1 && <div className="text-2xl text-purple-400 font-bold mx-1">→</div>}
                </React.Fragment>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 相关因子 */}
      {displayFactors && displayFactors.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>相关因子</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {displayFactors.map((factor, index) => (
                <div key={index} className="p-3 border border-gray-700 rounded-lg bg-gray-800/30">
                  <div className="flex items-start justify-between mb-2">
                    <h4 className="text-sm font-medium text-white">{factor.name || factor.code}</h4>
                    {factor.direction && (
                      <span className={`text-xs px-2 py-1 rounded ${getDirectionColor(factor.direction)}`}>
                        {factor.direction}
                      </span>
                    )}
                  </div>

                  <div className="space-y-1 text-xs text-gray-400">
                    <p>代码: {factor.code}</p>
                    {factor.category && <p>分类: {factor.category}</p>}
                    {factor.driver && <p>驱动: {factor.driver}</p>}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 图谱补全 - 在相关因子下方显示 */}
      {showGraphAugment && (
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
      )}

      {/* 相似新闻卡片模态框 */}
      {selectedSimilarNews && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-4xl">
            {similarDetailLoading ? (
              <Card>
                <CardContent className="p-8">
                  <Loading text="加载新闻详情..." />
                </CardContent>
              </Card>
            ) : similarNewsDetail ? (
              <NewsCard
                news={similarNewsDetail as NewsItem}
                onClose={() => setSelectedSimilarNews(null)}
                onNewsSelect={(newsId) => {
                  if (onNewsSelect) {
                    onNewsSelect(newsId)
                    setSelectedSimilarNews(null)
                  }
                }}
              />
            ) : (
              <Card>
                <CardContent className="p-8 text-center text-gray-400">加载新闻失败</CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default NewsDetail
