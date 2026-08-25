import { FormEvent, useEffect, useState } from 'react'
import { createWorkspaceUser, getWorkspaceUsers, updateWorkspaceUser, WorkspaceUser } from '@/api/workspaceUsers'

export function UserManagementPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [users, setUsers] = useState<WorkspaceUser[]>([])
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'admin' | 'member'>('member')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = async () => {
    try {
      const result = await getWorkspaceUsers()
      setUsers(result.items)
      setError('')
    } catch {
      setError('无法读取用户列表')
    }
  }

  useEffect(() => { if (open) void load() }, [open])
  if (!open) return null

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!username.trim() || !displayName.trim() || !password || busy) return
    setBusy(true)
    try {
      await createWorkspaceUser({ username: username.trim(), display_name: displayName.trim(), password, role })
      setUsername(''); setDisplayName(''); setPassword(''); setRole('member')
      await load()
    } catch {
      setError('创建用户失败，请检查用户名是否重复')
    } finally { setBusy(false) }
  }

  async function changeUser(user: WorkspaceUser, changes: Partial<Pick<WorkspaceUser, 'role' | 'is_active'>>) {
    try {
      const result = await updateWorkspaceUser(user.id, changes)
      setUsers((items) => items.map((item) => item.id === user.id ? result : item))
    } catch { setError('保存用户设置失败') }
  }

  return <>
    <div className="deleted-overlay" onClick={onClose} aria-hidden="true" />
    <aside className="deleted-drawer" role="dialog" aria-label="用户管理">
      <div className="deleted-drawer-head"><h2>用户管理</h2><button className="deleted-drawer-close" onClick={onClose} aria-label="关闭">×</button></div>
      <div className="deleted-group">
        <div className="deleted-group-title">新建演示用户</div>
        <form onSubmit={createUser} style={{ display: 'grid', gap: 8 }}>
          <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="用户名" />
          <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="显示名称" />
          <input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="登录密码" type="password" />
          <select value={role} onChange={(event) => setRole(event.target.value as 'admin' | 'member')}><option value="member">成员</option><option value="admin">管理员</option></select>
          <button className="pm-button primary" disabled={busy}>创建用户</button>
        </form>
      </div>
      <div className="deleted-group">
        <div className="deleted-group-title">工作区用户</div>
        {users.map((user) => <div className="account-info-panel-row" key={user.id} style={{ alignItems: 'center', gap: 8 }}>
          <span><strong>{user.display_name}</strong><br /><small>{user.username}</small></span>
          <select value={user.role} onChange={(event) => void changeUser(user, { role: event.target.value as 'admin' | 'member' })}>
            <option value="member">成员</option><option value="admin">管理员</option>
          </select>
          <button className="pm-button" onClick={() => void changeUser(user, { is_active: !user.is_active })}>{user.is_active ? '停用' : '启用'}</button>
        </div>)}
        {error && <small className="sidebar-error">{error}</small>}
      </div>
    </aside>
  </>
}
