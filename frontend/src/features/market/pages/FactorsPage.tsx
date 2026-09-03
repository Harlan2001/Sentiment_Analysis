import React, { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import { useQuery } from '@tanstack/react-query'
import { fetchFactorActivityOverview, fetchMacroData, fetchMacroIndicators } from '@/api/market'
import type { FactorDefinition } from '@/api/market'
import { Skeleton } from '@/components/ui'
import { WatchlistAction } from '../components/WatchlistAction'

const CATEGORIES: Record<string, string> = { LIQUIDITY: '货币流动性', POLICY: '政策监管', MACRO: '经济增长', RISK: '债券供需', SENTIMENT: '情绪风险', INDUSTRY: '债券供需' }
const DOMAINS = [
  ['price', '通胀与价格'], ['real', '实体景气'], ['real_estate', '房地产'],
  ['trade', '进出口'], ['fiscal', '财政'], ['industry', '产业'],
]

type Factor = FactorDefinition
type DirectionFilter = 'ALL' | Factor['current_direction']
type ActivityPeriod = '7d' | '30d' | '365d'
const FACTOR_PAGE_SIZE = 20

function normalizeFactor(raw: Factor): Factor {
  const activity30d = Number(raw.activity_30d ?? raw.recent_news_count ?? 0)
  return {
    ...raw,
    activity_7d: Number(raw.activity_7d ?? 0),
    activity_30d: activity30d,
    activity_365d: Number(raw.activity_365d ?? raw.news_count ?? 0),
    positive_count: Number(raw.positive_count ?? 0),
    negative_count: Number(raw.negative_count ?? 0),
    neutral_count: Number(raw.neutral_count ?? 0),
    current_direction: raw.current_direction || '中性',
    heat_level: raw.heat_level || (activity30d >= 20 ? '高' : activity30d >= 5 ? '中' : '低'),
    trend_7d: raw.trend_7d || [],
    latest_event_at: raw.latest_event_at || null,
  }
}

export default function FactorsPage() {
  const [searchParams] = useSearchParams()
  const [view, setView] = useState<'signals' | 'macro'>(searchParams.get('view') === 'macro' ? 'macro' : 'signals')
  return <div className="home-section-page factor-section-page">
    <header className="home-section-heading factor-section-heading">
      <div className="factor-view-tabs">
      {(['signals', 'macro'] as const).map(key => <button key={key} onClick={() => setView(key)} className={`factor-view-tab${view === key ? ' active' : ''}`}>
        {key === 'signals' ? '因子信号' : '宏观数据'}
      </button>)}
      </div>
    </header>
    {view === 'signals' ? <FactorSignals /> : <MacroWorkspace presetCodes={searchParams.get('codes')?.split(',').filter(Boolean) || []} />}
  </div>
}

function FactorSignals() {
  const navigate = useNavigate()
  const location = useLocation()
  const [category, setCategory] = useState('ALL')
  const [direction, setDirection] = useState<DirectionFilter>('ALL')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [activityPeriod, setActivityPeriod] = useState<ActivityPeriod>('7d')
  const { data, isLoading, isError } = useQuery({ queryKey: ['factors-activity-overview'], queryFn: fetchFactorActivityOverview, staleTime: 5 * 60 * 1000 })
  const allFactors = useMemo(() => ((data?.factors || []) as Factor[]).map(normalizeFactor), [data])
  const factors = useMemo(() => allFactors.filter(f =>
    (category === 'ALL' || f.category === category)
    && (direction === 'ALL' || f.current_direction === direction)
    && (`${f.name}${f.code}`).toLowerCase().includes(query.toLowerCase())
  ).sort((a, b) => b.activity_30d - a.activity_30d), [allFactors, category, direction, query])
  const categories = useMemo(() => [...new Set(allFactors.map(f => f.category))], [allFactors])
  const totalPages = Math.max(1, Math.ceil(factors.length / FACTOR_PAGE_SIZE))
  const pagedFactors = factors.slice((page - 1) * FACTOR_PAGE_SIZE, page * FACTOR_PAGE_SIZE)
  useEffect(() => setPage(1), [category, direction, query])
  const openFactor = (factor: Factor) => navigate(`/factor/${factor.id}`, { state: { from: `${location.pathname}${location.search}` } })
  return <div className="home-section-grid">
    <main className="home-section-main">
      <div className="factor-library-toolbar">
        <label className="factor-library-search"><span>⌕</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索因子名称或代码" /></label>
        <span className="factor-library-count">{factors.length} 个因子</span>
        <FilterDropdown label="类别" value={category} options={[['ALL', '全部类别'], ...categories.map(key => [key, CATEGORIES[key] || key])]} onChange={setCategory} />
        <FilterDropdown label="当前方向" value={direction} options={[['ALL', '全部方向'], ['利多', '利多'], ['利空', '利空'], ['中性', '中性']]} onChange={(value) => setDirection(value as DirectionFilter)} />
      </div>
      {isLoading ? <Skeleton height="360px" variant="rectangular" /> : isError ? <Empty text="因子数据加载失败" /> : <><div className="factor-signal-table rounded-xl border border-[#2a2a2e] bg-[#111111] overflow-x-auto">
        <table className="w-full min-w-[900px] table-fixed text-left"><colgroup><col className="w-[25%]" /><col className="w-[15%]" /><col className="w-[10%]" /><col className="w-[14%]" /><col className="w-[10%]" /><col className="w-[10%]" /><col className="w-[16%]" /></colgroup><thead><tr className="border-b border-[#2a2a2e] text-xs text-gray-500"><th className="px-4 py-3">因子</th><th className="px-4 py-3">类别</th><th className="px-4 py-3">当前方向</th><th className="px-4 py-3 text-center">七日走势</th><th className="px-4 py-3">热度</th><th className="px-4 py-3 text-center">事件</th><th className="px-4 py-3">更新</th></tr></thead>
          <tbody>{pagedFactors.map(f => <tr key={f.code} role="link" tabIndex={0} onClick={() => openFactor(f)} onKeyDown={(event) => { if (event.key === 'Enter') openFactor(f) }} className="cursor-pointer border-b border-[#1e1e1e] hover:bg-[#181818]"><td className="px-4 py-3"><div className="truncate text-sm text-gray-200 font-medium">{f.name}</div><div className="truncate text-xs text-gray-600 mt-0.5">{f.code}</div></td><td className="px-4 py-3 text-sm text-gray-400"><span className="block truncate">{CATEGORIES[f.category] || f.category}</span></td><td className="px-4 py-3"><span className={f.current_direction === '利多' ? 'factor-direction up' : f.current_direction === '利空' ? 'factor-direction down' : 'factor-direction neutral'}>{f.current_direction}</span></td><td className="px-4 py-3 text-center"><FactorMiniTrend values={f.trend_7d || []} /></td><td className="px-4 py-3"><span className={`factor-heat ${f.heat_level}`}>{f.heat_level}</span></td><td className="px-4 py-3 text-center text-sm text-gray-300">{f.activity_30d}</td><td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">{factorUpdated(f.latest_event_at)}</td></tr>)}</tbody>
        </table>
      </div><div className="factor-table-pagination"><span>第 {page} / {totalPages} 页 · 共 {factors.length} 个因子</span><div><button disabled={page === 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>上一页</button><button disabled={page === totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>下一页</button></div></div></>}
    </main>
    <aside className="home-section-sidebar factor-signal-sidebar"><FactorActivityRanking factors={allFactors} period={activityPeriod} onPeriodChange={setActivityPeriod} onOpen={openFactor} loading={isLoading} /></aside>
  </div>
}

function factorUpdated(value: string | null) { if (!value) return '暂无事件'; const date = new Date(value.replace(' ', 'T')); if (Number.isNaN(date.getTime())) return value.slice(0, 10); return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(date) }
function FactorMiniTrend({ values }: { values: number[] }) { if (!values.length) return <span className="factor-mini-trend-empty">暂无趋势</span>; const max = Math.max(...values, 1); const min = Math.min(...values, 0); const range = max - min || 1; const coords = values.map((value, index) => ({ x: index * (100 / Math.max(values.length - 1, 1)), y: 26 - ((value - min) / range) * 20 })); const clampY = (value: number) => Math.max(3, Math.min(27, value)); let path = `M ${coords[0].x.toFixed(1)} ${coords[0].y.toFixed(1)}`; for (let index = 0; index < coords.length - 1; index++) { const previous = coords[index - 1] || coords[index]; const current = coords[index]; const next = coords[index + 1]; const afterNext = coords[index + 2] || next; const control1 = { x: current.x + (next.x - previous.x) / 6, y: clampY(current.y + (next.y - previous.y) / 6) }; const control2 = { x: next.x - (afterNext.x - current.x) / 6, y: clampY(next.y - (afterNext.y - current.y) / 6) }; path += ` C ${control1.x.toFixed(1)} ${control1.y.toFixed(1)}, ${control2.x.toFixed(1)} ${control2.y.toFixed(1)}, ${next.x.toFixed(1)} ${next.y.toFixed(1)}` } return <svg className="factor-mini-trend mx-auto" viewBox="0 0 100 30" preserveAspectRatio="none" aria-label={`最近七日活跃度：${values.join('、')}`}><path d={path} /></svg> }

function FilterDropdown({ label, value, options, onChange }: { label: string; value: string; options: string[][]; onChange: (value: string) => void }) { const [open, setOpen] = useState(false); const selected = options.find(option => option[0] === value)?.[1] || value; return <div className="factor-filter-dropdown"><button type="button" onClick={() => setOpen(current => !current)} aria-expanded={open}><span>{label}</span><b>{selected}</b><i /></button>{open && <div className="factor-filter-menu">{options.map(([key, text]) => <button type="button" key={key} className={key === value ? 'active' : ''} onClick={() => { onChange(key); setOpen(false) }}>{text}</button>)}</div>}</div> }

const RANKING_COLOR = '#f97316'
const RANKING_GRADIENT = 'linear-gradient(90deg, #f59e0b 0%, #f97316 48%, #ef4444 100%)'
function FactorActivityRanking({ factors, period, onPeriodChange, onOpen, loading }: { factors: Factor[]; period: ActivityPeriod; onPeriodChange: (period: ActivityPeriod) => void; onOpen: (factor: Factor) => void; loading: boolean }) { const field: Record<ActivityPeriod, keyof Factor> = { '7d': 'activity_7d', '30d': 'activity_30d', '365d': 'activity_365d' }; const ranking = [...factors].sort((a, b) => Number(b[field[period]]) - Number(a[field[period]])).slice(0, 10); const max = Math.max(...ranking.map(item => Number(item[field[period]])), 1); return <section className="factor-activity-ranking-panel"><header><div><h2>活跃因子 Top 10</h2><p>按关联事件数量排名</p></div></header><div className="factor-ranking-periods">{([['7d', '近7日'], ['30d', '近30日'], ['365d', '近1年']] as [ActivityPeriod, string][]).map(([key, text]) => <button type="button" key={key} className={period === key ? 'active' : ''} onClick={() => onPeriodChange(key)}>{text}</button>)}</div>{loading ? <Skeleton height="360px" variant="rectangular" /> : <ol className="factor-activity-ranking">{ranking.map((factor, index) => { const count = Number(factor[field[period]]); return <li key={factor.id}><button type="button" onClick={() => onOpen(factor)}><span className="factor-ranking-copy"><em style={{ color: RANKING_COLOR }}>{index + 1}</em><b title={factor.name}>{factor.name}</b><strong>{count}</strong></span><span className="factor-ranking-track"><i style={{ width: `${count ? Math.max(4, (count / max) * 100) : 0}%`, backgroundImage: RANKING_GRADIENT }} /></span></button></li> })}</ol>}</section> }

function MacroWorkspace({ presetCodes }: { presetCodes: string[] }) {
  const [domain, setDomain] = useState('price'); const [mode, setMode] = useState<'single' | 'compare'>('compare'); const [selected, setSelected] = useState<string[]>([])
  const { data: indicators, isLoading } = useQuery({ queryKey: ['macro-indicators'], queryFn: fetchMacroIndicators, staleTime: 10 * 60 * 1000 })
  const list = useMemo(() => (indicators?.indicators || []).filter((i: any) => i.domain === domain), [indicators, domain])
  const presetSignature = presetCodes.join(',')
  useEffect(() => {
    if (!presetCodes.length || !indicators?.indicators?.length) return
    const available = presetCodes.filter((code) => indicators.indicators.some((item: any) => item.code === code)).slice(0, 4)
    if (!available.length) return
    const first = indicators.indicators.find((item: any) => item.code === available[0])
    if (first?.domain) setDomain(first.domain)
    setMode(available.length === 1 ? 'single' : 'compare')
    setSelected(available)
  }, [indicators, presetSignature])
  useEffect(() => { if (!presetCodes.length && list.length) setSelected(mode === 'single' ? [list[0].code] : list.slice(0, 3).map((i: any) => i.code)) }, [domain, mode, list, presetSignature])
  const { data: chartData, isLoading: chartLoading } = useQuery({ queryKey: ['macro-data', selected], queryFn: () => fetchMacroData(selected, '202101', '202612'), enabled: selected.length > 0, staleTime: 10 * 60 * 1000 })
  const option = useMemo(() => {
    const series = (chartData?.indicators || []).map((item: any) => {
      const isPercent = item.name.includes('增速') || item.name.includes('(%)')
      return { name: item.name, type: 'line', smooth: true, showSymbol: false, yAxisIndex: isPercent ? 1 : 0, data: item.data.map((point: any) => point.value) }
    })
    const hasPercentSeries = series.some((item: any) => item.yAxisIndex === 1)
    return {
      tooltip: { trigger: 'axis' },
      legend: { top: 10, left: 48, right: 64, type: 'scroll', textStyle: { color: '#aaa' } },
      grid: { left: 48, right: hasPercentSeries ? 64 : 20, top: 72, bottom: 42 },
      xAxis: { type: 'category', data: chartData?.indicators?.[0]?.data?.map((point: any) => point.datestr) || [], axisLabel: { color: '#777' }, axisLine: { lineStyle: { color: '#333' } } },
      yAxis: [
        { type: 'value', splitLine: { lineStyle: { color: '#262626' } }, axisLabel: { color: '#777' } },
        { type: 'value', show: hasPercentSeries, position: 'right', name: '%', nameTextStyle: { color: '#777' }, splitLine: { show: false }, axisLabel: { color: '#777', formatter: '{value}%' } },
      ],
      series,
    }
  }, [chartData])
  const toggle = (code: string) => setSelected(prev => mode === 'single' ? [code] : prev.includes(code) ? prev.filter(x => x !== code) : prev.length < 4 ? [...prev, code] : prev)
  return <div className="home-section-grid"><main className="home-section-main rounded-xl border border-[#2a2a2e] bg-[#111111] p-5 overflow-hidden"><div className="flex justify-between gap-3 mb-4"><div><h2 className="text-base font-semibold text-white">{mode === 'single' ? '单指标走势' : '多指标对比'}</h2><p className="text-xs text-gray-500 mt-1">{selected.length} 项已选择</p></div><div className="factor-mode-tabs">{(['compare', 'single'] as const).map(k => <button key={k} onClick={() => setMode(k)} className={`factor-mode-tab${mode === k ? ' active' : ''}`}>{k === 'compare' ? '多指标对比' : '单指标'}</button>)}</div></div>{chartLoading ? <Skeleton height="340px" variant="rectangular" /> : <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 360 }} />}</main><aside className="home-section-sidebar factor-macro-sidebar rounded-xl border border-[#2a2a2e] bg-[#111111]"><div className="p-4 border-b border-[#2a2a2e]"><h2 className="text-sm font-semibold text-white">指标筛选</h2><div className="flex flex-wrap gap-2 mt-3">{DOMAINS.map(([key, label]) => <FilterButton key={key} active={domain === key} onClick={() => setDomain(key)}>{label}</FilterButton>)}</div></div><div className="p-2">{isLoading ? <Skeleton height="200px" variant="rectangular" /> : list.map((i: any) => <div key={i.code} className="flex items-center gap-2 rounded-lg px-2 py-2.5 hover:bg-[#181818]"><label className="flex min-w-0 flex-1 cursor-pointer gap-3"><input type={mode === 'single' ? 'radio' : 'checkbox'} name="macro-indicator" checked={selected.includes(i.code)} onChange={() => toggle(i.code)} className="mt-0.5 accent-amber-500" /><span className="min-w-0"><span className="block truncate text-sm text-gray-200">{i.name}</span><span className="block truncate text-xs text-gray-600">{i.code}</span></span></label><WatchlistAction objectType="macro_signal" objectId={i.code} title={i.name} sourceUrl="/factors?view=macro" className="shrink-0" /></div>)}</div></aside></div>
}
function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) { return <button onClick={onClick} className={`factor-filter-tab${active ? ' active' : ''}`}>{children}</button> }
function Empty({ text }: { text: string }) { return <div className="h-full min-h-[240px] rounded-xl border border-[#2a2a2e] bg-[#111111] flex items-center justify-center text-sm text-gray-600 text-center p-6">{text}</div> }
