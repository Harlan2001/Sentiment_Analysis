import React from 'react'

/**
 * 板块两栏框架（520 : 300）
 * - 这是新工作台"壳"提供的共享栅格契约：左栏展示板块内容，右栏展示该板块自己的侧栏
 * - 各板块页只需传入 main / side，无需重复写栅格布局
 */
interface SectionLayoutProps {
  /** 板块中文名（用于占位标题） */
  title: string
  /** 左栏内容（板块主体） */
  main?: React.ReactNode
  /** 右栏内容（该板块自己的固定侧栏） */
  side?: React.ReactNode
}

const SectionLayout: React.FC<SectionLayoutProps> = ({ title, main, side }) => {
  return (
    <div className="flex gap-4 p-4 h-full">
      {/* 左栏：板块内容（520） */}
      <div className="flex-[5] min-w-0 overflow-y-auto pr-1">
        {main ?? <div className="text-sm text-gray-500">{title} 板块内容区</div>}
      </div>

      {/* 右栏：该板块自己的侧栏（300） */}
      <div className="flex-[3] min-w-0 overflow-y-auto pr-1">
        {side ?? <div className="text-sm text-gray-500">{title} 侧栏区</div>}
      </div>
    </div>
  )
}

export default SectionLayout
