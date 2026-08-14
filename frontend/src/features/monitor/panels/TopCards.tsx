import React from 'react'
import type { TopCards } from '@/types'
import { MetricCard } from './Widgets'

interface Props {
  cards: TopCards
}

export const TopSummaryCards: React.FC<Props> = ({ cards }) => {
  const pendingStatus = cards.pending > 500 ? 'danger' : cards.pending > 100 ? 'warning' : 'normal'

  return (
    <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 mb-4">
      <MetricCard label="新闻总量" value={cards.news_total.toLocaleString()} />
      <MetricCard label="已分析" value={cards.analyzed.toLocaleString()} />
      <MetricCard label="待分析" value={cards.pending.toLocaleString()} status={pendingStatus} />
      <MetricCard label="因子总数" value={cards.factor_total.toLocaleString()} />
      <MetricCard label="收益率覆盖" value={`${cards.yield_days}天`} />
    </div>
  )
}
