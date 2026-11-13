import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useForecastHistory, useForecastReport } from '@/features/market/hooks/useForecastApi'
import { Skeleton } from '@/components/ui'
import type {
  ForecastDriver,
  ForecastHistoryItem,
  ForecastPrediction,
  FullForecastReport,
  ScenarioItem,
} from '@/types'
import ForecastCalendar from '../components/ForecastCalendar'
import './forecast.css'

type HorizonKey = '日' | '周' | '月'

const HORIZONS: Array<{ key: HorizonKey; label: string; description: string }> = [
  { key: '日', label: 'T+1', description: '1 个交易日' },
  { key: '周', label: 'T+5', description: '5 个交易日' },
  { key: '月', label: 'T+20', description: '20 个交易日' },
]

const SCENARIO_ORDER: Record<string, number> = { 基准: 0, 牛市: 1, 熊市: 2, 黑天鹅: 3 }

function asReport(value: unknown): FullForecastReport | null {
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value) : value
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as FullForecastReport
      : null
  } catch {
    return null
  }
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function formatPercent(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

function formatBp(value: number | null): string {
  if (value === null) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}bp`
}

function isUp(prediction: ForecastPrediction): boolean {
  return (finiteNumber(prediction.上涨概率) ?? 0) >= (finiteNumber(prediction.下跌概率) ?? 0)
}

function primaryBp(prediction: ForecastPrediction): number | null {
  return finiteNumber(isUp(prediction) ? prediction.上涨基点 : prediction.下跌基点)
}

function directionLabel(prediction: ForecastPrediction, explicitTarget: boolean): string {
  const direction = isUp(prediction) ? '上行' : '下行'
  return explicitTarget ? `收益率${direction}` : direction
}

function validDateParam(value: string | null): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

function previousReport(
  history: ForecastHistoryItem[] | undefined,
  currentDate: string,
): FullForecastReport | null {
  const previous = (history ?? [])
    .filter((item) => item.date < currentDate && item.reports?.full_report)
    .sort((a, b) => b.date.localeCompare(a.date))[0]
  return previous ? asReport(previous.reports.full_report) : null
}

export default function ForecastPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const dateParam = searchParams.get('date')
  const selectedDate = validDateParam(dateParam) ? dateParam : null
  const { data, isLoading, isError, refetch } = useForecastReport(selectedDate ?? undefined)
  const { data: historyData, isError: isHistoryError } = useForecastHistory(30)
  const [activeHorizon, setActiveHorizon] = useState<HorizonKey>('周')
  const [historyOpen, setHistoryOpen] = useState(false)

  const report = useMemo(() => asReport(data?.latestReport?.prediction), [data])
  const reportMeta = data?.latestReport
  const reportDate = reportMeta?.trade_date ?? selectedDate ?? ''
  const noReport = !isLoading && !isError && !!data && data.reports.length === 0
  const explicitTarget = report?.预测标的?.期限 === '10Y'
  const availableHorizons = HORIZONS.filter((item) => report?.预测结果?.[item.key])
  const activeKey = report?.预测结果?.[activeHorizon]
    ? activeHorizon
    : availableHorizons[0]?.key ?? '日'
  const activeMeta = HORIZONS.find((item) => item.key === activeKey) ?? HORIZONS[0]
  const activePrediction = report?.预测结果?.[activeKey]
  const prior = useMemo(
    () => previousReport(historyData?.history, reportDate),
    [historyData, reportDate],
  )
  const priorPrediction = prior?.预测结果?.[activeKey]

  const selectDate = useCallback((date: string | null) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      if (date) next.set('date', date)
      else next.delete('date')
      return next
    })
  }, [setSearchParams])
  const closeHistory = useCallback(() => setHistoryOpen(false), [])

  let comparison = '暂无上期对照'
  if (activePrediction && priorPrediction) {
    const sameDirection = isUp(activePrediction) === isUp(priorPrediction)
    const currentBp = primaryBp(activePrediction)
    const previousBp = primaryBp(priorPrediction)
    const bpDelta = currentBp !== null && previousBp !== null ? currentBp - previousBp : null
    comparison = `${sameDirection ? '方向不变' : `${isUp(priorPrediction) ? '上行' : '下行'} → ${isUp(activePrediction) ? '上行' : '下行'}`}${bpDelta !== null ? ` · 主方向BP较上期 ${formatBp(bpDelta)}` : ''}`
  }

  return (
    <div className="home-section-page forecast-page-shell">
      <main className="forecast-page">
        <header className="forecast-header">
          <div>
            <div className="forecast-title-row">
              <h1>{explicitTarget ? '10Y 国债收益率预测' : '债券市场预测'}</h1>
              <span className="forecast-research-badge">研究参考</span>
            </div>
            <p>{explicitTarget
              ? report?.预测标的?.方向口径 ?? '上涨/下跌均指10Y国债收益率方向'
              : '历史报告未明确预测期限与方向口径，以下内容按原报告展示'}</p>
          </div>
          <div className="forecast-header-actions">
            {selectedDate && <button type="button" onClick={() => selectDate(null)}>最新报告</button>}
            <button type="button" onClick={() => setHistoryOpen(true)}>历史报告</button>
          </div>
        </header>

        {isLoading ? <PageLoading />
          : isError ? <Empty text="预测报告加载失败，请稍后重试" onRetry={() => void refetch()} />
            : noReport ? <Empty text="该日期暂无预测报告" />
              : !report || !reportMeta ? <Empty text="预测报告解析失败或缺少完整报告" />
                : <>
                  <section className="forecast-report-meta" aria-label="报告信息">
                    <span>报告日期 <b>{reportDate}</b></span>
                    <span>生成时间 <b>{reportMeta.created_at || '—'}</b></span>
                    <span>模型 <b>{reportMeta.model_name || '—'}</b></span>
                    <span>Prompt <b>{reportMeta.prompt_version || '—'}</b></span>
                    {report.数据状态?.新闻截至 && <span>新闻截至 <b>{report.数据状态.新闻截至}</b></span>}
                    {report.数据状态?.收益率截至 && <span>收益率截至 <b>{report.数据状态.收益率截至}</b></span>}
                  </section>

                  {activePrediction && <section className={`forecast-hero is-${isUp(activePrediction) ? 'up' : 'down'}`}>
                    <div className="forecast-hero-copy">
                      <span className="forecast-eyebrow">{activeMeta.label} · {activeMeta.description}核心判断</span>
                      <h2>{directionLabel(activePrediction, explicitTarget)}为主</h2>
                      <p>{report.报告摘要 || activePrediction.分析理由 || '原报告未提供摘要。'}</p>
                    </div>
                    <div className="forecast-hero-change">
                      <span>较上一期</span>
                      <strong>{comparison}</strong>
                      <small>概率是方向分布，置信度是模型自评，均不代表历史准确率</small>
                    </div>
                  </section>}

                  <section className="forecast-horizon-grid" aria-label="预测周期">
                    {availableHorizons.map((item) => {
                      const prediction = report.预测结果?.[item.key]
                      return prediction ? <PredictionCard
                        key={item.key}
                        meta={item}
                        prediction={prediction}
                        active={item.key === activeKey}
                        explicitTarget={explicitTarget}
                        onSelect={() => setActiveHorizon(item.key)}
                      /> : null
                    })}
                  </section>

                  <div className="forecast-decision-grid">
                    <DriversPanel
                      drivers={report.核心驱动}
                      activeKey={activeKey}
                      activeLabel={activeMeta.label}
                      prediction={activePrediction}
                      reportDate={reportDate}
                    />
                    <ConditionsPanel prediction={activePrediction} risk={report.风险提示} />
                  </div>

                  <ScenarioPanel scenarios={report.情景分析} />
                  <FullAnalysis report={report} />

                  <footer className="forecast-footnote">
                    本页为 AI 基于既有行情与新闻生成的研究参考，不构成交易指令。历史预测诊断仅在 admin 监控看板展示。
                  </footer>
                </>}
      </main>

      {historyOpen && <HistoryDialog
        history={historyData?.history}
        isError={isHistoryError}
        selectedDate={selectedDate}
        onSelect={(date) => { selectDate(date); closeHistory() }}
        onClose={closeHistory}
      />}
    </div>
  )
}

function PredictionCard({
  meta,
  prediction,
  active,
  explicitTarget,
  onSelect,
}: {
  meta: { key: HorizonKey; label: string; description: string }
  prediction: ForecastPrediction
  active: boolean
  explicitTarget: boolean
  onSelect: () => void
}) {
  const up = finiteNumber(prediction.上涨概率)
  const down = finiteNumber(prediction.下跌概率)
  const confidence = finiteNumber(prediction.置信度)
  const total = up !== null && down !== null ? up + down : null
  const validPair = total !== null && Math.abs(total - 1) <= 0.02 && up! >= 0 && down! >= 0
  const upWidth = validPair && total! > 0 ? (up! / total!) * 100 : 0
  const directionUp = isUp(prediction)
  const bp = primaryBp(prediction)

  return (
    <button
      type="button"
      className={`forecast-horizon-card${active ? ' active' : ''}`}
      aria-pressed={active}
      aria-label={`查看${meta.label}预测依据`}
      onClick={onSelect}
    >
      <span className="forecast-horizon-head">
        <strong>{meta.label}</strong>
        <span>{meta.description}</span>
      </span>
      <span className="forecast-direction">
        <i className={`forecast-direction-dot ${directionUp ? 'up' : 'down'}`} aria-hidden="true" />
        {directionLabel(prediction, explicitTarget)}
      </span>
      <span className="forecast-probabilities">
        <span><i className="up" />上行 <b>{formatPercent(up)}</b></span>
        <span><i className="down" />下行 <b>{formatPercent(down)}</b></span>
      </span>
      {validPair && <span className="forecast-probability-track" aria-hidden="true">
        <i className="up" style={{ width: `${upWidth}%` }} />
        <i className="down" style={{ width: `${100 - upWidth}%` }} />
      </span>}
      <span className="forecast-primary-bp">
        <span>主方向条件变动</span>
        <b>{formatBp(bp)}</b>
      </span>
      <span className="forecast-horizon-foot">
        <span title="模型自评置信度，不等于方向概率或历史准确率">置信度 {confidence === null ? '—' : confidence.toFixed(2)}</span>
        <span>{active ? '当前分析' : '查看依据 →'}</span>
      </span>
    </button>
  )
}

function DriversPanel({
  drivers,
  activeKey,
  activeLabel,
  prediction,
  reportDate,
}: {
  drivers?: ForecastDriver[]
  activeKey: HorizonKey
  activeLabel: string
  prediction?: ForecastPrediction
  reportDate: string
}) {
  const relevant = (drivers ?? []).filter((driver) =>
    !driver.适用周期?.length || driver.适用周期.includes(activeKey),
  )
  return (
    <section className="forecast-panel forecast-drivers-panel">
      <PanelHeading title="为什么这样判断" subtitle={`${activeLabel}周期 · 驱动与原始证据`} />
      {relevant.length > 0 ? <div className="forecast-driver-list">
        {relevant.map((driver, index) => <DriverRow key={`${driver.类型}-${index}`} driver={driver} reportDate={reportDate} />)}
      </div> : <div className="forecast-legacy-reason">
        <span>{drivers?.length ? '该周期暂无结构化驱动与证据' : '历史报告未提供结构化驱动与证据'}</span>
        <p>{prediction?.分析理由 || '该周期暂无分析理由。'}</p>
      </div>}
      {relevant.length > 0 && prediction?.分析理由 && <div className="forecast-active-reason">
        <strong>{activeLabel}周期补充</strong>
        <p>{prediction.分析理由}</p>
      </div>}
    </section>
  )
}

function DriverRow({ driver, reportDate }: { driver: ForecastDriver; reportDate: string }) {
  const evidenceIds = Array.from(new Set((driver.证据新闻ID ?? []).filter((id) => Number.isInteger(id) && id > 0)))
  return (
    <article className="forecast-driver-row">
      <div className="forecast-driver-topline">
        <strong>{driver.类型 || '市场驱动'}</strong>
        {driver.方向 && <span className={`forecast-driver-direction ${driver.方向 === '上行' ? 'up' : driver.方向 === '下行' ? 'down' : ''}`}>{driver.方向 === '中性' ? '影响中性' : `收益率${driver.方向}`}</span>}
        {!!driver.适用周期?.length && <small>{driver.适用周期.map((key) => HORIZONS.find((item) => item.key === key)?.label).join(' / ')}</small>}
      </div>
      <p>{driver.理由 || '—'}</p>
      <div className="forecast-evidence-links">
        {evidenceIds.length > 0 ? evidenceIds.map((id) => <Link
          key={id}
          to={`/news/${id}?from=forecast&date=${encodeURIComponent(reportDate)}`}
        >证据 · 新闻 {id} →</Link>) : <span>该驱动无直接新闻证据</span>}
      </div>
    </article>
  )
}

function ConditionsPanel({ prediction, risk }: { prediction?: ForecastPrediction; risk?: string }) {
  return (
    <aside className="forecast-panel forecast-conditions-panel">
      <PanelHeading title="成立条件与失效风险" subtitle="先知道什么时候不该沿用当前判断" />
      <ConditionList title="核心假设" items={prediction?.假设条件} empty="原报告未提供核心假设" />
      <ConditionList title="观点失效条件" items={prediction?.失效条件} empty="历史报告未结构化提供失效条件" />
      {risk && <div className="forecast-risk-block"><strong>风险提示</strong><p>{risk}</p></div>}
    </aside>
  )
}

function ConditionList({ title, items, empty }: { title: string; items?: string[]; empty: string }) {
  return (
    <section className="forecast-condition-list">
      <h3>{title}</h3>
      {items?.length ? <ul>{items.filter(Boolean).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p>{empty}</p>}
    </section>
  )
}

function ScenarioPanel({ scenarios }: { scenarios?: FullForecastReport['情景分析'] }) {
  const entries = (Object.entries(scenarios ?? {}) as Array<[string, ScenarioItem]>)
    .filter(([, scenario]) => Boolean(scenario))
    .sort((a, b) => (SCENARIO_ORDER[a[0]] ?? 9) - (SCENARIO_ORDER[b[0]] ?? 9))
  if (!entries.length) return null
  return (
    <section className="forecast-panel forecast-scenarios-panel">
      <PanelHeading title="情景预案" subtitle="概率、可观察触发条件与后续关注，不是确定性结果" />
      <div className="forecast-scenario-list">
        {entries.map(([name, scenario]) => <article key={name} className="forecast-scenario-row">
          <header><strong>{name}</strong><b>{formatPercent(finiteNumber(scenario.概率))}</b></header>
          <p>{scenario.描述 || '—'}</p>
          <dl>
            <div><dt>触发条件</dt><dd>{scenario.触发条件 || '原报告未提供'}</dd></div>
            <div><dt>应对关注</dt><dd>{scenario.应对关注 || '原报告未提供'}</dd></div>
          </dl>
        </article>)}
      </div>
    </section>
  )
}

function FullAnalysis({ report }: { report: FullForecastReport }) {
  const sections = [
    ['市场概览', report.市场概览],
    ['技术分析', report.技术分析],
    ['因子分析', report.因子分析],
    ['策略建议', report.策略建议],
  ].filter((section): section is [string, string] => Boolean(section[1]))
  if (!sections.length) return null
  return (
    <section className="forecast-full-analysis">
      <PanelHeading title="完整分析" subtitle="保留原始研报内容，按需展开，不再截断成小滚动区" />
      <div>
        {sections.map(([title, text]) => <details key={title}>
          <summary>{title}<span aria-hidden="true">＋</span></summary>
          <p>{text}</p>
        </details>)}
      </div>
    </section>
  )
}

function HistoryDialog({
  history,
  isError,
  selectedDate,
  onSelect,
  onClose,
}: {
  history?: ForecastHistoryItem[]
  isError: boolean
  selectedDate: string | null
  onSelect: (date: string) => void
  onClose: () => void
}) {
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      previousFocus?.focus()
    }
  }, [onClose])

  return (
    <div className="forecast-history-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="forecast-history-dialog" role="dialog" aria-modal="true" aria-labelledby="forecast-history-title">
        <header><div><h2 id="forecast-history-title">历史预测报告</h2><p>选择有报告的日期，返回后保留 URL 深链</p></div><button ref={closeRef} type="button" aria-label="关闭历史报告" onClick={onClose}>×</button></header>
        {isError ? <p className="forecast-history-error">历史日历加载失败，请稍后重试。</p>
          : <ForecastCalendar history={history} selectedDate={selectedDate} onSelect={onSelect} />}
      </section>
    </div>
  )
}

function PanelHeading({ title, subtitle }: { title: string; subtitle: string }) {
  return <header className="forecast-panel-heading"><h2>{title}</h2><p>{subtitle}</p></header>
}

function PageLoading() {
  return <div className="forecast-loading" aria-label="预测报告加载中"><Skeleton height="160px" variant="rectangular" /><Skeleton height="210px" variant="rectangular" /><Skeleton height="300px" variant="rectangular" /></div>
}

function Empty({ text, onRetry }: { text: string; onRetry?: () => void }): ReactNode {
  return <div className="forecast-empty"><p>{text}</p>{onRetry && <button type="button" onClick={onRetry}>重新加载</button>}</div>
}
