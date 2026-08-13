/**
 * 发现页 — 新闻（flex-1）+ 市场数据（w-80）
 * 点击新闻/收益率/因子/摘要/策略后显示对应的详情覆盖层
 */
import React, { FormEvent, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import DiscoverNewsPanel from './DiscoverNewsPanel'
import MarketSidePanel from './MarketSidePanel'
import NewsDetailPanel from './NewsDetailPanel'
import YieldDetailPanel from './YieldDetailPanel'
import FactorDetailPanel from './FactorDetailPanel'
import StrategyDetailPanel from './StrategyDetailPanel'
import ForecastDetailPanel from './ForecastDetailPanel' // main新增，务必补上

type DetailView =
  | { type: 'news'; newsId: number }
  | { type: 'yield'; period: string }
  | { type: 'factor'; factorId: number }
  | { type: 'forecast' } // main新增forecast类型
  | { type: 'strategy' }
  | null

const DiscoverSection: React.FC = () => {
  const navigate = useNavigate()
  const formRef = useRef<HTMLFormElement>(null)
  const [detailView, setDetailView] = useState<DetailView>(null)
  const [question, setQuestion] = useState('')

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

  function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const draft = question.trim()
    navigate(draft ? `/chat/new?draft=${encodeURIComponent(draft)}` : '/chat/new')
  }

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
            onSummaryClick={() => openDetail({ type: 'forecast' })}
            onStrategyClick={() => openDetail({ type: 'strategy' })}
          />
        </div>
      </div>

      <form className="market-chat-dock" onSubmit={submitQuestion} ref={formRef}>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              formRef.current?.requestSubmit()
            }
          }}
          placeholder="询问关于今日债券市场的任何问题…"
          rows={2}
        />
        <div className="market-chat-actions">
          <span>BondSense · Agent 对话</span>
          <span className="market-chat-hint">Enter 发送，Shift + Enter 换行</span>
          <button type="submit" disabled={!question.trim()} aria-label="进入新会话">↑</button>
        </div>
      </form>

      {detailView?.type === 'news' && <NewsDetailPanel newsId={detailView.newsId} onClose={handleCloseDetail} onNewsClick={(newsId) => openDetail({ type: 'news', newsId })} />}
      {detailView?.type === 'yield' && <YieldDetailPanel period={detailView.period} onClose={handleCloseDetail} onNewsClick={(newsId) => openDetail({ type: 'news', newsId })} />}
      {detailView?.type === 'factor' && <FactorDetailPanel factorId={detailView.factorId} onClose={handleCloseDetail} onNewsClick={(newsId) => openDetail({ type: 'news', newsId })} />}
      {detailView?.type === 'forecast' && <ForecastDetailPanel onClose={handleCloseDetail} />}
      {detailView?.type === 'strategy' && <StrategyDetailPanel onClose={handleCloseDetail} />}
    </div>
  )
}

export default DiscoverSection