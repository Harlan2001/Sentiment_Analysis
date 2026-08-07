/**
 * 新闻详情 — Perplexity 风格，absolute 覆盖新闻+收益率区域
 */
import React, { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchNewsById, fetchNewsYieldData, fetchSimilarNews } from '@/api'
import NewsContentBlocks from '@/components/Pages/NewsContentBlocks'
import { Loading } from '@/components/UI'

interface Props { newsId: number; onClose: () => void; onNewsClick: (newsId: number) => void }

const NewsDetailPanel: React.FC<Props> = ({ newsId, onClose, onNewsClick }) => {
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
  const dirColor = detail?.direction === 'positive' ? 'text-[#22c55e]' :
    detail?.direction === 'negative' ? 'text-[#ef4444]' : 'text-[#6b7280]'

  return (
    <div className="absolute inset-0 z-30 bg-[#0d0d0d] overflow-y-auto">
      {/* 顶部栏 */}
      <div className="sticky top-0 z-10 flex items-center px-4 py-3 bg-[#0d0d0d]/95 backdrop-blur-sm border-b border-[#1f1f1f]">
        <button onClick={onClose}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#2a2a2a] text-[13px] text-[#8b949e] hover:text-white hover:border-[#3a3a3a] hover:bg-[#1a1a1a] transition-colors">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 12H5m0 0l7 7m-7-7l7-7"/></svg>
          返回发现页
        </button>
      </div>

      <div className="mx-auto w-full px-4 md:px-6 pb-16" style={{ maxWidth: '720px' }}>
        {isLoading ? (
          <div className="py-20"><Loading text="加载中..." /></div>
        ) : detail ? (
          <div className="space-y-6 pt-4">
            {/* 标题 */}
            <h1 className="font-serif text-[1.8rem] md:text-[2.3rem] leading-[1.3] font-normal text-white">{detail.title}</h1>

            {/* 元信息 */}
            <div className="flex items-center gap-3 text-[13px] text-[#8b949e]">
              <span>{detail.source}</span>
              <span>·</span>
              <span>{detail.publish_time}</span>
              <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ml-auto ${dirColor} ${dirColor === 'text-[#22c55e]' ? 'bg-[#22c55e]/15' : dirColor === 'text-[#ef4444]' ? 'bg-[#ef4444]/15' : 'bg-[#6b7280]/15'}`}>AI：{dirLabel}</span>
            </div>

            {/* AI 分析 */}
            {detail.reason && (
              <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-5">
                <div className="text-[11px] font-medium text-[#6b7280] uppercase tracking-wide mb-3">AI 分析</div>
                <div className="border-l-2 border-[#8b5cf6] pl-4">
                  <p className={`text-[14px] font-semibold mb-2 ${dirColor}`}>{dirLabel} · {detail.horizon || '短期'}</p>
                  <p className="text-[13px] text-[#8b949e] leading-relaxed">{detail.reason}</p>
                </div>
              </div>
            )}

            {/* 关联因子 */}
            {detail.factors && detail.factors.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {detail.factors.map((f: any) => (
                  <span key={f.code} className="px-3 py-1.5 rounded-lg text-[12px] bg-[#1a1a1a] text-[#8b949e] border border-[#2a2a2a]">{f.name || f.code}</span>
                ))}
              </div>
            )}

            {/* 新闻正文（含图片，不单独渲染封面图避免重复） */}
            {detail.content_blocks && detail.content_blocks.length > 0 && (
              <div className="py-2">
                <NewsContentBlocks blocks={detail.content_blocks!} />
              </div>
            )}

            {/* 收益率 */}
            {yieldData?.data && yieldData.data.length > 0 && (
              <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-5">
                <div className="text-[11px] font-medium text-[#6b7280] uppercase tracking-wide mb-3">近期收益率</div>
                <div className="flex flex-wrap gap-2">
                  {(yieldData.data ?? []).slice(0, 10).map((pt: any) => (
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
              <div className="text-[16px] font-bold text-white mb-4">发现更多</div>
              {similar && similar.length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {(similar ?? []).slice(0, 4).map((s: any) => {
                    const domain = s.title?.match(/^[\w.]+/)?.[0] || ''
                    return (
                      <div key={s.news_id}
                        onClick={() => onNewsClick(s.news_id)}
                        className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-3 hover:bg-[#1a1a1a] transition-colors cursor-pointer flex flex-col gap-1">
                        <div className="flex items-center gap-1.5">
                          <div className="relative shrink-0 overflow-hidden rounded-full w-4 h-4 bg-white">
                            <img src={`https://www.google.com/s2/favicons?sz=32&domain=${domain}.com`} alt="" className="w-4 h-4 block" />
                          </div>
                          <span className="text-[10px] text-[#8b949e] truncate">{domain}</span>
                        </div>
                        <div className="text-[12px] text-[#e0e0e0] line-clamp-3 leading-snug">{s.title}</div>
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
