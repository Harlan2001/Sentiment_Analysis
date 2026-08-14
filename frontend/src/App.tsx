import React, { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/Layout/MainLayout'
import { useAuth } from './contexts/AuthContext'
import { useBehaviorTracker } from './hooks/useBehaviorTracker'
import { Loading } from './components/UI/Loading'
import { WorkbenchShell } from './shell/WorkbenchShell'
import { PlaceholderPage } from './shell/PlaceholderPage'

// 旧页面（不依赖 ECharts，直接导入）
import AgentPage from './components/Pages/AgentPage'
import StrategyListPage from './components/Pages/StrategyListPage'
import ChangePage from './components/Pages/ChangePage'
import LoginPage from './components/Pages/LoginPage'
import ResearchListPage from './components/Pages/ResearchListPage'
import ResearchDetailPage from './components/Pages/ResearchDetailPage'
import AiStrategyGenerationPreviewPage from './components/Pages/AiStrategyGenerationPreviewPage'
import AiStrategyHistoryPage from './components/Pages/AiStrategyHistoryPage'

// 工作台板块（不依赖 ECharts，直接导入）
import MarketSection from './components/Pages/sections/DiscoverSection'
import FactorsSection from './components/Pages/sections/FactorsSection'
import ReturnsSection from './components/Pages/sections/ReturnsSection'
import WatchlistSection from './components/Pages/sections/WatchlistSection'
import PortfolioSection from './components/Pages/sections/PortfolioSection'
import WorkflowSection from './components/Pages/sections/WorkflowSection'

// 依赖 ECharts 的页面懒加载，避免首屏加载 1MB+ 的 ECharts
const NewsPage = lazy(() => import('./components/Pages/NewsPage'))
const FactorPage = lazy(() => import('./components/Pages/FactorPage'))
const PredictionPage = lazy(() => import('./components/Pages/PredictionPage'))
const DashboardPage = lazy(() => import('./components/Pages/DashboardPage'))
const MacroDataPage = lazy(() => import('./components/Pages/MacroDataPage'))
const ForecastSection = lazy(() => import('./components/Pages/sections/ForecastSection'))

// 工作台功能页（懒加载，减小首屏体积）
const HomePage = lazy(() => import('./features/home/HomePage').then((m) => ({ default: m.HomePage })))
const ChatPage = lazy(() => import('./features/chat/ChatPage').then((m) => ({ default: m.ChatPage })))
const ComputerPage = lazy(() => import('./features/computer/ComputerPage').then((m) => ({ default: m.ComputerPage })))
const ReportGenerationPage = lazy(() => import('./features/computer/ReportGenerationPage').then((m) => ({ default: m.ReportGenerationPage })))
const ReportGenerationDetailPage = lazy(() => import('./features/computer/ReportGenerationDetailPage').then((m) => ({ default: m.ReportGenerationDetailPage })))
const StrategyPage = lazy(() => import('./features/computer/StrategyPage').then((m) => ({ default: m.StrategyPage })))
const ComputerNewsPage = lazy(() => import('./features/computer/NewsPage').then((m) => ({ default: m.NewsPage })))
const StrategyPromptPage = lazy(() => import('./features/computer/StrategyPromptPage').then((m) => ({ default: m.StrategyPromptPage })))
const SkillsPage = lazy(() => import('./features/custom/SkillsPage').then((m) => ({ default: m.SkillsPage })))
const McpPage = lazy(() => import('./features/custom/McpPage').then((m) => ({ default: m.McpPage })))
const ProjectManagementPage = lazy(() => import('./features/project/ProjectManagementPage').then((m) => ({ default: m.ProjectManagementPage })))
const ProjectCreatePage = lazy(() => import('./features/project/ProjectCreatePage').then((m) => ({ default: m.ProjectCreatePage })))
import './features/computer/ReportGeneration.css'

/**
 * 路由表：
 * - 新工作台「壳」（默认首页）：/market /returns /forecast /watchlist /portfolio /workflow
 * - Legacy pages remain available at their existing routes.
 */
function AppRoutes() {
  return (
    <Suspense fallback={<Loading text="加载中..." />}>
      <Routes>
      {/* Workspace shell and market pages */}
      <Route element={<WorkbenchShell />}>
        <Route path="/" element={<Navigate to="/market" replace />} />
        {/* Market pages */}
        <Route path="/market" element={<MarketSection />} />
        <Route path="/factors" element={<FactorsSection />} />
        <Route path="/returns" element={<ReturnsSection />} />
        <Route path="/forecast" element={<Suspense fallback={<Loading text="加载中..." />}><ForecastSection /></Suspense>} />
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
    </Suspense>
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
