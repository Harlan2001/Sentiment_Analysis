export function AccountInfoPanel({
  open,
  onClose,
  onLogout,
}: {
  open: boolean
  onClose: () => void
  onLogout: () => void
}) {
  if (!open) return null

  return (
    <>
      <div className="deleted-overlay" onClick={onClose} aria-hidden="true" />
      <aside className="deleted-drawer" role="dialog" aria-label="账户信息">
        <div className="deleted-drawer-head">
          <h2>账户信息</h2>
          <button
            className="deleted-drawer-close"
            onClick={onClose}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        <div className="deleted-group" style={{ paddingTop: 16 }}>
          <div className="account-info-panel-avatar">
            <span>你</span>
          </div>
          <div className="account-info-panel-name">当前用户</div>
          <div className="account-info-panel-role">BondSense 工作台</div>
        </div>

        <div className="deleted-group">
          <div className="deleted-group-title">方案与状态</div>
          <div className="account-info-panel-row">
            <span>当前方案</span>
            <span className="account-info-panel-value">基础版</span>
          </div>
          <div className="account-info-panel-row">
            <span>登录状态</span>
            <span className="account-info-panel-value">已登录</span>
          </div>
        </div>

        <div className="deleted-group">
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
      </aside>
    </>
  )
}
