/**
 * 紧凑新闻行 — latest / recommend / calendar 共用最小展示结构。
 * recommend 显示时间衰减后 final_score；calendar 只显示静态 importance_score 与绝对 HH:mm。
 */
import React from 'react'
import { fmtClockTime, fmtTime } from '../utils/format'
import ImportanceBadge from './ImportanceBadge'
import '../market-news.css'

const DIR_META: Record<string, { label: string; cls: string }> = {
  positive: { label: '利多', cls: 'news-dir--up' },
  negative: { label: '利空', cls: 'news-dir--down' },
  neutral: { label: '中性', cls: 'news-dir--neutral' },
}

export const DirectionBadge: React.FC<{ direction?: string | null }> = ({ direction }) => {
  const meta = DIR_META[direction || '']
  if (!meta) return null
  return <span className={`news-dir-badge ${meta.cls}`}>{meta.label}</span>
}

export const FactorChips: React.FC<{
  factors: { id: number; name: string }[]
  maxVisible?: number
}> = ({ factors, maxVisible = 2 }) => {
  if (!factors?.length) return null
  const visible = factors.slice(0, maxVisible)
  const rest = factors.length - visible.length
  return (
    <span className="news-factor-chips">
      {visible.map((factor) => (
        <span key={factor.id} className="news-factor-chip" title={factor.name}>{factor.name}</span>
      ))}
      {rest > 0 && <span className="news-factor-chip">+{rest}</span>}
    </span>
  )
}

/** DiscoverNewsItem 与此结构天然兼容；收益新闻通过显式 adapter 传入。 */
export interface NewsListRowItem {
  id: number
  title: string
  pub_time?: string | null
  source_name?: string | null
  thumbnail?: string | null
  direction?: string | null
  reason?: string | null
  horizon?: string | null
  factors?: { id: number; name: string }[]
  importance_score?: number | null
  final_score?: number | null
  score_version?: string | null
}

interface Props {
  item: NewsListRowItem
  variant?: 'latest' | 'recommend' | 'calendar'
  onClick: () => void
}

const NewsListRow: React.FC<Props> = ({ item, variant = 'latest', onClick }) => {
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onClick()
    }
  }
  const showReason = variant === 'recommend' || variant === 'calendar'
  const time = variant === 'calendar' ? fmtClockTime(item.pub_time) : fmtTime(item.pub_time)

  return (
    <article
      className={`news-row${variant === 'calendar' ? ' news-row--calendar' : ''}`}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
    >
      {item.thumbnail && (
        <img className="news-row-thumb" src={item.thumbnail} alt="" loading="lazy" />
      )}
      <div className="news-row-main">
        <h3 className="news-row-title">{item.title}</h3>
        {showReason && item.reason && <p className="news-row-summary">{item.reason}</p>}
        <div className="news-row-meta">
          {time && <time className="news-row-time" dateTime={item.pub_time ?? undefined}>{time}</time>}
          {item.source_name && <span className="news-row-source">{item.source_name}</span>}
          {variant === 'calendar' && item.horizon && <span className="news-row-horizon">{item.horizon}</span>}
          <FactorChips factors={item.factors ?? []} maxVisible={variant === 'calendar' ? 3 : 2} />
        </div>
      </div>
      <div className="news-row-aside">
        {variant === 'recommend' && item.final_score != null && (
          <ImportanceBadge score={item.final_score} mode="decayed" />
        )}
        {variant === 'calendar' && (
          <ImportanceBadge score={item.importance_score} mode="static" scoreVersion={item.score_version} />
        )}
        <DirectionBadge direction={item.direction} />
      </div>
    </article>
  )
}

export default NewsListRow
