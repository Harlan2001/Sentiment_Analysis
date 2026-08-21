import React, { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import { useQuery } from '@tanstack/react-query'
import { fetchAllFactors, fetchFactorDetail, fetchMacroData, fetchMacroIndicators } from '@/api/market'
import { Skeleton } from '@/components/UI'
import type { FactorDetailData } from '@/types'

const CATEGORIES: Record<string, string> = { LIQUIDITY: '货币流动性', POLICY: '政策监管', MACRO: '经济增长', RISK: '债券供需', SENTIMENT: '情绪风险', INDUSTRY: '债券供需' }
const DOMAINS = [
  ['price', '通胀与价格'], ['real', '实体景气'], ['real_estate', '房地产'],
  ['trade', '进出口'], ['fiscal', '财政'], ['industry', '产业'],
]

type Factor = { id: number; code: string; name: string; category: string; factor_type?: string; news_count?: number; recent_news_count?: number }
const FACTOR_PAGE_SIZE = 20

export default function FactorsSection() {
  const [searchParams] = useSearchParams()
  const [view, setView] = useState<'signals' | 'macro'>(searchParams.get('view') === 'macro' ? 'macro' : 'signals')
  const [selectedFactor, setSelectedFactor] = useState<Factor | null>(null)
  return <div className="home-section-page factor-section-page">
    <header className="home-section-heading factor-section-heading">
      <div className="factor-view-tabs">
      {(['signals', 'macro'] as const).map(key => <button key={key} onClick={() => setView(key)} className={`factor-view-tab${view === key ? ' active' : ''}`}>
        {key === 'signals' ? '因子信号' : '宏观数据'}
      </button>)}
      </div>
      {view === 'signals' && selectedFactor && <h2 className="factor-activity-label">7日活跃度走势</h2>}
    </header>
    {view === 'signals' ? <FactorSignals selectedFactor={selectedFactor} onSelect={setSelectedFactor} /> : <MacroWorkspace />}
  </div>
}

function FactorSignals({ selectedFactor, onSelect }: { selectedFactor: Factor | null; onSelect: (factor: Factor) => void }) {
  const [category, setCategory] = useState('ALL')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = useQuery({ queryKey: ['factors-all'], queryFn: fetchAllFactors, staleTime: 5 * 60 * 1000 })
  const factors = useMemo(() => ((data?.factors || []) as Factor[]).filter(f => (category === 'ALL' || f.category === category) && (`${f.name}${f.code}`).toLowerCase().includes(query.toLowerCase())).sort((a, b) => (b.recent_news_count || 0) - (a.recent_news_count || 0)), [data, category, query])
  const categories = useMemo(() => [...new Set((data?.factors || []).map((f: Factor) => f.category))], [data])
  const totalPages = Math.max(1, Math.ceil(factors.length / FACTOR_PAGE_SIZE))
  const pagedFactors = factors.slice((page - 1) * FACTOR_PAGE_SIZE, page * FACTOR_PAGE_SIZE)
  useEffect(() => setPage(1), [category, query])
  return <div className="home-section-grid">
    <main className="home-section-main">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <label className="flex items-center gap-2 h-9 px-3 rounded-lg border border-[#2a2a2e] bg-[#0d0d0d] text-gray-500 w-64"><span>⌕</span><input className="w-full bg-transparent border-0 outline-0 text-sm text-gray-200 placeholder-gray-600" value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索因子名称或代码" /></label>
        <span className="text-xs text-gray-600">{factors.length} 个因子</span>
      </div>
      <div className="flex gap-2 flex-wrap mb-4">
        <FilterButton active={category === 'ALL'} onClick={() => setCategory('ALL')}>全部</FilterButton>
        {categories.map(key => <FilterButton key={key} active={category === key} onClick={() => setCategory(key)}>{CATEGORIES[key] || key}</FilterButton>)}
      </div>
      {isLoading ? <Skeleton height="360px" variant="rectangular" /> : isError ? <Empty text="因子数据加载失败" /> : <><div className="factor-signal-table rounded-xl border border-[#2a2a2e] bg-[#111111] overflow-x-auto">
        <table className="w-full min-w-[820px] table-fixed text-left"><colgroup><col className="w-[34%]" /><col className="w-[16%]" /><col className="w-[12%]" /><col className="w-[12%]" /><col className="w-[11%]" /><col className="w-[15%]" /></colgroup><thead><tr className="border-b border-[#2a2a2e] text-xs text-gray-500"><th className="px-4 py-3">因子</th><th className="px-4 py-3">分类</th><th className="px-4 py-3">方向</th><th className="px-4 py-3">热度</th><th className="px-4 py-3 text-center">事件</th><th className="px-4 py-3">更新</th></tr></thead>
          <tbody>{pagedFactors.map(f => { const direction = factorDirection(f.code); const heat = factorHeat(f.code); return <tr key={f.code} onClick={() => onSelect(f)} className={`cursor-pointer border-b border-[#1e1e1e] hover:bg-[#181818] ${selectedFactor?.code === f.code ? 'bg-[#1a1a1a]' : ''}`}><td className="px-4 py-3"><div className="truncate text-sm text-gray-200 font-medium">{f.name}</div><div className="truncate text-xs text-gray-600 mt-0.5">{f.code}</div></td><td className="px-4 py-3 text-sm text-gray-400"><span className="block truncate">{CATEGORIES[f.category] || f.category}</span></td><td className="px-4 py-3"><span className={direction === '利多' ? 'factor-direction up' : direction === '利空' ? 'factor-direction down' : 'factor-direction neutral'}>{direction}</span></td><td className="px-4 py-3"><span className={`factor-heat ${heat}`}>{heat}</span></td><td className="px-4 py-3 text-center text-sm text-gray-300">{f.recent_news_count || f.news_count || 0}</td><td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">{factorUpdated(f.code)}</td></tr> })}</tbody>
        </table>
      </div><div className="factor-table-pagination"><span>第 {page} / {totalPages} 页 · 共 {factors.length} 个因子</span><div><button disabled={page === 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>上一页</button><button disabled={page === totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>下一页</button></div></div></>}
    </main>
    <aside className="home-section-sidebar factor-signal-sidebar"><FactorSidebar factor={selectedFactor} /></aside>
  </div>
}

function factorSeed(code: string) { return [...code].reduce((sum, char) => sum + char.charCodeAt(0), 0) }
function factorDirection(code: string) { return ['利多', '利空', '中性'][factorSeed(code) % 3] }
function factorHeat(code: string) { return ['高', '中', '低'][factorSeed(code) % 3] }
function factorUpdated(code: string) { return ['今天 10:20', '今天 09:40', '昨天', '昨天 16:20', '2 天前'][factorSeed(code) % 5] }
function FactorSevenDayTrend({ values }: { values: number[] }) { if (!values.length) return <div className="factor-seven-day-empty">近 7 日暂无活跃数据</div>; const max = Math.max(...values, 1); const min = Math.min(...values, 0); const range = max - min || 1; const points = values.map((value, index) => ({ x: values.length === 1 ? 50 : index * (100 / (values.length - 1)), y: 30 - ((value - min) / range) * 26 })); const path = points.length === 1 ? `M 34 ${points[0].y} L 66 ${points[0].y}` : points.reduce((result, point, index) => { if (index === 0) return `M ${point.x} ${point.y}`; if (index === points.length - 1) return `${result} L ${point.x} ${point.y}`; const previous = points[index - 1]; return `${result} Q ${previous.x} ${previous.y} ${(previous.x + point.x) / 2} ${(previous.y + point.y) / 2}` }, ''); return <svg className="factor-seven-day-chart" viewBox="0 0 100 32" preserveAspectRatio="none" aria-label="近7日活跃度趋势"><path d={path} /></svg> }

function FactorSidebar({ factor }: { factor: Factor | null }) {
  const { data, isLoading } = useQuery<FactorDetailData>({ queryKey: ['factor-detail', factor?.id], queryFn: () => fetchFactorDetail(factor!.id), enabled: !!factor, staleTime: 60 * 1000 })
  if (!factor) return <Empty text="选择一个因子，查看走势与相关新闻" />
  if (isLoading) return <Skeleton height="360px" variant="rectangular" />
  if (!data || 'error' in data) return <Empty text="未能加载因子详情" />
  const values = data.daily_counts.map(d => d.count)
  return <div className="factor-detail-sidebar">
    <section className="factor-detail-activity rounded-xl border border-[#2a2a2e] bg-[#111111] p-4"><p className="text-xs text-gray-500">{data.name} · 近 7 天 {data.news_count} 条关联新闻</p><FactorSevenDayTrend values={values} /></section>
    <section className="factor-detail-news rounded-xl border border-[#2a2a2e] bg-[#111111] p-4"><h2 className="text-sm font-semibold text-white mb-3">相关新闻</h2><div className="space-y-2">{data.related_news.length ? data.related_news.map(n => <div key={n.id} className="rounded-lg border border-[#1e1e1e] bg-[#0d0d0d] p-3"><div className="flex gap-2 text-xs text-gray-500 mb-1"><span>{n.pub_time.slice(5, 16)}</span><span className={n.direction === 'positive' ? 'text-red-400' : n.direction === 'negative' ? 'text-green-400' : 'text-gray-400'}>{n.direction === 'positive' ? '利多' : n.direction === 'negative' ? '利空' : '中性'}</span></div><p className="text-sm leading-snug text-gray-200 line-clamp-2">{n.title}</p></div>) : <p className="text-sm text-gray-600 py-4 text-center">暂无相关新闻</p>}</div></section>
  </div>
}

function MacroWorkspace() {
  const [domain, setDomain] = useState('price'); const [mode, setMode] = useState<'single' | 'compare'>('compare'); const [selected, setSelected] = useState<string[]>([])
  const { data: indicators, isLoading } = useQuery({ queryKey: ['macro-indicators'], queryFn: fetchMacroIndicators, staleTime: 10 * 60 * 1000 })
  const list = useMemo(() => (indicators?.indicators || []).filter((i: any) => i.domain === domain), [indicators, domain])
  useEffect(() => { if (list.length) setSelected(mode === 'single' ? [list[0].code] : list.slice(0, 3).map((i: any) => i.code)) }, [domain, mode, list])
  const { data: chartData, isLoading: chartLoading } = useQuery({ queryKey: ['macro-data', selected], queryFn: () => fetchMacroData(selected, '202101', '202612'), enabled: selected.length > 0, staleTime: 10 * 60 * 1000 })
  const option = useMemo(() => ({ tooltip: { trigger: 'axis' }, legend: { textStyle: { color: '#aaa' } }, grid: { left: 48, right: 20, top: 36, bottom: 34 }, xAxis: { type: 'category', data: chartData?.indicators?.[0]?.data?.map((d: any) => d.datestr) || [], axisLabel: { color: '#777' }, axisLine: { lineStyle: { color: '#333' } } }, yAxis: { type: 'value', splitLine: { lineStyle: { color: '#262626' } }, axisLabel: { color: '#777' } }, series: (chartData?.indicators || []).map((i: any) => ({ name: i.name, type: 'line', smooth: true, showSymbol: false, data: i.data.map((d: any) => d.value) })) }), [chartData])
  const toggle = (code: string) => setSelected(prev => mode === 'single' ? [code] : prev.includes(code) ? prev.filter(x => x !== code) : prev.length < 4 ? [...prev, code] : prev)
  return <div className="home-section-grid"><main className="home-section-main rounded-xl border border-[#2a2a2e] bg-[#111111] p-5 overflow-hidden"><div className="flex justify-between gap-3 mb-4"><div><h2 className="text-base font-semibold text-white">{mode === 'single' ? '单指标走势' : '多指标对比'}</h2><p className="text-xs text-gray-500 mt-1">{selected.length} 项已选择</p></div><div className="factor-mode-tabs">{(['compare', 'single'] as const).map(k => <button key={k} onClick={() => setMode(k)} className={`factor-mode-tab${mode === k ? ' active' : ''}`}>{k === 'compare' ? '多指标对比' : '单指标'}</button>)}</div></div>{chartLoading ? <Skeleton height="340px" variant="rectangular" /> : <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 360 }} />}</main><aside className="home-section-sidebar factor-macro-sidebar rounded-xl border border-[#2a2a2e] bg-[#111111]"><div className="p-4 border-b border-[#2a2a2e]"><h2 className="text-sm font-semibold text-white">指标筛选</h2><div className="flex flex-wrap gap-2 mt-3">{DOMAINS.map(([key, label]) => <FilterButton key={key} active={domain === key} onClick={() => setDomain(key)}>{label}</FilterButton>)}</div></div><div className="p-2">{isLoading ? <Skeleton height="200px" variant="rectangular" /> : list.map((i: any) => <label key={i.code} className="flex gap-3 px-2 py-2.5 rounded-lg hover:bg-[#181818] cursor-pointer"><input type={mode === 'single' ? 'radio' : 'checkbox'} name="macro-indicator" checked={selected.includes(i.code)} onChange={() => toggle(i.code)} className="accent-amber-500 mt-0.5" /><span className="min-w-0"><span className="block text-sm text-gray-200 truncate">{i.name}</span><span className="block text-xs text-gray-600 truncate">{i.code}</span></span></label>)}</div></aside></div>
}
function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) { return <button onClick={onClick} className={`factor-filter-tab${active ? ' active' : ''}`}>{children}</button> }
function Empty({ text }: { text: string }) { return <div className="h-full min-h-[240px] rounded-xl border border-[#2a2a2e] bg-[#111111] flex items-center justify-center text-sm text-gray-600 text-center p-6">{text}</div> }
