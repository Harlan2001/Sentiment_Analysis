/**
 * 右侧市场数据面板 — 收益率卡片网格 + 因子 + AI 摘要 + 策略信号
 */
import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchMarketPanel } from '@/api/market'
import { fetchCreditSpreadOverview } from '@/api/creditSpread'
import { fetchFuturesOverview } from '@/api/futures'
import { fetchTreasurySpread } from '@/api/treasury'
import YieldCardGrid from './YieldCardGrid'
import FactorActivityBar from './FactorActivityBar'
import AIMarketSummary from './AIMarketSummary'
import { Skeleton } from '@/components/ui'

interface Props {
  onYieldClick: (period: string) => void
  onFactorClick: (factorId: number) => void
  onSummaryClick: () => void
}

const MarketSidePanel: React.FC<Props> = ({ onYieldClick, onFactorClick, onSummaryClick }) => {
  const navigate = useNavigate()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['discover', 'market-panel'],
    queryFn: fetchMarketPanel,
    staleTime: 0,
    refetchOnMount: true,
  })
  const credit = useQuery({
    queryKey: ['market-side', 'credit', '10Y'],
    queryFn: () => fetchCreditSpreadOverview('10Y'),
    staleTime: 5 * 60 * 1000,
  })
  const futures = useQuery({
    queryKey: ['market-side', 'futures'],
    queryFn: fetchFuturesOverview,
    staleTime: 5 * 60 * 1000,
  })
  const ust = useQuery({
    queryKey: ['market-side', 'ust', '10Y'],
    queryFn: () => fetchTreasurySpread('10Y'),
    staleTime: 5 * 60 * 1000,
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
      <section className="cross-asset-snapshot" aria-label="跨资产快照">
        <header><span>跨资产快照</span><button type="button" onClick={() => navigate('/info')}>市场数据 ↗</button></header>
        <div>
          <button type="button" onClick={() => navigate('/info?asset=cgb')}>
            <span>中国10Y</span><strong>{data.yields.items.find((item) => item.period === '10Y')?.value.toFixed(3) ?? '—'}%</strong>
          </button>
          <button type="button" onClick={() => navigate('/info?asset=credit')}>
            <span>10Y信用利差</span><strong>{credit.data?.latest ? `${credit.data.latest.spread_bp.toFixed(1)}bp` : '—'}</strong>
          </button>
          <button type="button" onClick={() => navigate('/info?asset=futures')}>
            <span>T会员多空比</span><strong>{futures.data?.comparison.find((item) => item.variety === 'T')?.ratio?.toFixed(3) ?? '—'}</strong>
          </button>
          <button type="button" onClick={() => navigate('/info?asset=ust')}>
            <span>美国10Y</span><strong>{ust.data?.latest ? `${ust.data.latest.us.toFixed(3)}%` : '—'}</strong>
          </button>
          <button type="button" onClick={() => navigate('/info?asset=ust')}>
            <span>10Y中美利差</span><strong>{ust.data?.latest ? `${ust.data.latest.spread_bp.toFixed(0)}bp` : '—'}</strong>
          </button>
        </div>
        <p>各指标使用自身最近有效市场日期，点击进入对应资产详情。</p>
      </section>
      <div className="market-side-context-label"><span>当前资产详情</span><strong>中国国债</strong></div>
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
