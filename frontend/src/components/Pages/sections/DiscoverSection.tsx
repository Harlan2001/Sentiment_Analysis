/**
 * 发现页 — 新闻（flex-1）+ 市场数据（w-80）
 * 点击新闻/收益率/因子/摘要/策略后显示对应的详情覆盖层
 */
import React, { useState, useCallback } from 'react'
import DiscoverNewsPanel from './DiscoverNewsPanel'
import MarketSidePanel from './MarketSidePanel'
import NewsDetailPanel from './NewsDetailPanel'
import YieldDetailPanel from './YieldDetailPanel'
import FactorDetailPanel from './FactorDetailPanel'
import ForecastDetailPanel from './ForecastDetailPanel'
import StrategyDetailPanel from './StrategyDetailPanel'

type DetailView =
  | { type: 'news'; newsId: number }
  | { type: 'yield'; period: string }
  | { type: 'factor'; factorId: number }
  | { type: 'forecast' }
  | { type: 'strategy' }
  | null

const DiscoverSection: React.FC = () => {
  const [detailView, setDetailView] = useState<DetailView>(null)
  // 同步到 history，使得点击返回可回到上一页面而不是固定回到发现首页
  React.useEffect(() => {
    const onPop = (e: PopStateEvent) => {
      const st: any = (e.state as any) || window.history.state || {}
      if (st && st.detailView) setDetailView(st.detailView)
      else setDetailView(null)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const handleNewsClick = useCallback((newsId: number) => {
    const v = { type: 'news', newsId } as DetailView
    try { window.history.pushState({ ...window.history.state, detailView: v }, '') } catch(e) {}
    setDetailView(v)
  }, [])

  const handleYieldClick = useCallback((period: string) => {
    const v = { type: 'yield', period } as DetailView
    try { window.history.pushState({ ...window.history.state, detailView: v }, '') } catch(e) {}
    setDetailView(v)
  }, [])

  const handleFactorClick = useCallback((factorId: number) => {
    const v = { type: 'factor', factorId } as DetailView
    try { window.history.pushState({ ...window.history.state, detailView: v }, '') } catch(e) {}
    setDetailView(v)
  }, [])

  const handleSummaryClick = useCallback(() => {
    const v = { type: 'forecast' } as DetailView
    try { window.history.pushState({ ...window.history.state, detailView: v }, '') } catch(e) {}
    setDetailView(v)
  }, [])

  const handleStrategyClick = useCallback(() => {
    const v = { type: 'strategy' } as DetailView
    try { window.history.pushState({ ...window.history.state, detailView: v }, '') } catch(e) {}
    setDetailView(v)
  }, [])

  const handleCloseDetail = useCallback(() => {
    // 优先使用浏览器历史返回，若无历史则直接关闭
    try {
      if (window.history.state && window.history.state.detailView) {
        window.history.back()
        return
      }
    } catch (e) {}
    setDetailView(null)
  }, [])

  return (
    <div className="relative flex gap-0 h-full">
      {/* 中间：新闻发现区 */}
      <div className="flex-1 min-w-0 overflow-y-auto">
        <DiscoverNewsPanel onNewsClick={handleNewsClick} />
      </div>

      {/* 右侧：市场数据面板 */}
      <div className="w-80 flex-shrink-0 border-l border-[#2a2a2a] overflow-y-auto bg-[#0a0a0a]">
        <MarketSidePanel
          onYieldClick={handleYieldClick}
          onFactorClick={handleFactorClick}
          onSummaryClick={handleSummaryClick}
          onStrategyClick={handleStrategyClick}
        />
      </div>

      {/* 详情覆盖层：根据类型显示不同面板 */}
      {detailView?.type === 'news' && (
        <NewsDetailPanel
          newsId={detailView.newsId}
          onClose={handleCloseDetail}
          onNewsClick={handleNewsClick}
        />
      )}
      {detailView?.type === 'yield' && (
        <YieldDetailPanel
          period={detailView.period}
          onClose={handleCloseDetail}
          onNewsClick={handleNewsClick}
        />
      )}
      {detailView?.type === 'factor' && (
        <FactorDetailPanel
          factorId={detailView.factorId}
          onClose={handleCloseDetail}
          onNewsClick={handleNewsClick}
        />
      )}
      {detailView?.type === 'forecast' && (
        <ForecastDetailPanel onClose={handleCloseDetail} />
      )}
      {detailView?.type === 'strategy' && (
        <StrategyDetailPanel onClose={handleCloseDetail} />
      )}
    </div>
  )
}

export default DiscoverSection
