/**
 * 新闻发现面板 — 高密度单列行列表（S3-1）
 * 无限滚动 + IntersectionObserver；排序模式切换在 S3-3 接入（URL ?sort=）
 */
import React, { useRef, useEffect, useMemo } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { fetchDiscoverNews } from '@/api/market'
import NewsListRow from './NewsListRow'
import { Skeleton } from '@/components/ui'
import '../market-news.css'

interface Props { onNewsClick: (newsId: number) => void }
const PAGE_SIZE = 20

const NewsListSkeleton: React.FC = () => (
  <div className="news-list" aria-busy="true" aria-label="新闻加载中">
    {Array.from({ length: 8 }).map((_, i) => (
      <div key={i} className="news-row-skeleton">
        <Skeleton width={88} height={66} variant="rectangular" />
        <div className="news-row-skeleton-main">
          <Skeleton height={13} variant="rectangular" />
          <Skeleton height={11} width="55%" variant="rectangular" />
        </div>
      </div>
    ))}
  </div>
)

const DiscoverNewsPanel: React.FC<Props> = ({ onNewsClick }) => {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError, refetch } =
    useInfiniteQuery({
      queryKey: ['discover', 'news'],
      queryFn: ({ pageParam = 1 }) =>
        fetchDiscoverNews({ page: pageParam as number, page_size: PAGE_SIZE }),
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

  const all = useMemo(() => data?.pages.flatMap(p => p.items) ?? [], [data])

  if (isLoading) return <NewsListSkeleton />
  if (isError) return (
    <div className="news-list-state">
      <span>加载失败</span>
      <button type="button" className="btn-secondary" onClick={() => refetch()}>重试</button>
    </div>
  )
  if (all.length === 0) return <div className="news-list-state">暂无新闻数据</div>

  return (
    <div className="news-list">
      {all.map((item) => (
        <NewsListRow key={item.id} item={item} variant="latest" onClick={() => onNewsClick(item.id)} />
      ))}
      <div ref={sentinel} className="news-list-sentinel">
        {isFetchingNextPage && <div className="news-list-spinner" />}
        {!hasNextPage && all.length > 0 && <span>已加载全部新闻</span>}
      </div>
    </div>
  )
}

export default DiscoverNewsPanel
