import React from 'react'
import type { NewsItem } from '@/types'
import { maskSource } from '@/utils/helpers'

interface NewsListProps {
  news: NewsItem[]
  selectedNews?: NewsItem | null
  selectedNewsId?: number | null
  onNewsSelect: (news: NewsItem) => void
}

const NewsList: React.FC<NewsListProps> = ({ news, selectedNews, selectedNewsId, onNewsSelect }) => {
  const getDirectionColor = (direction?: string) => {
    switch (direction) {
      case 'positive':
      case '看涨':
        return 'text-green-400'
      case 'negative':
      case '看跌':
        return 'text-red-400'
      case 'neutral':
      case '中性':
        return 'text-yellow-400'
      default:
        return 'text-gray-400'
    }
  }

  const getDirectionIcon = (direction?: string) => {
    switch (direction) {
      case 'positive':
      case '看涨':
        return '↑'
      case 'negative':
      case '看跌':
        return '↓'
      case 'neutral':
      case '中性':
        return '→'
      default:
        return '•'
    }
  }

  const formatDateTime = (publishTime?: string) => {
    if (!publishTime) return ''
    try {
      const date = new Date(publishTime)
      const ymd = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
      const time = date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
      })
      return `${ymd} ${time}`
    } catch {
      return publishTime
    }
  }

  const truncateText = (text: string, maxLength: number = 100) => {
    if (text.length <= maxLength) return text
    return text.substring(0, maxLength) + '...'
  }

  return (
    <div className="space-y-3 max-h-96 overflow-y-auto">
      {news.map((item) => (
        <div
          key={item.id}
          onClick={() => onNewsSelect(item)}
          data-track="news_click"
          data-target={`news_id:${item.id}`}
          data-detail={JSON.stringify({ title: (item.title || '').slice(0, 60), source: item.source })}
          className={`p-3 rounded-lg border cursor-pointer transition-all duration-200 ${
            selectedNews?.id === item.id || selectedNewsId === item.id
              ? 'border-purple-500 bg-purple-500/10'
              : 'border-gray-700 hover:border-gray-600 hover:bg-gray-800/50'
          }`}
        >
          {/* 标题和时间 */}
          <div className="flex items-start justify-between mb-2">
            <h3 className="text-sm font-medium text-white flex-1 mr-2 line-clamp-2">{item.title}</h3>
            <div className="flex flex-col items-end gap-1 flex-shrink-0">
              <span className="text-xs text-gray-400">{formatDateTime(item.publish_time)}</span>
              {item.direction && (
                <span className={`text-xs font-medium ${getDirectionColor(item.direction)}`}>
                  {getDirectionIcon(item.direction)} {item.direction}
                </span>
              )}
            </div>
          </div>

          {/* 摘要 */}
          {item.summary && <p className="text-xs text-gray-400 leading-relaxed mb-2">{truncateText(item.summary)}</p>}

          {/* 标签信息 */}
          <div className="flex items-center gap-2 text-xs">
            {item.source && maskSource(item.source) && (
              <span className="px-2 py-1 bg-gray-700 text-gray-300 rounded">{maskSource(item.source)}</span>
            )}
            {item.horizon && <span className="px-2 py-1 bg-gray-700 text-gray-300 rounded">{item.horizon}</span>}
            {item.publisher && <span className="px-2 py-1 bg-gray-700 text-gray-300 rounded">{item.publisher}</span>}
          </div>

          {/* 因子预览 */}
          {item.factors && item.factors.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {item.factors.slice(0, 3).map((factor, index) => (
                <span key={index} className="text-xs px-2 py-1 bg-purple-500/20 text-purple-300 rounded">
                  {factor.name || factor.code}
                </span>
              ))}
              {item.factors.length > 3 && (
                <span className="text-xs px-2 py-1 bg-gray-700 text-gray-400 rounded">+{item.factors.length - 3}</span>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default NewsList
