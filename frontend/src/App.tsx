import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/Layout/MainLayout'
import WorkspaceLayout from './components/Layout/WorkspaceLayout'
import { NewsPage, FactorPage, PredictionPage, AgentPage, StrategyListPage, ChangePage, LoginPage, DashboardPage, MacroDataPage, ResearchListPage, ResearchDetailPage, AiStrategyGenerationPreviewPage, AiStrategyHistoryPage } from './components/Pages'
import { MarketSection, ReturnsSection, ForecastSection, WatchlistSection, PortfolioSection, WorkflowSection } from './components/Pages/sections'
import { useAuth } from './contexts/AuthContext'
import { useBehaviorTracker } from './hooks/useBehaviorTracker'
import { Loading } from './components/UI/Loading'

/**
 * 路由表：
 * - 新工作台「壳」（默认首页）：/market /returns /forecast /watchlist /portfolio /workflow
 * - 旧页面（保留原路径）：/news /factors /prediction /dashboard 等
 */
function AppRoutes() {
  return (
    <Routes>
      {/* 新工作台壳（默认首页） */}
      <Route element={<WorkspaceLayout />}>
        <Route path="/" element={<Navigate to="/market" replace />} />
        <Route path="/market" element={<MarketSection />} />
        <Route path="/returns" element={<ReturnsSection />} />
        <Route path="/forecast" element={<ForecastSection />} />
        <Route path="/watchlist" element={<WatchlistSection />} />
        <Route path="/portfolio" element={<PortfolioSection />} />
        <Route path="/workflow" element={<WorkflowSection />} />
      </Route>

      {/* 旧页面（保留原路径） */}
      <Route element={<MainLayout />}>
        <Route path="/news" element={<NewsPage />} />
        <Route path="/factors" element={<FactorPage />} />
        <Route path="/prediction" element={<PredictionPage />} />
        <Route path="/agents" element={<AgentPage />} />
        <Route path="/macro-signal-logs" element={<Navigate to="/dashboard" replace />} />
        <Route path="/select-strategy" element={<Navigate to="/strategies" replace />} />
        <Route path="/strategies" element={<StrategyListPage />} />
        <Route path="/change" element={<ChangePage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/macro-data" element={<MacroDataPage />} />
        <Route path="/research" element={<ResearchListPage />} />
        <Route path="/research/:id" element={<ResearchDetailPage />} />
        <Route path="/ai-strategy-generation-preview" element={<AiStrategyGenerationPreviewPage />} />
        <Route path="/ai-strategy-generation-preview/:conversationId" element={<AiStrategyGenerationPreviewPage />} />
        <Route path="/ai-strategy-generation-history" element={<AiStrategyHistoryPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/market" replace />} />
    </Routes>
  )
}

/**
 * 受保护的路由组件：
 * - 免登录模式（authEnabled=false）：直接渲染子路由
 * - 登录模式（authEnabled=true）：未认证则重定向到 /login
 */
function ProtectedRoutes() {
  const { isAuthenticated, authEnabled, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <Loading text="加载中..." />
      </div>
    )
  }

  // 免登录模式，直接放行
  if (!authEnabled) {
    return <AppRoutes />
  }

  // 登录模式，未认证 → 重定向到登录页
  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  // 已认证，正常渲染
  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/market" replace />} />
      <Route path="/*" element={<AppRoutes />} />
    </Routes>
  )
}

function App() {
  useBehaviorTracker();
  return (
    <div className="app-container min-h-screen">
      <ProtectedRoutes />
    </div>
  )
}

export default App