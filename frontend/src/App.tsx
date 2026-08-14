import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AppRoutes } from '@/routes'
import LoginPage from '@/features/auth/LoginPage'
import { useAuth } from './contexts/AuthContext'
import { useBehaviorTracker } from './hooks/useBehaviorTracker'
import { Loading } from './components/UI/Loading'
import './features/computer/ReportGeneration.css'

/**
 * 认证门。
 * - 免登录模式（authEnabled=false）：直接渲染应用路由。
 * - 登录模式：未认证 → /login；已认证 → 渲染壳内路由（AppRoutes）。
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