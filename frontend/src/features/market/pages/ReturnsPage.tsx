import { useEffect, useId, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fetchReturnsCalendar } from '@/api/market'
import { Skeleton } from '@/components/ui'
import type { CalendarDayItem, CalendarNewsItem, ReturnsCalendarResponse, YieldChangeItem } from '@/types'
import NewsListRow from '../components/NewsListRow'
import {
  bpArrow,
  dateKey,
  formatBp,
  formatYieldValue,
  fullDateLabel,
  hasUsableBenchmark,
  isValidDateKey,
  monthCells,
  monthRange,
  normalizeCalendarDirection,
  shiftMonth,
  shortDateLabel,
  toCalendarNewsRow,
} from '../utils/returnsCalendar'
import './returns.css'

const DAY_HEADERS = ['一', '二', '三', '四', '五', '六', '日']
const PERIOD_ORDER = ['3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '30Y']
const PERIOD_LABELS: Record<string, string> = {
  '3M': '3月', '6M': '6月', '1Y': '1年', '2Y': '2年', '3Y': '3年',
  '5Y': '5年', '7Y': '7年', '10Y': '10年', '30Y': '30年',
}

type YieldsByPeriod = Record<string, YieldChangeItem>

function Empty({ text, compact = false }: { text: string; compact?: boolean }) {
  return <div className={`returns-empty${compact ? ' returns-empty--compact' : ''}`}>{text}</div>
}

function MarketSummary({
  yields,
  counts,
}: {
  yields: YieldsByPeriod
  counts: { supporting: number; opposing: number; neutral: number } | null
}) {
  const benchmark = yields['10Y']
  const hasYields = Object.keys(yields).length > 0
  return (
    <section className="returns-card returns-market" aria-labelledby="returns-market-title">
      <div className="returns-section-heading">
        <div><h2 id="returns-market-title">国债收益率</h2><p>实际值与较上一有效交易日变动</p></div>
        <span>基准 10Y</span>
      </div>
      {!hasYields ? <Empty text="该日期暂无国债收益率数据" compact /> : <>
        <div className="returns-benchmark">
          <div>
            <span className="returns-benchmark-label">10Y 国债收益率</span>
            <strong>{formatYieldValue(benchmark)}</strong>
          </div>
          <div className={`returns-benchmark-change is-${benchmark?.direction ?? 'unavailable'}`}>
            <span aria-hidden="true">{bpArrow(benchmark)}</span>
            <b>{formatBp(benchmark)}</b>
          </div>
          <p>
            {benchmark?.previous_date
              ? `较 ${benchmark.previous_date}（上一有效交易日）`
              : benchmark && benchmark.diff_bp !== null && benchmark.direction !== 'unavailable'
                ? '较上一有效交易日'
                : '暂无前值'}
          </p>
        </div>
        <div className="returns-yield-grid" aria-label="九期限国债收益率">
          {PERIOD_ORDER.map((period) => {
            const item = yields[period]
            return (
              <article className="returns-yield-item" key={period}>
                <span>{item?.label || PERIOD_LABELS[period]}</span>
                <strong>{formatYieldValue(item)}</strong>
                <div className={`is-${item?.direction ?? 'unavailable'}`}>
                  <span aria-hidden="true">{bpArrow(item)}</span>
                  <b>{formatBp(item)}</b>
                </div>
                <small>{!item ? '暂无数据' : item.diff_bp === null || item.direction === 'unavailable' ? '暂无前值' : item.previous_date ? `较 ${item.previous_date}` : '较上一有效交易日'}</small>
              </article>
            )
          })}
        </div>
      </>}
      {counts && <div className="returns-alignment-summary">
        <div aria-label="新闻方向对照计数">
          <span>同向 {counts.supporting}</span>
          <span>反向 {counts.opposing}</span>
          <span>中性 {counts.neutral}</span>
        </div>
        <p>AI 新闻方向与 10Y 收益率变动的方向对照，不代表因果归因</p>
      </div>}
    </section>
  )
}

function EvidenceGroup({
  title,
  items,
  onOpen,
  initiallyOpen = false,
  primary = false,
  emptyText,
}: {
  title: string
  items: CalendarNewsItem[]
  onOpen: (id: number) => void
  initiallyOpen?: boolean
  primary?: boolean
  emptyText?: string
}) {
  const [open, setOpen] = useState(initiallyOpen)
  const [showAll, setShowAll] = useState(false)
  const listId = useId()
  const visible = primary && !showAll ? items.slice(0, 5) : items
  return (
    <section className={`returns-evidence-group${primary ? ' is-primary' : ''}`}>
      {primary ? (
        <div className="returns-evidence-heading"><h3>{title} {items.length}</h3><span>静态重要性优先</span></div>
      ) : (
        <h3 className="returns-evidence-heading">
          <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-controls={listId}>
            <span>{title} {items.length}</span><span aria-hidden="true">{open ? '−' : '+'}</span>
          </button>
        </h3>
      )}
      {(primary || open) && <div id={listId}>
        {items.length === 0 ? <Empty text={emptyText ?? '暂无新闻'} compact /> : <>
          <div className="returns-news-list">
            {(primary ? visible : items).map((item) => (
              <NewsListRow key={item.id} item={toCalendarNewsRow(item)} variant="calendar" onClick={() => onOpen(item.id)} />
            ))}
          </div>
          {primary && items.length > 5 && <button
            type="button"
            className="returns-show-all"
            aria-expanded={showAll}
            aria-controls={listId}
            onClick={() => setShowAll((value) => !value)}
          >{showAll ? `收起${title}` : `展开全部 ${items.length} 条`}</button>}
        </>}
      </div>}
    </section>
  )
}

function DailyEvidence({
  yields,
  news,
  onOpen,
}: {
  yields: YieldsByPeriod
  news: CalendarNewsItem[]
  onOpen: (id: number) => void
}) {
  const aligned = hasUsableBenchmark(yields['10Y'])
  const supporting = news.filter((item) => item.market_alignment === 'supporting')
  const opposing = news.filter((item) => item.market_alignment === 'opposing')
  const neutral = news.filter((item) => item.market_alignment !== 'supporting' && item.market_alignment !== 'opposing')
  const bullish = news.filter((item) => normalizeCalendarDirection(item.direction) === 'positive')
  const bearish = news.filter((item) => normalizeCalendarDirection(item.direction) === 'negative')
  const ordinaryNeutral = news.filter((item) => {
    const direction = normalizeCalendarDirection(item.direction)
    return direction !== 'positive' && direction !== 'negative'
  })

  return (
    <>
      <MarketSummary yields={yields} counts={aligned ? {
        supporting: supporting.length,
        opposing: opposing.length,
        neutral: neutral.length,
      } : null} />
      <section className="returns-card returns-evidence" aria-labelledby="returns-evidence-title">
        <div className="returns-section-heading">
          <div><h2 id="returns-evidence-title">{aligned ? '每日新闻证据' : '方向性新闻'}</h2><p>{aligned ? '同向优先，同时保留反向与中性证据' : '10Y 暂无可计算基准，按 AI 方向普通分组'}</p></div>
        </div>
        {news.length > 0 && <p className="returns-score-note">静态分，未叠加相对当前时间的衰减</p>}
        {news.length === 0 ? <Empty text="该日期暂无方向性新闻" /> : aligned ? (
          <div className="returns-evidence-groups">
            <EvidenceGroup title="重点同向新闻" items={supporting} onOpen={onOpen} primary emptyText="未发现同向新闻" />
            <EvidenceGroup title="反向证据" items={opposing} onOpen={onOpen} />
            <EvidenceGroup title="中性及其他" items={neutral} onOpen={onOpen} />
          </div>
        ) : (
          <div className="returns-evidence-groups">
            <EvidenceGroup title="利多新闻" items={bullish} onOpen={onOpen} initiallyOpen />
            <EvidenceGroup title="利空新闻" items={bearish} onOpen={onOpen} initiallyOpen />
            <EvidenceGroup title="中性新闻" items={ordinaryNeutral} onOpen={onOpen} />
          </div>
        )}
      </section>
    </>
  )
}

function ReturnsCalendar({
  selectedDate,
  today,
  data,
  onSelect,
  onChangeMonth,
}: {
  selectedDate: string
  today: string
  data: ReturnsCalendarResponse | undefined
  onSelect: (date: string) => void
  onChangeMonth: (offset: number) => void
}) {
  const year = Number(selectedDate.slice(0, 4))
  const month = Number(selectedDate.slice(5, 7))
  const days = useMemo(() => new Map((data?.days ?? []).map((day) => [day.date, day])), [data])
  return (
    <section className="returns-card returns-calendar" aria-labelledby="returns-calendar-title">
      <div className="returns-calendar-controls">
        <button type="button" onClick={() => onChangeMonth(-1)} aria-label="上个月">‹</button>
        <h2 id="returns-calendar-title">{`${year}年${month}月 收益日历`}</h2>
        <button type="button" onClick={() => onChangeMonth(1)} aria-label="下个月">›</button>
      </div>
      <div className="returns-month-grid">
        {DAY_HEADERS.map((day) => <span className="returns-weekday" key={day}>{day}</span>)}
        {monthCells(selectedDate).map((value, index) => {
          if (!value) return <span className="returns-calendar-blank" key={`blank-${index}`} aria-hidden="true" />
          const summary = days.get(value)
          const benchmark = data?.yields_by_date?.[value]?.['10Y']
          const bp = formatBp(benchmark)
          const selected = value === selectedDate
          const isToday = value === today
          const label = [
            fullDateLabel(value),
            `10Y ${bp}`,
            summary ? `利多 ${summary.bullish_count} 条，利空 ${summary.bearish_count} 条，中性 ${summary.neutral_count} 条` : '暂无新闻统计',
            isToday ? '今天' : '',
            selected ? '已选择' : '',
          ].filter(Boolean).join('，')
          return (
            <button
              type="button"
              key={value}
              data-date={value}
              className={`returns-calendar-day${selected ? ' is-selected' : ''}${isToday ? ' is-today' : ''}`}
              onClick={() => onSelect(value)}
              aria-pressed={selected}
              aria-current={isToday ? 'date' : undefined}
              aria-label={label}
            >
              <span className="returns-day-number">{Number(value.slice(-2))}</span>
              <span className={`returns-day-bp is-${benchmark?.direction ?? 'unavailable'}`} aria-hidden="true">{bpArrow(benchmark)}{bp.replace(' BP', '')}</span>
              {summary && <span className="returns-day-counts" aria-hidden="true"><span>多 {summary.bullish_count}</span><span>空 {summary.bearish_count}</span></span>}
            </button>
          )
        })}
      </div>
      <div className="returns-calendar-legend"><span>多 = 利多 · 空 = 利空</span><span>BP 为 10Y 较上一有效交易日变动</span></div>
    </section>
  )
}

function ActiveFactors({
  day,
  loading,
  failed,
  onOpen,
}: {
  day: CalendarDayItem | undefined
  loading: boolean
  failed: boolean
  onOpen: (id: number) => void
}) {
  const factors = day?.active_factors ?? []
  return (
    <section className="returns-card returns-factors" aria-labelledby="returns-factors-title">
      <div className="returns-section-heading">
        <div><h2 id="returns-factors-title">活跃因子 Top 5</h2><p>当日全部关联新闻 Top 5</p></div>
      </div>
      {loading ? <Skeleton height="180px" variant="rectangular" /> : failed ? <Empty text="因子数据暂不可用" compact /> : factors.length ? (
        <div className="returns-factor-list">
          {factors.map((factor, index) => (
            <button type="button" key={factor.id} onClick={() => onOpen(factor.id)} className="returns-factor-row">
              <span className="returns-factor-rank">{index + 1}</span>
              <span className="returns-factor-copy"><strong>{factor.name}</strong><small>{factor.category} · {factor.news_count} 条关联新闻</small></span>
              <b>{factor.news_count}</b>
            </button>
          ))}
        </div>
      ) : <Empty text="暂无活跃因子" compact />}
    </section>
  )
}

export default function ReturnsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const today = useMemo(() => dateKey(new Date()), [])
  const requestedDate = searchParams.get('date')
  const selectedDate = isValidDateKey(requestedDate) ? requestedDate : today
  const range = useMemo(() => monthRange(selectedDate), [selectedDate])
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['returns-calendar', range.start, range.end],
    queryFn: () => fetchReturnsCalendar(range),
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (requestedDate === selectedDate) return
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.set('date', selectedDate)
      return next
    }, { replace: true })
  }, [requestedDate, selectedDate, setSearchParams])

  function updateDate(value: string) {
    const next = new URLSearchParams(searchParams)
    next.set('date', value)
    setSearchParams(next)
  }

  const yields = data?.yields_by_date?.[selectedDate] ?? {}
  const news = data?.news_by_date?.[selectedDate] ?? []
  const selectedDay = data?.days.find((day) => day.date === selectedDate)
  const returnPath = `/returns?date=${selectedDate}`

  return (
    <div className="returns-page">
      <header className="returns-page-header">
        <div><h1>收益日历</h1><p>{shortDateLabel(selectedDate)} · 10Y 基准与每日新闻证据</p></div>
        <button type="button" className="returns-today-button" onClick={() => updateDate(today)}>回到今天</button>
      </header>
      <div className="returns-layout">
        <main className="returns-daily">
          {isLoading ? <div className="returns-card returns-loading" aria-label="收益数据加载中" aria-busy="true"><Skeleton height="560px" variant="rectangular" /></div> : isError || !data ? (
            <div className="returns-card returns-error" role="alert"><span>收益数据加载失败，请稍后重试</span><button type="button" onClick={() => refetch()}>重试</button></div>
          ) : (
            <DailyEvidence
              key={selectedDate}
              yields={yields}
              news={news}
              onOpen={(id) => navigate(`/news/${id}?from=returns&date=${selectedDate}`)}
            />
          )}
        </main>
        <aside className="returns-calendar-area">
          <ReturnsCalendar selectedDate={selectedDate} today={today} data={data} onSelect={updateDate} onChangeMonth={(offset) => updateDate(shiftMonth(selectedDate, offset))} />
        </aside>
        <aside className="returns-factors-area">
          <ActiveFactors day={selectedDay} loading={isLoading} failed={isError} onOpen={(id) => navigate(`/factor/${id}`, { state: { from: returnPath } })} />
        </aside>
      </div>
    </div>
  )
}
