/**
 * 收益率详情 — Perplexity Finance 风格
 * 分段红/绿曲线 + 滚轮缩放（不滚动页面）+ hover 坐标 + 竖向时间轴 + 新闻
 */
import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { Loading } from '@/components/UI'
import { API_PREFIX } from '@/api/client'

interface Props { period: string; onClose: () => void; onNewsClick: (newsId: number) => void }

const CH = 220
const G = '#ef4444', R = '#22c55e', GRD = '#2a2a2a', AX = '#6b7280', FG = '#8b949e'

const YieldDetailPanel: React.FC<Props> = ({ period, onClose, onNewsClick }) => {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [hoverIdx, setHoverIdx] = useState(-1)
  const [zoomLevel, setZoomLevel] = useState(1)
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch(`${API_PREFIX}/discover/yield-detail?period=${period}`)
      .then(r => r.json()).then(d => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }, [period])

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', h); return () => document.removeEventListener('keydown', h)
  }, [onClose])

  const zoomWindows = [30, 14, 7, 3]
  const zoomWindow = zoomWindows[zoomLevel]

  const handleZoom = useCallback((level: number) => { setHoverIdx(-1); setZoomLevel(level) }, [])

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setHoverIdx(-1)
    setZoomLevel(prev => e.deltaY > 0 ? Math.max(0, prev - 1) : Math.min(3, prev + 1))
  }, [])

  const { slicedVals, slicedDates } = useMemo(() => {
    if (!data) return { slicedVals: [] as number[], slicedDates: [] as string[] }
    const allV = [...(data.sparkline?.values || [])]
    const allD = [...(data.sparkline?.dates || [])]
    if (!allV.length) return { slicedVals: [] as number[], slicedDates: [] as string[] }
    const n = Math.min(zoomWindow, allV.length)
    return { slicedVals: allV.slice(allV.length - n), slicedDates: allD.slice(allD.length - n) }
  }, [data, zoomWindow])

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!chartRef.current || !slicedVals.length) return
    const rect = chartRef.current.getBoundingClientRect()
    const mx = e.clientX - rect.left, w = rect.width || 1, n = slicedVals.length
    setHoverIdx(Math.max(0, Math.min(n - 1, Math.round((mx / w) * (n - 1)))))
  }, [slicedVals])

  if (loading) return <div className="absolute inset-0 z-30 bg-[#0d0d0d] flex items-center justify-center"><Loading text="加载中..." /></div>
  if (!data || !slicedVals.length) return <div className="absolute inset-0 z-30 bg-[#0d0d0d] flex items-center justify-center text-[#8b949e] text-sm">无数据</div>

  const vals = slicedVals, dts = slicedDates, nv = vals.length
  const yMin = Math.min(...vals), yMax = Math.max(...vals), yRng = yMax - yMin || 0.01
  const dir = data.direction || 'flat'
  const lc = dir === 'up' ? G : dir === 'down' ? R : AX
  const dArrow = dir === 'up' ? '↑' : dir === 'down' ? '↓' : '→'
  const dCol = dir === 'up' ? 'text-[#ef4444]' : dir === 'down' ? 'text-[#22c55e]' : 'text-[#6b7280]'

  const sw = 680, pl = 46, pr = 4, pt = 14, pb = 28
  const pw = sw - pl - pr, ph = CH - pt - pb
  const tx = (i: number) => pl + (i / Math.max(nv - 1, 1)) * pw
  const ty = (v: number) => pt + ph - ((v - yMin) / yRng) * ph

  let grid = ''
  for (let i = 0; i <= 4; i++) {
    const y = pt + (i / 4) * ph
    grid += `<line x1="${pl}" x2="${pl + pw}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${GRD}" stroke-width="0.5" opacity="0.6"/>`
    grid += `<text x="${pl - 6}" y="${y + 4}" fill="${AX}" font-size="10" text-anchor="end" font-family="monospace">${(yMax - (i / 4) * yRng).toFixed(3)}</text>`
  }
  let xl = ''
  for (let i = 0; i < nv; i += Math.max(1, Math.floor(nv / 6))) xl += `<text x="${tx(i).toFixed(1)}" y="${pt + ph + 16}" fill="${FG}" font-size="10" text-anchor="middle">${dts[i]}</text>`

  const areaPts = [ `${tx(0).toFixed(1)},${pt + ph}` ]
  for (let i = 0; i < nv; i++) areaPts.push(`${tx(i).toFixed(1)},${ty(vals[i]).toFixed(1)}`)
  areaPts.push(`${tx(nv - 1).toFixed(1)},${pt + ph}`)

  let segs = ''
  for (let i = 0; i < nv - 1; i++) segs += `<line x1="${tx(i).toFixed(1)}" y1="${ty(vals[i]).toFixed(1)}" x2="${tx(i + 1).toFixed(1)}" y2="${ty(vals[i + 1]).toFixed(1)}" stroke="${vals[i+1] >= vals[i] ? G : R}" stroke-width="1.8" stroke-linecap="round" shape-rendering="geometricPrecision"/>`

  const gid = `g${Math.random().toString(36).slice(2, 6)}`
  let hoverEl = ''
  if (hoverIdx >= 0 && hoverIdx < nv) {
    const hx = tx(hoverIdx).toFixed(1), hy = ty(vals[hoverIdx]).toFixed(1)
    hoverEl = `<line x1="${hx}" x2="${hx}" y1="${pt}" y2="${pt+ph}" stroke="white" stroke-width="0.8" opacity="0.5"/><circle cx="${hx}" cy="${hy}" r="4" fill="white" stroke="${lc}" stroke-width="2"/>`
  }

  let chartSvg = ''
  try {
    chartSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="${sw}" height="${CH}" viewBox="0 0 ${sw} ${CH}"><defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${lc}" stop-opacity="0.15"/><stop offset="100%" stop-color="${lc}" stop-opacity="0.02"/></linearGradient></defs>${grid}${xl}<polygon points="${areaPts.join(' ')}" fill="url(#${gid})"/>${segs}<line x1="${pl}" x2="${pl+pw}" y1="${ty(data.value)}" y2="${ty(data.value)}" stroke="${AX}" stroke-width="0.7" stroke-dasharray="4 3" opacity="0.4"/>${hoverEl}</svg>`
  } catch(e) { chartSvg = '' }

  const m1 = (data.key_metrics || []).slice(0, 3)
  const m2 = (data.key_metrics || []).slice(3, 6)
  const safeHI = (hoverIdx >= 0 && hoverIdx < nv) ? hoverIdx : -1
  const sigDates = data.significant_dates || []

  return (
    <div className="absolute inset-0 z-30 bg-[#0d0d0d] overflow-y-auto">
      <div className="sticky top-0 z-10 flex items-center justify-between px-4 py-2.5 bg-[#0d0d0d]/95 backdrop-blur-sm border-b border-[#1f1f1f]">
        <button onClick={onClose} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[13px] text-[#8b949e] hover:text-white hover:bg-[#1a1a1a]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 12H5m0 0l7 7m-7-7l7-7"/></svg>返回
        </button>
        <div className="flex items-center gap-1">
          {zoomWindows.map((d, i) => (
            <button key={d} onClick={() => handleZoom(i)} className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${zoomLevel === i ? 'bg-white/10 text-white' : 'text-[#6b7280] hover:text-white'}`}>{d}D</button>
          ))}
        </div>
      </div>

      <div className="mx-auto w-full px-4 md:px-6 pb-16" style={{ maxWidth: '1060px' }}>
        <div className="space-y-5 pt-5">
          {/* Price Header */}
          <div>
            <div className="flex items-baseline gap-4">
              <span className="text-[2.8rem] font-mono font-semibold text-white tracking-tight leading-none">{data.value?.toFixed(3)}<span className="text-[1.4rem] text-[#6b7280]">%</span></span>
              <span className={`flex items-center gap-1 text-[15px] font-mono font-medium ${dCol}`}><span>{dArrow}</span>{(data.diff_bp ?? 0) > 0 ? '+' : ''}{data.diff_bp}BP</span>
            </div>
            <div className="text-[12px] text-[#6b7280] mt-1">收盘：{data.update_date} · {data.label} · 滚轮缩放</div>
          </div>

          {/* Chart */}
          <div className="relative detail-card overflow-hidden"
            ref={chartRef} onMouseMove={onMouseMove} onMouseLeave={() => setHoverIdx(-1)} onWheel={onWheel}>
            <div className="w-full overflow-hidden">
              <div className="min-w-full" dangerouslySetInnerHTML={{ __html: chartSvg }} /><div style={{ width: '100%', minWidth: sw }} />
            </div>
            {safeHI >= 0 && (
              <div className="absolute pointer-events-none z-20 px-2.5 py-1.5 rounded-lg bg-[#1a1a1a]/95 border border-[#3a3a3a] text-white text-[12px] font-mono shadow-lg"
                style={{ left: Math.min(12 + (safeHI / Math.max(nv - 1, 1)) * 620, 560), top: 6 }}>
                <span className="text-[#8b949e]">{dts[safeHI]}</span><span className="ml-2 font-semibold">{vals[safeHI].toFixed(3)}%</span>
              </div>
            )}
          </div>

          {/* Metrics */}
          <div className="detail-card overflow-hidden">
            <div className="grid grid-cols-3 gap-px bg-[#1f1f1f]">
              {m1.map((m: any) => (<div key={m.label} className="bg-[#111111] px-4 py-4"><div className="text-sm text-[#6b7280]">{m.label}</div><div className="text-base font-mono font-semibold text-white mt-1">{m.value}</div></div>))}
            </div>
            {m2.length > 0 && (
              <div className="grid grid-cols-3 gap-px bg-[#1f1f1f] border-t border-[#1f1f1f]">
                {m2.map((m: any) => (<div key={m.label} className="bg-[#111111] px-4 py-4"><div className="text-sm text-[#6b7280]">{m.label}</div><div className="text-base font-mono font-semibold text-white mt-1">{m.value}</div></div>))}
              </div>
            )}
          </div>

          {/* Significant Dates — Perplexity Timeline Style */}
          {sigDates.length > 0 && (
            <div>
              <h3 className="text-lg font-bold text-white mb-4">显著价格变动</h3>
              <div className="relative detail-card overflow-hidden">
                <div className="divide-y divide-[#1f1f1f]">
                  {sigDates.map((sd: any, idx: number) => {
                    const up = sd.direction === 'up'
                    const hasNews = (sd.news || []).length > 0
                    return (
                      <div key={sd.date} className="relative">
                        {/* Vertical timeline connector */}
                        {idx < sigDates.length - 1 && (
                          <div className="absolute left-[27px] top-10 bottom-0 w-px bg-[#2a2a2a]" />
                        )}
                        <div className="p-4">
                          {/* Date + price row */}
                          <div className="flex items-center gap-3 mb-2">
                            <span className={`relative z-10 w-2.5 h-2.5 rounded-full border-2 ${up ? 'border-[#ef4444] bg-[#ef4444]' : 'border-[#22c55e] bg-[#22c55e]'} ${sd.news?.length ? 'ring-2 ring-offset-2 ring-offset-[#111111] ' + (up ? 'ring-[#ef4444]/30' : 'ring-[#22c55e]/30') : ''}`} />
                            <span className="text-[13px] text-white font-medium">{sd.date}</span>
                            <span className={`text-[13px] font-mono font-semibold ${up ? 'text-[#ef4444]' : 'text-[#22c55e]'}`}>
                              {up ? '↑' : '↓'} {Math.abs(sd.diff_bp).toFixed(1)}BP
                            </span>
                          </div>
                          {/* News cards */}
                          {hasNews ? (
                            <div className="ml-6 space-y-2">
                              {(sd.news || []).map((n: any) => (
                                <div key={n.id} onClick={(e) => { e.stopPropagation(); onNewsClick(n.id) }}
                                  className="rounded-lg bg-[#0a0a0a] border border-[#1f1f1f] p-3 hover:bg-[#151515] hover:border-[#2a2a2a] transition-colors cursor-pointer">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${n.direction === 'positive' ? 'bg-[#ef4444]' : 'bg-[#22c55e]'}`} />
                                    <span className="text-[13px] text-[#e0e0e0] leading-snug">{n.title}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="ml-6 text-[11px] text-[#6b7280] italic">当日无显著方向性新闻</div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default YieldDetailPanel
