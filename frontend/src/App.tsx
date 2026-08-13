import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/Layout/MainLayout'
import {
  NewsPage,
  FactorPage,
  PredictionPage,
  AgentPage,
  StrategyListPage,
  ChangePage,
  LoginPage,
  DashboardPage,
  MacroDataPage,
  ResearchListPage,
  ResearchDetailPage,
  AiStrategyGenerationPreviewPage,
  AiStrategyHistoryPage,
} from './components/Pages'
import {
  MarketSection,
  FactorsSection,
  ReturnsSection,
  ForecastSection,
  WatchlistSection,
  PortfolioSection,
  WorkflowSection,
} from './components/Pages/sections'
import { useAuth } from './contexts/AuthContext'
import { useBehaviorTracker } from './hooks/useBehaviorTracker'
import { Loading } from './components/UI/Loading'
import { WorkbenchShell } from './shell/WorkbenchShell'
import { PlaceholderPage } from './shell/PlaceholderPage'
import { HomePage } from './features/home/HomePage'
import { ChatPage } from './features/chat/ChatPage'
import { ComputerPage } from './features/computer/ComputerPage'
import { ReportGenerationPage } from './features/computer/ReportGenerationPage'
import { ReportGenerationDetailPage } from './features/computer/ReportGenerationDetailPage'
import { StrategyPage } from './features/computer/StrategyPage'
import { NewsPage as ComputerNewsPage } from './features/computer/NewsPage'
import { StrategyPromptPage } from './features/computer/StrategyPromptPage'
import { SkillsPage } from './features/custom/SkillsPage'
import { McpPage } from './features/custom/McpPage'
import { ProjectManagementPage } from './features/project/ProjectManagementPage'
import { ProjectCreatePage } from './features/project/ProjectCreatePage'
import './features/computer/ReportGeneration.css'

/**
 * 路由表：
 * - 新工作台「壳」（默认首页）：/market /returns /forecast /watchlist /portfolio /workflow
 * - Legacy pages remain available at their existing routes.
 */
function AppRoutes() {
  return (
    <Routes>
      {/* Workspace shell and market pages */}
      <Route element={<WorkbenchShell />}>
        <Route path="/" element={<Navigate to="/market" replace />} />
        {/* Market pages */}
        <Route path="/market" element={<MarketSection />} />
        <Route path="/factors" element={<FactorsSection />} />
        <Route path="/returns" element={<ReturnsSection />} />
        <Route path="/forecast" element={<ForecastSection />} />
        <Route path="/watchlist" element={<WatchlistSection />} />
        <Route path="/portfolio" element={<PortfolioSection />} />
        <Route path="/workflow" element={<WorkflowSection />} />
        {/* Workspace pages */}
        <Route path="/home" element={<HomePage />} />
        <Route path="/chat/new" element={<ChatPage />} />
        <Route path="/chat/:conversationId" element={<ChatPage />} />
        <Route path="/computer" element={<ComputerPage />} />
        <Route path="/computer/reports" element={<ReportGenerationPage />} />
        <Route path="/computer/reports/:taskId" element={<ReportGenerationDetailPage />} />
        <Route path="/computer/strategies" element={<StrategyPage />} />
        <Route path="/computer/strategies/prompt" element={<StrategyPromptPage />} />
        <Route path="/computer/news" element={<ComputerNewsPage />} />
        <Route path="/custom/skills" element={<SkillsPage />} />
        <Route path="/custom/mcp" element={<McpPage />} />
        <Route path="/projects" element={<Navigate to="/projects/new" replace />} />
        <Route path="/projects/new" element={<ProjectCreatePage />} />
        <Route path="/projects/:projectId" element={<ProjectManagementPage />} />
        <Route
          path="/settings"
          element={
            <PlaceholderPage
              title="设置"
              description="Account settings and sign-out will be available in a later module."
            />
          }
        />
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
 * Protected routing component.
 * - Authentication disabled: render application routes directly.
 * - 登录模式（authEnabled=true）：未认证则重定向到 /login
 */
function ProtectedRoutes() {
  const { isAuthenticated, authEnabled, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <Loading text="Loading..." />
      </div>
    )
  }

  // 免登录模式，直接放行
  if (!authEnabled) {
    return <AppRoutes />
  }

  // Authentication enabled and not authenticated: redirect to login.
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
  useBehaviorTracker()
  return (
    <div className="app-container min-h-screen">
      <ProtectedRoutes />
    </div>
  )
}

export default App
