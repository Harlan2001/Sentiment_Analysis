import React from 'react'
import SectionLayout from '@/components/Layout/SectionLayout'
import { Empty } from '@/components/UI'

const MarketSection: React.FC = () => {
  return (
    <SectionLayout
      title="市场"
      main={
        <Empty
          title="市场板块开发中"
          message="此处将展示收益率曲线、市场热点、舆情信号等 · 由 B 负责"
          icon={<span className="text-5xl">📈</span>}
        />
      }
      side={
        <Empty
          title="侧栏"
          message="该板块自己的固定侧栏"
          icon={<span className="text-4xl">🔍</span>}
        />
      }
    />
  )
}

export default MarketSection