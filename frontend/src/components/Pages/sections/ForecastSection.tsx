/**
 * 预测页面 — AI 预测报告 + 概率仪表盘 + 场景分析 + 历史回溯
 */
import React, { useState, useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useForecastReport, useForecastHistory } from '@/hooks/useForecastApi'
import { Skeleton } from '@/components/UI'
import type { ForecastReport, ForecastPrediction, FullForecastReport, ScenarioItem, ScenarioAnalysis } from '@/types'

function formatDate(iso?: string, fmt?: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (fmt === 'MM-DD HH:mm') {
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  return iso.slice(0, 10)
}

/** 概率仪表盘 */
function ProbabilityGauge({ rise, riseBp, fallBp }: { rise: number; riseBp: number; fallBp: number }) {
  const risePct = Math.round(rise * 100)
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    series: [{
      type: 'gauge',
      startAngle: 210, endAngle: -30, min: 0, max: 100, splitNumber: 5,
      radius: '95%', center: ['50%', '58%'],
      pointer: { itemStyle: { color: risePct >= 50 ? '#ef4444' : '#22c55e' }, length: '55%', width: 5 },
      axisLine: {
        lineStyle: {
          width: 14,
          color: [[0.5, '#22c55e'], [1, '#ef4444']],
        },
      },
      axisTick: { show: false },
      splitLine: { length: 8, lineStyle: { color: '#0f172a', width: 2 } },
      axisLabel: { color: '#94a3b8', fontSize: 9, distance: -26 },
      detail: {
        valueAnimation: true,
        formatter: (v: number) => `${v}%`,
        color: risePct >= 50 ? '#ef4444' : '#22c55e',
        fontSize: 26, offsetCenter: [0, '-12%'],
      },
      title: { show: false },
      data: [{ value: risePct }],
    }],
  }
  return (
    <div className="flex flex-col items-center">
      <ReactECharts option={option} style={{ height: 150, width: 180 }} opts={{ renderer: 'svg' }} />
      <div className="-mt-2 text-center text-xs text-gray-400">
        上涨 <span className="text-red-400 font-semibold">+{riseBp.toFixed(1)} BP</span>
        <span className="mx-2 text-gray-600">·</span>
        下跌 <span className="text-green-400 font-semibold">{fallBp.toFixed(1)} BP</span>
      </div>
    </div>
  )
}

function ScenarioCard({ title, scenario, icon }: { title: string; scenario: ScenarioItem; icon: string }) {
  return (
    <div className="rounded-xl bg-[#111111] border border-[#2a2a2e] p-4">
      <div className="flex items-center gap-2 mb-2">
        <span>{icon}</span>
        <span className="text-sm font-medium text-white">{title}</span>
        <span className="text-xs text-gray-500 ml-auto">概率 {(scenario.概率 * 100).toFixed(1)}%</span>
      </div>
      <p className="text-sm text-gray-400 leading-relaxed line-clamp-3">{scenario.描述}</p>
    </div>
  )
}

const SCENARIO_ICONS: Record<string, string> = {
  '基准': '📊', '牛市': '📈', '熊市': '📉', '黑天鹅': '🦢',
}

const ForecastSection: React.FC = () => {
  const [historyLimit] = useState(30)
  const { data: reportData, isLoading, isError } = useForecastReport()
  const { data: historyData } = useForecastHistory(historyLimit)

  const fullReport = useMemo<FullForecastReport | null>(() => {
    if (!reportData?.latestReport?.prediction) return null
    const pred = reportData.latestReport.prediction
    if (typeof pred === 'string') {
      try { return JSON.parse(pred) }
      catch { return null }
    }
    return pred as FullForecastReport
  }, [reportData])

  const predictions = useMemo(() => {
    if (!fullReport) return null
    return {
      day: fullReport['预测结果']?.['日'],
      week: fullReport['预测结果']?.['周'],
      month: fullReport['预测结果']?.['月'],
    }
  }, [fullReport])

  const scenarios = useMemo(() => {
    if (!fullReport) return null
    const sa = fullReport['情景分析']
    if (!sa) return null
    return {
      '基准': sa['基准'],
      '牛市': sa['牛市'],
      '熊市': sa['熊市'],
      '黑天鹅': sa['黑天鹅'],
    }
  }, [fullReport])

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="p-5 space-y-5">
        <h1 className="text-lg font-bold text-white">AI 预测报告</h1>

        {isLoading ? (
          <div className="space-y-3">
            <Skeleton height="200px" variant="rectangular" />
            <Skeleton height="150px" variant="rectangular" />
            <Skeleton height="100px" variant="rectangular" />
          </div>
        ) : isError || !reportData?.latestReport ? (
          <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
            预测报告加载失败，请稍后重试
          </div>
        ) : (
          <>
            {/* 报告头部 */}
            <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold text-white">
                    {reportData.latestReport.trade_date} 市场预测分析报告
                  </h2>
                  <p className="text-xs text-gray-500 mt-1">
                    模型: {reportData.latestReport.model_name} · 版本: {reportData.latestReport.prompt_version}
                  </p>
                </div>
                <div className="text-right text-xs text-gray-500">
                  生成时间<br />
                  <span className="text-gray-400">{formatDate(reportData.latestReport.created_at, 'MM-DD HH:mm')}</span>
                </div>
              </div>
              {fullReport?.报告摘要 && (
                <div className="mt-4 pt-4 border-t border-[#2a2a2e]">
                  <p className="text-sm text-gray-300 leading-relaxed">{fullReport.报告摘要}</p>
                </div>
              )}
            </div>

            {/* 概率仪表盘：日/周/月 */}
            {predictions && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(['day', 'week', 'month'] as const).map(period => {
                  const p = predictions[period]
                  if (!p) return null
                  const label = period === 'day' ? '日度预测' : period === 'week' ? '周度预测' : '月度预测'
                  return (
                    <div key={period} className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
                      <h3 className="text-xs font-medium text-gray-500 mb-2">{label}</h3>
                      <ProbabilityGauge rise={p.上涨概率} riseBp={p.上涨基点} fallBp={p.下跌基点} />
                      {p.分析理由 && (
                        <p className="text-xs text-gray-500 mt-2 line-clamp-2">{p.分析理由}</p>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* 市场概览 */}
            {fullReport?.['市场概览'] && (
              <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
                <h3 className="text-xs font-medium text-gray-500 mb-3">市场概览</h3>
                <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
                  {typeof fullReport['市场概览'] === 'string' ? fullReport['市场概览'] : String(fullReport['市场概览'])}
                </div>
              </div>
            )}

            {/* 情景分析 */}
            {scenarios && Object.keys(scenarios).length > 0 && (
              <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
                <h3 className="text-xs font-medium text-gray-500 mb-3">情景分析</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {Object.entries(scenarios).map(([key, scenario]) => {
                    if (!scenario) return null
                    return <ScenarioCard key={key} title={key} scenario={scenario} icon={SCENARIO_ICONS[key] || '📊'} />
                  })}
                </div>
              </div>
            )}

            {/* 技术分析 + 因子分析 */}
            {(fullReport?.['技术分析'] || fullReport?.['因子分析']) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {fullReport['技术分析'] && (
                  <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
                    <h3 className="text-xs font-medium text-gray-500 mb-3">技术分析</h3>
                    <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
                      {typeof fullReport['技术分析'] === 'string' ? fullReport['技术分析'] : String(fullReport['技术分析'])}
                    </div>
                  </div>
                )}
                {fullReport['因子分析'] && (
                  <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
                    <h3 className="text-xs font-medium text-gray-500 mb-3">因子分析</h3>
                    <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
                      {typeof fullReport['因子分析'] === 'string' ? fullReport['因子分析'] : String(fullReport['因子分析'])}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 策略建议 */}
            {fullReport?.['策略建议'] && (
              <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
                <h3 className="text-xs font-medium text-gray-500 mb-3">策略建议</h3>
                <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
                  {typeof fullReport['策略建议'] === 'string' ? fullReport['策略建议'] : String(fullReport['策略建议'])}
                </div>
              </div>
            )}

            {/* 风险提示 */}
            {fullReport?.['风险提示'] && (
              <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
                <h3 className="text-xs font-medium text-amber-400 mb-3">风险提示</h3>
                <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
                  {typeof fullReport['风险提示'] === 'string' ? fullReport['风险提示'] : String(fullReport['风险提示'])}
                </div>
              </div>
            )}

            {/* 历史预测 */}
            <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
              <h3 className="text-xs font-medium text-gray-500 mb-3">
                历史预测 · 最近 7 天
              </h3>
              {!historyData ? (
                <div className="text-xs text-gray-600 py-4 text-center">加载中...</div>
              ) : (historyData.history || []).length === 0 ? (
                <div className="text-xs text-gray-600 py-4 text-center">暂无历史预测数据</div>
              ) : (
                <div className="space-y-2">
                  {(historyData.history || []).slice(0, 7).map(day => {
                    const fullReport = (day.reports as any)?.full_report
                    if (!fullReport) return null
                    const predResult = fullReport['预测结果'] || {}
                    const dayPred = predResult['日']
                    if (!dayPred) return null
                    const isRise = (dayPred.上涨概率 || 0) > (dayPred.下跌概率 || 0)
                    const prob = isRise ? (dayPred.上涨概率 || 0) : (dayPred.下跌概率 || 0)
                    const bp = isRise ? (dayPred.上涨基点 || 0) : (dayPred.下跌基点 || 0)
                    return (
                      <HistoryRow
                        key={day.date}
                        date={day.date}
                        isRise={isRise}
                        prob={prob}
                        bp={bp}
                        fullReport={fullReport}
                      />
                    )
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

/** 可点击展开的历史预测行 */
function HistoryRow({ date, isRise, prob, bp, fullReport }: {
  date: string; isRise: boolean; prob: number; bp: number;
  fullReport?: FullForecastReport | null;
}) {
  const [expanded, setExpanded] = useState(false)
  const pct = prob > 0 ? `${Math.round(prob * 100)}%` : '-'

  return (
    <div>
      <button
        className="w-full flex items-center gap-3 py-2 px-3 rounded-lg bg-[#0d0d0d] border border-[#1e1e1e] hover:bg-[#141414] transition-colors group"
        onClick={() => setExpanded(v => !v)}
      >
        <span className="text-xs text-gray-500 w-20 shrink-0">{date}</span>
        <span className={`text-xs font-medium w-12 ${isRise ? 'text-red-400' : 'text-green-400'}`}>
          {isRise ? '看涨' : '看跌'}
        </span>
        <div className="flex-1 h-1.5 rounded-full bg-[#1e1e1e] overflow-hidden">
          <div
            className={`h-full rounded-full ${isRise ? 'bg-red-500/60' : 'bg-green-500/60'}`}
            style={{ width: `${Math.round(prob * 100)}%` }}
          />
        </div>
        <span className="text-xs text-gray-500 w-12 text-right">{pct}</span>
        <span className={`text-xs w-16 text-right font-mono ${isRise ? 'text-red-400' : 'text-green-400'}`}>
          {bp > 0 ? '+' : ''}{bp.toFixed(1)}BP
        </span>
        <span className={`text-gray-600 text-xs transition-transform ${expanded ? 'rotate-90' : ''}`}>▶</span>
      </button>
      {expanded && fullReport && (
        <div className="mt-2 ml-9 p-4 rounded-lg bg-[#0d0d0d] border border-[#1e1e1e] space-y-3 text-sm text-gray-300">
          {fullReport.报告摘要 && (
            <p className="leading-relaxed">{fullReport.报告摘要}</p>
          )}
          {fullReport.市场概览 && (
            <div>
              <span className="text-xs font-medium text-gray-500">市场概览</span>
              <p className="mt-1 leading-relaxed whitespace-pre-line">
                {typeof fullReport.市场概览 === 'string' ? fullReport.市场概览.slice(0, 300) : String(fullReport.市场概览).slice(0, 300)}
              </p>
            </div>
          )}
          {fullReport.策略建议 && (
            <div>
              <span className="text-xs font-medium text-gray-500">策略建议</span>
              <p className="mt-1 leading-relaxed">
                {typeof fullReport.策略建议 === 'string' ? fullReport.策略建议.slice(0, 200) : String(fullReport.策略建议).slice(0, 200)}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ForecastSection
