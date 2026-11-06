/**
 * 推荐排行榜折叠面板（S3-3）—— 仅推荐排序模式展示，位于左栏信息流之上
 * 三标签：新闻榜 Top10 / 因子榜 Top10（附类别分布）/ 多空榜各 Top5
 * 折叠状态记 localStorage；请求失败独立降级一行提示，不阻塞信息流。
 */
import React, { useState } from 'react'
import type { RecommendRankingsResponse, RankingNewsItem } from '@/types'
import { useRecommendRankings } from '../hooks/useRecommendRankings'
import { DirectionBadge } from './NewsListRow'
import { fmtTime } from '../utils/format'
import '../market-news.css'

const COLLAPSE_KEY = 'market:recommend-ranking-collapsed'

const CATEGORY_LABELS: Record<string, string> = {
  POLICY: '政策监管',
  MACRO: '经济增长',
  LIQUIDITY: '资金流动性',
  RISK: '债券供需',
  SENTIMENT: '市场情绪',
  INDUSTRY: '行业产业',
}

type BoardTab = 'news' | 'factor' | 'direction'
const TABS: { key: BoardTab; label: string }[] = [
  { key: 'news', label: '新闻榜' },
  { key: 'factor', label: '因子榜' },
  { key: 'direction', label: '多空榜' },
]

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === '1'
  } catch {
    return false
  }
}

interface Props {
  days: number
  onNewsClick: (newsId: number) => void
  onFactorClick: (factorId: number) => void
}

const RecommendRankingPanel: React.FC<Props> = ({ days, onNewsClick, onFactorClick }) => {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [tab, setTab] = useState<BoardTab>('news')
  const { data, isLoading, isError } = useRecommendRankings(days)

  const toggleCollapsed = () => {
    const next = !collapsed
    setCollapsed(next)
    try {
      localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0')
    } catch {
      // 隐私模式等场景 localStorage 不可写，折叠态仅保留在内存
    }
  }

  return (
    <section className="news-ranking-panel" aria-label="推荐排行榜">
      <header className="news-ranking-header">
        <button type="button" className="news-ranking-toggle" onClick={toggleCollapsed} aria-expanded={!collapsed}>
          <span className="news-ranking-caret">{collapsed ? '▸' : '▾'}</span>
          <h2>推荐排行榜</h2>
          <span className="news-ranking-sub">近 {days} 天 · 重要性 × 时效衰减</span>
        </button>
      </header>

      {!collapsed && (
        <div className="news-ranking-body">
          <div className="news-ranking-tabs">
            {TABS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={tab === item.key ? 'active' : ''}
                onClick={() => setTab(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>

          {isLoading && <div className="news-ranking-hint">榜单加载中…</div>}
          {isError && <div className="news-ranking-hint news-ranking-hint--error">排行榜暂不可用，不影响下方新闻流</div>}
          {!isLoading && !isError && data && <BoardContent tab={tab} data={data} onNewsClick={onNewsClick} onFactorClick={onFactorClick} />}
        </div>
      )}
    </section>
  )
}

const BoardContent: React.FC<{
  tab: BoardTab
  data: RecommendRankingsResponse
  onNewsClick: (newsId: number) => void
  onFactorClick: (factorId: number) => void
}> = ({ tab, data, onNewsClick, onFactorClick }) => {
  if (tab === 'news') {
    if (!data.top_news.length) return <div className="news-ranking-hint">暂无榜单数据</div>
    return (
      <ol className="news-ranking-list">
        {data.top_news.map((item, index) => (
          <NewsRankRow key={item.id} item={item} index={index} onClick={() => onNewsClick(item.id)} />
        ))}
      </ol>
    )
  }

  if (tab === 'factor') {
    if (!data.hot_factors.length) return <div className="news-ranking-hint">暂无榜单数据</div>
    const maxCount = Math.max(...data.hot_factors.map((f) => f.news_count), 1)
    return (
      <>
        <ol className="news-ranking-list">
          {data.hot_factors.map((factor, index) => (
            <li key={factor.id}>
              <button type="button" className="news-ranking-item" onClick={() => onFactorClick(factor.id)}>
                <span className="news-ranking-copy">
                  <em>{index + 1}</em>
                  <b title={factor.name}>{factor.name}</b>
                  <strong>{factor.news_count}</strong>
                </span>
                <span className="news-ranking-track">
                  <i style={{ width: `${Math.max(4, (factor.news_count / maxCount) * 100)}%` }} />
                </span>
              </button>
            </li>
          ))}
        </ol>
        {data.category_distribution.length > 0 && (
          <div className="news-ranking-categories">
            <h3>类别分布</h3>
            <div className="news-ranking-category-list">
              {data.category_distribution.map((c) => (
                <span key={c.category} className="news-ranking-category">
                  {CATEGORY_LABELS[c.category] || c.category}
                  <b>{(c.share * 100).toFixed(0)}%</b>
                </span>
              ))}
            </div>
          </div>
        )}
      </>
    )
  }

  const { positive, negative } = data.direction_board
  if (!positive.length && !negative.length) return <div className="news-ranking-hint">暂无榜单数据</div>
  return (
    <div className="news-ranking-direction">
      <DirectionGroup title="利多 Top 5" items={positive} onNewsClick={onNewsClick} />
      <DirectionGroup title="利空 Top 5" items={negative} onNewsClick={onNewsClick} />
    </div>
  )
}

const NewsRankRow: React.FC<{ item: RankingNewsItem; index: number; onClick: () => void }> = ({ item, index, onClick }) => (
  <li>
    <button type="button" className="news-ranking-item" onClick={onClick}>
      <span className="news-ranking-copy">
        <em>{index + 1}</em>
        <b title={item.title}>{item.title}</b>
        {item.final_score != null && <strong>{Math.round(item.final_score)}</strong>}
      </span>
      <span className="news-ranking-meta">
        <DirectionBadge direction={item.direction} />
        <time>{fmtTime(item.pub_time)}</time>
      </span>
    </button>
  </li>
)

const DirectionGroup: React.FC<{
  title: string
  items: RankingNewsItem[]
  onNewsClick: (newsId: number) => void
}> = ({ title, items, onNewsClick }) => (
  <div className="news-ranking-direction-group">
    <h3>{title}</h3>
    {items.length === 0 ? (
      <p className="news-ranking-hint">暂无</p>
    ) : (
      <ol className="news-ranking-list">
        {items.map((item, index) => (
          <NewsRankRow key={item.id} item={item} index={index} onClick={() => onNewsClick(item.id)} />
        ))}
      </ol>
    )}
  </div>
)

export default RecommendRankingPanel
