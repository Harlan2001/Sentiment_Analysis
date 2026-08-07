import { Navigate, Route, Routes } from 'react-router-dom'
import { WorkbenchShell } from './shell/WorkbenchShell'
import { PlaceholderPage } from './shell/PlaceholderPage'
import { HomePage } from './features/home/HomePage'
import { ChatPage } from './features/chat/ChatPage'
import { ComputerPage } from './features/computer/ComputerPage'
import { ReportPage } from './features/computer/ReportPage'
import { StrategyPage } from './features/computer/StrategyPage'
import { NewsPage } from './features/computer/NewsPage'
import { StrategyPromptPage } from './features/computer/StrategyPromptPage'
import { FactorLibraryPage } from './features/custom/FactorLibraryPage'
import { FactorDetailPage } from './features/custom/FactorDetailPage'
import { MacroPage } from './features/custom/MacroPage'
import { ProjectPage } from './features/project/ProjectPage'
import { SkillsPage } from './features/custom/SkillsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<WorkbenchShell />}>
        <Route path="/home" element={<HomePage />} />
        <Route path="/chat/new" element={<ChatPage />} />
        <Route path="/chat/:conversationId" element={<ChatPage />} />
        <Route path="/computer" element={<ComputerPage />} />
        <Route path="/computer/reports" element={<ReportPage />} />
        <Route path="/computer/strategies" element={<StrategyPage />} />
        <Route path="/computer/strategies/prompt" element={<StrategyPromptPage />} />
        <Route path="/computer/news" element={<NewsPage />} />
        <Route path="/custom/factors" element={<FactorLibraryPage />} />
        <Route path="/custom/factors/:factorId" element={<FactorDetailPage />} />
        <Route path="/custom/macro" element={<MacroPage />} />
        <Route path="/custom/skills" element={<SkillsPage />} />
        <Route path="/projects" element={<ProjectPage />} />
        <Route path="/projects/:projectId" element={<ProjectPage />} />
        <Route path="/settings" element={<PlaceholderPage title="设置" description="基础账号信息和退出入口将在后续模块实现。" />} />
      </Route>
      <Route path="/" element={<Navigate to="/home" replace />} />
      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
  )
}
