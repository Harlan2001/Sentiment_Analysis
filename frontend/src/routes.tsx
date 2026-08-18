import type { ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { ROUTES } from '@/config/routes'
import { WorkbenchShell } from '@/shell/WorkbenchShell'
import { PlaceholderPage } from '@/shell/PlaceholderPage'
import { HomePage } from '@/features/home/HomePage'
import { ChatPage } from '@/features/chat/ChatPage'
import { ComputerPage } from '@/features/computer/ComputerPage'
import { ReportGenerationPage } from '@/features/computer/ReportGenerationPage'
import { ReportGenerationDetailPage } from '@/features/computer/ReportGenerationDetailPage'
import { ReportLibraryPage } from '@/features/computer/ReportLibraryPage'
import { StrategyPage } from '@/features/computer/StrategyPage'
import { NewsPage as ComputerNewsPage } from '@/features/computer/NewsPage'
import { NewsSummaryDetailPage } from '@/features/computer/NewsSummaryDetailPage'
import { StrategyPromptPage } from '@/features/computer/StrategyPromptPage'
import { SkillsPage } from '@/features/custom/SkillsPage'
import { McpPage } from '@/features/custom/McpPage'
import { ProjectManagementPage } from '@/features/project/ProjectManagementPage'
import { ProjectCreatePage } from '@/features/project/ProjectCreatePage'
import {
  MarketSection,
  FactorsSection,
  ReturnsSection,
  ForecastSection,
  WatchlistSection,
  PortfolioSection,
  WorkflowSection,
} from '@/features/market'

/**
 * 路由 → 元素映射。
 * 仅此文件持有 React 元素；config/routes.ts 是纯数据（防循环依赖）。
 * 若某条 ROUTES 记录缺少元素，会静默跳过 —— 保持元素映射与路由表一一对应。
 */
const ROUTE_ELEMENTS: Record<string, ReactNode> = {
  '/market': <MarketSection />,
  '/factors': <FactorsSection />,
  '/returns': <ReturnsSection />,
  '/forecast': <ForecastSection />,
  '/watchlist': <WatchlistSection />,
  '/portfolio': <PortfolioSection />,
  '/workflow': <WorkflowSection />,
  '/home': <HomePage />,
  '/chat': <ChatPage />,
  '/chat/:conversationId': <ChatPage />,
  '/computer': <ComputerPage />,
  '/computer/reports': <ReportGenerationPage />,
  '/computer/reports/library': <ReportLibraryPage />,
  '/computer/reports/:taskId': <ReportGenerationDetailPage />,
  '/computer/strategies': <StrategyPage />,
  '/computer/strategies/prompt': <StrategyPromptPage />,
  '/computer/news': <ComputerNewsPage />,
  '/computer/news/:taskId': <NewsSummaryDetailPage />,
  '/custom/mcp': <McpPage />,
  '/custom/skills': <SkillsPage />,
  '/projects/new': <ProjectCreatePage />,
  '/projects/:projectId': <ProjectManagementPage />,
  '/settings': (
    <PlaceholderPage
      title="设置"
      description="Account settings and sign-out will be available in a later module."
    />
  ),
}

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
            <Route key={r.path} path={r.path} element={ROUTE_ELEMENTS[r.path]} />
          ) : null
        )}
      </Route>
      <Route path="*" element={<Navigate to="/market" replace />} />
    </Routes>
  )
}
