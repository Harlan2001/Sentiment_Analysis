import React, { useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { useForecastHistory, useForecastReport } from '@/features/market/hooks/useForecastApi'
import { Skeleton } from '@/components/UI'
import type { FullForecastReport } from '@/types'

export default function ForecastSection() {
  const { data, isLoading, isError } = useForecastReport()
  const { data: history } = useForecastHistory(30)
  const report = useMemo<FullForecastReport | null>(() => { const value = data?.latestReport?.prediction; if (!value) return null; try { return typeof value === 'string' ? JSON.parse(value) : value as FullForecastReport } catch { return null } }, [data])
  return <div className="home-section-page">
    <header className="home-section-heading"><h1 className="text-lg font-bold text-white">AI 预测报告</h1><p className="text-xs text-gray-500 mt-1">{data?.latestReport?.trade_date || ''} 市场预测分析</p></header>
    <div className="home-section-grid">
    <main className="home-section-main space-y-4">
      {isLoading ? <div className="space-y-3"><Skeleton height="180px" variant="rectangular" /><Skeleton height="300px" variant="rectangular" /></div> : isError || !report ? <div className="h-64 flex items-center justify-center text-sm text-gray-500">预测报告加载失败，请稍后重试</div> : <>
        {report.报告摘要 && <Card title="报告摘要" className="forecast-summary-card"><p className="text-sm text-gray-300 leading-relaxed">{report.报告摘要}</p></Card>}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{([['日', '日度预测'], ['周', '周度预测'], ['月', '月度预测']] as const).map(([key, label]) => { const p = report.预测结果?.[key]; return p ? <ForecastMetric key={key} label={label} rise={p.上涨概率} bp={p.上涨基点} reason={p.分析理由} /> : null })}</div>
        {report.市场概览 && <Card title="市场概览"><p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">{report.市场概览}</p></Card>}
        {report.情景分析 && <Card title="情景分析"><div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{Object.entries(report.情景分析).map(([name, scenario]: any) => scenario && <div key={name} className="rounded-lg border border-[#2a2a2e] bg-[#0d0d0d] p-4"><div className="flex justify-between text-sm text-white"><span>{name}</span><span className="text-amber-400">{Math.round((scenario.概率 || 0) * 100)}%</span></div><p className="mt-2 text-sm text-gray-400 leading-relaxed">{scenario.描述}</p></div>)}</div></Card>}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{report.技术分析 && <Card title="技术分析"><p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">{report.技术分析}</p></Card>}{report.因子分析 && <Card title="因子分析"><p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">{report.因子分析}</p></Card>}</div>
        {report.策略建议 && <Card title="策略建议"><p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">{report.策略建议}</p></Card>}{report.风险提示 && <Card title="风险提示"><p className="text-sm text-amber-200 leading-relaxed whitespace-pre-line">{report.风险提示}</p></Card>}
      </>}
    </main>
    <aside className="home-section-sidebar forecast-history-sidebar"><HistoryPanel history={history} /></aside>
    </div>
  </div>
}
function ForecastMetric({ label, rise, bp, reason }: { label: string; rise: number; bp: number; reason?: string }) { const value = Math.round((rise || 0) * 100); return <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4"><p className="text-xs text-gray-500">{label}</p><ReactECharts opts={{ renderer: 'svg' }} style={{ height: 135 }} option={{ series: [{ type: 'gauge', startAngle: 210, endAngle: -30, min: 0, max: 100, pointer: { itemStyle: { color: value >= 50 ? '#ef4444' : '#22c55e' } }, axisLine: { lineStyle: { width: 12, color: [[.5, '#22c55e'], [1, '#ef4444']] } }, detail: { formatter: '{value}%', color: value >= 50 ? '#ef4444' : '#22c55e', fontSize: 22 }, data: [{ value }], axisLabel: { color: '#777' } }] }} /><p className={bp >= 0 ? 'text-sm text-red-400' : 'text-sm text-green-400'}>{bp >= 0 ? '+' : ''}{bp?.toFixed(1)} BP</p>{reason && <p className="mt-2 text-xs text-gray-500 line-clamp-3">{reason}</p>}</section> }
function HistoryPanel({ history }: { history: any }) { const [open, setOpen] = useState<string | null>(null); return <section className="h-full rounded-xl border border-[#2a2a2e] bg-[#111111] p-4"><h2 className="text-sm font-semibold text-white">历史预测</h2><p className="text-xs text-gray-500 mt-1 mb-3">最近 7 天</p>{!history ? <p className="text-sm text-gray-600 text-center py-5">加载中...</p> : <div className="space-y-2">{(history.history || []).slice(0, 7).map((item: any) => { const report = item.reports?.full_report; const day = report?.预测结果?.日; if (!day) return null; const rise = (day.上涨概率 || 0) >= (day.下跌概率 || 0); const expanded = open === item.date; return <div key={item.date}><button onClick={() => setOpen(expanded ? null : item.date)} className="w-full rounded-lg border border-[#1e1e1e] bg-[#0d0d0d] px-3 py-2 text-left hover:bg-[#171717]"><div className="flex items-center gap-2 text-xs"><span className="text-gray-500">{item.date}</span><span className={rise ? 'text-red-400' : 'text-green-400'}>{rise ? '看涨' : '看跌'}</span><span className="ml-auto text-gray-400">{Math.round(((rise ? day.上涨概率 : day.下跌概率) || 0) * 100)}%</span></div></button>{expanded && <p className="px-3 py-2 text-xs text-gray-400 leading-relaxed">{report.报告摘要 || '暂无详细摘要'}</p>}</div> })}</div>}</section> }
function Card({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) { return <section className={`rounded-xl border border-[#2a2a2e] bg-[#111111] p-5 ${className}`}><h2 className="text-sm font-medium text-gray-400 mb-3">{title}</h2>{children}</section> }
