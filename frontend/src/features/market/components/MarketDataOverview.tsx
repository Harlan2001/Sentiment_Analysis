import { useState, type KeyboardEvent, type MouseEvent, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { fetchMarketPanel } from '@/api/market'
import { fetchCreditSpreadOverview } from '@/api/creditSpread'
import { fetchFuturesOverview, fetchFuturesTrend } from '@/api/futures'
import { fetchTreasurySpread } from '@/api/treasury'
import { Skeleton } from '@/components/ui'

export type MarketDataAsset = 'cgb' | 'credit' | 'futures' | 'ust'

interface Props {
  onOpen: (asset: MarketDataAsset) => void
  kicker?: string
  title?: string
  description?: string
}

const COLORS: Record<MarketDataAsset, string> = {
  cgb: '#7aa2f7',
  credit: '#c792ea',
  futures: '#e7b66f',
  ust: '#65c9b2',
}

function lineOption(dates: string[], values: Array<number | null>, color: string, unit: string) {
  return {
    animationDuration: 350,
    grid: { left: 42, right: 14, top: 18, bottom: 26 },
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: 'rgba(24,24,28,.96)',
      borderColor: '#45454c',
      textStyle: { color: '#eee', fontSize: 11 },
      valueFormatter: (value: number) => `${value.toFixed(unit === 'bp' ? 1 : 3)}${unit}`,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: { color: '#666', fontSize: 9, hideOverlap: true },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#303038' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitNumber: 3,
      axisLabel: { color: '#666', fontSize: 9 },
      axisTick: { show: false },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#25252b', type: 'dashed' } },
    },
    series: [{
      type: 'line',
      data: values,
      smooth: 0.28,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 2, color },
      itemStyle: { color },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: `${color}35` }, { offset: 1, color: `${color}00` }],
        },
      },
    }],
  }
}

function formatDelta(value: number | null, unit: string) {
  if (value === null || !Number.isFinite(value)) return '暂无前值'
  const digits = unit === 'bp' ? 1 : 3
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}${unit}`
}

function selectorClick(event: MouseEvent<HTMLButtonElement>, onSelect: () => void) {
  event.stopPropagation()
  onSelect()
}

function OverviewCard({
  asset,
  title,
  subtitle,
  selectors,
  selected,
  onSelect,
  value,
  delta,
  deltaUnit,
  date,
  loading,
  error,
  dates,
  values,
  chartUnit,
  children,
  onOpen,
}: {
  asset: MarketDataAsset
  title: string
  subtitle: string
  selectors: string[]
  selected: string
  onSelect: (value: string) => void
  value: string
  delta: number | null
  deltaUnit: string
  date: string | null
  loading: boolean
  error: boolean
  dates: string[]
  values: Array<number | null>
  chartUnit: string
  children?: ReactNode
  onOpen: () => void
}) {
  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onOpen()
    }
  }

  return (
    <article
      className="market-data-overview-card"
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={handleKeyDown}
      aria-label={`查看${title}详情`}
    >
      <header className="market-data-card-head">
        <div>
          <span className="market-data-card-kicker">{subtitle}</span>
          <h2>{title}</h2>
        </div>
        <span className="market-data-card-arrow" aria-hidden="true">↗</span>
      </header>

      <div className="market-data-selector" aria-label={`${title}切换项`}>
        {selectors.map((item) => (
          <button
            type="button"
            key={item}
            className={item === selected ? 'active' : ''}
            onClick={(event) => selectorClick(event, () => onSelect(item))}
          >
            {item}
          </button>
        ))}
      </div>

      {loading ? (
        <Skeleton height="210px" variant="rectangular" />
      ) : error ? (
        <div className="market-data-card-state">数据加载失败，进入详情后可重试</div>
      ) : values.length < 2 ? (
        <div className="market-data-card-state">当前选择项的历史样本不足</div>
      ) : (
        <>
          <div className="market-data-card-metric">
            <strong>{value}</strong>
            <span className={delta !== null && delta > 0 ? 'is-up' : delta !== null && delta < 0 ? 'is-down' : ''}>
              {formatDelta(delta, deltaUnit)}
            </span>
          </div>
          {children}
          <ReactECharts
            opts={{ renderer: 'svg' }}
            notMerge
            option={lineOption(dates, values, COLORS[asset], chartUnit)}
            style={{ height: 178, width: '100%' }}
          />
        </>
      )}

      <footer className="market-data-card-foot">
        <span>{date ? `数据截至 ${date}` : '暂无有效数据日期'}</span>
        <span>查看详情</span>
      </footer>
    </article>
  )
}

function ChinaGovernmentCard({ onOpen }: { onOpen: () => void }) {
  const [term, setTerm] = useState('10Y')
  const { data, isLoading, isError } = useQuery({
    queryKey: ['market-data', 'cgb-overview'],
    queryFn: fetchMarketPanel,
    staleTime: 5 * 60 * 1000,
  })
  const available = data?.yields.items.map((item) => item.period) ?? []
  const preferred = ['1Y', '2Y', '5Y', '10Y', '30Y'].filter((item) => available.includes(item))
  const item = data?.yields.items.find((row) => row.period === term)

  return (
    <OverviewCard
      asset="cgb"
      title="中国国债"
      subtitle="收益率历史走势"
      selectors={preferred.length ? preferred : ['1Y', '2Y', '5Y', '10Y', '30Y']}
      selected={term}
      onSelect={setTerm}
      value={item ? `${item.value.toFixed(3)}%` : '—'}
      delta={item?.diff_bp ?? null}
      deltaUnit="bp"
      date={data?.yields.update_date ?? null}
      loading={isLoading}
      error={isError}
      dates={item?.sparkline.dates ?? []}
      values={item?.sparkline.values ?? []}
      chartUnit="%"
      onOpen={onOpen}
    />
  )
}

function CreditCard({ onOpen }: { onOpen: () => void }) {
  const [term, setTerm] = useState('10Y')
  const { data, isLoading, isError } = useQuery({
    queryKey: ['market-data', 'credit-overview', term],
    queryFn: () => fetchCreditSpreadOverview(term),
    staleTime: 5 * 60 * 1000,
  })
  const preferred = ['1Y', '2Y', '3Y', '5Y', '10Y'].filter((item) => data?.available_terms.includes(item))
  const series = data?.series ?? []
  const previous = series.length > 1 ? series[series.length - 2] : null
  const delta = data?.latest && previous ? data.latest.spread_bp - previous.spread_bp : null

  return (
    <OverviewCard
      asset="credit"
      title="信用债"
      subtitle="整体信用利差"
      selectors={preferred.length ? preferred : ['1Y', '3Y', '5Y', '10Y']}
      selected={term}
      onSelect={setTerm}
      value={data?.latest ? `${data.latest.spread_bp.toFixed(1)}bp` : '—'}
      delta={delta}
      deltaUnit="bp"
      date={data?.latest?.date ?? null}
      loading={isLoading}
      error={isError}
      dates={series.map((item) => item.date)}
      values={series.map((item) => item.spread_bp)}
      chartUnit="bp"
      onOpen={onOpen}
    />
  )
}

function FuturesCard({ onOpen }: { onOpen: () => void }) {
  const [variety, setVariety] = useState('T')
  const overview = useQuery({
    queryKey: ['market-data', 'futures-overview'],
    queryFn: fetchFuturesOverview,
    staleTime: 5 * 60 * 1000,
  })
  const trend = useQuery({
    queryKey: ['market-data', 'futures-trend', variety],
    queryFn: () => fetchFuturesTrend(variety, 60),
    staleTime: 5 * 60 * 1000,
  })
  const series = trend.data?.series ?? []
  const latest = series.at(-1)
  const previous = series.length > 1 ? series[series.length - 2] : null
  const current = overview.data?.comparison.find((item) => item.variety === variety)?.ratio ?? latest?.ratio ?? null
  const delta = latest?.ratio !== null && latest?.ratio !== undefined && previous?.ratio !== null && previous?.ratio !== undefined
    ? latest.ratio - previous.ratio
    : null
  const selectors = overview.data?.varieties.map((item) => item.variety) ?? ['TS', 'TF', 'T', 'TL']

  return (
    <OverviewCard
      asset="futures"
      title="国债期货"
      subtitle="会员多空结构"
      selectors={selectors}
      selected={variety}
      onSelect={setVariety}
      value={current === null ? '—' : current.toFixed(3)}
      delta={delta}
      deltaUnit=""
      date={overview.data?.trade_date ?? latest?.date ?? null}
      loading={overview.isLoading || trend.isLoading}
      error={overview.isError || trend.isError}
      dates={series.map((item) => item.date)}
      values={series.map((item) => item.ratio)}
      chartUnit=""
      onOpen={onOpen}
    >
      <p className="market-data-card-note">前20名会员多头合计 ÷ 空头合计</p>
    </OverviewCard>
  )
}

function UstCard({ onOpen }: { onOpen: () => void }) {
  const [term, setTerm] = useState('10Y')
  const { data, isLoading, isError } = useQuery({
    queryKey: ['market-data', 'ust-overview', term],
    queryFn: () => fetchTreasurySpread(term),
    staleTime: 5 * 60 * 1000,
  })
  const series = data?.series ?? []
  const previous = series.length > 1 ? series[series.length - 2] : null
  const delta = data?.latest && previous ? (data.latest.us - previous.us) * 100 : null

  return (
    <OverviewCard
      asset="ust"
      title="美债"
      subtitle="美国国债收益率"
      selectors={data?.available_terms.length ? data.available_terms : ['2Y', '10Y', '30Y']}
      selected={term}
      onSelect={setTerm}
      value={data?.latest ? `${data.latest.us.toFixed(3)}%` : '—'}
      delta={delta}
      deltaUnit="bp"
      date={data?.latest?.date ?? null}
      loading={isLoading}
      error={isError}
      dates={series.map((item) => item.date)}
      values={series.map((item) => item.us)}
      chartUnit="%"
      onOpen={onOpen}
    />
  )
}

export function MarketDataOverview({
  onOpen,
  kicker = 'MARKET DATA',
  title = '四资产市场数据',
  description = '选择期限或品种查看真实历史序列；点击图表进入完整资产详情。',
}: Props) {
  return (
    <section className="market-data-overview">
      <header className="market-data-overview-head">
        <div>
          <p>{kicker}</p>
          <h1>{title}</h1>
          <span>{description}</span>
        </div>
        <div className="market-data-overview-status">
          <i />
          各卡片独立显示实际数据日期
        </div>
      </header>
      <div className="market-data-overview-grid">
        <ChinaGovernmentCard onOpen={() => onOpen('cgb')} />
        <CreditCard onOpen={() => onOpen('credit')} />
        <FuturesCard onOpen={() => onOpen('futures')} />
        <UstCard onOpen={() => onOpen('ust')} />
      </div>
    </section>
  )
}
