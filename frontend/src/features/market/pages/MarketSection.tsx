/**
 * 发现页 — 新闻（flex-1）+ 市场数据（w-80）
 * 点击新闻/收益率/因子/摘要/策略后显示对应的详情覆盖层
 */
import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { HomeChatDock } from '../components/HomeChatDock'
import DiscoverNewsPanel from '../components/DiscoverNewsPanel'
import MarketSidePanel from '../components/MarketSidePanel'
import NewsDetailPanel from '../components/NewsDetailPanel'
import YieldDetailPanel from '../components/YieldDetailPanel'
import FactorDetailPanel from '../components/FactorDetailPanel'
import StrategyDetailPanel from '../components/StrategyDetailPanel'

type DetailView =
  | { type: 'news'; newsId: number }
  | { type: 'yield'; period: string }
  | { type: 'factor'; factorId: number }
  | { type: 'strategy' }
  | null

const MarketSection: React.FC = () => {
  const navigate = useNavigate()
  const [detailView, setDetailView] = useState<DetailView>(null)

  React.useEffect(() => {
    const onPop = (event: PopStateEvent) => {
      const state = (event.state as { detailView?: DetailView } | null) || window.history.state
      setDetailView(state?.detailView || null)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const openDetail = useCallback((view: NonNullable<DetailView>) => {
    try {
      window.history.pushState({ ...window.history.state, detailView: view }, '')
    } catch(e) {
      // 兼容异常兜底
    }
    setDetailView(view)
  }, [])

  const handleCloseDetail = useCallback(() => {
    if (window.history.state?.detailView) {
      window.history.back()
      return
    }
    setDetailView(null)
  }, [])

  return (
    <div className="market-workspace">
      <div className="market-workspace-body">
        <div className="market-discover-panel">
          <DiscoverNewsPanel onNewsClick={(newsId) => openDetail({ type: 'news', newsId })} />
        </div>
        <div className="market-side-panel">
          <MarketSidePanel
            onYieldClick={(period) => openDetail({ type: 'yield', period })}
            onFactorClick={(factorId) => openDetail({ type: 'factor', factorId })}
            onSummaryClick={() => navigate('/forecast')}
            onStrategyClick={() => openDetail({ type: 'strategy' })}
          />
        </div>
      </div>

      <HomeChatDock placeholder={'\u8be2\u95ee\u5173\u4e8e\u4eca\u65e5\u503a\u5238\u5e02\u573a\u7684\u4efb\u4f55\u95ee\u9898\u2026'} />

      {detailView?.type === 'news' && <NewsDetailPanel newsId={detailView.newsId} onClose={handleCloseDetail} onNewsClick={(newsId) => openDetail({ type: 'news', newsId })} />}
      {detailView?.type === 'yield' && <YieldDetailPanel period={detailView.period} onClose={handleCloseDetail} onNewsClick={(newsId) => openDetail({ type: 'news', newsId })} />}
      {detailView?.type === 'factor' && <FactorDetailPanel factorId={detailView.factorId} onClose={handleCloseDetail} onNewsClick={(newsId) => openDetail({ type: 'news', newsId })} />}
      {detailView?.type === 'strategy' && <StrategyDetailPanel onClose={handleCloseDetail} />}
    </div>
  )
}

export default MarketSection