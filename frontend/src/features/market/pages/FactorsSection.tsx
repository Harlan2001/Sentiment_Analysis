import React, { useEffect, useMemo, useState } from 'react'
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

export default function FactorsSection() {
  const [view, setView] = useState<'signals' | 'macro'>('signals')
  const [selectedFactor, setSelectedFactor] = useState<Factor | null>(null)
  return <div className="flex flex-col h-full overflow-hidden p-5">
    <div className="flex items-center gap-2 mb-5 shrink-0">
      {(['signals', 'macro'] as const).map(key => <button key={key} onClick={() => setView(key)} className={`px-4 py-2 rounded-lg text-sm border transition-colors ${view === key ? 'border-amber-500/50 bg-amber-500/10 text-amber-400' : 'border-[#2a2a2e] text-gray-500 hover:text-gray-200'}`}>
        {key === 'signals' ? '因子信号' : '宏观数据'}
      </button>)}
    </div>
    {view === 'signals' ? <FactorSignals selectedFactor={selectedFactor} onSelect={setSelectedFactor} /> : <MacroWorkspace />}
  </div>
}

function FactorSignals({ selectedFactor, onSelect }: { selectedFactor: Factor | null; onSelect: (factor: Factor) => void }) {
  const [category, setCategory] = useState('ALL')
  const [query, setQuery] = useState('')
  const { data, isLoading, isError } = useQuery({ queryKey: ['factors-all'], queryFn: fetchAllFactors, staleTime: 5 * 60 * 1000 })
  const factors = useMemo(() => ((data?.factors || []) as Factor[]).filter(f => (category === 'ALL' || f.category === category) && (`${f.name}${f.code}`).toLowerCase().includes(query.toLowerCase())).sort((a, b) => (b.recent_news_count || 0) - (a.recent_news_count || 0)), [data, category, query])
  const categories = useMemo(() => [...new Set((data?.factors || []).map((f: Factor) => f.category))], [data])
  return <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(300px,3fr)] gap-4 min-h-0 flex-1">
    <main className="min-w-0 overflow-y-auto pr-1">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <label className="flex items-center gap-2 h-9 px-3 rounded-lg border border-[#2a2a2e] bg-[#0d0d0d] text-gray-500 w-64"><span>⌕</span><input className="w-full bg-transparent border-0 outline-0 text-sm text-gray-200 placeholder-gray-600" value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索因子名称或代码" /></label>
        <span className="text-xs text-gray-600">{factors.length} 个因子</span>
      </div>
      <div className="flex gap-2 flex-wrap mb-4">
        <FilterButton active={category === 'ALL'} onClick={() => setCategory('ALL')}>全部</FilterButton>
        {categories.map(key => <FilterButton key={key} active={category === key} onClick={() => setCategory(key)}>{CATEGORIES[key] || key}</FilterButton>)}
      </div>
      {isLoading ? <Skeleton height="360px" variant="rectangular" /> : isError ? <Empty text="因子数据加载失败" /> : <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] overflow-hidden">
        <table className="w-full text-left"><thead><tr className="border-b border-[#2a2a2e] text-xs text-gray-500"><th className="px-4 py-3">因子</th><th className="px-4 py-3">分类</th><th className="px-4 py-3">类型</th><th className="px-4 py-3 text-right">近 30 天新闻</th></tr></thead>
          <tbody>{factors.map(f => <tr key={f.code} onClick={() => onSelect(f)} className={`cursor-pointer border-b border-[#1e1e1e] hover:bg-[#181818] ${selectedFactor?.code === f.code ? 'bg-amber-500/5' : ''}`}><td className="px-4 py-3"><div className="text-sm text-gray-200 font-medium">{f.name}</div><div className="text-xs text-gray-600 mt-0.5">{f.code}</div></td><td className="px-4 py-3 text-sm text-gray-400">{CATEGORIES[f.category] || f.category}</td><td className="px-4 py-3 text-sm text-gray-500">{f.factor_type || '-'}</td><td className="px-4 py-3 text-right text-sm text-amber-400">{f.recent_news_count || 0}</td></tr>)}</tbody>
        </table>
      </div>}
    </main>
    <aside className="min-w-0 overflow-y-auto pr-1"><FactorSidebar factor={selectedFactor} /></aside>
  </div>
}

function FactorSidebar({ factor }: { factor: Factor | null }) {
  const { data, isLoading } = useQuery<FactorDetailData>({ queryKey: ['factor-detail', factor?.id], queryFn: () => fetchFactorDetail(factor!.id), enabled: !!factor, staleTime: 60 * 1000 })
  if (!factor) return <Empty text="选择一个因子，查看走势与相关新闻" />
  if (isLoading) return <Skeleton height="360px" variant="rectangular" />
  if (!data || 'error' in data) return <Empty text="未能加载因子详情" />
  const dates = data.daily_counts.map(d => d.date.slice(5)); const values = data.daily_counts.map(d => d.count)
  return <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4 space-y-5"><div><p className="text-xs text-gray-500">{data.category}</p><h2 className="text-base font-semibold text-white mt-1">{data.name}</h2><p className="text-xs text-gray-500 mt-1">近 7 天 {data.news_count} 条关联新闻</p></div>
    <div><h3 className="text-xs font-medium text-gray-400 mb-2">活跃度走势</h3><ReactECharts opts={{ renderer: 'svg' }} style={{ height: 190 }} option={{ grid: { left: 26, right: 8, top: 12, bottom: 26 }, xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#333' } }, axisLabel: { color: '#777', fontSize: 10 } }, yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#262626' } }, axisLabel: { color: '#777', fontSize: 10 } }, series: [{ type: 'bar', data: values, barMaxWidth: 22, itemStyle: { color: '#d97706', borderRadius: [3, 3, 0, 0] } }], tooltip: { trigger: 'axis' } }} /></div>
    <div><h3 className="text-xs font-medium text-gray-400 mb-2">相关新闻</h3><div className="space-y-2">{data.related_news.length ? data.related_news.map(n => <div key={n.id} className="rounded-lg border border-[#1e1e1e] bg-[#0d0d0d] p-3"><div className="flex gap-2 text-xs text-gray-500 mb-1"><span>{n.pub_time.slice(5, 16)}</span>{n.direction && <span className={n.direction === 'positive' ? 'text-red-400' : 'text-green-400'}>{n.direction === 'positive' ? '利多' : '利空'}</span>}</div><p className="text-sm leading-snug text-gray-200 line-clamp-2">{n.title}</p></div>) : <p className="text-sm text-gray-600 py-4 text-center">暂无相关新闻</p>}</div></div>
  </section>
}

function MacroWorkspace() {
  const [domain, setDomain] = useState('price'); const [mode, setMode] = useState<'single' | 'compare'>('compare'); const [selected, setSelected] = useState<string[]>([])
  const { data: indicators, isLoading } = useQuery({ queryKey: ['macro-indicators'], queryFn: fetchMacroIndicators, staleTime: 10 * 60 * 1000 })
  const list = useMemo(() => (indicators?.indicators || []).filter((i: any) => i.domain === domain), [indicators, domain])
  useEffect(() => { if (list.length) setSelected(mode === 'single' ? [list[0].code] : list.slice(0, 3).map((i: any) => i.code)) }, [domain, mode, list])
  const { data: chartData, isLoading: chartLoading } = useQuery({ queryKey: ['macro-data', selected], queryFn: () => fetchMacroData(selected, '202101', '202612'), enabled: selected.length > 0, staleTime: 10 * 60 * 1000 })
  const option = useMemo(() => ({ tooltip: { trigger: 'axis' }, legend: { textStyle: { color: '#aaa' } }, grid: { left: 48, right: 20, top: 36, bottom: 34 }, xAxis: { type: 'category', data: chartData?.indicators?.[0]?.data?.map((d: any) => d.datestr) || [], axisLabel: { color: '#777' }, axisLine: { lineStyle: { color: '#333' } } }, yAxis: { type: 'value', splitLine: { lineStyle: { color: '#262626' } }, axisLabel: { color: '#777' } }, series: (chartData?.indicators || []).map((i: any) => ({ name: i.name, type: 'line', smooth: true, showSymbol: false, data: i.data.map((d: any) => d.value) })) }), [chartData])
  const toggle = (code: string) => setSelected(prev => mode === 'single' ? [code] : prev.includes(code) ? prev.filter(x => x !== code) : prev.length < 4 ? [...prev, code] : prev)
  return <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(300px,3fr)] gap-4 min-h-0 flex-1"><main className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5 min-h-[440px] overflow-hidden"><div className="flex justify-between gap-3 mb-4"><div><h2 className="text-base font-semibold text-white">{mode === 'single' ? '单指标走势' : '多指标对比'}</h2><p className="text-xs text-gray-500 mt-1">{selected.length} 项已选择</p></div><div className="flex overflow-hidden rounded-lg border border-[#2a2a2e]">{(['compare', 'single'] as const).map(k => <button key={k} onClick={() => setMode(k)} className={`px-3 text-xs ${mode === k ? 'bg-amber-500/15 text-amber-400' : 'text-gray-500'}`}>{k === 'compare' ? '多指标对比' : '单指标'}</button>)}</div></div>{chartLoading ? <Skeleton height="340px" variant="rectangular" /> : <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 360 }} />}</main><aside className="rounded-xl border border-[#2a2a2e] bg-[#111111] overflow-y-auto"><div className="p-4 border-b border-[#2a2a2e]"><h2 className="text-sm font-semibold text-white">指标筛选</h2><div className="flex flex-wrap gap-2 mt-3">{DOMAINS.map(([key, label]) => <FilterButton key={key} active={domain === key} onClick={() => setDomain(key)}>{label}</FilterButton>)}</div></div><div className="p-2">{isLoading ? <Skeleton height="200px" variant="rectangular" /> : list.map((i: any) => <label key={i.code} className="flex gap-3 px-2 py-2.5 rounded-lg hover:bg-[#181818] cursor-pointer"><input type={mode === 'single' ? 'radio' : 'checkbox'} name="macro-indicator" checked={selected.includes(i.code)} onChange={() => toggle(i.code)} className="accent-amber-500 mt-0.5" /><span className="min-w-0"><span className="block text-sm text-gray-200 truncate">{i.name}</span><span className="block text-xs text-gray-600 truncate">{i.code}</span></span></label>)}</div></aside></div>
}
function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) { return <button onClick={onClick} className={`px-2.5 py-1 rounded-lg text-xs border ${active ? 'border-amber-500/40 bg-amber-500/10 text-amber-400' : 'border-[#2a2a2e] text-gray-500 hover:text-gray-300'}`}>{children}</button> }
function Empty({ text }: { text: string }) { return <div className="h-full min-h-[240px] rounded-xl border border-[#2a2a2e] bg-[#111111] flex items-center justify-center text-sm text-gray-600 text-center p-6">{text}</div> }
