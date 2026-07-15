import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/Layout/MainLayout'
import { NewsPage, FactorPage, DataPage, PredictionPage, AgentPage, MacroSignalLogPage, SelectStrategyPage, StrategyListPage, ChangePage, LoginPage, DashboardPage } from './components/Pages'
import { useAuth } from './contexts/AuthContext'
import { useBehaviorTracker } from './hooks/useBehaviorTracker'
import { Loading } from './components/UI/Loading'

/**
 * 受保护的路由组件：
 * - 免登录模式（authEnabled=false）：直接渲染子路由
 * - 登录模式（authEnabled=true）：未认证则重定向到 /login
 */
function ProtectedRoutes() {
  const { isAuthenticated, authEnabled, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-gray-900 to-gray-800">
        <Loading text="加载中..." />
      </div>
    )
  }

  // 免登录模式，直接放行
  if (!authEnabled) {
    return (
      <MainLayout>
        <Routes>
          <Route path="/" element={<NewsPage />} />
          <Route path="/news" element={<NewsPage />} />
          <Route path="/factors" element={<FactorPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/prediction" element={<PredictionPage />} />
          <Route path="/agents" element={<AgentPage />} />
          <Route path="/macro-signal-logs" element={<MacroSignalLogPage />} />
          <Route path="/select-strategy" element={<SelectStrategyPage />} />
          <Route path="/strategies" element={<StrategyListPage />} />
          <Route path="/change" element={<ChangePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="*" element={<Navigate to="/news" replace />} />
        </Routes>
      </MainLayout>
    )
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
    <MainLayout>
      <Routes>
        <Route path="/" element={<NewsPage />} />
        <Route path="/login" element={<Navigate to="/news" replace />} />
        <Route path="/news" element={<NewsPage />} />
        <Route path="/factors" element={<FactorPage />} />
        <Route path="/data" element={<DataPage />} />
        <Route path="/prediction" element={<PredictionPage />} />
        <Route path="/agents" element={<AgentPage />} />
        <Route path="/macro-signal-logs" element={<MacroSignalLogPage />} />
        <Route path="/select-strategy" element={<SelectStrategyPage />} />
        <Route path="/strategies" element={<StrategyListPage />} />
        <Route path="/change" element={<ChangePage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="*" element={<Navigate to="/news" replace />} />
      </Routes>
    </MainLayout>
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