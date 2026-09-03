import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createWorkspaceUser, getWorkspaceUsers, updateWorkspaceUser, WorkspaceUser } from '@/api/workspaceUsers'

type Role = WorkspaceUser['role']
type StatusFilter = 'all' | 'active' | 'inactive'
type RoleFilter = 'all' | Role
type Editing = { id: string; displayName: string } | null
type ConfirmingStatus = { id: string; nextActive: boolean } | null
type Notice = { tone: 'success' | 'error'; message: string } | null

const ROLE_COPY: Record<Role, { label: string; description: string }> = {
  member: { label: '成员', description: '使用工作台业务功能' },
  admin: { label: '管理员', description: '可管理账户与查看监控数据' },
}

export function UserManagementPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [users, setUsers] = useState<WorkspaceUser[]>([])
  const [loading, setLoading] = useState(false)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice>(null)

  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [role, setRole] = useState<Role>('member')
  const [submitted, setSubmitted] = useState(false)

  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all')
  const [editing, setEditing] = useState<Editing>(null)
  const [confirmingStatus, setConfirmingStatus] = useState<ConfirmingStatus>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await getWorkspaceUsers()
      setUsers(result.items)
    } catch {
      setNotice({ tone: 'error', message: '无法读取用户列表，请检查网络后重试。' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    void load()
    setUsername('')
    setDisplayName('')
    setPassword('')
    setShowPassword(false)
    setRole('member')
    setSubmitted(false)
    setSearch('')
    setStatusFilter('all')
    setRoleFilter('all')
    setEditing(null)
    setConfirmingStatus(null)
    setNotice(null)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.setTimeout(() => closeButtonRef.current?.focus(), 0)
    return () => { document.body.style.overflow = previousOverflow }
  }, [open, load])

  useEffect(() => {
    if (!open) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (confirmingStatus) setConfirmingStatus(null)
      else if (editing) setEditing(null)
      else onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [confirmingStatus, editing, onClose, open])

  const counts = useMemo(() => ({
    total: users.length,
    active: users.filter((user) => user.is_active).length,
    admins: users.filter((user) => user.role === 'admin').length,
  }), [users])

  const visibleUsers = useMemo(() => {
    const query = search.trim().toLowerCase()
    return users.filter((user) => {
      const matchesStatus = statusFilter === 'all' || (statusFilter === 'active' ? user.is_active : !user.is_active)
      const matchesRole = roleFilter === 'all' || user.role === roleFilter
      const matchesSearch = !query || user.display_name.toLowerCase().includes(query)
      return matchesStatus && matchesRole && matchesSearch
    })
  }, [roleFilter, search, statusFilter, users])

  const invalidUsername = submitted && !username.trim()
  const invalidDisplayName = submitted && !displayName.trim()
  const invalidPassword = submitted && !password

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitted(true)
    if (!username.trim() || !displayName.trim() || !password || busyKey) return
    setBusyKey('create')
    setNotice(null)
    try {
      const created = await createWorkspaceUser({ username: username.trim(), display_name: displayName.trim(), password, role })
      setUsers((items) => [...items, created].sort((a, b) => a.username.localeCompare(b.username)))
      setUsername('')
      setDisplayName('')
      setPassword('')
      setRole('member')
      setSubmitted(false)
      setNotice({ tone: 'success', message: `已创建账户“${created.display_name}”。` })
    } catch {
      setNotice({ tone: 'error', message: '创建失败。请确认用户名未被使用，并检查填写内容。' })
    } finally {
      setBusyKey(null)
    }
  }

  async function changeRole(user: WorkspaceUser, nextRole: Role) {
    if (nextRole === user.role || busyKey) return
    setBusyKey(`role:${user.id}`)
    setNotice(null)
    try {
      const result = await updateWorkspaceUser(user.id, { role: nextRole })
      setUsers((items) => items.map((item) => item.id === user.id ? result : item))
      setNotice({ tone: 'success', message: `已将“${user.display_name}”设为${ROLE_COPY[nextRole].label}。` })
    } catch {
      setNotice({ tone: 'error', message: `未能修改“${user.display_name}”的角色，请重试。` })
    } finally {
      setBusyKey(null)
    }
  }

  async function toggleActive(user: WorkspaceUser, nextActive: boolean) {
    if (busyKey) return
    setBusyKey(`active:${user.id}`)
    setNotice(null)
    try {
      const result = await updateWorkspaceUser(user.id, { is_active: nextActive })
      setUsers((items) => items.map((item) => item.id === user.id ? result : item))
      setConfirmingStatus(null)
      setNotice({ tone: 'success', message: `已${nextActive ? '启用' : '停用'}“${user.display_name}”。` })
    } catch {
      setNotice({ tone: 'error', message: `${nextActive ? '启用' : '停用'}“${user.display_name}”失败，请重试。` })
    } finally {
      setBusyKey(null)
    }
  }

  async function saveDisplayName(user: WorkspaceUser) {
    const nextName = editing?.displayName.trim() ?? ''
    if (!nextName || nextName === user.display_name || busyKey) {
      if (nextName === user.display_name) setEditing(null)
      return
    }
    setBusyKey(`name:${user.id}`)
    setNotice(null)
    try {
      const result = await updateWorkspaceUser(user.id, { display_name: nextName })
      setUsers((items) => items.map((item) => item.id === user.id ? result : item))
      setEditing(null)
      setNotice({ tone: 'success', message: `显示名称已更新为“${nextName}”。` })
    } catch {
      setNotice({ tone: 'error', message: '修改显示名称失败，请重试。' })
    } finally {
      setBusyKey(null)
    }
  }

  if (!open) return null

  return (
    <div className="modal-layer" role="presentation">
      <button className="modal-backdrop" onClick={onClose} aria-label="关闭用户管理" />
      <section className="user-modal" role="dialog" aria-modal="true" aria-labelledby="user-management-title">
        <header className="modal-head user-modal-head">
          <div><span className="user-modal-eyebrow">管理员控制台</span><h2 id="user-management-title">用户管理</h2><p>创建工作台账户，并维护成员的名称、角色与登录状态。</p></div>
          <button ref={closeButtonRef} className="modal-close" onClick={onClose} aria-label="关闭">✕</button>
        </header>

        <div className="user-modal-main">
          {notice && <div className={`user-notice ${notice.tone}`} role={notice.tone === 'error' ? 'alert' : 'status'}><span>{notice.tone === 'success' ? '✓' : '!'}</span><p>{notice.message}</p>{notice.tone === 'error' && users.length === 0 && <button onClick={() => void load()}>重新读取</button>}<button className="user-notice-close" onClick={() => setNotice(null)} aria-label="关闭提示">✕</button></div>}
          <div className="user-modal-body">
          <aside className="user-create-pane">
            <div className="user-section-heading"><span>01</span><div><h3>创建新账户</h3><p>账户创建后会立即启用。</p></div></div>
            <form onSubmit={createUser} className="user-create-form" noValidate>
              <label><span>用户名 <em>用于登录</em></span><input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="例如 zhangsan" autoComplete="off" aria-invalid={invalidUsername} />{invalidUsername && <small>请输入用户名</small>}</label>
              <label><span>显示名称 <em>界面展示</em></span><input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="例如 张三" autoComplete="off" aria-invalid={invalidDisplayName} />{invalidDisplayName && <small>请输入显示名称</small>}</label>
              <label><span>初始密码</span><div className="user-password-field"><input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="输入登录密码" type={showPassword ? 'text' : 'password'} autoComplete="new-password" aria-invalid={invalidPassword} /><button type="button" onClick={() => setShowPassword((shown) => !shown)} aria-label={showPassword ? '隐藏密码' : '显示密码'}>{showPassword ? '隐藏' : '显示'}</button></div>{invalidPassword && <small>请输入初始密码</small>}</label>
              <fieldset className="user-role-options">
                <legend>账户角色</legend>
                {(Object.keys(ROLE_COPY) as Role[]).map((roleKey) => <label key={roleKey} className={role === roleKey ? 'selected' : ''}><input type="radio" name="new-user-role" value={roleKey} checked={role === roleKey} onChange={() => setRole(roleKey)} /><span className="user-role-radio" /><span><strong>{ROLE_COPY[roleKey].label}</strong><small>{ROLE_COPY[roleKey].description}</small></span></label>)}
              </fieldset>
              <button className="user-create-submit" disabled={busyKey === 'create'}>{busyKey === 'create' ? '正在创建…' : '创建账户'} <span aria-hidden="true">→</span></button>
            </form>
          </aside>

          <section className="user-directory">
            <div className="user-directory-head">
              <div className="user-directory-title-row">
                <div className="user-section-heading"><span>02</span><div><h3>账户目录</h3><p>点击名称即可编辑；角色修改后立即生效。</p></div></div>
                <div className="user-inline-stats" aria-label="账户统计"><span><strong>{counts.total}</strong> 个账户</span><i /><span><strong>{counts.active}</strong> 已启用</span><i /><span><strong>{counts.admins}</strong> 管理员</span></div>
              </div>
              <div className="user-directory-filters">
                <label className="user-search"><span aria-hidden="true">⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索显示名称" aria-label="搜索用户" />{search && <button onClick={() => setSearch('')} aria-label="清除搜索">✕</button>}</label>
                <label className="user-filter-select"><span>角色</span><select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value as RoleFilter)} aria-label="按角色筛选"><option value="all">全部角色</option><option value="admin">管理员</option><option value="member">成员</option></select></label>
                <label className="user-filter-select"><span>状态</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)} aria-label="按账号状态筛选"><option value="all">全部状态</option><option value="active">已启用</option><option value="inactive">已停用</option></select></label>
              </div>
            </div>
            <div className="user-table-head" aria-hidden="true"><span><b>账户</b><small>点击名称编辑</small><em>{loading ? '同步中…' : `${visibleUsers.length} 个`}</em></span><span><b>角色</b><small>可直接修改</small></span><span><b>状态</b></span><span><b>操作</b></span></div>
            <div className="user-modal-list" aria-busy={loading}>
              {loading && users.length === 0 ? <div className="user-modal-empty"><span className="user-loading-spinner" />正在读取账户…</div> : visibleUsers.length === 0 ? <div className="user-modal-empty"><strong>没有匹配的账户</strong><span>请更换关键词或状态筛选。</span></div> : visibleUsers.map((user) => {
                const isEditingName = editing?.id === user.id
                const isConfirming = confirmingStatus?.id === user.id
                const isUpdating = busyKey?.endsWith(`:${user.id}`) ?? false
                return <article className="user-row" key={user.id} data-active={user.is_active ? '1' : '0'}>
                  <div className="user-identity"><span className="user-avatar">{(user.display_name || user.username).trim().slice(0, 1).toUpperCase()}</span>{isEditingName ? <div className="user-name-edit"><input autoFocus value={editing.displayName} onChange={(event) => setEditing({ id: user.id, displayName: event.target.value })} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); void saveDisplayName(user) } if (event.key === 'Escape') setEditing(null) }} aria-label="修改显示名称" /><div><button onClick={() => void saveDisplayName(user)} disabled={!editing.displayName.trim() || isUpdating}>保存</button><button onClick={() => setEditing(null)}>取消</button></div></div> : <button className="user-name-button" onClick={() => setEditing({ id: user.id, displayName: user.display_name })}><strong>{user.display_name}</strong></button>}</div>
                  <label className="user-row-role"><span className="sr-only">{user.display_name}的角色</span><select value={user.role} disabled={!!busyKey} title="点击修改角色" onChange={(event) => void changeRole(user, event.target.value as Role)}><option value="member">成员</option><option value="admin">管理员</option></select></label>
                  <span className={`user-status ${user.is_active ? 'active' : 'inactive'}`}><i />{user.is_active ? '已启用' : '已停用'}</span>
                  <button className={`user-status-action ${user.is_active ? 'disable' : 'enable'}`} disabled={!!busyKey} onClick={() => setConfirmingStatus({ id: user.id, nextActive: !user.is_active })}>{isUpdating ? '处理中…' : user.is_active ? '停用' : '启用'}</button>
                  {isConfirming && <div className="user-row-confirm" role="alertdialog" aria-label={`${confirmingStatus.nextActive ? '启用' : '停用'}账户确认`}><p><strong>确认{confirmingStatus.nextActive ? '启用' : '停用'}“{user.display_name}”？</strong><span>{confirmingStatus.nextActive ? '该账户将恢复登录权限。' : '该账户将无法登录，已有业务数据不会删除。'}</span></p><button onClick={() => setConfirmingStatus(null)}>取消</button><button className="confirm" onClick={() => void toggleActive(user, confirmingStatus.nextActive)}>{confirmingStatus.nextActive ? '确认启用' : '确认停用'}</button></div>}
                </article>
              })}
            </div>
          </section>
          </div>
        </div>
      </section>
    </div>
  )
}
