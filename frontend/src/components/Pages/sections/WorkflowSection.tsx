import React from 'react'
import SectionLayout from '@/components/Layout/SectionLayout'
import { Empty } from '@/components/UI'

const WorkflowSection: React.FC = () => {
  return (
    <SectionLayout
      title="工作流"
      main={
        <Empty
          title="工作流板块开发中"
          message="此处将展示数据流水线、最近任务等 · 由 C 负责"
          icon={<span className="text-5xl">⚙️</span>}
        />
      }
      side={
        <Empty
          title="侧栏"
          message="该板块自己的固定侧栏"
          icon={<span className="text-4xl">🔁</span>}
        />
      }
    />
  )
}

export default WorkflowSection