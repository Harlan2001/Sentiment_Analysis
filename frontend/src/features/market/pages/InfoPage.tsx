import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import FuturesPage from '@/features/market/pages/FuturesPage'
import CreditSpreadPage from '@/features/market/pages/CreditSpreadPage'
import TreasurySpreadPage from '@/features/market/pages/TreasurySpreadPage'

/**
 * 信息 —— 市场信息类页面的统一入口。
 *
 * 期货持仓 / 信用利差 / 中美利差三者本质都是"看市场数据"，归到同一入口下
 * 用二级标签切换，避免导航栏标签过多。
 *
 * **实现方式**：本页只做标签壳，三个页面各自保持独立路由与完整功能
 * （各有右栏、图表、聊天框），此处仅负责切换渲染。
 * 因此原有 URL（/futures、/credit-spread、/treasury-spread）依然可用，
 * 外部链接与书签不受影响。
 */

type InfoTab = 'futures' | 'credit' | 'treasury'

const TABS: { key: InfoTab; label: string; hint: string }[] = [
  { key: 'futures', label: '期货持仓', hint: '国债期货多空持仓' },
  { key: 'credit', label: '信用利差', hint: '信用债与国债利差' },
  { key: 'treasury', label: '中美利差', hint: '中债与美债利差' },
]

export default function InfoPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initial = (searchParams.get('tab') as InfoTab) || 'futures'
  const [tab, setTab] = useState<InfoTab>(
    TABS.some((item) => item.key === initial) ? initial : 'futures',
  )

  const switchTab = (key: InfoTab) => {
    setTab(key)
    // 同步 URL，便于分享与刷新后保持当前标签
    setSearchParams({ tab: key }, { replace: true })
  }

  return (
    <div className="info-shell">
      <nav className="info-tabs" aria-label="市场信息分类">
        {TABS.map((item) => (
          <button
            key={item.key}
            onClick={() => switchTab(item.key)}
            className={`info-tab${tab === item.key ? ' active' : ''}`}
          >
            <span className="info-tab-label">{item.label}</span>
            <span className="info-tab-hint">{item.hint}</span>
          </button>
        ))}
      </nav>

      <div className="info-body" key={tab}>
        {tab === 'futures' && <FuturesPage />}
        {tab === 'credit' && <CreditSpreadPage />}
        {tab === 'treasury' && <TreasurySpreadPage />}
      </div>
    </div>
  )
}