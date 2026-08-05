import React from 'react'
import SectionLayout from '@/components/Layout/SectionLayout'
import { Empty } from '@/components/UI'

const WatchlistSection: React.FC = () => {
  return (
    <SectionLayout
      title="关注列表"
      main={
        <Empty
          title="关注列表板块开发中"
          message="此处将展示用户关注列表、异动提醒等 · 由 C 负责"
          icon={<span className="text-5xl">⭐</span>}
        />
      }
      side={
        <Empty
          title="侧栏"
          message="该板块自己的固定侧栏"
          icon={<span className="text-4xl">🔔</span>}
        />
      }
    />
  )
}

export default WatchlistSection