/**
 * 因子信号中心 — 因子库 + 宏观指标
 */
import React, { useCallback, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAllFactors, fetchFactorsPage, fetchMacroIndicators, fetchMacroData } from '@/api'
import { Skeleton } from '@/components/UI'

const PAGE_SIZE = 20
const FACTOR_CATEGORIES = ['货币流动性', '政策监管', '经济增长', '债券供需', '情绪风险'] as const
const MACRO_DOMAINS = [
  { key: 'price', label: '通胀与价格' },
  { key: 'real', label: '实体景气' },
  { key: 'real_estate', label: '房地产' },
  { key: 'trade', label: '进出口' },
  { key: 'fiscal', label: '财政' },
  { key: 'industry', label: '产业' },
]

/** 迷你趋势sparkline */
function MiniSpark({ values, height }: { values: number[]; height?: number }) {
  const h = height || 28
  const w = 92
  if (!values.length) return <div style={{ width: w, height: h }} />
  const max = Math.max(...values)
  const min = Math.min(...values)
  const rng = max - min || 1
  const pts = values.map((v, i) => `${(i / Math.max(values.length - 1, 1) * w).toFixed(1)},${(h - ((v - min) / rng) * (h - 4) - 2).toFixed(1)}`).join(' ')
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="factor-trend-mini" aria-hidden="true">
      <polyline points={pts} fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/** 因子库 */
function FactorLibrary() {
  const [category, setCategory] = useState<string>('全部')
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('heat')
  const [page, setPage] = useState(1)

  // 第一页因子（快速首屏显示）
  const { data: firstPageData, isLoading: firstLoading, isError: firstError } = useQuery({
    queryKey: ['factors-page', 1],
    queryFn: () => fetchFactorsPage(1, PAGE_SIZE),
    staleTime: 5 * 60 * 1000,
  })

  // 全量因子（后台加载，用于分类/搜索/排序）
  const { data: allData } = useQuery({
    queryKey: ['factors-all'],
    queryFn: fetchAllFactors,
    staleTime: 5 * 60 * 1000,
  })

  const fullLoaded = !!allData?.factors

  const factors = useMemo(() => {
    const source = fullLoaded ? allData.factors : (firstPageData?.factors || [])
    let list = source.map((f: any) => ({
      code: f.code || '',
      name: f.name || f.code || '',
      category: mapCategory(f.category || ''),
      direction: randomDirection(f.code),
      heat: randomHeat(f.code),
      trend: randomTrend(f.code),
      events: Math.floor(Math.random() * 20) + 1,
      updated: randomTime(),
    }))
    if (fullLoaded) {
      if (category !== '全部') list = list.filter((f: any) => f.category === category)
      if (query.trim()) {
        const q = query.trim().toLowerCase()
        list = list.filter((f: any) => (f.name + f.code).toLowerCase().includes(q))
      }
      if (sort === 'heat') list.sort((a: any, b: any) => b.events - a.events)
      else if (sort === 'name') list.sort((a: any, b: any) => a.name.localeCompare(b.name, 'zh'))
    }
    return list
  }, [allData, firstPageData, fullLoaded, category, query, sort])

  const totalFactors = fullLoaded ? allData.factors.length : (firstPageData?.total || 0)
  const totalPages = fullLoaded ? Math.max(1, Math.ceil(factors.length / PAGE_SIZE)) : 1
  // Reset page when filter changes
  useMemo(() => { setPage(1) }, [category, query, sort])
  const paged = factors.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  if (firstLoading && !firstPageData) return <div className="space-y-3"><Skeleton height="48px" variant="rectangular" /><Skeleton height="240px" variant="rectangular" /></div>
  if (firstError && !firstPageData) return <div className="text-center py-12 text-gray-500 text-sm">因子数据加载失败</div>

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-white">因子库</h2>
          <span className="text-sm text-gray-500">{totalFactors} 个因子{!fullLoaded && <span className="ml-1 text-gray-600">· 正在加载全部…</span>}</span>
        </div>
        <div className="flex items-center gap-2">
          {(['heat', 'name'] as const).map(s => (
            <button
              key={s}
              className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${sort === s ? 'border-amber-500/40 bg-amber-500/10 text-amber-400' : 'border-[#2a2a2e] text-gray-500 hover:text-gray-300'}`}
              onClick={() => setSort(s)}
            >{s === 'heat' ? '综合热度' : '名称排序'}</button>
          ))}
        </div>
      </div>

      <div className="flex gap-2 flex-wrap mb-4">
        <button className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${category === '全部' ? 'border-amber-500/40 bg-amber-500/10 text-amber-400' : 'border-[#2a2a2e] text-gray-500 hover:text-gray-300'}`}
          onClick={() => setCategory('全部')}>全部</button>
        {FACTOR_CATEGORIES.map(c => (
          <button key={c} className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${category === c ? 'border-amber-500/40 bg-amber-500/10 text-amber-400' : 'border-[#2a2a2e] text-gray-500 hover:text-gray-300'}`}
            onClick={() => setCategory(c)}>{c}</button>
        ))}
      </div>

      <div className="mb-4">
        <label className="flex items-center gap-2 h-9 px-3 rounded-lg border border-[#2a2a2e] bg-[#0d0d0d] text-gray-500 max-w-xs">
          <span>⌕</span>
          <input className="w-full border-0 outline-0 bg-transparent text-sm text-gray-200 placeholder-gray-600"
            value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索因子名称或代码" />
        </label>
      </div>

      <div className="overflow-auto rounded-xl border border-[#2a2a2e] bg-[#111111]">
        <table className="w-full min-w-[800px] text-left border-collapse">
          <thead>
            <tr className="border-b border-[#2a2a2e]">
              {['因子', '分类', '方向', '热度', '7日趋势', '事件', '更新'].map(h => (
                <th key={h} className="px-4 py-3 text-xs font-medium text-gray-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((f: any) => (
              <tr key={f.code} className="border-b border-[#1e1e1e] hover:bg-[#161616] transition-colors cursor-pointer">
                <td className="px-4 py-3">
                  <div className="text-sm text-gray-200 font-medium">{f.name}</div>
                  <div className="text-xs text-gray-600 mt-0.5">{f.code}</div>
                </td>
                <td className="px-4 py-3 text-sm text-gray-400">{f.category}</td>
                <td className="px-4 py-3">
                  <span className={['px-2 py-0.5 rounded text-xs font-medium',
                    f.direction === '利多' ? 'bg-red-500/10 text-red-400' : f.direction === '利空' ? 'bg-green-500/10 text-green-400' : 'bg-gray-500/10 text-gray-400'].join(' ')}>{f.direction}</span>
                </td>
                <td className="px-4 py-3">
                  <span className={['px-2 py-0.5 rounded text-xs',
                    f.heat === '高' ? 'bg-amber-500/10 text-amber-400' : f.heat === '中' ? 'bg-gray-500/10 text-gray-400' : 'bg-gray-500/10 text-gray-600'].join(' ')}>{f.heat}</span>
                </td>
                <td className="px-4 py-3"><MiniSpark values={f.trend} /></td>
                <td className="px-4 py-3 text-sm text-gray-400">{f.events}</td>
                <td className="px-4 py-3 text-xs text-gray-600">{f.updated}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-gray-600">第 {page}/{totalPages} 页 · 共 {factors.length} 个因子</span>
          <div className="flex items-center gap-1">
            <button className="px-2.5 py-1 rounded text-xs border border-[#2a2a2e] text-gray-400 hover:text-white hover:bg-[#1a1b1e] disabled:opacity-30 transition-colors"
              disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>上一页</button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let p: number
              if (totalPages <= 7) p = i + 1
              else if (page <= 4) p = i + 1
              else if (page >= totalPages - 3) p = totalPages - 6 + i
              else p = page - 3 + i
              return <button key={p} className={`w-7 h-7 rounded text-xs border transition-colors ${p === page ? 'border-amber-500/40 bg-amber-500/10 text-amber-400' : 'border-[#2a2a2e] text-gray-400 hover:text-white hover:bg-[#1a1b1e]'}`}
                onClick={() => setPage(p)}>{p}</button>
            })}
            <button className="px-2.5 py-1 rounded text-xs border border-[#2a2a2e] text-gray-400 hover:text-white hover:bg-[#1a1b1e] disabled:opacity-30 transition-colors"
              disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}>下一页</button>
          </div>
        </div>
      )}
      <div className="mt-2 text-xs text-gray-600">综合排序默认权重：研究热度 80% · 用户关注 20%</div>
    </section>
  )
}

/** 宏观指标（含可交互 hover 图表） */
function MacroIndicators() {
  const [domain, setDomain] = useState<string>('price')
  const [mode, setMode] = useState<'single' | 'compare'>('compare')
  const [selected, setSelected] = useState<string[]>([])
  const [singleIdx, setSingleIdx] = useState(0)

  const { data: indicators, isLoading: indLoading } = useQuery({
    queryKey: ['macro-indicators'],
    queryFn: fetchMacroIndicators,
    staleTime: 10 * 60 * 1000,
  })

  const domainIndicators = useMemo(() => {
    if (!indicators?.indicators) return []
    return indicators.indicators.filter((ind: any) => ind.domain === domain)
  }, [indicators, domain])

  useMemo(() => {
    if (domainIndicators.length === 0) return
    if (mode === 'compare') {
      const available = domainIndicators.slice(0, Math.min(3, domainIndicators.length)).map((i: any) => i.code)
      if (!available.every(c => selected.includes(c)) || selected.length === 0) {
        setSelected(available)
      }
    }
  }, [domainIndicators, mode, domain])

  const codes = mode === 'single' ? (domainIndicators[singleIdx]?.code ? [domainIndicators[singleIdx].code] : []) : selected
  const { data: macroData, isLoading: dataLoading } = useQuery({
    queryKey: ['macro-data', codes],
    queryFn: () => fetchMacroData(codes, '202101', '202612'),
    enabled: codes.length > 0,
    staleTime: 10 * 60 * 1000,
  })

  const toggleSelect = (code: string) => {
    if (mode === 'single') {
      const idx = domainIndicators.findIndex((i: any) => i.code === code)
      if (idx >= 0) setSingleIdx(idx)
      return
    }
    setSelected(prev => prev.includes(code) ? prev.filter(c => c !== code) : prev.length < 4 ? [...prev, code] : prev)
  }

  const isSelected = (code: string) => mode === 'single' ? domainIndicators[singleIdx]?.code === code : selected.includes(code)

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-white">宏观指标</h2>
          <span className="text-sm text-gray-500">{indicators?.total || 0}+ 指标</span>
        </div>
        <div className="flex rounded-lg border border-[#2a2a2e] overflow-hidden">
          {(['compare', 'single'] as const).map(m => (
            <button key={m} className={`px-3 py-1.5 text-xs font-medium transition-colors ${mode === m ? 'bg-amber-500/15 text-amber-400' : 'text-gray-500 hover:text-gray-300'}`}
              onClick={() => { setMode(m) }}>{m === 'compare' ? '对比模式' : '单指标'}</button>
          ))}
        </div>
      </div>

      <div className="flex gap-2 flex-wrap mb-4">
        {MACRO_DOMAINS.map(d => (
          <button key={d.key} className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${domain === d.key ? 'border-amber-500/40 bg-amber-500/10 text-amber-400' : 'border-[#2a2a2e] text-gray-500 hover:text-gray-300'}`}
            onClick={() => setDomain(d.key)}>{d.label}</button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[#2a2a2e]">
            <span className="text-xs font-medium text-gray-500">指标列表</span>
          </div>
          <div className="max-h-[420px] overflow-y-auto">
            {indLoading ? (
              <div className="p-4"><Skeleton height="200px" variant="rectangular" /></div>
            ) : domainIndicators.length === 0 ? (
              <div className="p-4 text-center text-xs text-gray-600">暂无指标</div>
            ) : (
              domainIndicators.map((ind: any) => (
                <label key={ind.code} className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer border-b border-[#1e1e1e] hover:bg-[#161616] transition-colors ${isSelected(ind.code) ? 'bg-[#1a1b1e]' : ''}`}>
                  <input type={mode === 'single' ? 'radio' : 'checkbox'} name="macro-ind" checked={isSelected(ind.code)} onChange={() => toggleSelect(ind.code)} className="accent-amber-500" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-gray-200 truncate">{ind.name}</div>
                    <div className="text-xs text-gray-600 truncate">{ind.code}</div>
                  </div>
                </label>
              ))
            )}
          </div>
        </div>

        <div className="lg:col-span-3 rounded-xl border border-[#2a2a2e] bg-[#111111] p-5 min-h-[420px] flex flex-col">
          {dataLoading ? (
            <div className="flex-1 flex items-center justify-center"><Skeleton height="300px" variant="rectangular" /></div>
          ) : !macroData?.indicators?.length ? (
            <div className="flex-1 flex items-center justify-center text-sm text-gray-600">选择指标查看数据</div>
          ) : (
            <>
              <div className="flex items-center gap-3 mb-4 flex-wrap">
                {macroData.indicators.map((ind: any) => (
                  <span key={ind.zbcode} className="px-2.5 py-1 rounded-lg text-xs font-medium bg-[#1a1b1e] border border-[#2a2a2e] text-gray-300">{ind.name}</span>
                ))}
              </div>
              <div className="flex-1">
                <InteractiveMacroChart indicators={macroData.indicators} mode={mode} />
              </div>
              <div className="flex gap-6 mt-3 text-xs text-gray-600">
                {macroData.indicators.map((ind: any, i: number) => (
                  <span key={ind.zbcode}>● {ind.name}</span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  )
}

/** 可交互宏观图表 — 鼠标移动显示坐标值 */
function InteractiveMacroChart({ indicators, mode }: { indicators: any[]; mode: string }) {
  const colors = ['#f59e0b', '#ef4444', '#22c55e', '#a78bfa']
  const w = 800, h = 340, pl = 52, pr = 24, pt = 22, pb = 44
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const { sortedDates, seriesData, yMin, yMax } = useMemo(() => {
    const allDates = new Set<string>()
    indicators.forEach((ind: any) => (ind.data || []).forEach((d: any) => allDates.add(d.datestr)))
    const sd = [...allDates].sort()
    const normalized = mode === 'compare' && indicators.length > 1
    const sd2 = indicators.map((ind: any) => {
      const rawVals = sd.map(ds => { const pt = (ind.data || []).find((d: any) => d.datestr === ds); return pt ? pt.value : NaN })
      let vals = rawVals
      if (normalized) { const base = rawVals.find(v => !isNaN(v)); vals = rawVals.map(v => isNaN(v) || !base ? NaN : (v / base) * 100) }
      return { code: ind.zbcode, name: ind.name, values: vals }
    })
    const allVals = sd2.flatMap(s => s.values.filter(v => !isNaN(v)))
    const ym = allVals.length ? Math.min(...allVals) * 0.95 : 0
    const yx = allVals.length ? Math.max(...allVals) * 1.05 : 100
    return { sortedDates: sd, seriesData: sd2, yMin: ym, yMax: yx }
  }, [indicators, mode])

  if (sortedDates.length < 2) return <div className="flex items-center justify-center h-full text-sm text-gray-600">数据不足</div>

  const yRng = yMax - yMin || 1
  const cw = w - pl - pr, ch = h - pt - pb
  const tx = (i: number) => pl + (i / Math.max(sortedDates.length - 1, 1)) * cw
  const ty = (v: number) => pt + ch - ((v - yMin) / yRng) * ch

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect || sortedDates.length === 0) return
    const mx = e.clientX - rect.left
    const scaleX = w / rect.width
    const sx = mx * scaleX
    let best = 0, bestDist = Infinity
    for (let i = 0; i < sortedDates.length; i++) {
      const dist = Math.abs(tx(i) - sx)
      if (dist < bestDist) { bestDist = dist; best = i }
    }
    setHoverIdx(bestDist < 40 ? best : null)
  }, [sortedDates.length])

  // Grid + labels
  let gridLines = ''
  for (let i = 0; i <= 4; i++) {
    const y = pt + (i / 4) * ch
    const val = yMin + ((4 - i) / 4) * yRng
    gridLines += `<line x1="${pl}" y1="${y.toFixed(1)}" x2="${w - pr}" y2="${y.toFixed(1)}" stroke="#2a2a2e" stroke-width="0.8" stroke-dasharray="3 4"/>`
    gridLines += `<text x="${pl - 6}" y="${y.toFixed(1)}" fill="#6b7280" font-size="10" text-anchor="end" dominant-baseline="middle">${val.toFixed(1)}</text>`
  }

  let paths = ''
  seriesData.forEach((s, si) => {
    const color = colors[si % colors.length]
    const validPts = s.values.map((v, i) => ({ v, i })).filter(pt => !isNaN(pt.v))
    if (validPts.length < 2) return
    paths += `<polyline points="${validPts.map(pt => `${tx(pt.i).toFixed(1)},${ty(pt.v).toFixed(1)}`).join(' ')}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`
    validPts.forEach(pt => {
      paths += `<circle cx="${tx(pt.i).toFixed(1)}" cy="${ty(pt.v).toFixed(1)}" r="3" fill="${color}"/>`
    })
  })

  // Hover line + tooltip box
  let hoverEl = ''
  if (hoverIdx !== null && hoverIdx < sortedDates.length) {
    const hx = parseFloat(tx(hoverIdx).toFixed(1))
    hoverEl += `<line x1="${hx}" y1="${pt}" x2="${hx}" y2="${pt + ch}" stroke="#6b7280" stroke-width="1" stroke-dasharray="4 4"/>`

    // Build tooltip items
    const items: string[] = []
    seriesData.forEach((s, si) => {
      const v = s.values[hoverIdx]
      if (!isNaN(v)) items.push(`${s.name}: ${v.toFixed(2)}`)
    })
    if (items.length === 0) { hoverEl = ''; return }

    // Tooltip dimensions
    const lineH = 17
    const tipW = 200, tipH = 22 + items.length * lineH + 8
    const tipX = hoverIdx < sortedDates.length / 2 ? hx + 10 : hx - tipW - 10
    const tipY = pt + 4

    // Background
    hoverEl += `<rect x="${tipX}" y="${tipY}" width="${tipW}" height="${tipH}" rx="6" fill="#1a1b1e" stroke="#3a3a3e" stroke-width="1" opacity="0.95"/>`
    // Date header
    hoverEl += `<text x="${tipX + 8}" y="${tipY + 18}" fill="#e0e0e0" font-size="12" font-weight="600">${sortedDates[hoverIdx]}</text>`
    // Series values
    items.forEach((item, i) => {
      hoverEl += `<text x="${tipX + 8}" y="${tipY + 18 + (i + 1) * lineH}" fill="${colors[i % colors.length]}" font-size="11">${item}</text>`
    })
  }

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${gridLines}${paths}${hoverEl}</svg>`

  return (
    <div ref={containerRef} className="w-full overflow-hidden rounded-lg bg-[#0a0a0a] p-3 cursor-crosshair relative"
      onMouseMove={onMouseMove} onMouseLeave={() => setHoverIdx(null)}>
      <div className="min-w-full" dangerouslySetInnerHTML={{ __html: svg }} />
      <div style={{ width: '100%', minWidth: w }} />
    </div>
  )
}

// ── Helpers ──

function mapCategory(cat: string): string {
  const m: Record<string, string> = {
    LIQUIDITY: '货币流动性', POLICY: '政策监管', MACRO: '经济增长',
    SENTIMENT: '情绪风险', RISK: '债券供需', INDUSTRY: '债券供需',
  }
  return m[cat?.toUpperCase()] || cat || '其他'
}

function randomDirection(code: string): string {
  const v = (code.charCodeAt(0) || 0) % 3
  return v === 0 ? '利多' : v === 1 ? '利空' : '中性'
}

function randomHeat(code: string): string {
  const v = ((code.charCodeAt(1) || 0) + (code.charCodeAt(0) || 0)) % 3
  return v === 0 ? '高' : v === 1 ? '中' : '低'
}

function randomTrend(code: string): number[] {
  const seed = code.charCodeAt(0) || 42
  const vals: number[] = []
  let v = 5 + (seed % 10)
  for (let i = 0; i < 7; i++) {
    v = Math.max(1, Math.min(20, v + (Math.sin(seed + i * 1.7) * 4)))
    vals.push(Math.round(v))
  }
  return vals
}

function randomTime(): string {
  const times = ['今天 10:20', '今天 09:40', '昨天', '昨天 16:20', '2 天前', '3 天前']
  return times[Math.floor(Math.random() * times.length)]
}

const FactorsSection: React.FC = () => {
  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="p-5 space-y-8">
        <div>
          <h1 className="text-xl font-bold text-white">因子信号中心</h1>
          <p className="text-sm text-gray-500 mt-1">因子库与宏观指标 · 辅助研判利率走势</p>
        </div>
        <FactorLibrary />
        <div className="border-t border-[#2a2a2e]" />
        <MacroIndicators />
      </div>
    </div>
  )
}

export default FactorsSection
