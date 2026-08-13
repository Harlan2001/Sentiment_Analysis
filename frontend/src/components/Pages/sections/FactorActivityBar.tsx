/**
 * 因子活跃度进度条 — Top5
 */
import React from 'react'
import type { FactorActivity } from '@/types'

interface Props {
  factors: FactorActivity[]
  onFactorClick: (factorId: number) => void
}

const FactorActivityBar: React.FC<Props> = ({ factors, onFactorClick }) => {
  const content = factors.length === 0
    ? <div className="text-center text-[11px] text-[#6b7280] py-2">暂无活跃因子数据</div>
    : factors.map((f, i) => (
        <div key={f.id} className="flex items-center gap-2 cursor-pointer hover:bg-[#1a1a1a] rounded-md px-1 py-0.5 transition-colors -mx-1"
          onClick={() => onFactorClick(f.id)}>
          <span className="text-[11px] text-[#6b7280] w-4 text-right tabular-nums">{i + 1}</span>
          <span className="text-[12px] text-[#e0e0e0] w-20 truncate" title={f.name}>{f.name}</span>
          <div className="flex-1 h-1.5 rounded-full bg-[#1f1f1f] overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-[#f59e0b] to-[#d97706] transition-all duration-500"
              style={{ width: `${f.activity_score * 100}%` }}
            />
          </div>
          <span className="text-[11px] font-mono text-[#8b949e] w-9 text-right tabular-nums">
            {f.activity_score.toFixed(2)}
          </span>
        </div>
      ))

  return (
    <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] overflow-hidden">
      <div className="px-3 py-2 border-b border-[#1f1f1f]">
        <span className="text-[11px] font-medium text-[#6b7280] uppercase tracking-wide">
          今日活跃因子
        </span>
      </div>
      <div className="px-3 py-2 space-y-1.5">{content}</div>
    </div>
  )
}

export default FactorActivityBar
