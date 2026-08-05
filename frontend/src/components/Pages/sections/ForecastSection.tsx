import React from 'react'
import SectionLayout from '@/components/Layout/SectionLayout'
import { Empty } from '@/components/UI'

const ForecastSection: React.FC = () => {
  return (
    <SectionLayout
      title="预测"
      main={
        <Empty
          title="预测板块开发中"
          message="此处将展示 AI 预测报告、预测路径、驱动因子等 · 由 C 负责"
          icon={<span className="text-5xl">✨</span>}
        />
      }
      side={
        <Empty
          title="侧栏"
          message="该板块自己的固定侧栏"
          icon={<span className="text-4xl">📅</span>}
        />
      }
    />
  )
}

export default ForecastSection