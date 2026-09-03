import React, { useEffect, useMemo, useState } from 'react'
import { Loading } from '@/components/ui'
import { fetchFactorDetail } from '@/api/market'
import type { FactorDetailData } from '@/types'

interface Props {
  factorId: number
  onClose: () => void
  onNewsClick: (newsId: number) => void
  onFactorClick?: (factorId: number) => void
}

type Period = '7d' | '30d' | '365d'
type TrendPoint = FactorDetailData['trend_series'][Period][number]

const PERIOD_LABELS: Record<Period, string> = { '7d': '近7日', '30d': '近30日', '365d': '近1年' }
const CATEGORY_LABELS: Record<string, string> = {
  MACRO: '宏观经济', POLICY: '政策与监管', MARKET: '市场交易', INDUSTRY: '行业产业',
  SENTIMENT: '市场情绪', CREDIT: '信用风险', LIQUIDITY: '资金流动性', GLOBAL: '海外市场',
}
const DIRECTION_META = {
  positive: { label: '利多', color: '#e05a5a' },
  negative: { label: '利空', color: '#1fa77a' },
  neutral: { label: '中性', color: '#6b7280' },
}

function DirectionTrendChart({ points, period }: { points: TrendPoint[]; period: Period }) {
  if (!points.length) return <div className="factor-detail-empty">暂无趋势数据</div>
  const width = 720
  const height = 210
  const padding = { left: 34, right: 12, top: 18, bottom: 30 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom
  const maxTotal = Math.max(...points.map(point => point.total), 1)
  const gap = chartWidth / points.length
  const barWidth = Math.min(period === '30d' ? 11 : 24, Math.max(4, gap * 0.62))

  return (
    <svg className="factor-detail-trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${PERIOD_LABELS[period]}因子活跃度与方向趋势`}>
      {[0, 0.5, 1].map(ratio => {
        const y = padding.top + chartHeight * (1 - ratio)
        return <g key={ratio}><line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="#252529" /><text x={padding.left - 7} y={y + 3} textAnchor="end" fill="#666" fontSize="9">{Math.round(maxTotal * ratio)}</text></g>
      })}
      {points.map((point, index) => {
        const x = padding.left + index * gap + (gap - barWidth) / 2
        let cursorY = padding.top + chartHeight
        const month = point.date.slice(5, 7)
        const day = point.date.slice(-2)
        const label = period === '365d'
          ? `${month}月`
          : period === '30d' && index !== 0 && index !== points.length - 1 && day !== '01'
            ? day
            : `${month}/${day}`
        return (
          <g key={point.date}>
            <title>{`${point.date}：利多 ${point.positive}，利空 ${point.negative}，中性 ${point.neutral}`}</title>
            {(['neutral', 'negative', 'positive'] as const).map(direction => {
              const value = point[direction]
              const segmentHeight = value ? Math.max(2, value / maxTotal * chartHeight) : 0
              cursorY -= segmentHeight
              return <rect key={direction} x={x} y={cursorY} width={barWidth} height={segmentHeight} rx="2" fill={DIRECTION_META[direction].color} />
            })}
            <text x={x + barWidth / 2} y={height - 9} textAnchor="middle" fill="#666" fontSize={period === '30d' ? '8' : '9'}>{label}</text>
          </g>
        )
      })}
    </svg>
  )
}

function DirectionDonut({ counts }: { counts: Record<'positive' | 'negative' | 'neutral', number> }) {
  const total = counts.positive + counts.negative + counts.neutral
  const positive = total ? counts.positive / total * 100 : 0
  const negative = total ? counts.negative / total * 100 : 0
  const background = total
    ? `conic-gradient(${DIRECTION_META.positive.color} 0 ${positive}%, ${DIRECTION_META.negative.color} ${positive}% ${positive + negative}%, ${DIRECTION_META.neutral.color} ${positive + negative}% 100%)`
    : '#252529'
  return (
    <div className="factor-direction-summary">
      <div className="factor-direction-donut" style={{ background }}><span><b>{total}</b><small>事件</small></span></div>
      <div className="factor-direction-legend">
        {(['positive', 'negative', 'neutral'] as const).map(direction => (
          <div key={direction}><i style={{ background: DIRECTION_META[direction].color }} /><span>{DIRECTION_META[direction].label}</span><b>{counts[direction]}</b><small>{total ? Math.round(counts[direction] / total * 100) : 0}%</small></div>
        ))}
      </div>
    </div>
  )
}

const FactorDetailPanel: React.FC<Props> = ({ factorId, onClose, onNewsClick, onFactorClick }) => {
  const [data, setData] = useState<FactorDetailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [period, setPeriod] = useState<Period>('30d')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(false)
    fetchFactorDetail(factorId)
      .then(result => { if (active) setData(result) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [factorId])

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  const points = data?.trend_series?.[period] || []
  const periodCounts = useMemo(() => points.reduce((total, point) => ({
    positive: total.positive + point.positive,
    negative: total.negative + point.negative,
    neutral: total.neutral + point.neutral,
  }), { positive: 0, negative: 0, neutral: 0 }), [points])

  if (loading) return <div className="factor-detail-overlay factor-detail-state"><Loading text="加载中…" /></div>
  if (error || !data || 'error' in data) return <div className="factor-detail-overlay factor-detail-state">因子数据暂不可用</div>

  const directionClass = data.current_direction === '利多' ? 'up' : data.current_direction === '利空' ? 'down' : 'neutral'
  const changeText = data.activity_change_7d === null
    ? '新增活跃'
    : `${data.activity_change_7d > 0 ? '+' : ''}${data.activity_change_7d}%`
  const maxShared = Math.max(...data.related_factors.map(factor => factor.shared_count), 1)

  return (
    <div className="factor-detail-overlay">
      <div className="factor-detail-topbar">
        <button type="button" onClick={onClose} className="factor-detail-back" aria-label="返回因子页面">← <span>返回因子</span></button>
      </div>

      <main className="factor-detail-page">
        <header className="factor-detail-header">
          <div className="factor-detail-kickers">
            <span>{CATEGORY_LABELS[data.category] || data.category}</span>
            {data.factor_type && <span>{data.factor_type === 'quantitative' ? '量化因子' : '概念因子'}</span>}
            <span className={`factor-direction ${directionClass}`}>{data.current_direction}</span>
            <span className={`factor-heat ${data.heat_level}`}>热度 {data.heat_level}</span>
          </div>
          <h1>{data.name}</h1>
          <div className="factor-detail-code">{data.code}</div>
          <p className="factor-detail-insight">{data.insight}</p>
        </header>

        <section className="factor-detail-metrics" aria-label="因子概览">
          <article><span>当前方向</span><strong className={directionClass}>{data.current_direction}</strong><small>基于近30日事件</small></article>
          <article><span>近7日事件</span><strong>{data.activity_7d}</strong><small>关联新闻数量</small></article>
          <article><span>近30日事件</span><strong>{data.activity_30d}</strong><small>中期活跃情况</small></article>
          <article><span>活跃变化</span><strong className={(data.activity_change_7d || 0) >= 0 ? 'up' : 'down'}>{changeText}</strong><small>相比前7日</small></article>
          <article><span>最近更新</span><strong className="date">{data.latest_event_at || '暂无'}</strong><small>最近关联事件</small></article>
        </section>

        <section className="factor-detail-visual-grid">
          <article className="factor-detail-card factor-trend-panel">
            <header><div><h2>活跃度与方向趋势</h2><p>柱高代表事件数量，颜色代表市场方向</p></div><div className="factor-detail-periods">{(['7d', '30d', '365d'] as Period[]).map(value => <button type="button" key={value} className={period === value ? 'active' : ''} onClick={() => setPeriod(value)}>{PERIOD_LABELS[value]}</button>)}</div></header>
            <DirectionTrendChart points={points} period={period} />
            <footer>{(['positive', 'negative', 'neutral'] as const).map(direction => <span key={direction}><i style={{ background: DIRECTION_META[direction].color }} />{DIRECTION_META[direction].label}</span>)}</footer>
          </article>
          <article className="factor-detail-card factor-direction-panel">
            <header><div><h2>方向占比</h2><p>{PERIOD_LABELS[period]}关联事件构成</p></div></header>
            <DirectionDonut counts={periodCounts} />
          </article>
        </section>

        <section className="factor-detail-bottom-grid">
          <article className="factor-detail-card factor-news-panel">
            <header><div><h2>相关新闻</h2><p>最近关联事件，共 {data.related_news.length} 条</p></div><span>模块内滚动查看更多</span></header>
            <div className="factor-detail-news-scroll">
              {data.related_news.length ? data.related_news.map(news => {
                const direction = news.direction === 'positive' ? 'positive' : news.direction === 'negative' ? 'negative' : 'neutral'
                return <button type="button" key={news.id} className={`factor-news-item ${direction}`} onClick={() => onNewsClick(news.id)}><div><time>{news.pub_time}</time><span>{DIRECTION_META[direction].label}</span></div><strong>{news.title}</strong>{news.reason && <p>{news.reason}</p>}</button>
              }) : <div className="factor-detail-empty">暂无相关新闻</div>}
            </div>
          </article>

          <article className="factor-detail-card factor-related-panel">
            <header><div><h2>相关因子 Top 5</h2><p>按共同关联新闻数量排序</p></div></header>
            <div className="factor-related-list">
              {data.related_factors.length ? data.related_factors.map((factor, index) => <button type="button" key={factor.id} onClick={() => onFactorClick?.(factor.id)} disabled={!onFactorClick}><span><em>{index + 1}</em><b title={factor.name}>{factor.name}</b><strong>{factor.shared_count}</strong></span><i><b style={{ width: `${Math.max(5, factor.shared_count / maxShared * 100)}%` }} /></i></button>) : <div className="factor-detail-empty">暂无相关因子</div>}
            </div>
          </article>
        </section>
      </main>
    </div>
  )
}

export default FactorDetailPanel
