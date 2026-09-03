/**
 * 新闻发现面板 — Perplexity 风格错落有致布局
 * 每组 = 1大窗口(整行) + 2行[中窗口+小窗口]，去掉多余小窗口行
 */
import React, { useRef, useEffect, useMemo } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { fetchDiscoverNews } from '@/api/market'
import NewsCardLarge from './NewsCardLarge'
import NewsCardSmall from './NewsCardSmall'
import { Skeleton } from '@/components/UI'

interface Props { onNewsClick: (newsId: number) => void }
const PAGE_SIZE = 20

const DiscoverNewsPanel: React.FC<Props> = ({ onNewsClick }) => {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } =
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
  const withImg = useMemo(() => all.filter(it => it.thumbnail), [all])
  const withoutImg = useMemo(() => all.filter(it => !it.thumbnail), [all])

  if (isLoading) return <div className="p-4 space-y-3"><Skeleton height="240px" variant="rectangular" /><div className="grid grid-cols-2 gap-3">{Array.from({length:4}).map((_,i)=><Skeleton key={i} height="120px" variant="rectangular"/>)}</div></div>
  if (isError) return <div className="flex items-center justify-center h-64 text-[#8b949e] text-sm">加载失败</div>
  if (all.length === 0) return <div className="flex items-center justify-center h-64 text-[#8b949e] text-sm">暂无新闻数据</div>

  const rows: React.ReactNode[] = []
  let wi = 0, ni = 0, flip = false

  while (wi < withImg.length) {
    // 大窗口（整行）
    const large = withImg[wi++]
    rows.push(<NewsCardLarge key={large.id} item={large} onClick={() => onNewsClick(large.id)} />)

    // 大窗口下配2行[中窗口+小窗口]
    for (let r = 0; r < 2 && wi < withImg.length; r++) {
      const medium = withImg[wi++]
      const smalls = withoutImg.slice(ni, ni + 2)
      ni += smalls.length

      const mediumCard = (
        <NewsCardLarge key={medium.id} item={medium} onClick={() => onNewsClick(medium.id)} compact />
      )
      const smallsCol = (
        <div className="flex flex-col gap-3">
          {smalls.map(s => (
            <NewsCardSmall key={s.id} item={s} onClick={() => onNewsClick(s.id)} />
          ))}
          {smalls.length < 2 && <div className="flex-1" />}
        </div>
      )

      rows.push(
        <div key={`row-${medium.id}`} className="grid grid-cols-2 gap-3">
          {flip ? smallsCol : mediumCard}
          {flip ? mediumCard : smallsCol}
        </div>,
      )
      flip = !flip
    }
  }

  // 剩余无图小窗口
  const remaining = withoutImg.slice(ni)
  if (remaining.length > 0) {
    for (let i = 0; i < remaining.length; i += 2) {
      rows.push(
        <div key={`rem-${i}`} className="grid grid-cols-2 gap-3">
          {remaining.slice(i, i + 2).map(s => (
            <NewsCardSmall key={s.id} item={s} onClick={() => onNewsClick(s.id)} />
          ))}
        </div>,
      )
    }
  }

  return (
    <div className="p-4 space-y-3">
      {rows}
      <div ref={sentinel} className="flex justify-center py-4">
        {isFetchingNextPage && <div className="w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />}
        {!hasNextPage && all.length > 0 && <span className="text-sm text-[#8b949e]">已加载全部新闻</span>}
      </div>
    </div>
  )
}

export default DiscoverNewsPanel
