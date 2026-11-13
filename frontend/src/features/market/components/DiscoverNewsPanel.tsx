/**
 * 新闻发现面板 —— 响应式资讯卡片 + 排序/筛选/排行榜。
 * 无限滚动 + IntersectionObserver；排序模式由 URL ?sort= 驱动并与 segmented 双向同步。
 */
import React, { useRef, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useInfiniteQuery } from '@tanstack/react-query'
import { fetchDiscoverNews } from '@/api/market'
import NewsFeedCard from './NewsFeedCard'
import NewsSortSegmented, { readSort } from './NewsSortSegmented'
import RecommendRankingPanel from './RecommendRankingPanel'
import FilterDropdown from './FilterDropdown'
import { Skeleton } from '@/components/ui'
import '../market-news.css'
import '../news-feed-cards.css'

interface Props {
  onNewsClick: (newsId: number) => void
  onFactorClick: (factorId: number) => void
}
const PAGE_SIZE = 20

const DIRECTION_OPTIONS: [string, string][] = [
  ['ALL', '全部方向'],
  ['positive', '利多'],
  ['negative', '利空'],
  ['neutral', '中性'],
]
const SOURCE_OPTIONS: [string, string][] = [
  ['ALL', '全部来源'],
  ['wallstreetcn', '数据源1'],
  ['yicai', '数据源2'],
]
const DAYS_OPTIONS: [string, string][] = [
  ['', '全部时间'],
  ['1', '近 1 天'],
  ['7', '近 7 天'],
  ['30', '近 30 天'],
]

const NewsListSkeleton: React.FC = () => (
  <div className="news-list" aria-busy="true" aria-label="新闻加载中">
    {Array.from({ length: 6 }).map((_, i) => (
      <div key={i} className="news-row-skeleton">
        <div className="news-row-skeleton-top">
          <Skeleton width={72} height={12} variant="rectangular" />
          <Skeleton width={40} height={20} variant="rectangular" />
        </div>
        <div className="news-row-skeleton-main">
          <Skeleton height={17} width="92%" variant="rectangular" />
          <Skeleton height={17} width="68%" variant="rectangular" />
          <Skeleton height={12} variant="rectangular" />
          <Skeleton height={12} width="76%" variant="rectangular" />
        </div>
        <div className="news-row-skeleton-footer">
          <Skeleton width={112} height={20} variant="rectangular" />
          <Skeleton width={48} height={12} variant="rectangular" />
        </div>
      </div>
    ))}
  </div>
)

const DiscoverNewsPanel: React.FC<Props> = ({ onNewsClick, onFactorClick }) => {
  const [searchParams, setSearchParams] = useSearchParams()
  const sort = readSort(searchParams.get('sort'))

  const [direction, setDirection] = useState('ALL')
  const [source, setSource] = useState('ALL')
  const [days, setDays] = useState('')

  // recommend 硬窗口：未选天数时兜底 7 天；latest 模式空串 = 不限窗口
  const effectiveDays = sort === 'recommend' ? Number(days || 7) : days ? Number(days) : undefined
  const queryFilters = {
    sort,
    direction: direction === 'ALL' ? undefined : direction,
    source: source === 'ALL' ? undefined : source,
    days: effectiveDays,
  }

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError, refetch } =
    useInfiniteQuery({
      queryKey: ['discover', 'news', queryFilters],
      queryFn: ({ pageParam = 1 }) =>
        fetchDiscoverNews({ page: pageParam as number, page_size: PAGE_SIZE, ...queryFilters }),
      getNextPageParam: (lp) => (lp.page < lp.total_pages ? lp.page + 1 : undefined),
      initialPageParam: 1, staleTime: 0, refetchOnMount: true,
    })

  const sentinel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = sentinel.current; if (!el) return
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting && hasNextPage && !isFetchingNextPage) fetchNextPage() },
      { rootMargin: '300px' },
    )
    obs.observe(el); return () => obs.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const all = useMemo(() => data?.pages.flatMap((p) => p.items) ?? [], [data])
  const total = data?.pages[0]?.total ?? 0

  const backToLatest = () => {
    const params = new URLSearchParams(searchParams)
    params.delete('sort')
    setSearchParams(params, { replace: true })
  }

  return (
    <div className="news-feed">
      <header className="news-feed-header">
        <div>
          <div className="news-feed-kicker"><span />BOND MARKET · NEWS</div>
          <h1>市场资讯</h1>
          <p>追踪债市要闻，捕捉政策与情绪变化</p>
        </div>
        <div className="news-feed-count" aria-label={`共 ${total} 条资讯`}>
          <strong>{isLoading ? '—' : total}</strong>
          <span>条资讯</span>
        </div>
      </header>

      <div className="news-toolbar">
        <NewsSortSegmented />
        <div className="news-toolbar-filters">
          <FilterDropdown label="方向" value={direction} options={DIRECTION_OPTIONS} onChange={setDirection} />
          <FilterDropdown label="来源" value={source} options={SOURCE_OPTIONS} onChange={setSource} />
          <FilterDropdown label="时间" value={days} options={DAYS_OPTIONS} onChange={setDays} />
        </div>
      </div>

      {sort === 'recommend' && (
        <RecommendRankingPanel days={effectiveDays ?? 7} onNewsClick={onNewsClick} onFactorClick={onFactorClick} />
      )}

      {isLoading ? (
        <NewsListSkeleton />
      ) : isError ? (
        <div className="news-list-state">
          <span>加载失败</span>
          <button type="button" className="btn-secondary" onClick={() => refetch()}>重试</button>
        </div>
      ) : all.length === 0 ? (
        <div className="news-list-state">
          <span>{sort === 'recommend' ? '当前筛选下暂无可推荐新闻' : '暂无新闻数据'}</span>
          {sort === 'recommend' && (
            <button type="button" className="btn-secondary" onClick={backToLatest}>切回时间排序</button>
          )}
        </div>
      ) : (
        <>
          <div className="news-list-heading">
            <h2>{sort === 'recommend' ? '推荐要闻' : '最新发布'}</h2>
            <span>{sort === 'recommend' ? '重要性与时效综合排序' : '按发布时间持续更新'}</span>
          </div>
          <div className="news-list">
            {all.map((item) => (
              <NewsFeedCard
                key={item.id}
                item={item}
                variant={sort === 'recommend' ? 'recommend' : 'latest'}
                onClick={() => onNewsClick(item.id)}
              />
            ))}
            <div ref={sentinel} className="news-list-sentinel">
              {isFetchingNextPage && <div className="news-list-spinner" />}
              {!hasNextPage && all.length > 0 && <span><i />已加载全部新闻<i /></span>}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default DiscoverNewsPanel
