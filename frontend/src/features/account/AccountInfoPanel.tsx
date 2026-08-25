import { useEffect } from 'react'

export function AccountInfoPanel({
  open,
  onClose,
  onLogout,
}: {
  open: boolean
  onClose: () => void
  onLogout: () => void
}) {
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="modal-layer" role="presentation">
      <button className="modal-backdrop" onClick={onClose} aria-label="关闭账户信息" />
      <section className="account-modal" role="dialog" aria-modal="true" aria-label="账户信息">
        <header className="modal-head">
          <div><h2>账户信息</h2><p>管理当前工作台账户与登录状态。</p></div>
          <button
            className="modal-close"
            onClick={onClose}
            aria-label="关闭"
          >
            ✕
          </button>
        </header>

        <div className="account-modal-profile">
          <div className="account-info-panel-avatar">
            <span>你</span>
          </div>
          <div className="account-info-panel-name">当前用户</div>
          <div className="account-info-panel-role">BondSense 工作台</div>
        </div>

        <div className="account-modal-section">
          <div className="account-modal-section-title">方案与状态</div>
          <div className="account-info-panel-row">
            <span>当前方案</span>
            <span className="account-info-panel-value">基础版</span>
          </div>
          <div className="account-info-panel-row">
            <span>登录状态</span>
            <span className="account-info-panel-value">已登录</span>
          </div>
        </div>

        <div className="account-modal-footer">
          <button
            className="account-info-panel-logout"
            onClick={() => {
              onLogout()
              onClose()
            }}
          >
            <span>↪</span>退出登录
          </button>
        </div>
      </section>
    </div>
  )
}
