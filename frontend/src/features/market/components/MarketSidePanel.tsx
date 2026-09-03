/**
 * 右侧市场数据面板 — 收益率卡片网格 + 因子 + AI 摘要 + 策略信号
 */
import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMarketPanel } from '@/api/market'
import YieldCardGrid from './YieldCardGrid'
import FactorActivityBar from './FactorActivityBar'
import AIMarketSummary from './AIMarketSummary'
import { Skeleton } from '@/components/UI'

interface Props {
  onYieldClick: (period: string) => void
  onFactorClick: (factorId: number) => void
  onSummaryClick: () => void
}

const MarketSidePanel: React.FC<Props> = ({ onYieldClick, onFactorClick, onSummaryClick }) => {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['discover', 'market-panel'],
    queryFn: fetchMarketPanel,
    staleTime: 0,
    refetchOnMount: true,
  })

  if (isLoading) {
    return (
      <div className="p-2 space-y-2">
        <Skeleton height="320px" variant="rectangular" />
        <Skeleton height="140px" variant="rectangular" />
        <Skeleton height="100px" variant="rectangular" />
        <Skeleton height="80px" variant="rectangular" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center h-64 text-[#8b949e] text-xs p-4">
        市场数据加载失败
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 p-2">
      <YieldCardGrid yields={data.yields} onYieldClick={onYieldClick} />
      <FactorActivityBar factors={data.factors} onFactorClick={onFactorClick} />
      {data.ai_summary ? (
        <AIMarketSummary data={data.ai_summary} onClick={onSummaryClick} />
      ) : (
        <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-3 text-center text-[11px] text-[#6b7280]">
          AI 市场摘要暂无数据
        </div>
      )}
    </div>
  )
}

export default MarketSidePanel
