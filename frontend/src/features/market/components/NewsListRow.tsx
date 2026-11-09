/**
 * 紧凑新闻行 — 高密度单列列表的基本单元（S3-1）
 * latest：标题 + meta（时间/来源/因子）+ 方向 badge
 * recommend：额外展示 reason 摘要一行与右侧时间衰减后分值
 */
import React from 'react'
import type { DiscoverNewsItem } from '@/types'
import { fmtTime } from '../utils/format'
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

const MAX_VISIBLE_FACTORS = 2

export const FactorChips: React.FC<{ factors: { id: number; name: string }[] }> = ({ factors }) => {
  if (!factors?.length) return null
  const visible = factors.slice(0, MAX_VISIBLE_FACTORS)
  const rest = factors.length - visible.length
  return (
    <span className="news-factor-chips">
      {visible.map((f) => (
        <span key={f.id} className="news-factor-chip" title={f.name}>{f.name}</span>
      ))}
      {rest > 0 && <span className="news-factor-chip">+{rest}</span>}
    </span>
  )
}

interface Props {
  item: DiscoverNewsItem
  variant?: 'latest' | 'recommend'
  onClick: () => void
}

const NewsListRow: React.FC<Props> = ({ item, variant = 'latest', onClick }) => {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onClick()
    }
  }

  return (
    <article
      className="news-row"
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
        {variant === 'recommend' && item.reason && (
          <p className="news-row-summary">{item.reason}</p>
        )}
        <div className="news-row-meta">
          {item.pub_time && <span className="news-row-time">{fmtTime(item.pub_time)}</span>}
          {item.source_name && <span className="news-row-source">{item.source_name}</span>}
          <FactorChips factors={item.factors ?? []} />
        </div>
      </div>
      <div className="news-row-aside">
        {variant === 'recommend' && item.final_score != null && (
          <span className="news-row-score" title="重要性评分（已叠加时间衰减）">
            {Math.round(item.final_score)}
          </span>
        )}
        <DirectionBadge direction={item.direction} />
      </div>
    </article>
  )
}

export default NewsListRow
