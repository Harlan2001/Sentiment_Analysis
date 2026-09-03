import React from 'react'
import { AppRoutes } from '@/routes'
import { useBehaviorTracker } from './utils/useBehaviorTracker'
import './features/workflow/workflow.css'

/**
 * 应用入口：直接渲染应用路由，不再强制登录门。
 * - 免登录模式：直接浏览。
 * - 登录模式：未认证也能进入页面浏览只读数据，
 *   登录入口在左下角账户区（点击弹出登录框），登录后解锁写操作与个人数据。
 */
function App() {
  useBehaviorTracker()
  return (
    <div className="app-container min-h-screen">
      <AppRoutes />
    </div>
  )
}

export default App