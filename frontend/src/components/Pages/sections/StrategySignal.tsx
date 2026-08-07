/**
 * 最新策略信号 — 展示 2-3 条推荐，可点击进入详情
 */
import React from 'react'
import type { StrategySignalData } from '@/types'

interface Props {
  signals: StrategySignalData[]
  onClick: () => void
}

const CONFIDENCE_COLOR = (v: number) =>
  v >= 0.7 ? 'text-[#22c55e]' : v >= 0.5 ? 'text-[#f59e0b]' : 'text-[#ef4444]'

const StrategySignal: React.FC<Props> = ({ signals, onClick }) => {
  return (
    <div
      className="rounded-xl bg-[#111111] border border-[#2a2a2a] overflow-hidden cursor-pointer hover:border-[#3a3a3a] transition-colors"
      onClick={onClick}
    >
      <div className="px-3 py-2 border-b border-[#1f1f1f] flex items-center justify-between">
        <span className="text-[11px] font-medium text-[#6b7280] uppercase tracking-wide">
          最新策略信号
        </span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[#6b7280]">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </div>

      <div className="divide-y divide-[#1f1f1f]">
        {signals.slice(0, 3).map((data, i) => (
          <div key={i} className="px-3 py-2.5">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-[#6b7280] font-mono">#{i + 1}</span>
              <p className="text-[13px] font-semibold text-white truncate">{data.recommendation}</p>
            </div>
            <div className="flex items-center gap-2 mt-1.5">
              <span className={`text-[11px] font-mono font-medium ${CONFIDENCE_COLOR(data.confidence)}`}>
                置信度 {(data.confidence * 100).toFixed(0)}%
              </span>
            </div>
            {data.reasons.length > 0 && (
              <div className="mt-1.5 flex gap-1 flex-wrap">
                {data.reasons.slice(0, 2).map((r, j) => (
                  <span key={j} className="px-1.5 py-0.5 rounded-md text-[10px] bg-[#3b82f6]/10 text-[#3b82f6] truncate max-w-[150px]">
                    {r}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default StrategySignal
