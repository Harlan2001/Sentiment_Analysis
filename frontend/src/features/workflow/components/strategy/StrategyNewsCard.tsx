import type { StrategyNewsReference } from './useStrategyWizard'

export function StrategyNewsCard({ news, onOpen }: {
  news: StrategyNewsReference
  onOpen: (newsId: number) => void
}) {
  const newsId = Number(news.news_id || news.id || 0)
  const title = String(news.title || '未命名新闻')
  const meta = [news.source, news.publish_time || news.pub_time].filter(Boolean).join(' · ')
  const description = String(news.reason || '')

  return (
    <button type="button" className="sw-news-card" onClick={() => newsId > 0 && onOpen(newsId)} disabled={!newsId}>
      <span className="sw-news-copy">
        <strong>{title}</strong>
        <small>{meta || '来源信息暂缺'}</small>
        {description && <p>{description}</p>}
      </span>
      <span className="sw-news-link">查看详情 →</span>
    </button>
  )
}
