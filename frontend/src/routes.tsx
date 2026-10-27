import type { ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { ROUTES } from '@/config/routes'
import { WorkbenchShell } from '@/shell/WorkbenchShell'
import { PlaceholderPage } from '@/shell/PlaceholderPage'
import { HomePage } from '@/features/home/HomePage'
import { ChatPage } from '@/features/chat/ChatPage'
import { WorkflowHomePage } from '@/features/workflow/pages/WorkflowHomePage'
import { ReportGenerationPage } from '@/features/workflow/pages/ReportGenerationPage'
import { ReportGenerationDetailPage } from '@/features/workflow/pages/ReportGenerationDetailPage'
import { ReportLibraryPage } from '@/features/workflow/pages/ReportLibraryPage'
import { StrategyPage } from '@/features/workflow/pages/StrategyPage'
import { NewsSummaryPage } from '@/features/workflow/pages/NewsSummaryPage'
import { NewsSummaryDetailPage } from '@/features/workflow/pages/NewsSummaryDetailPage'
import { StrategyPromptPage } from '@/features/workflow/pages/StrategyPromptPage'
import PolicyDocumentsPage from '@/features/workflow/pages/PolicyDocumentsPage'
import PolicyDocumentDetailPage from '@/features/workflow/pages/PolicyDocumentDetailPage'
import { SkillsPage } from '@/features/custom/SkillsPage'
import { McpPage } from '@/features/custom/McpPage'
import { MemoryPage } from '@/features/custom/MemoryPage'
import { FileLibraryPage } from '@/features/file-library/FileLibraryPage'
import { ProjectManagementPage } from '@/features/project/ProjectManagementPage'
import { ProjectCreatePage } from '@/features/project/ProjectCreatePage'
import {
  MarketPage,
  FactorsPage,
  ReturnsPage,
  ForecastPage,
  WatchlistPage,
  PortfolioPage,
} from '@/features/market'
import FuturesPage from '@/features/market/pages/FuturesPage'
import CreditSpreadPage from '@/features/market/pages/CreditSpreadPage'
import TreasurySpreadPage from '@/features/market/pages/TreasurySpreadPage'
import InfoPage from '@/features/market/pages/InfoPage'
import BacktestPage from '@/features/market/pages/BacktestPage'
import NewsDetailPage from '@/features/market/pages/NewsDetailPage'
import YieldDetailPage from '@/features/market/pages/YieldDetailPage'
import FactorDetailPage from '@/features/market/pages/FactorDetailPage'
import { LoginRequiredPage } from '@/features/auth/LoginRequiredPage'

/**
 * 路由 → 元素映射。
 * 仅此文件持有 React 元素；config/routes.ts 是纯数据（防循环依赖）。
 * 若某条 ROUTES 记录缺少元素，会静默跳过 —— 保持元素映射与路由表一一对应。
 */
const ROUTE_ELEMENTS: Record<string, ReactNode> = {
  '/market': <MarketPage />,
  '/info': <InfoPage />,
  '/backtest': <BacktestPage />,
  '/factors': <FactorsPage />,
  '/returns': <ReturnsPage />,
  '/forecast': <ForecastPage />,
  '/watchlist': <WatchlistPage />,
  '/portfolio': <PortfolioPage />,
  '/futures': <FuturesPage />,
  '/credit-spread': <CreditSpreadPage />,
  '/treasury-spread': <TreasurySpreadPage />,
  '/workflow': <WorkflowHomePage />,
  '/home': <HomePage />,
  '/chat': <ChatPage />,
  '/chat/:conversationId': <ChatPage />,
  '/computer/reports': <ReportGenerationPage />,
  '/computer/reports/library': <ReportLibraryPage />,
  '/computer/reports/:taskId': <ReportGenerationDetailPage />,
  '/computer/strategies': <StrategyPage />,
  '/computer/strategies/prompt': <StrategyPromptPage />,
  '/computer/news': <NewsSummaryPage />,
  '/computer/news/:taskId': <NewsSummaryDetailPage />,
  '/computer/policy': <PolicyDocumentsPage />,
  '/computer/policy/:documentId': <PolicyDocumentDetailPage />,
  '/custom/mcp': <McpPage />,
  '/custom/skills': <SkillsPage />,
  '/custom/memory': <MemoryPage />,
  '/file-library': <FileLibraryPage />,
  '/projects/new': <ProjectCreatePage />,
  '/projects/:projectId': <ProjectManagementPage />,
  '/news/:newsId': <NewsDetailPage />,
  '/yield/:period': <YieldDetailPage />,
  '/factor/:factorId': <FactorDetailPage />,
  '/settings': (
    <PlaceholderPage
      title="设置"
      description="Account settings and sign-out will be available in a later module."
    />
  ),
}

const LOGIN_REQUIRED_ROUTES = new Set([
  '/watchlist',
  '/portfolio',
  '/workflow',
  '/computer/reports',
  '/computer/reports/library',
  '/computer/reports/:taskId',
  '/computer/strategies',
  '/computer/strategies/prompt',
  '/computer/news',
  '/computer/news/:taskId',
  '/custom/mcp',
  '/custom/skills',
  '/custom/memory',
  '/file-library',
  '/projects/new',
  '/projects/:projectId',
  '/settings',
])

/** 壳内路由：由 config/routes.ts 驱动（含重定向），未匹配路径兜底到 /market */
export function AppRoutes() {
  const shellRoutes = ROUTES.filter((r) => r.inShell !== false)
  return (
    <Routes>
      <Route element={<WorkbenchShell />}>
        {shellRoutes.map((r) =>
          r.redirect ? (
            <Route key={r.path} path={r.path} element={<Navigate to={r.redirect} replace />} />
          ) : ROUTE_ELEMENTS[r.path] ? (
            <Route
              key={r.path}
              path={r.path}
              element={LOGIN_REQUIRED_ROUTES.has(r.path) ? <LoginRequiredPage>{ROUTE_ELEMENTS[r.path]}</LoginRequiredPage> : ROUTE_ELEMENTS[r.path]}
            />
          ) : null
        )}
      </Route>
      <Route path="*" element={<Navigate to="/market" replace />} />
    </Routes>
  )
}
