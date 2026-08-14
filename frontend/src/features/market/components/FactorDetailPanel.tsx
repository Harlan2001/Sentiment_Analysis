/**
 * 因子详情 — Perplexity 风格
 * 7日趋势精密柱状图 + 关联新闻 + 相关因子
 */
import React, { useEffect, useState } from 'react'
import { Loading } from '@/components/UI'
import { API_PREFIX } from '@/api/client'

interface Props { factorId: number; onClose: () => void; onNewsClick: (newsId: number) => void }

const FactorDetailPanel: React.FC<Props> = ({ factorId, onClose, onNewsClick }) => {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_PREFIX}/discover/factor-detail?factor_id=${factorId}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [factorId])

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', h); return () => document.removeEventListener('keydown', h)
  }, [onClose])

  if (loading) return (
    <div className="absolute inset-0 z-30 bg-[#0d0d0d] flex items-center justify-center"><Loading text="加载中..." /></div>
  )
  if (!data) return (
    <div className="absolute inset-0 z-30 bg-[#0d0d0d] flex items-center justify-center text-[#8b949e] text-sm">因子数据不可用</div>
  )

  const counts: number[] = (data.daily_counts || []).map((d: any) => d.count)
  const days: string[] = (data.daily_counts || []).map((d: any) => d.date.slice(5))
  const cMin = 0, cMax = Math.max(...counts, 1)
  // 缩小 Y 轴范围：使用 0 到最大值*1.15，确保柱子有视觉差异
  const cRange = cMax * 1.15 - cMin || 1

  // 构建柱状图 SVG
  const sw = 600, sh = 140, pl = 32, pr = 8, pt = 12, pb = 24
  const cw = sw - pl - pr, ch = sh - pt - pb
  const barW = Math.max(8, (cw / counts.length) * 0.55)
  const gap = cw / counts.length

  let bars = ''
  counts.forEach((c, i) => {
    const bx = pl + i * gap + (gap - barW) / 2
    const h = Math.max(2, (c / cRange) * ch)
    const by = pt + ch - h
    const alpha = c / cMax
    const color = alpha > 0.6 ? '#f59e0b' : alpha > 0.3 ? '#d97706' : '#b45309'
    bars += `<rect x="${bx.toFixed(1)}" y="${by.toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" rx="3" fill="${color}" fill-opacity="${(0.4 + alpha * 0.6).toFixed(2)}"/>`
    bars += `<text x="${(bx + barW / 2).toFixed(1)}" y="${pt + ch + 15}" fill="#8b949e" font-size="11" text-anchor="middle">${days[i]}</text>`
    bars += `<text x="${(bx + barW / 2).toFixed(1)}" y="${by - 4}" fill="#fde68a" font-size="11" text-anchor="middle">${c}</text>`
  })

  // Y axis labels
  let yLabels = ''
  for (let i = 0; i <= 3; i++) {
    const v = Math.round((i / 3) * cMax)
    const y = pt + ch - (i / 3) * ch
    yLabels += `<text x="${pl - 6}" y="${y + 3}" fill="#6b7280" font-size="9" text-anchor="end">${v}</text>`
  }

  const chartSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="${sw}" height="${sh}" viewBox="0 0 ${sw} ${sh}">` +
    `<line x1="${pl}" x2="${pl + cw}" y1="${pt + ch}" y2="${pt + ch}" stroke="#2a2a2a" stroke-width="0.8"/>` +
    yLabels + bars +
    `</svg>`

  return (
    <div className="absolute inset-0 z-30 bg-[#0d0d0d] overflow-y-auto">
      <div className="sticky top-0 z-10 flex items-center px-4 py-2.5 bg-[#0d0d0d]/95 backdrop-blur-sm border-b border-[#1f1f1f]">
        <button onClick={onClose} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[13px] text-[#8b949e] hover:text-white hover:bg-[#1a1a1a]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 12H5m0 0l7 7m-7-7l7-7"/></svg>
          返回
        </button>
      </div>

      <div className="mx-auto w-full px-4 md:px-6 pb-16" style={{ maxWidth: '1060px' }}>
        <div className="space-y-5 pt-5">
          {/* Header */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              {data.category ? (
                <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-[#1a1a1a] text-[#8b949e] border border-[#2a2a2a]">{data.category}</span>
              ) : null}
            </div>
            <h1 className="text-2xl font-bold text-white">{data.name}</h1>
            <div className="flex items-center gap-5 mt-2 text-sm text-[#8b949e]">
              <span>7日新闻数 <span className="text-white font-mono font-medium">{data.news_count}</span></span>
              <span>活跃度 <span className="text-white font-mono font-medium">{(data.activity_score * 100).toFixed(0)}%</span></span>
            </div>
          </div>

          {/* 7-day bar chart */}
          {counts.length > 0 && (
            <div className="detail-card">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 rounded-full bg-[#f59e0b]" />
                <span className="text-[12px] font-medium text-[#6b7280] uppercase tracking-wide">7日活跃度趋势</span>
              </div>
              <div className="w-full overflow-hidden rounded-lg bg-[#0a0a0a] p-3 pt-4">
                <div className="min-w-full" dangerouslySetInnerHTML={{ __html: chartSvg }} />
                <div style={{ width: '100%', minWidth: sw }} />
              </div>
            </div>
          )}

          {/* Related News */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-4 rounded-full bg-[#ef4444]" />
              <span className="text-[12px] font-medium text-[#6b7280] uppercase tracking-wide">关联新闻 ({data.related_news?.length || 0})</span>
            </div>
            <div className="space-y-2">
              {data.related_news?.map((n: any) => {
                const dirCls = n.direction === 'positive' ? 'border-l-[#ef4444]' : n.direction === 'negative' ? 'border-l-[#22c55e]' : 'border-l-[#6b7280]'
                const dirLabel = n.direction === 'positive' ? '利多' : n.direction === 'negative' ? '利空' : '中性'
                const dirStyle = n.direction === 'positive' ? 'bg-[#ef4444]/15 text-[#ef4444]' : n.direction === 'negative' ? 'bg-[#22c55e]/15 text-[#22c55e]' : 'bg-[#6b7280]/15 text-[#6b7280]'
                return (
                  <div key={n.id} onClick={() => onNewsClick(n.id)}
                    className={`rounded-xl bg-[#111111] border border-[#2a2a2a] border-l-2 ${dirCls} p-4 hover:bg-[#1a1a1a] transition-colors cursor-pointer`}>
                    <div className="flex items-center gap-2 text-[11px] text-[#6b7280] mb-1.5">
                      <span>{n.pub_time}</span>
                      {n.direction ? <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${dirStyle}`}>{dirLabel}</span> : null}
                    </div>
                    <div className="text-[13px] text-[#e0e0e0] leading-snug font-medium">{n.title}</div>
                    {n.reason ? <div className="text-[11px] text-[#8b949e] mt-1.5 line-clamp-2 leading-relaxed">{n.reason}</div> : null}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Related Factors */}
          {data.related_factors?.length > 0 && (
            <div className="detail-card">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 rounded-full bg-[#f59e0b]" />
                <span className="text-[12px] font-medium text-[#6b7280] uppercase tracking-wide">相关因子</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {data.related_factors.map((f: any) => (
                  <span key={f.id} className="px-3 py-1.5 rounded-lg text-[12px] bg-[#0a0a0a] text-[#e0e0e0] border border-[#1f1f1f]">{f.name}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default FactorDetailPanel
