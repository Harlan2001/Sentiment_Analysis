import type { ReactNode } from 'react'
import { useAuth } from '@/contexts/AuthContext'

function openLogin() {
  window.dispatchEvent(new Event('bondsense-open-login'))
}

export function LoginRequiredPage({ children }: { children: ReactNode }) {
  const { authEnabled, isAuthenticated, isLoading } = useAuth()

  if (isLoading || !authEnabled || isAuthenticated) return <>{children}</>

  return (
    <section className="login-required-page" aria-labelledby="login-required-title">
      <div className="login-required-card">
        <span className="login-required-mark" aria-hidden="true">B</span>
        <p className="login-required-kicker">个人工作台</p>
        <h1 id="login-required-title">登录后使用此功能</h1>
        <p>项目、个人关注、持仓、Skills 和连接器仅对登录用户开放。</p>
        <button type="button" onClick={openLogin}>去登录</button>
        <small>市场、因子、收益、预测和临时会话可直接浏览。</small>
      </div>
    </section>
  )
}
