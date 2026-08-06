import React from 'react'
import SectionLayout from '@/components/Layout/SectionLayout'
import { Empty } from '@/components/UI'

const PortfolioSection: React.FC = () => {
  return (
    <SectionLayout
      title="投资组合"
      main={
        <Empty
          title="投资组合板块开发中"
          message="此处将展示资产配置、AI 组合建议等 · 由 C 负责"
          icon={<span className="text-5xl">💼</span>}
        />
      }
      side={<Empty title="侧栏" message="该板块自己的固定侧栏" icon={<span className="text-4xl">📊</span>} />}
    />
  )
}

export default PortfolioSection
