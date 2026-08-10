/**
 * 无图迷你新闻卡片 — 纯文字紧凑型，高度为有图卡片的 1/2
 */
import React from 'react'
import type { DiscoverNewsItem } from '@/types'

interface Props { item: DiscoverNewsItem; onClick: () => void }

const DIR_TAG: Record<string, { label: string; cls: string }> = {
  positive: { label: '利多', cls: 'bg-[#22c55e]/15 text-[#22c55e]' },
  negative: { label: '利空', cls: 'bg-[#ef4444]/15 text-[#ef4444]' },
  neutral:  { label: '中性', cls: 'bg-[#6b7280]/15 text-[#6b7280]' },
}

function fmtTime(t: string): string {
  if (!t) return ''
  const d = Math.floor((Date.now() - new Date(t).getTime()) / 864e5)
  if (d > 0) return `${d}天前`
  const h = Math.floor((Date.now() - new Date(t).getTime()) / 36e5)
  return h > 0 ? `${h}小时前` : '刚刚'
}

const NewsCardSmall: React.FC<Props> = ({ item, onClick }) => {
  const dir = DIR_TAG[item.direction || '']
  const domain = item.source_name || item.source || ''
  const favicon = item.source ? `https://www.google.com/s2/favicons?sz=32&domain=${item.source}.com` : ''

  return (
    <div onClick={onClick}
      className="group rounded-xl bg-[#111111] hover:bg-[#1a1a1a] p-3 cursor-pointer flex-1
                 transition-all duration-200 hover:-translate-y-0.5
                 hover:shadow-[0_8px_30px_rgba(0,0,0,0.6)] border border-[#2a2a2a] hover:border-[#3a3a3a]
                 flex flex-col gap-1 justify-center min-h-0">
      {/* 来源行 */}
      <div className="flex items-center gap-1.5 min-w-0">
        {favicon && <div className="relative shrink-0 overflow-hidden rounded-full w-3 h-3 bg-white"><img src={favicon} alt="" className="w-3 h-3 block" /></div>}
        <span className="text-[10px] text-[#8b949e] truncate">{domain}</span>
      </div>
      {/* 标题 */}
      <h4 className="text-[12px] font-medium leading-snug line-clamp-2 text-[#e0e0e0] group-hover:text-white transition-colors">{item.title}</h4>
      {/* 底部 */}
      <div className="flex items-center gap-1.5 mt-auto">
        <span className="text-[10px] text-[#6b7280] flex-shrink-0">{fmtTime(item.pub_time)}</span>
        {dir && <span className={`px-1 py-0.5 rounded-full text-[9px] font-medium ml-auto flex-shrink-0 ${dir.cls}`}>{dir.label}</span>}
      </div>
    </div>
  )
}

export default NewsCardSmall
