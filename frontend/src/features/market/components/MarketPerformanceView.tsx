import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { Link } from 'react-router-dom'
import { fetchMarketPanel } from '@/api/market'
import { fetchCreditSpreadOverview } from '@/api/creditSpread'
import { fetchFuturesOverview, fetchFuturesTrend } from '@/api/futures'
import { fetchTreasurySpread } from '@/api/treasury'
import { Skeleton } from '@/components/ui'
import type { AssetScope } from './AssetScopeStrip'
import './market-performance.css'

type PerformanceAsset = Exclude<AssetScope, 'all'>

interface Props {
  asset: AssetScope
  onOpen: (asset: PerformanceAsset) => void
}

interface ChangePoint {
  date: string
  value: number
  change: number | null
}

const ASSET_META: Record<PerformanceAsset, { name: string; color: string }> = {
  cgb: { name: '中国国债', color: '#7aa2f7' },
  credit: { name: '信用债', color: '#c792ea' },
  futures: { name: '国债期货', color: '#e7b66f' },
  ust: { name: '美债', color: '#65c9b2' },
}

const FUTURES_VARIETY_NAMES: Record<string, string> = {
  TS: '2年期国债期货',
  TF: '5年期国债期货',
  T: '10年期国债期货',
  TL: '30年期国债期货',
}

function signed(value: number | null, unit: string, digits = 1) {
  if (value === null || !Number.isFinite(value)) return '暂无前值'
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}${unit}`
}

function tone(value: number | null) {
  if (value === null || value === 0) return 'is-flat'
  return value > 0 ? 'is-up' : 'is-down'
}

function buildChanges<T>(series: T[], date: (item: T) => string, value: (item: T) => number, scale = 1): ChangePoint[] {
  return series.map((item, index) => {
    const current = value(item)
    const previous = index > 0 ? value(series[index - 1]) : null
    return { date: date(item), value: current, change: previous === null ? null : (current - previous) * scale }
  })
}

function changeChart(points: ChangePoint[], color: string, unit: string) {
  const visible = points.slice(-24)
  return {
    animationDuration: 300,
    grid: { left: 48, right: 16, top: 18, bottom: 28 },
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: 'rgba(24,24,28,.96)',
      borderColor: '#45454c',
      textStyle: { color: '#eee', fontSize: 11 },
      valueFormatter: (value: number) => signed(value, unit, unit === 'bp' ? 1 : 3),
    },
    xAxis: {
      type: 'category',
      data: visible.map((item) => item.date),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#303038' } },
      axisLabel: { color: '#686872', fontSize: 9, hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      splitNumber: 4,
      axisLabel: { color: '#686872', fontSize: 9, formatter: `{value}${unit}` },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#25252b', type: 'dashed' } },
    },
    series: [{
      type: 'bar',
      data: visible.map((item) => item.change),
      barMaxWidth: 13,
      itemStyle: {
        color: (params: { value: number | null }) => params.value === null || params.value === 0
          ? '#555761'
          : params.value > 0 ? color : '#67b99a',
        borderRadius: [2, 2, 0, 0],
      },
      markLine: { silent: true, symbol: 'none', lineStyle: { color: '#494a52', width: 1 }, data: [{ yAxis: 0 }] },
    }],
  }
}

function PerformanceCard({
  asset,
  metric,
  value,
  change,
  unit,
  date,
  status,
  loading,
  error,
  onOpen,
}: {
  asset: PerformanceAsset
  metric: string
  value: string
  change: number | null
  unit: string
  date: string | null
  status: string
  loading: boolean
  error: boolean
  onOpen: () => void
}) {
  const meta = ASSET_META[asset]
  return (
    <button type="button" className="performance-snapshot-card" onClick={onOpen}>
      <span className="performance-snapshot-accent" style={{ background: meta.color }} />
      <header><span>{meta.name}</span><em>查看分析 →</em></header>
      {loading ? <Skeleton height="92px" variant="rectangular" /> : error ? (
        <div className="performance-snapshot-state">数据暂不可用</div>
      ) : (
        <>
          <p>{metric}</p>
          <div className="performance-snapshot-value"><strong>{value}</strong><b className={tone(change)}>{signed(change, unit, unit === 'bp' ? 1 : 3)}</b></div>
          <small>{status}</small>
        </>
      )}
      <footer>{date ? `数据截至 ${date}` : '暂无有效数据日期'}</footer>
    </button>
  )
}

function PerformanceOverview({ onOpen }: { onOpen: Props['onOpen'] }) {
  const cgb = useQuery({ queryKey: ['market-performance', 'cgb'], queryFn: fetchMarketPanel, staleTime: 5 * 60 * 1000 })
  const credit = useQuery({ queryKey: ['market-performance', 'credit', '10Y'], queryFn: () => fetchCreditSpreadOverview('10Y'), staleTime: 5 * 60 * 1000 })
  const futures = useQuery({ queryKey: ['market-performance', 'futures', 'T'], queryFn: () => fetchFuturesTrend('T', 60), staleTime: 5 * 60 * 1000 })
  const futuresOverview = useQuery({ queryKey: ['market-performance', 'futures-overview'], queryFn: fetchFuturesOverview, staleTime: 5 * 60 * 1000 })
  const ust = useQuery({ queryKey: ['market-performance', 'ust', '10Y'], queryFn: () => fetchTreasurySpread('10Y'), staleTime: 5 * 60 * 1000 })

  const cgb10y = cgb.data?.yields.items.find((item) => item.period === '10Y')
  const creditPoints = buildChanges(credit.data?.series ?? [], (item) => item.date, (item) => item.spread_bp)
  const creditLatest = creditPoints.at(-1)
  const futuresSeries = (futures.data?.series ?? []).filter((item) => item.ratio !== null)
  const futuresPoints = buildChanges(futuresSeries, (item) => item.date, (item) => item.ratio!, 1)
  const futuresLatest = futuresPoints.at(-1)
  const ustPoints = buildChanges(ust.data?.series ?? [], (item) => item.date, (item) => item.us, 100)
  const ustLatest = ustPoints.at(-1)

  return (
    <section className="market-performance-overview">
      <header className="market-performance-overview-head">
        <div><p>MARKET MOVES</p><h2>最新市场变化</h2><span>这里关注较上一有效观测的变化和研究含义；历史水平与完整曲线请在“市场数据”查看。</span></div>
        <Link to="/info">查看历史市场数据 →</Link>
      </header>
      <div className="performance-snapshot-grid">
        <PerformanceCard
          asset="cgb" metric="10Y收益率日变动" value={cgb10y ? `${cgb10y.value.toFixed(3)}%` : '—'}
          change={cgb10y?.diff_bp ?? null} unit="bp" date={cgb.data?.yields.update_date ?? null}
          status="收益率变化，不等于债券投资收益" loading={cgb.isLoading} error={cgb.isError} onOpen={() => onOpen('cgb')}
        />
        <PerformanceCard
          asset="credit" metric="10Y整体信用利差日变动" value={credit.data?.latest ? `${credit.data.latest.spread_bp.toFixed(1)}bp` : '—'}
          change={creditLatest?.change ?? null} unit="bp" date={credit.data?.latest?.date ?? null}
          status="整体曲线口径，不代表评级或单券" loading={credit.isLoading} error={credit.isError} onOpen={() => onOpen('credit')}
        />
        <PerformanceCard
          asset="futures" metric="10年期国债期货会员多空比日变动" value={futuresLatest ? futuresLatest.value.toFixed(3) : '—'}
          change={futuresLatest?.change ?? null} unit="" date={futuresOverview.data?.trade_date ?? futuresLatest?.date ?? null}
          status="持仓结构观察，当前不是价格收益" loading={futures.isLoading || futuresOverview.isLoading} error={futures.isError || futuresOverview.isError} onOpen={() => onOpen('futures')}
        />
        <PerformanceCard
          asset="ust" metric="10Y美债收益率日变动" value={ust.data?.latest ? `${ust.data.latest.us.toFixed(3)}%` : '—'}
          change={ustLatest?.change ?? null} unit="bp" date={ust.data?.latest?.date ?? null}
          status="收益率变化，不等于价格或总回报" loading={ust.isLoading} error={ust.isError} onOpen={() => onOpen('ust')}
        />
      </div>
      <div className="performance-method-grid">
        <article><span>本页回答</span><strong>最近发生了什么变化？</strong><p>以日变动、事件证据和可用的研究口径解释市场表现。</p></article>
        <article><span>市场数据回答</span><strong>历史水平和曲线是什么？</strong><p>查看完整时间序列、期限结构、分位和底层数据详情。</p></article>
        <article><span>比较限制</span><strong>不同指标不直接排名</strong><p>收益率、信用利差和会员持仓结构单位不同，不生成统一涨跌榜。</p></article>
      </div>
    </section>
  )
}

function RecentChangeTable({ points, valueUnit, changeUnit, digits = 2 }: { points: ChangePoint[]; valueUnit: string; changeUnit: string; digits?: number }) {
  return (
    <div className="performance-change-table">
      <header><span>日期</span><span>观测值</span><span>较前值</span></header>
      {points.slice(-10).reverse().map((item) => (
        <div key={item.date}><span>{item.date}</span><strong>{item.value.toFixed(digits)}{valueUnit}</strong><b className={tone(item.change)}>{signed(item.change, changeUnit, changeUnit === 'bp' ? 1 : 3)}</b></div>
      ))}
    </div>
  )
}

function PerformanceDetailShell({ asset, title, subtitle, terms, term, onTerm, termLabels, children }: {
  asset: PerformanceAsset
  title: string
  subtitle: string
  terms: string[]
  term: string
  onTerm: (term: string) => void
  termLabels?: Record<string, string>
  children: React.ReactNode
}) {
  return (
    <section className="performance-detail" style={{ '--performance-color': ASSET_META[asset].color } as React.CSSProperties}>
      <header className="performance-detail-head"><div><p>PERFORMANCE ANALYSIS</p><h2>{title}</h2><span>{subtitle}</span></div><div className="performance-term-tabs">{terms.map((item) => <button type="button" key={item} className={item === term ? 'active' : ''} onClick={() => onTerm(item)}>{termLabels?.[item] ?? item}</button>)}</div></header>
      {children}
    </section>
  )
}

function CreditPerformance() {
  const [term, setTerm] = useState('10Y')
  const query = useQuery({ queryKey: ['market-performance', 'credit', term], queryFn: () => fetchCreditSpreadOverview(term), staleTime: 5 * 60 * 1000 })
  const points = buildChanges(query.data?.series ?? [], (item) => item.date, (item) => item.spread_bp)
  const latest = points.at(-1)
  const current = query.data?.latest
  const previousRaw = (query.data?.series ?? []).at(-2)
  const creditYieldChange = current && previousRaw ? (current.credit - previousRaw.credit) * 100 : null
  const govYieldChange = current && previousRaw ? (current.gov - previousRaw.gov) * 100 : null
  return (
    <PerformanceDetailShell asset="credit" title="信用债表现" subtitle="观察整体信用利差的近期变化，并拆分信用收益率与同期限国债收益率。" terms={query.data?.available_terms ?? ['1Y', '3Y', '5Y', '10Y']} term={term} onTerm={setTerm}>
      {query.isLoading ? <Skeleton height="420px" variant="rectangular" /> : query.isError || !current ? <div className="performance-detail-state">信用债表现数据暂不可用</div> : <>
        <div className="performance-kpis"><div><span>当前整体利差</span><strong>{current.spread_bp.toFixed(1)}bp</strong></div><div><span>利差日变动</span><strong className={tone(latest?.change ?? null)}>{signed(latest?.change ?? null, 'bp')}</strong></div><div><span>信用收益率日变动</span><strong className={tone(creditYieldChange)}>{signed(creditYieldChange, 'bp')}</strong></div><div><span>国债收益率日变动</span><strong className={tone(govYieldChange)}>{signed(govYieldChange, 'bp')}</strong></div></div>
        <div className="performance-detail-grid"><article className="performance-change-chart"><header><h3>{term}整体信用利差日变动</h3><span>正值=走阔，负值=收窄</span></header><ReactECharts opts={{ renderer: 'svg' }} option={changeChart(points, ASSET_META.credit.color, 'bp')} style={{ height: 300 }} /></article><article className="performance-recent"><header><h3>最近10个观测日</h3><span>整体曲线口径</span></header><RecentChangeTable points={points} valueUnit="bp" changeUnit="bp" digits={1} /></article></div>
        <p className="performance-boundary-note">当前只支持整体中短期票据曲线。利差走阔/收窄不等同于单券收益，评级、行业、主体和单券表现仍需独立数据。</p>
      </>}
    </PerformanceDetailShell>
  )
}

function FuturesPerformance() {
  const [variety, setVariety] = useState('T')
  const overview = useQuery({ queryKey: ['market-performance', 'futures-overview'], queryFn: fetchFuturesOverview, staleTime: 5 * 60 * 1000 })
  const query = useQuery({ queryKey: ['market-performance', 'futures', variety], queryFn: () => fetchFuturesTrend(variety, 60), staleTime: 5 * 60 * 1000 })
  const series = (query.data?.series ?? []).filter((item) => item.ratio !== null)
  const points = buildChanges(series, (item) => item.date, (item) => item.ratio!, 1)
  const latest = series.at(-1)
  const previous = series.at(-2)
  const latestPoint = points.at(-1)
  return (
    <PerformanceDetailShell asset="futures" title="国债期货持仓表现" subtitle="当前数据只能观察会员持仓结构变化，不能计算合约价格收益或策略PnL。" terms={overview.data?.varieties.map((item) => item.variety) ?? ['TS', 'TF', 'T', 'TL']} term={variety} onTerm={setVariety} termLabels={FUTURES_VARIETY_NAMES}>
      {query.isLoading || overview.isLoading ? <Skeleton height="420px" variant="rectangular" /> : query.isError || !latest ? <div className="performance-detail-state">国债期货会员持仓数据暂不可用</div> : <>
        <div className="performance-kpis"><div><span>当前会员多空比</span><strong>{latest.ratio?.toFixed(3) ?? '—'}</strong></div><div><span>多空比日变动</span><strong className={tone(latestPoint?.change ?? null)}>{signed(latestPoint?.change ?? null, '', 3)}</strong></div><div><span>前20名多头变化</span><strong className={tone(previous ? latest.long_total - previous.long_total : null)}>{signed(previous ? latest.long_total - previous.long_total : null, '', 0)}</strong></div><div><span>前20名空头变化</span><strong className={tone(previous ? latest.short_total - previous.short_total : null)}>{signed(previous ? latest.short_total - previous.short_total : null, '', 0)}</strong></div></div>
        <div className="performance-detail-grid"><article className="performance-change-chart"><header><h3>{FUTURES_VARIETY_NAMES[variety] ?? `${variety}国债期货`}会员多空比日变动</h3><span>结构变化，不是收益</span></header><ReactECharts opts={{ renderer: 'svg' }} option={changeChart(points, ASSET_META.futures.color, '')} style={{ height: 300 }} /></article><article className="performance-recent"><header><h3>最近10个观测日</h3><span>前20名会员口径</span></header><RecentChangeTable points={points} valueUnit="" changeUnit="" digits={3} /></article></div>
        <p className="performance-boundary-note">会员排名不等于全市场持仓、客户持仓或价格表现。取得可靠合约价格与结算价前，本页不展示期货收益、基差、连续合约收益或策略PnL。</p>
      </>}
    </PerformanceDetailShell>
  )
}

function UstPerformance() {
  const [term, setTerm] = useState('10Y')
  const query = useQuery({ queryKey: ['market-performance', 'ust', term], queryFn: () => fetchTreasurySpread(term), staleTime: 5 * 60 * 1000 })
  const series = query.data?.series ?? []
  const points = buildChanges(series, (item) => item.date, (item) => item.us, 100)
  const latest = series.at(-1)
  const previous = series.at(-2)
  const latestPoint = points.at(-1)
  const cnChange = latest && previous ? (latest.cn - previous.cn) * 100 : null
  const spreadChange = latest && previous ? latest.spread_bp - previous.spread_bp : null
  return (
    <PerformanceDetailShell asset="ust" title="美债表现" subtitle="观察美债收益率日变动及其与中国国债、中美利差的同步变化。" terms={query.data?.available_terms ?? ['2Y', '10Y', '30Y']} term={term} onTerm={setTerm}>
      {query.isLoading ? <Skeleton height="420px" variant="rectangular" /> : query.isError || !latest ? <div className="performance-detail-state">美债表现数据暂不可用</div> : <>
        <div className="performance-kpis"><div><span>当前美债收益率</span><strong>{latest.us.toFixed(3)}%</strong></div><div><span>美债收益率日变动</span><strong className={tone(latestPoint?.change ?? null)}>{signed(latestPoint?.change ?? null, 'bp')}</strong></div><div><span>同期限中债日变动</span><strong className={tone(cnChange)}>{signed(cnChange, 'bp')}</strong></div><div><span>中美利差日变动</span><strong className={tone(spreadChange)}>{signed(spreadChange, 'bp')}</strong></div></div>
        <div className="performance-detail-grid"><article className="performance-change-chart"><header><h3>{term}美债收益率日变动</h3><span>美国市场日频观测</span></header><ReactECharts opts={{ renderer: 'svg' }} option={changeChart(points, ASSET_META.ust.color, 'bp')} style={{ height: 300 }} /></article><article className="performance-recent"><header><h3>最近10个观测日</h3><span>不等于价格回报</span></header><RecentChangeTable points={points} valueUnit="%" changeUnit="bp" digits={3} /></article></div>
        <p className="performance-boundary-note">当前结果是收益率bp变化，不是债券价格或总回报。中美利差仅在双方同日均有数据时计算，不插值。</p>
      </>}
    </PerformanceDetailShell>
  )
}

export default function MarketPerformanceView({ asset, onOpen }: Props) {
  if (asset === 'all') return <PerformanceOverview onOpen={onOpen} />
  if (asset === 'credit') return <CreditPerformance />
  if (asset === 'futures') return <FuturesPerformance />
  if (asset === 'ust') return <UstPerformance />
  return null
}
