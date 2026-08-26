import React, { useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { useForecastHistory, useForecastReport } from '@/features/market/hooks/useForecastApi'
import { Skeleton } from '@/components/UI'
import type { FullForecastReport, ScenarioItem } from '@/types'
import ForecastCalendar from '../components/ForecastCalendar'

const UP = '#f87171'
const DOWN = '#4ade80'

const UP_DIRS = new Set(['上行', '上升', '上涨', '走高', '走强', '扩大', '增加', '回升', '升', '涨'])
const DOWN_DIRS = new Set(['下行', '下降', '下跌', '走低', '走弱', '收窄', '减少', '回落', '降', '跌'])

function highlightNumbers(text: string): React.ReactNode {
  const re = /(上行|上升|上涨|走高|走强|扩大|增加|回升|升|涨|下行|下降|下跌|走低|走弱|收窄|减少|回落|降|跌)?\s*([-+]?\d+(?:\.\d+)?)\s*(%|bp|基点|个基点)/g
  const nodes: React.ReactNode[] = []
  let last = 0
  let key = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    const dir = m[1]
    const num = m[2]
    const cls = dir ? (UP_DIRS.has(dir) ? 'text-red-400' : 'text-green-400') : num.startsWith('+') ? 'text-red-400' : num.startsWith('-') ? 'text-green-400' : null
    if (m.index > last) nodes.push(text.slice(last, m.index))
    nodes.push(cls ? <span key={key++} className={`${cls} font-medium`}>{m[0]}</span> : m[0])
    last = m.index + m[0].length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

export default function ForecastSection() {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const { data, isLoading, isError } = useForecastReport(selectedDate ?? undefined)
  const { data: history } = useForecastHistory(30)
  const report = useMemo<FullForecastReport | null>(() => { const value = data?.latestReport?.prediction; if (!value) return null; try { return typeof value === 'string' ? JSON.parse(value) : value as FullForecastReport } catch { return null } }, [data])
  const noReport = !isLoading && !isError && !!data && (!data.reports || data.reports.length === 0)

  return <div className="home-section-page" style={{ gridTemplateRows: 'minmax(0, 1fr)' }}>
    <div className="home-section-grid">
    <main className="home-section-main space-y-4">
      <div className="pt-2">
        <h1 className="text-lg font-bold text-white">AI 预测报告</h1>
      </div>
      {isLoading ? <div className="space-y-3"><Skeleton height="180px" variant="rectangular" /><Skeleton height="300px" variant="rectangular" /></div>
        : isError ? <Empty text="预测报告加载失败，请稍后重试" />
        : noReport ? <Empty text="该日期暂无预测报告" />
        : !report ? <Empty text="预测报告解析失败" />
        : <>
        {report.报告摘要 && <Card title="报告摘要" className="forecast-summary-card"><p className="text-sm text-gray-300 leading-relaxed indent-[2em]">{report.报告摘要}</p></Card>}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{([['日', '日度预测'], ['周', '周度预测'], ['月', '月度预测']] as const).map(([key, label]) => { const p = report.预测结果?.[key]; return p ? <ForecastMetric key={key} label={label} rise={p.上涨概率} fall={p.下跌概率} bp={p.上涨基点} reason={p.分析理由} /> : null })}</div>
        {report.市场概览 && <Card title="市场概览"><p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line indent-[2em] max-h-[91px] overflow-y-auto pr-2">{report.市场概览}</p></Card>}
        {report.情景分析 && <Card title="情景分析"><ScenarioBars scenarios={report.情景分析} /></Card>}
        {report.技术分析 && <Card title="技术分析"><p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line indent-[2em] max-h-[91px] overflow-y-auto pr-2">{highlightNumbers(report.技术分析)}</p></Card>}
        {report.因子分析 && <Card title="因子分析"><p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line indent-[2em] max-h-[91px] overflow-y-auto pr-2">{highlightNumbers(report.因子分析)}</p></Card>}
        {report.策略建议 && <Card title="策略建议"><StrategyChips text={report.策略建议} /></Card>}
      </>}
    </main>
    <aside className="home-section-sidebar forecast-history-sidebar"><ForecastCalendar history={history?.history} selectedDate={selectedDate} onSelect={setSelectedDate} /><RiskPanel report={report} /></aside>
    </div>
  </div>
}

function ForecastMetric({ label, rise, fall, bp, reason }: { label: string; rise: number; fall: number; bp: number; reason?: string }) {
  const value = Math.round((rise || 0) * 100)
  const up = (rise || 0) >= (fall || 0)
  const color = up ? UP : DOWN
  const bpWidth = Math.min((Math.abs(bp || 0) / 30) * 100, 100)
  const light = up ? '#fca5a5' : '#86efac'
  const shadow = up ? 'rgba(248,113,113,0.35)' : 'rgba(74,222,128,0.35)'
  const option = {
    series: [{
      type: 'gauge', startAngle: 210, endAngle: -30, min: 0, max: 100,
      radius: '100%', center: ['50%', '60%'],
      pointer: { length: '50%', width: 2.5, itemStyle: { color: '#e5e5e5' } },
      progress: { show: true, roundCap: true, width: 8, itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: light }, { offset: 1, color }] }, shadowBlur: 6, shadowColor: shadow } },
      axisLine: { roundCap: true, lineStyle: { width: 8, color: [[1, '#232327']] } },
      axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
      anchor: { show: false }, title: { show: false },
      detail: { formatter: '{value}%', offsetCenter: [0, '18%'], color, fontSize: 24, fontWeight: 600 },
      data: [{ value }],
    }],
  }
  return <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
    <div className="flex items-center justify-between"><p className="text-xs text-gray-500">{label}</p><span className="inline-flex items-center gap-1.5 text-xs text-gray-400"><i className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />{up ? '看涨' : '看跌'}</span></div>
    <ReactECharts opts={{ renderer: 'svg' }} style={{ height: 130 }} option={option} />
    <div className="flex items-center gap-2"><span className="text-[11px] text-gray-500 shrink-0">预期基点</span><div className="h-1.5 flex-1 rounded-full bg-[#2a2a2e] overflow-hidden"><div className="h-full rounded-full" style={{ width: `${bpWidth}%`, background: bp >= 0 ? UP : DOWN }} /></div><span className={`text-sm font-medium shrink-0 ${bp >= 0 ? 'text-red-400' : 'text-green-400'}`}>{bp >= 0 ? '+' : ''}{bp?.toFixed(1)} BP</span></div>
    {reason && <p className="mt-2.5 text-xs text-gray-500 line-clamp-3">{reason}</p>}
  </section>
}

const SCENARIO_META: Record<string, { color: string; order: number }> = {
  '基准': { color: '#6b7280', order: 0 },
  '牛市': { color: UP, order: 1 },
  '熊市': { color: DOWN, order: 2 },
  '黑天鹅': { color: '#f59e0b', order: 3 },
}

function ScenarioBars({ scenarios }: { scenarios: NonNullable<FullForecastReport['情景分析']> }) {
  const entries = (Object.entries(scenarios) as [string, ScenarioItem][]).filter(([, v]) => Boolean(v)).sort((a, b) => (SCENARIO_META[a[0]]?.order ?? 9) - (SCENARIO_META[b[0]]?.order ?? 9))
  return <div className="space-y-3.5">{entries.map(([name, s]) => { const pct = Math.round((s.概率 || 0) * 100); const color = SCENARIO_META[name]?.color ?? '#8b8b8b'; return <div key={name}>
    <div className="flex items-center justify-between text-xs mb-1.5"><span className="inline-flex items-center gap-1.5 text-gray-300"><i className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />{name}</span><span className="text-gray-400 font-mono">{pct}%</span></div>
    <div className="h-2 rounded-full bg-[#2a2a2e] overflow-hidden"><div className="h-full rounded-full" style={{ width: `${Math.min(pct, 100)}%`, background: color }} /></div>
    {s.描述 && <p className="mt-1.5 text-xs text-gray-500 leading-relaxed">{s.描述}</p>}
    {s.触发条件 && <p className="mt-1 text-[11px] text-gray-600">触发：{s.触发条件}</p>}
  </div> })}</div>
}

function StrategyChips({ text }: { text: string }) {
  const items = text.split(/\n|；|;/).map((s) => s.trim()).filter(Boolean)
  if (items.length <= 1) return <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line indent-[2em] max-h-[91px] overflow-y-auto pr-2">{text}</p>
  return <div className="flex flex-wrap gap-2 max-h-[91px] overflow-y-auto pr-2">{items.map((item, i) => { const clean = item.replace(/^[\s·•\-–—\d.、:：()]+/, ''); return <span key={i} className="inline-flex items-center gap-1.5 rounded-lg border border-[#2a2a2e] bg-[#0d0d0d] px-3 py-1.5 text-xs text-gray-300"><span className="text-amber-400">•</span>{clean || item}</span> })}</div>
}

function RiskPanel({ report }: { report: FullForecastReport | null }) {
  const text = report?.风险提示
  if (!text) return null
  return <section className="rounded-xl border border-amber-400/20 bg-[#111111] p-4">
    <h2 className="flex items-center gap-1.5 text-sm font-semibold text-amber-300 mb-2"><span className="text-xs">▲</span>风险提示</h2>
    <p className="text-sm text-amber-200 leading-relaxed whitespace-pre-line">{text}</p>
  </section>
}

function Empty({ text }: { text: string }) { return <div className="min-h-[240px] rounded-xl border border-[#2a2a2e] bg-[#111111] flex items-center justify-center text-sm text-gray-500">{text}</div> }

function Card({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) { return <section className={`rounded-xl border border-[#2a2a2e] bg-[#111111] p-5 ${className}`}><h2 className="text-sm font-medium text-gray-400 mb-3">{title}</h2>{children}</section> }
