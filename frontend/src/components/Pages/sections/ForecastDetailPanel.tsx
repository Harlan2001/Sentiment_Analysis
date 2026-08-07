/**
 * AI 预测报告详情面板 — Perplexity Finance 风格
 */
import React, { useEffect, useState } from 'react'
import { Loading } from '@/components/UI'
import { API_PREFIX } from '@/constants'

interface Props { onClose: () => void }

const SC: Record<string, { bg: string; bd: string; tx: string }> = {
  '基准': { bg: 'bg-[#3b82f6]/8', bd: 'border-[#3b82f6]/25', tx: 'text-[#3b82f6]' },
  '牛市': { bg: 'bg-[#22c55e]/8', bd: 'border-[#22c55e]/25', tx: 'text-[#22c55e]' },
  '熊市': { bg: 'bg-[#ef4444]/8', bd: 'border-[#ef4444]/25', tx: 'text-[#ef4444]' },
  '黑天鹅': { bg: 'bg-[#f59e0b]/8', bd: 'border-[#f59e0b]/25', tx: 'text-[#f59e0b]' },
}

function ProbBar({ prob, color }: { prob: number; color: string }) {
  const pct = Math.round((prob || 0) * 100)
  return (
    <div className="flex-1 h-1.5 rounded-full bg-[#1f1f1f] overflow-hidden">
      <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
    </div>
  )
}

const ForecastDetailPanel: React.FC<Props> = ({ onClose }) => {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', h); return () => document.removeEventListener('keydown', h)
  }, [onClose])

  useEffect(() => {
    fetch(`${API_PREFIX}/forecast`)
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const report = data?.reports?.[0]
  const pred = report?.prediction || {}

  return (
    <div className="absolute inset-0 z-30 bg-[#0d0d0d] overflow-y-auto">
      <div className="sticky top-0 z-10 flex items-center px-4 py-2.5 bg-[#0d0d0d]/95 backdrop-blur-sm border-b border-[#1f1f1f]">
        <button onClick={onClose}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[13px] text-[#8b949e] hover:text-white hover:bg-[#1a1a1a] transition-colors">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 12H5m0 0l7 7m-7-7l7-7"/></svg>
          返回
        </button>
      </div>

      <div className="mx-auto w-full px-4 md:px-6 pb-16" style={{ maxWidth: '720px' }}>
        {loading ? (
          <div className="py-20 flex justify-center"><Loading text="加载中..." /></div>
        ) : !report ? (
          <div className="py-20 text-center text-[#8b949e] text-sm">暂无预测报告</div>
        ) : (
          <div className="space-y-5 pt-5">
            <div>
              <span className="text-[12px] text-[#6b7280]">{report.trade_date}</span>
              <h1 className="text-[1.8rem] font-semibold text-white mt-1">AI 市场预测</h1>
            </div>

            {/* 市场概览 */}
            {pred['市场概览'] && (
              <div className="detail-card">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-1 h-4 rounded-full bg-[#8b5cf6]" />
                  <span className="text-[12px] font-medium text-[#6b7280] uppercase tracking-wide">市场概览</span>
                </div>
                <p className="text-[13px] text-[#8b949e] leading-relaxed whitespace-pre-line">{pred['市场概览']}</p>
              </div>
            )}

            {/* 预测结果 */}
            {pred['预测结果'] && (
              <div className="detail-card">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-1 h-4 rounded-full bg-[#3b82f6]" />
                  <span className="text-[12px] font-medium text-[#6b7280] uppercase tracking-wide">预测结果</span>
                </div>
                <div className="space-y-3">
                  {Object.entries(pred['预测结果']).map(([k, v]: [string, any]) => (
                    <div key={k} className="rounded-lg bg-[#0a0a0a] p-4 border border-[#1f1f1f]">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-[14px] font-medium text-white">{k}维度</span>
                        {v['置信度'] != null && (
                          <span className="text-[11px] text-[#a78bfa]">置信度 {(v['置信度'] * 100).toFixed(0)}%</span>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <div className="flex justify-between text-[11px]">
                            <span className="text-[#6b7280]">上涨</span>
                            <span className="text-[#22c55e] font-mono">{((v['上涨概率'] || 0) * 100).toFixed(0)}%</span>
                          </div>
                          <ProbBar prob={v['上涨概率'] || 0} color="bg-[#22c55e]" />
                          <span className="text-[10px] text-[#22c55e]">+{v['上涨基点'] || 0}BP</span>
                        </div>
                        <div className="space-y-1.5">
                          <div className="flex justify-between text-[11px]">
                            <span className="text-[#6b7280]">下跌</span>
                            <span className="text-[#ef4444] font-mono">{((v['下跌概率'] || 0) * 100).toFixed(0)}%</span>
                          </div>
                          <ProbBar prob={v['下跌概率'] || 0} color="bg-[#ef4444]" />
                          <span className="text-[10px] text-[#ef4444]">{v['下跌基点'] || 0}BP</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 技术分析 */}
            {pred['技术分析'] && (
              <div className="detail-card">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-1 h-4 rounded-full bg-[#f59e0b]" />
                  <span className="text-[12px] font-medium text-[#6b7280] uppercase tracking-wide">技术分析</span>
                </div>
                <p className="text-[13px] text-[#8b949e] leading-relaxed whitespace-pre-line">{pred['技术分析']}</p>
              </div>
            )}

            {/* 因子分析 */}
            {pred['因子分析'] && (
              <div className="detail-card">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-1 h-4 rounded-full bg-[#22c55e]" />
                  <span className="text-[12px] font-medium text-[#6b7280] uppercase tracking-wide">因子分析</span>
                </div>
                <p className="text-[13px] text-[#8b949e] leading-relaxed whitespace-pre-line">{pred['因子分析']}</p>
              </div>
            )}

            {/* 情景分析 */}
            {pred['情景分析'] && (
              <div className="detail-card">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-1 h-4 rounded-full bg-[#ec4899]" />
                  <span className="text-[12px] font-medium text-[#6b7280] uppercase tracking-wide">情景分析</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(pred['情景分析']).map(([name, s]: [string, any]) => {
                    const c = SC[name] || SC['基准']
                    return (
                      <div key={name} className={`rounded-lg ${c.bg} border ${c.bd} p-3.5`}>
                        <div className="flex items-center justify-between mb-1.5">
                          <span className={`text-[13px] font-medium ${c.tx}`}>{name}</span>
                          <span className={`text-[12px] font-mono ${c.tx}`}>{((s['概率'] || 0) * 100).toFixed(0)}%</span>
                        </div>
                        <p className="text-[11px] text-[#8b949e] leading-relaxed line-clamp-4">{s['描述']}</p>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* 策略建议 */}
            {pred['策略建议'] && (
              <div className="detail-card">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-1 h-4 rounded-full bg-[#a78bfa]" />
                  <span className="text-[12px] font-medium text-[#6b7280] uppercase tracking-wide">策略建议</span>
                </div>
                <p className="text-[13px] text-[#8b949e] leading-relaxed whitespace-pre-line">{pred['策略建议']}</p>
              </div>
            )}

            {/* 风险提示 */}
            {pred['风险提示'] && (
              <div className="detail-card" style={{ borderColor: 'rgba(239,68,68,0.12)', background: 'rgba(239,68,68,0.03)' }}>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-1 h-4 rounded-full bg-[#ef4444]" />
                  <span className="text-[12px] font-medium text-[#ef4444] uppercase tracking-wide">风险提示</span>
                </div>
                <p className="text-[13px] text-[#8b949e] leading-relaxed whitespace-pre-line">{pred['风险提示']}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default ForecastDetailPanel
