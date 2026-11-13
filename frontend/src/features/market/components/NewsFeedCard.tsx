/**
 * 发现页资讯卡片 —— 与收益日历共用的 NewsListRow 独立，避免跨页面样式耦合。
 * 最新与推荐排序共用分析摘要；推荐模式复用统一的重要性评分组件。
 */
import React from 'react'
import type { DiscoverNewsItem } from '@/types'
import { fmtTime } from '../utils/format'
import { DirectionBadge, FactorChips } from './NewsListRow'
import ImportanceBadge from './ImportanceBadge'

const SourceIcon: React.FC = () => (
  <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M3.25 2.75h7.5v10.5h-7.5a1 1 0 0 1-1-1v-8.5a1 1 0 0 1 1-1Z" />
    <path d="M10.75 5h2.25a.75.75 0 0 1 .75.75v6.5a1 1 0 0 1-1 1h-2M4.75 5.25h3.5M4.75 7.75h3.5M4.75 10.25h2.25" />
  </svg>
)

const ArrowIcon: React.FC = () => (
  <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M3.5 8h8M8.5 4.5 12 8l-3.5 3.5" />
  </svg>
)

interface Props {
  item: DiscoverNewsItem
  variant?: 'latest' | 'recommend'
  onClick: () => void
}

const NewsFeedCard: React.FC<Props> = ({ item, variant = 'latest', onClick }) => {
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onClick()
    }
  }
  const description = item.reason || item.summary

  return (
    <article
      className={`news-card news-card--${variant}`}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
    >
      <div className="news-card-header">
        {item.source_name && (
          <span className="news-card-source"><SourceIcon />{item.source_name}</span>
        )}
        <DirectionBadge direction={item.direction} />
      </div>

      <div className="news-card-body">
        <div className="news-card-main">
          <h3 className="news-card-title">{item.title}</h3>
          {description && <p className="news-card-summary">{description}</p>}
        </div>
        {item.thumbnail && (
          <img className="news-card-thumb" src={item.thumbnail} alt="" loading="lazy" />
        )}
      </div>

      <div className="news-card-footer">
        <FactorChips factors={item.factors ?? []} />
        <div className="news-card-aside">
          {variant === 'recommend' && item.final_score != null && (
            <span className="news-card-score">
              <span>推荐</span><ImportanceBadge score={item.final_score} mode="decayed" />
            </span>
          )}
          {item.pub_time && <time className="news-card-time" dateTime={item.pub_time}>{fmtTime(item.pub_time)}</time>}
          <span className="news-card-open"><ArrowIcon /></span>
        </div>
      </div>
    </article>
  )
}

export default NewsFeedCard
