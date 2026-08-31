/**
 * 新闻详情 — Perplexity 风格，absolute 覆盖新闻+收益率区域
 */
import React, { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchNewsById, fetchNewsYieldData, fetchSimilarNews } from '@/api/market'
import NewsContentBlocks from '@/components/news/NewsContentBlocks'
import { Loading } from '@/components/UI'
import { WatchlistAction } from './WatchlistAction'

interface Props { newsId: number; onClose: () => void; onNewsClick: (newsId: number) => void; closeLabel?: string }

const POLICY_DEMO_NEWS_IDS = new Set([18157, 18174, 18176, 18197, 18224, 18225, 18313, 18340, 18349])
const POLICY_DEMO_START = '2026-09-03'
const POLICY_DEMO_END = '2026-09-09'

function formatDateTime(value?: string) {
  if (!value) return '时间未知'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(parsed)
}

const NewsDetailPanel: React.FC<Props> = ({ newsId, onClose, onNewsClick, closeLabel = '返回发现页' }) => {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [onClose])

  const { data: detail, isLoading } = useQuery({
    queryKey: ['news', 'detail', newsId],
    queryFn: () => fetchNewsById(newsId),
    staleTime: 0,
  })

  const { data: yieldData } = useQuery({
    queryKey: ['news', 'yield', newsId],
    queryFn: () => fetchNewsYieldData(newsId, '10年', 10, 10),
    staleTime: 0,
  })

  const { data: similar } = useQuery({
    queryKey: ['news', 'similar', newsId],
    queryFn: () => fetchSimilarNews(newsId),
    staleTime: 0,
  })

  const dirLabel = detail?.direction === 'positive' ? '利多债市' :
    detail?.direction === 'negative' ? '利空债市' : '中性'
  const dirColor = detail?.direction === 'positive' ? 'text-[#ef4444]' :
    detail?.direction === 'negative' ? 'text-[#22c55e]' : 'text-[#6b7280]'
  const visibleYieldData = (yieldData?.data ?? [])
    .filter((point: any) => !POLICY_DEMO_NEWS_IDS.has(newsId) || (point.date >= POLICY_DEMO_START && point.date <= POLICY_DEMO_END))
    .slice(0, 10)

  return (
    <div className="absolute inset-0 z-30 bg-[#0d0d0d] overflow-y-auto">
      {/* 顶部栏 */}
      <div className="sticky top-0 z-10 flex items-center px-4 py-3 bg-[#0d0d0d]/95 backdrop-blur-sm border-b border-[#1f1f1f]">
        <button onClick={onClose}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#2a2a2a] text-[13px] text-[#8b949e] hover:text-white hover:border-[#3a3a3a] hover:bg-[#1a1a1a] transition-colors">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 12H5m0 0l7 7m-7-7l7-7"/></svg>
          {closeLabel}
        </button>
      </div>

      <div className="mx-auto w-full px-4 md:px-6 pb-16" style={{ maxWidth: '1060px' }}>
        {isLoading ? (
          <div className="py-20"><Loading text="加载中..." /></div>
        ) : detail ? (
          <div className="space-y-6 pt-4">
            {/* 标题 */}
            <h1 className="font-serif text-[2rem] md:text-[2.5rem] leading-[1.3] font-semibold text-white">{detail.title}</h1>

            {/* 元信息 */}
            <div className="flex items-center gap-3 text-[13px] text-[#8b949e]">
              <span>{detail.source}</span>
              <span>·</span>
              <span>{formatDateTime(detail.publish_time)}</span>
              <div className="ml-auto flex items-center gap-2"><WatchlistAction objectType="news" objectId={String(detail.id)} title={detail.title} sourceUrl={`/news/${detail.id}`} /><span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${dirColor} ${dirColor === 'text-[#ef4444]' ? 'bg-[#ef4444]/15' : dirColor === 'text-[#22c55e]' ? 'bg-[#22c55e]/15' : 'bg-[#6b7280]/15'}`}>AI：{dirLabel}</span></div>
            </div>

            {/* 新闻总结与债市影响 */}
            {detail.reason && (
              <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-5">
                <div className="text-[11px] font-medium text-[#6b7280] uppercase tracking-wide mb-3">新闻总结与债市影响</div>
                <div className="border-l-2 border-[#f59e0b] pl-4">
                  <p className={`text-[14px] font-semibold mb-2 ${dirColor}`}>{dirLabel} · {detail.horizon || '短期'}</p>
                  <p className="text-[13px] text-[#8b949e] leading-relaxed">{detail.reason}</p>
                </div>
                <div className="mt-4 grid grid-cols-1 gap-2 border-t border-[#252525] pt-4 text-[12px] md:grid-cols-3">
                  <div className="rounded-lg bg-[#171717] px-3 py-2.5"><span className="block text-[10px] text-[#666]">判断对象</span><strong className="mt-1 block font-medium text-[#c9c9c9]">中国国债价格与收益率</strong></div>
                  <div className="rounded-lg bg-[#171717] px-3 py-2.5"><span className="block text-[10px] text-[#666]">影响方向</span><strong className={`mt-1 block font-medium ${dirColor}`}>{dirLabel}</strong></div>
                  <div className="rounded-lg bg-[#171717] px-3 py-2.5"><span className="block text-[10px] text-[#666]">主要期限</span><strong className="mt-1 block font-medium text-[#c9c9c9]">{detail.horizon || '短期'}</strong></div>
                </div>
              </div>
            )}

            {/* 关联因子与传导明细 */}
            {detail.factors && detail.factors.length > 0 && (
              <div className="rounded-xl border border-[#2a2a2a] bg-[#111111] p-5">
                <div className="mb-3 text-[11px] font-medium uppercase tracking-wide text-[#6b7280]">因子传导明细</div>
                <p className="mb-4 text-[12px] leading-relaxed text-[#777]">以下因子展示这条新闻从政策或事件触发，经由经济变量变化，最终影响国债收益率的具体路径。</p>
                <div className="grid gap-2">
                  {detail.factors.map((f: any) => {
                    const factorDirection = f.direction === 'positive' ? '利多' : f.direction === 'negative' ? '利空' : '中性'
                    const factorColor = f.direction === 'positive' ? 'text-[#ef4444]' : f.direction === 'negative' ? 'text-[#22c55e]' : 'text-[#8b949e]'
                    return (
                      <div key={f.code} className="rounded-lg border border-[#252525] bg-[#161616] px-3.5 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="text-[12px] font-medium text-[#d6d6d6]">{f.name || f.code}</strong>
                          <span className="rounded border border-[#333] px-1.5 py-0.5 text-[9px] text-[#777]">{f.category || 'OTHER'}</span>
                          <span className={`ml-auto text-[10px] ${factorColor}`}>{factorDirection}</span>
                        </div>
                        {f.driver && <p className="mt-2 text-[11px] leading-relaxed text-[#858585]">{f.driver}</p>}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* 新闻正文（含图片，不单独渲染封面图避免重复） */}
            {detail.content_blocks && detail.content_blocks.length > 0 && (
              <div className="py-2">
                <NewsContentBlocks blocks={detail.content_blocks!} />
              </div>
            )}

            {/* 收益率 */}
            {visibleYieldData.length > 0 && (
              <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-5">
                <div className="text-[11px] font-medium text-[#6b7280] uppercase tracking-wide mb-3">近期收益率</div>
                <div className="flex flex-wrap gap-2">
                  {visibleYieldData.map((pt: any) => (
                    <div key={pt.date} className="px-3 py-1.5 rounded-lg bg-[#1a1a1a] text-[12px] border border-[#1f1f1f]">
                      <span className="text-[#6b7280]">{pt.date}</span>
                      <span className="font-mono text-white ml-2">{pt.value}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 发现更多 — 始终显示区域 */}
            <div className="pt-6 border-t border-[#1f1f1f]">
              <div className="text-lg font-bold text-white mb-4">发现更多</div>
              {similar && similar.length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {(similar ?? []).slice(0, 4).map((s: any) => {
                    const domain = s.title?.match(/^[\w.]+/)?.[0] || ''
                    return (
                      <div key={s.news_id}
                        onClick={() => onNewsClick(s.news_id)}
                        className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-4 hover:bg-[#1a1a1a] transition-colors cursor-pointer flex flex-col gap-2">
                        <div className="flex items-center gap-1.5">
                          <div className="relative shrink-0 overflow-hidden rounded-full w-5 h-5 bg-white">
                            <img src={`https://www.google.com/s2/favicons?sz=32&domain=${domain}.com`} alt="" className="w-5 h-5 block" />
                          </div>
                          <span className="text-xs text-[#8b949e] truncate">{domain}</span>
                        </div>
                        <div className="text-sm text-[#e0e0e0] line-clamp-3 leading-snug">{s.title}</div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="text-center text-[11px] text-[#6b7280] py-4">相似新闻加载中或暂无数据（需 FAISS 向量库支持）</div>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center text-[#8b949e] text-sm py-20">新闻数据不可用</div>
        )}
      </div>
    </div>
  )
}

export default NewsDetailPanel
