/**
 * 有图新闻卡片 — 大窗口(整行) / 中窗口(2×2网格 compact 模式)
 */
import React from 'react'
import type { DiscoverNewsItem } from '@/types'

interface Props { item: DiscoverNewsItem; onClick: () => void; compact?: boolean }

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

const NewsCardLarge: React.FC<Props> = ({ item, onClick, compact }) => {
  const dir = DIR_TAG[item.direction || '']
  const domain = item.source_name || item.source || ''
  const favicon = item.source ? `https://www.google.com/s2/favicons?sz=32&domain=${item.source}.com` : ''

  if (compact) {
    // 中窗口模式：2×2 网格中的有图卡片
    return (
      <div onClick={onClick}
        className="group rounded-xl bg-[#111111] hover:bg-[#1a1a1a] overflow-hidden cursor-pointer
                   transition-all duration-200 hover:-translate-y-0.5
                   hover:shadow-[0_8px_30px_rgba(0,0,0,0.6)] border border-[#2a2a2a] hover:border-[#3a3a3a]">
        <div className="aspect-[16/9] overflow-hidden bg-[#161616]">
          <img src={item.thumbnail!} alt={item.title} className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-500" loading="lazy" />
        </div>
        <div className="p-2.5 flex flex-col gap-1">
          <div className="flex items-center gap-1.5 min-w-0">
            {favicon && <div className="relative shrink-0 overflow-hidden rounded-full w-3 h-3 bg-white"><img src={favicon} alt="" className="w-3 h-3 block" /></div>}
            <span className="text-[10px] text-[#8b949e] truncate">{domain}</span>
          </div>
          <h4 className="text-[13px] font-medium leading-snug line-clamp-2 text-[#e0e0e0] group-hover:text-white transition-colors">{item.title}</h4>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-[10px] text-[#6b7280] flex-shrink-0">{fmtTime(item.pub_time)}</span>
            {dir && <span className={`px-1 py-0.5 rounded-full text-[9px] font-medium ml-auto flex-shrink-0 ${dir.cls}`}>{dir.label}</span>}
          </div>
        </div>
      </div>
    )
  }

  // 大窗口模式：整行，图片 16:9 + 更大文字
  return (
    <div onClick={onClick}
      className="group rounded-xl bg-[#111111] hover:bg-[#1a1a1a] overflow-hidden cursor-pointer
                 transition-all duration-200 hover:-translate-y-0.5
                 hover:shadow-[0_8px_30px_rgba(0,0,0,0.6)] border border-[#2a2a2a] hover:border-[#3a3a3a]">
      <div className="aspect-[21/9] md:aspect-[3/1] max-h-[320px] overflow-hidden bg-[#161616]">
        <img src={item.thumbnail!} alt={item.title} className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-500" loading="lazy" />
      </div>
      <div className="p-4 flex flex-col gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {favicon && <div className="relative shrink-0 overflow-hidden rounded-full w-4 h-4 bg-white"><img src={favicon} alt="" className="w-4 h-4 block" /></div>}
          <span className="text-[12px] text-[#8b949e] truncate">{domain}</span>
          <span className="text-[12px] text-[#6b7280] flex-shrink-0 ml-auto">{fmtTime(item.pub_time)}</span>
          {dir && <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0 ${dir.cls}`}>{dir.label}</span>}
        </div>
        <h3 className="text-[1.3rem] md:text-[1.6rem] font-semibold leading-tight line-clamp-2 text-white group-hover:text-[#e0e0e0] transition-colors">{item.title}</h3>
      </div>
    </div>
  )
}

export default NewsCardLarge
