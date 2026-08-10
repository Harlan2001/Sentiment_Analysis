/**
 * AI 市场摘要 — 默认展示 4 行，可展开
 * 显示方向标签（看涨/看跌/中性）+ 驱动因素
 */
import React, { useState } from 'react'
import type { AIMarketSummaryData } from '@/types'

interface Props {
  data: AIMarketSummaryData
  onClick: () => void
}

const DIR_TAG: Record<string, { label: string; cls: string }> = {
  bullish: { label: '看涨', cls: 'bg-[#22c55e]/15 text-[#22c55e]' },
  bearish: { label: '看跌', cls: 'bg-[#ef4444]/15 text-[#ef4444]' },
  neutral: { label: '中性', cls: 'bg-[#6b7280]/15 text-[#6b7280]' },
}

const AIMarketSummary: React.FC<Props> = ({ data, onClick }) => {
  const [expanded, setExpanded] = useState(false)
  const tag = DIR_TAG[data.direction] || DIR_TAG.neutral

  return (
    <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] overflow-hidden cursor-pointer hover:border-[#3a3a3a] transition-colors"
      onClick={onClick}>
      <div className="px-3 py-2 border-b border-[#1f1f1f] flex items-center justify-between">
        <span className="text-[11px] font-medium text-[#6b7280] uppercase tracking-wide">
          AI 市场摘要
        </span>
        <div className="flex items-center gap-1.5">
          {data.date && (
            <span className="text-[10px] text-[#6b7280]">{data.date}</span>
          )}
          <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${tag.cls}`}>
            {tag.label}
          </span>
        </div>
      </div>

      <div className="px-3 py-2">
        <div className="border-l-2 border-[#8b5cf6] pl-3 bg-gradient-to-r from-[#8b5cf6]/5 to-transparent rounded-r-md">
          <p className={`text-[12px] text-[#8b949e] leading-relaxed whitespace-pre-line ${expanded ? '' : 'line-clamp-4'}`}>
            {data.text}
          </p>
          {data.text.length > 200 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-[11px] text-[#3b82f6] hover:text-[#60a5fa] mt-1 transition-colors"
            >
              {expanded ? '收起' : '展开'}
            </button>
          )}
        </div>

        {data.drivers.length > 0 && (
          <div className="mt-2 space-y-0.5">
            {data.drivers.slice(0, 3).map((d, i) => (
              <div key={i} className="text-[11px] text-[#6b7280] flex items-start gap-1">
                <span className="text-[#3b82f6] flex-shrink-0">{i + 1}.</span>
                <span className="truncate">{d}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default AIMarketSummary
