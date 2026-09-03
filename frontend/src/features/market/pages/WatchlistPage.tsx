import { useCallback, useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { Link, useLocation } from 'react-router-dom'
import { fetchFactorDetail, fetchMacroData, fetchNewsById } from '@/api/market'
import { getWatchlistItems, removeWatchlistItem, type WatchlistItem, type WatchlistObjectType } from '@/api/watchlist'

type View = 'news' | 'factor' | 'macro_signal'
type NewsAI = { direction?: string; reason?: string }
const palette = ['#5b8ff9', '#61d9a5', '#f6bd16', '#e8684a', '#6dc8ec', '#9270ca']
const lineTypes = ['solid', 'dashed', 'dotted', 'solid', 'dashed', 'dotted'] as const
const symbols = ['circle', 'rect', 'triangle', 'diamond', 'pin', 'arrow'] as const
const viewNames: Record<View, string> = { news: '新闻情绪', factor: '因子走势', macro_signal: '宏观数据' }
const typeNames: Record<View, string> = { news: '新闻', factor: '因子', macro_signal: '宏观' }
const directions: Record<string, string> = { positive: '利多', bullish: '利多', negative: '利空', bearish: '利空', neutral: '中性' }
const newsAnalysisCache = new Map<string, NewsAI>()

function baseLineOption(name: string, dates: string[], values: Array<number | null>, color: string) {
  return {
    animationDuration: 300,
    color: [color],
    tooltip: { trigger: 'axis', backgroundColor: '#202024', borderColor: '#3a3a40', textStyle: { color: '#eee', fontSize: 11 }, axisPointer: { type: 'line', lineStyle: { color: '#666', type: 'dashed' } } },
    grid: { left: 48, right: 18, top: 18, bottom: 34, containLabel: false },
    xAxis: { type: 'category', boundaryGap: false, data: dates, axisLabel: { color: '#777', fontSize: 10, hideOverlap: true, margin: 11 }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#333' } } },
    yAxis: { type: 'value', scale: true, splitNumber: 3, axisLabel: { color: '#777', fontSize: 10, margin: 9 }, axisTick: { show: false }, axisLine: { show: false }, splitLine: { lineStyle: { color: '#28282d', type: 'dashed' } } },
    series: [{ name, type: 'line', smooth: .35, showSymbol: values.length <= 12, symbol: 'circle', symbolSize: 5, lineStyle: { width: 2.25, color }, itemStyle: { color, borderColor: '#111', borderWidth: 1 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: `${color}38` }, { offset: 1, color: `${color}00` }] } }, emphasis: { focus: 'series', scale: true }, data: values }],
  }
}

export default function WatchlistPage() {
  const location = useLocation()
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [view, setView] = useState<View>('news')
  const [newsAI, setNewsAI] = useState<Record<string, NewsAI>>({})
  const [newsAnalysisReady, setNewsAnalysisReady] = useState(false)
  const [factorData, setFactorData] = useState<Record<string, any>>({})
  const [macroData, setMacroData] = useState<Record<string, any>>({})
  const [selectedFactors, setSelectedFactors] = useState<string[]>([])
  const [selectedMacros, setSelectedMacros] = useState<string[]>([])

  const load = useCallback(async () => setItems((await getWatchlistItems()).items), [])
  useEffect(() => { void load() }, [load, location.key])
  useEffect(() => { const refresh = () => void load(); window.addEventListener('bondsense-watchlist-changed', refresh); return () => window.removeEventListener('bondsense-watchlist-changed', refresh) }, [load])

  const newsItems = useMemo(() => items.filter(item => item.object_type === 'news'), [items])
  const factorItems = useMemo(() => items.filter(item => item.object_type === 'factor'), [items])
  const macroItems = useMemo(() => items.filter(item => item.object_type === 'macro_signal'), [items])
  const visibleItems = view === 'news' ? newsItems : view === 'factor' ? factorItems : macroItems

  useEffect(() => {
    let active = true
    const cached = Object.fromEntries(newsItems.flatMap(item => newsAnalysisCache.has(item.object_id) ? [[item.id, newsAnalysisCache.get(item.object_id)!]] : []))
    setNewsAI(cached)
    const missing = newsItems.filter(item => !newsAnalysisCache.has(item.object_id))
    if (!missing.length) { setNewsAnalysisReady(true); return () => { active = false } }
    setNewsAnalysisReady(false)
    Promise.all(missing.map(async item => {
      try { const detail: any = await fetchNewsById(Number(item.object_id), undefined, true); const analysis = detail.analyses?.[0] || detail; return [item.id, { direction: detail.direction || analysis.direction, reason: detail.reason || analysis.reason }] as const }
      catch { return [item.id, {}] as const }
    })).then(rows => { if (!active) return; rows.forEach(([itemId, analysis]) => { const item = newsItems.find(value => value.id === itemId); if (item) newsAnalysisCache.set(item.object_id, analysis) }); setNewsAI(Object.fromEntries(newsItems.map(item => [item.id, newsAnalysisCache.get(item.object_id) || {}]))); setNewsAnalysisReady(true) })
    return () => { active = false }
  }, [newsItems])

  useEffect(() => {
    let active = true
    Promise.all(factorItems.map(async item => [item.object_id, await fetchFactorDetail(Number(item.object_id))] as const)).then(rows => { if (active) setFactorData(Object.fromEntries(rows)) }).catch(() => { if (active) setFactorData({}) })
    setSelectedFactors(current => current.filter(id => factorItems.some(item => item.object_id === id)).slice(0, 6).length ? current.filter(id => factorItems.some(item => item.object_id === id)).slice(0, 6) : factorItems.slice(0, 1).map(item => item.object_id))
    return () => { active = false }
  }, [factorItems])

  useEffect(() => {
    let active = true; const codes = macroItems.map(item => item.object_id)
    if (codes.length) fetchMacroData(codes).then((response: any) => { if (active) setMacroData(Object.fromEntries((response.indicators || []).map((row: any) => [row.zbcode, row]))) }).catch(() => { if (active) setMacroData({}) })
    else setMacroData({})
    setSelectedMacros(current => current.filter(id => codes.includes(id)).slice(0, 6).length ? current.filter(id => codes.includes(id)).slice(0, 6) : codes.slice(0, 1))
    return () => { active = false }
  }, [macroItems])

  const toggleSeries = (id: string) => {
    const setter = view === 'factor' ? setSelectedFactors : setSelectedMacros
    setter(current => current.includes(id) ? current.filter(value => value !== id) : current.length < 6 ? [...current, id] : current)
  }
  const remove = async (item: WatchlistItem) => { await removeWatchlistItem(item.id); await load(); window.dispatchEvent(new Event('bondsense-watchlist-changed')) }
  const counts = newsItems.reduce((result, item) => { const key = directions[newsAI[item.id]?.direction || 'neutral'] || '中性'; result[key] = (result[key] || 0) + 1; return result }, {} as Record<string, number>)
  const narrative = newsItems.filter(item => newsAI[item.id]?.reason).slice(0, 8)
  const sentimentOption = { animationDuration: 300, tooltip: { trigger: 'item', backgroundColor: '#202024', borderColor: '#3a3a40', textStyle: { color: '#eee' }, formatter: '{b}：{c} 条' }, grid: { left: 48, right: 28, top: 34, bottom: 38 }, xAxis: { type: 'category', data: ['利多', '中性', '利空'], axisLabel: { color: '#aaa', fontSize: 11, margin: 12 }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#333' } } }, yAxis: { type: 'value', minInterval: 1, splitNumber: 4, axisLabel: { color: '#777', fontSize: 10 }, axisTick: { show: false }, axisLine: { show: false }, splitLine: { lineStyle: { color: '#29292e', type: 'dashed' } } }, series: [{ type: 'bar', barMaxWidth: 52, label: { show: true, position: 'top', color: '#d4d4d8', fontSize: 12, fontWeight: 600 }, emphasis: { focus: 'self' }, data: [{ value: counts.利多 || 0, itemStyle: { color: '#fb7185', borderRadius: [6, 6, 0, 0] } }, { value: counts.中性 || 0, itemStyle: { color: '#a3a3a3', borderRadius: [6, 6, 0, 0] } }, { value: counts.利空 || 0, itemStyle: { color: '#34d399', borderRadius: [6, 6, 0, 0] } }] }] }

  const changeView = (next: View) => setView(next)
  return <div className="watchlist-workspace flex min-w-0">
    <main className="min-w-0 flex-1 space-y-3 px-4 py-3">
      <header><h1 className="text-lg font-semibold text-white">关注列表</h1></header>
      <section className="min-h-[250px] rounded-xl border border-[#3a3a40] bg-[#111] p-5"><div className="flex justify-between"><b className="text-base text-white">今日关注叙事</b><span className="text-[11px] text-gray-600">新闻 AI 摘要</span></div><div className="mt-4 max-h-44 space-y-2 overflow-y-auto pr-2 text-xs leading-6 text-gray-400">{narrative.length ? narrative.map(item => <p key={item.id}><b className={(directions[newsAI[item.id]?.direction || 'neutral'] || '中性') === '利多' ? 'text-rose-300' : (directions[newsAI[item.id]?.direction || 'neutral'] || '中性') === '利空' ? 'text-emerald-300' : 'text-gray-300'}>{directions[newsAI[item.id]?.direction || 'neutral'] || '中性'}：</b>{newsAI[item.id]?.reason}</p>) : <p className="text-gray-600">暂无已保存的新闻 AI 分析。</p>}</div></section>
      <section className="rounded-xl border border-[#2a2a2e] bg-[#111] p-3"><div className="flex items-center justify-between"><b className="text-sm text-white">数据分析</b><div className="flex rounded border border-[#343438] p-0.5">{(['news', 'factor', 'macro_signal'] as View[]).map(key => <button key={key} onClick={() => changeView(key)} className={`rounded px-2 py-1 text-[11px] ${view === key ? 'bg-white text-black' : 'text-gray-500'}`}>{viewNames[key]}</button>)}</div></div>
        {view === 'news' ? newsAnalysisReady ? <ReactECharts key="news-chart" notMerge opts={{ renderer: 'svg' }} style={{ height: 260 }} option={sentimentOption} /> : <div className="flex h-[260px] items-center justify-center"><div className="text-center"><span className="mx-auto block h-5 w-5 animate-spin rounded-full border-2 border-gray-700 border-t-gray-300" /><p className="mt-3 text-xs text-gray-600">正在加载新闻分类分析…</p></div></div> : <CombinedChart view={view} items={visibleItems} selected={view === 'factor' ? selectedFactors : selectedMacros} factorData={factorData} macroData={macroData} />}
      </section>
    </main>
    <aside className="sticky top-0 h-full w-[21rem] shrink-0 border-l border-[#2a2a2e] bg-[#111]"><div className="border-b border-[#2a2a2e] p-3"><b className="text-sm text-white">{typeNames[view]}关注列表</b><p className="mt-1 text-[11px] text-gray-600">{view === 'news' ? '查看详情或取消关注' : '点击整行控制左侧图表，最多选择 6 项'}</p></div><div className="p-2">{visibleItems.map((item, index) => { const selected = view === 'factor' ? selectedFactors.includes(item.object_id) : view === 'macro_signal' ? selectedMacros.includes(item.object_id) : false; return <div key={item.id} role={view === 'news' ? undefined : 'button'} tabIndex={view === 'news' ? undefined : 0} onClick={() => { if (view !== 'news') toggleSeries(item.object_id) }} onKeyDown={event => { if (view !== 'news' && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); toggleSeries(item.object_id) } }} className={`mb-1 rounded-lg p-3 ${view === 'news' ? '' : 'cursor-pointer'} ${selected ? 'bg-[#303034]' : 'hover:bg-[#19191c]'}`}><div className="flex w-full items-start gap-2 text-left">{selected && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: palette[index % palette.length] }} />}<b className="min-w-0 flex-1 truncate text-xs text-gray-200">{item.title}</b></div><div className="mt-2 flex gap-3 text-[11px]">{item.source_url && <Link to={item.source_url} onClick={event => event.stopPropagation()} className="text-gray-400 hover:text-white">查看详情</Link>}<button type="button" onClick={event => { event.stopPropagation(); void remove(item) }} className="text-rose-300">取消关注</button></div></div>})}</div></aside>
  </div>
}

function CombinedChart({ view, items, selected, factorData, macroData }: { view: Exclude<View, 'news'>; items: WatchlistItem[]; selected: string[]; factorData: Record<string, any>; macroData: Record<string, any> }) {
  const shown = items.filter(item => selected.includes(item.object_id)).slice(0, 6)
  if (!shown.length) return <div className="flex h-[260px] items-center justify-center text-xs text-gray-600">从右侧选择要展示的{view === 'factor' ? '因子' : '宏观指标'}。</div>
  const allDates = Array.from(new Set(shown.flatMap(item => { const raw = view === 'factor' ? factorData[item.object_id] : macroData[item.object_id]; return (view === 'factor' ? raw?.daily_counts || [] : raw?.data || []).map((point: any) => view === 'factor' ? point.date : point.datestr) }))).sort()
  const prepared = shown.map(item => { const raw = view === 'factor' ? factorData[item.object_id] : macroData[item.object_id]; const points = view === 'factor' ? raw?.daily_counts || [] : raw?.data || []; const map = new Map(points.map((point: any) => [view === 'factor' ? point.date : point.datestr, view === 'factor' ? point.count : point.value])); const rawValues = allDates.map(date => map.get(date) ?? null) as Array<number | null>; const first = rawValues.find(value => typeof value === 'number' && value !== 0); const data = view === 'macro_signal' && typeof first === 'number' ? rawValues.map(value => typeof value === 'number' ? +(value / first * 100).toFixed(3) : null) : rawValues; return { item, data, signature: JSON.stringify(data), colorIndex: Math.max(0, items.findIndex(value => value.id === item.id)) % palette.length } })
  const signatureCounts = prepared.reduce((counts, row) => counts.set(row.signature, (counts.get(row.signature) || 0) + 1), new Map<string, number>())
  const signaturePosition = new Map<string, number>()
  const series = prepared.map((row, index) => { const duplicateCount = signatureCounts.get(row.signature) || 1; const duplicateIndex = signaturePosition.get(row.signature) || 0; signaturePosition.set(row.signature, duplicateIndex + 1); const duplicated = duplicateCount > 1; const width = duplicated ? Math.max(2.25, 7 - duplicateIndex * 2.25) : 2.25 + (index % 2) * .4; const seriesColor = palette[row.colorIndex]; return { name: row.item.title, type: 'line', smooth: .35, showSymbol: (view === 'factor' && allDates.length <= 16) || duplicated, symbol: symbols[row.colorIndex], symbolSize: duplicated ? 7 + duplicateIndex : 6 + row.colorIndex % 2, connectNulls: true, z: duplicated ? duplicateIndex + 2 : shown.length - index, lineStyle: { width, type: duplicated && duplicateIndex > 0 ? lineTypes[Math.min(duplicateIndex, lineTypes.length - 1)] : lineTypes[row.colorIndex], color: seriesColor, opacity: duplicated && duplicateIndex === 0 ? .72 : 1, cap: 'round', join: 'round' }, itemStyle: { color: seriesColor, borderColor: '#111', borderWidth: 1.5 }, emphasis: { focus: 'series', blurScope: 'coordinateSystem', lineStyle: { width: Math.max(4, width + 1.5), opacity: 1 } }, data: row.data } })
  const option = { animationDuration: 450, color: palette, tooltip: { trigger: 'axis', confine: true, backgroundColor: 'rgba(28,28,32,.96)', borderColor: '#45454c', borderWidth: 1, padding: [9, 11], textStyle: { color: '#eee', fontSize: 11 }, axisPointer: { type: 'cross', lineStyle: { color: '#666', type: 'dashed' }, label: { backgroundColor: '#3b3b42' } } }, legend: { type: 'scroll', top: 10, left: 16, right: 16, selectedMode: false, icon: 'roundRect', itemWidth: 18, itemHeight: 3, textStyle: { color: '#b2b2b8', fontSize: 10 }, itemGap: 18, pageTextStyle: { color: '#888' }, pageIconColor: '#aaa', pageIconInactiveColor: '#444' }, grid: { left: 58, right: 24, top: 62, bottom: allDates.length > 18 ? 62 : 40 }, xAxis: { type: 'category', boundaryGap: false, data: allDates, axisLabel: { color: '#777', fontSize: 10, hideOverlap: true, margin: 12 }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#38383e' } } }, yAxis: { type: 'value', scale: true, splitNumber: 4, name: view === 'macro_signal' ? '首期=100' : '关联新闻数', nameGap: 18, nameTextStyle: { color: '#777', fontSize: 10 }, axisLabel: { color: '#777', fontSize: 10 }, axisTick: { show: false }, axisLine: { show: false }, splitLine: { lineStyle: { color: '#2a2a30', type: 'dashed' } } }, dataZoom: allDates.length > 18 ? [{ type: 'inside', start: 55, end: 100 }, { type: 'slider', height: 14, bottom: 10, borderColor: 'transparent', backgroundColor: '#1b1b1f', fillerColor: 'rgba(120,120,135,.22)', handleStyle: { color: '#777' }, textStyle: { color: '#666' }, showDetail: false }] : [], series }
  return <div className="mt-3 overflow-hidden rounded-lg bg-gradient-to-b from-[#17171b] to-[#111111] px-2 pt-1"><ReactECharts key={`${view}-${selected.join('-')}`} notMerge opts={{ renderer: 'svg' }} style={{ height: 360, width: '100%' }} option={option} /></div>
}
