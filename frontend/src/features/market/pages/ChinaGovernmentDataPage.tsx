import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { fetchMarketPanel } from '@/api/market'
import { Skeleton } from '@/components/ui'

const TERM_ORDER = ['3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '30Y']

function axisStyle() {
  return {
    axisLabel: { color: '#777', fontSize: 10 },
    axisTick: { show: false },
    axisLine: { lineStyle: { color: '#35353b' } },
  }
}

export default function ChinaGovernmentDataPage() {
  const [term, setTerm] = useState('10Y')
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['market-data', 'cgb-detail'],
    queryFn: fetchMarketPanel,
    staleTime: 5 * 60 * 1000,
  })

  const items = useMemo(() => {
    const rows = data?.yields.items ?? []
    return TERM_ORDER.map((period) => rows.find((item) => item.period === period)).filter(Boolean) as typeof rows
  }, [data])
  const current = items.find((item) => item.period === term) ?? items[0]
  const spread = data?.yields.spread_10y2y

  const historyOption = current ? {
    animationDuration: 350,
    tooltip: { trigger: 'axis', backgroundColor: '#202024', borderColor: '#444', textStyle: { color: '#eee', fontSize: 11 }, valueFormatter: (value: number) => `${value.toFixed(3)}%` },
    grid: { left: 52, right: 22, top: 24, bottom: 38 },
    xAxis: { type: 'category', boundaryGap: false, data: current.sparkline.dates, ...axisStyle() },
    yAxis: { type: 'value', scale: true, splitNumber: 4, ...axisStyle(), splitLine: { lineStyle: { color: '#29292f', type: 'dashed' } } },
    series: [{ type: 'line', smooth: .28, showSymbol: false, data: current.sparkline.values, lineStyle: { color: '#7aa2f7', width: 2.4 }, itemStyle: { color: '#7aa2f7' }, areaStyle: { color: 'rgba(122,162,247,.12)' } }],
  } : {}

  const curveOption = {
    animationDuration: 350,
    tooltip: { trigger: 'axis', backgroundColor: '#202024', borderColor: '#444', textStyle: { color: '#eee', fontSize: 11 }, valueFormatter: (value: number) => `${value.toFixed(3)}%` },
    grid: { left: 48, right: 18, top: 20, bottom: 34 },
    xAxis: { type: 'category', data: items.map((item) => item.period), ...axisStyle() },
    yAxis: { type: 'value', scale: true, splitNumber: 3, ...axisStyle(), splitLine: { lineStyle: { color: '#29292f', type: 'dashed' } } },
    series: [{ type: 'line', smooth: .32, symbolSize: 7, data: items.map((item) => item.value), lineStyle: { color: '#65c9b2', width: 2 }, itemStyle: { color: '#65c9b2' }, areaStyle: { color: 'rgba(101,201,178,.08)' } }],
  }

  if (isLoading) return <div className="market-data-detail-loading"><Skeleton height="560px" variant="rectangular" /></div>
  if (isError || !data) return <div className="market-data-detail-state">中国国债数据加载失败<button type="button" onClick={() => refetch()}>重新加载</button></div>
  if (!current) return <div className="market-data-detail-state">暂无中国国债收益率数据</div>

  return (
    <div className="market-data-asset-page">
      <header className="market-data-asset-heading">
        <div>
          <p>中国国债</p>
          <h1>收益率曲线与期限走势</h1>
          <span>数据截至 {data.yields.update_date} · 现有国债数据轻量整合</span>
        </div>
        <div className="market-data-term-tabs" aria-label="中国国债期限">
          {items.map((item) => (
            <button type="button" key={item.period} className={item.period === current.period ? 'active' : ''} onClick={() => setTerm(item.period)}>{item.period}</button>
          ))}
        </div>
      </header>

      <section className="market-data-kpis">
        <div><span>{current.label}收益率</span><strong>{current.value.toFixed(3)}%</strong></div>
        <div><span>较前值</span><strong className={current.diff_bp > 0 ? 'is-up' : current.diff_bp < 0 ? 'is-down' : ''}>{current.diff_bp > 0 ? '+' : ''}{current.diff_bp.toFixed(1)}bp</strong></div>
        <div><span>10Y-2Y</span><strong>{spread ? `${spread.value.toFixed(2)}%` : '—'}</strong></div>
        <div><span>可用期限</span><strong>{items.length}</strong></div>
      </section>

      <section className="market-data-primary-chart">
        <header><div><h2>{current.label}历史走势</h2><p>当前详情使用现有真实收益率序列</p></div><span>{current.period}</span></header>
        <ReactECharts opts={{ renderer: 'svg' }} option={historyOption} style={{ height: 330 }} />
      </section>

      <div className="market-data-secondary-grid">
        <section className="market-data-secondary-chart">
          <header><h2>当前收益率曲线</h2><span>{data.yields.update_date}</span></header>
          <ReactECharts opts={{ renderer: 'svg' }} option={curveOption} style={{ height: 250 }} />
        </section>
        <section className="market-data-secondary-chart market-data-table-card">
          <header><h2>各期限数据</h2><span>收益率 / BP变化</span></header>
          <div className="market-data-terms-table">
            {items.map((item) => (
              <button type="button" key={item.period} onClick={() => setTerm(item.period)} className={item.period === current.period ? 'active' : ''}>
                <span>{item.period}</span>
                <strong>{item.value.toFixed(3)}%</strong>
                <em className={item.diff_bp > 0 ? 'is-up' : item.diff_bp < 0 ? 'is-down' : ''}>{item.diff_bp > 0 ? '+' : ''}{item.diff_bp.toFixed(1)}bp</em>
              </button>
            ))}
          </div>
        </section>
      </div>

      <p className="market-data-method-note">收益率上行与债券价格下行通常方向相反。本页展示市场收益率数据，不代表债券持有收益或交易回报。</p>
    </div>
  )
}
