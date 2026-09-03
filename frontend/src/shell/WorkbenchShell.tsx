import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Conversation, Project, deleteConversation, deleteProject, getConversations, getProjectConversations, getSidebar } from '@/api/workbench'
import { DeletedItemsPanel } from '@/features/account/DeletedItemsPanel'
import { AccountInfoPanel } from '@/features/account/AccountInfoPanel'
import { UserManagementPanel } from '@/features/account/UserManagementPanel'
import { useAuth } from '@/contexts/AuthContext'
import LoginModal from '@/features/auth/LoginModal'
import { SECTION_TABS, PRODUCT_LINKS, HOME_PATHS, shellTitle } from '@/config/routes'
import { HomeChatDock } from '@/features/market/components/HomeChatDock'
import { DEMO_WORKFLOWS } from '@/features/workflow/pages/WorkflowDemoPage'

// 懒加载监控看板：其依赖的 ECharts 体积较大，仅在打开时加载
const MonitorDashboardPanel = lazy(() => import('@/features/monitor/MonitorDashboardPanel'))

type SidebarProject = Project & { recent_conversations: Conversation[] }

const ROLE_LABELS: Record<string, string> = {
  admin: '管理员',
  member: '成员',
  manager: '经理',
  user: '普通用户',
}

const HOME_CHAT_PLACEHOLDERS: Record<string, string> = {
  '/factors': '\u8be2\u95ee\u56e0\u5b50\u8868\u73b0\u3001\u7b5b\u9009\u6761\u4ef6\u6216\u56e0\u5b50\u89e3\u8bfb\u2026',
  '/returns': '\u8be2\u95ee\u6536\u76ca\u7387\u53d8\u52a8\u3001\u6536\u76ca\u65e5\u5386\u6216\u5173\u8054\u65b0\u95fb\u2026',
  '/forecast': '\u8be2\u95ee\u9884\u6d4b\u7ed3\u8bba\u3001\u60c5\u666f\u5047\u8bbe\u6216\u98ce\u9669\u63d0\u793a\u2026',
  '/watchlist': '\u8be2\u95ee\u5173\u6ce8\u6807\u7684\u3001\u5f02\u52a8\u63d0\u9192\u6216\u8ddf\u8e2a\u5efa\u8bae\u2026',
  '/portfolio': '\u8be2\u95ee\u8d44\u4ea7\u914d\u7f6e\u3001\u7ec4\u5408\u98ce\u9669\u6216\u8c03\u4ed3\u601d\u8def\u2026',
}
export function WorkbenchShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<SidebarProject[]>([])
  const [recent, setRecent] = useState<Conversation[]>([])
  const [allRecent, setAllRecent] = useState<Conversation[] | null>(null)
  const [expandedProjectId, setExpandedProjectId] = useState<string | null>(null)
  const [expandedConversations, setExpandedConversations] = useState<Conversation[]>([])
  const [projectsOpen, setProjectsOpen] = useState(true)
  const [conversationsOpen, setConversationsOpen] = useState(true)
  const [conversationTopic, setConversationTopic] = useState('新建对话')
  const [sidebarError, setSidebarError] = useState('')
  const { isAuthenticated, username, displayName, role, isAdmin, authEnabled, logout } = useAuth()
  const [accountOpen, setAccountOpen] = useState(false)
  const [loginOpen, setLoginOpen] = useState(false)
  const [accountInfoPanelOpen, setAccountInfoPanelOpen] = useState(false)
  const [deletedPanelOpen, setDeletedPanelOpen] = useState(false)
  const [monitorPanelOpen, setMonitorPanelOpen] = useState(false)
  const [userManagementOpen, setUserManagementOpen] = useState(false)
  const isHome = HOME_PATHS.has(location.pathname)
  const visitorBlockedHomePage = authEnabled && !isAuthenticated && (location.pathname === '/watchlist' || location.pathname === '/portfolio')
  const homeChatPlaceholder = visitorBlockedHomePage ? undefined : HOME_CHAT_PLACEHOLDERS[location.pathname]
  const topbarTitle = shellTitle(location.pathname, conversationTopic)
  const isWorkflowChild = location.pathname.startsWith('/computer/')
  const showWorkflowBack = new Set(['/computer/reports', '/computer/strategies', '/computer/news']).has(location.pathname)
  const hideWorkflowDetailTopbar = location.pathname === '/computer/strategies/prompt'
    || location.pathname.startsWith('/computer/reports/')
    || /^\/computer\/news\/[^/]+$/.test(location.pathname)
  const demoWorkflowId = location.pathname.match(/^\/computer\/demo\/([^/]+)$/)?.[1]
  const workflowChildTitle = (demoWorkflowId && DEMO_WORKFLOWS[demoWorkflowId]?.title) || topbarTitle.replace(/^工作流 · /, '')

  useEffect(() => {
    setMonitorPanelOpen(false)
  }, [location.pathname, location.search])

  const loadSidebar = useCallback(() => {
    getSidebar().then((data) => {
      setProjects(data.projects)
      setRecent(data.recent_conversations)
      setSidebarError('')
    }).catch((error: Error) => setSidebarError(error.message))
  }, [])

  useEffect(() => {
    loadSidebar()
    window.addEventListener('bondsense-sidebar-refresh', loadSidebar)
    return () => window.removeEventListener('bondsense-sidebar-refresh', loadSidebar)
  }, [loadSidebar])

  useEffect(() => {
    const showLogin = () => setLoginOpen(true)
    window.addEventListener('bondsense-open-login', showLogin)
    return () => window.removeEventListener('bondsense-open-login', showLogin)
  }, [])

  useEffect(() => {
    function updateTopic(event: Event) {
      const detail = (event as CustomEvent<Conversation>).detail
      if (detail && location.pathname.endsWith('/' + detail.id)) setConversationTopic(detail.title || '新建对话')
    }
    window.addEventListener('bondsense-conversation-topic-change', updateTopic)
    return () => window.removeEventListener('bondsense-conversation-topic-change', updateTopic)
  }, [location.pathname])

  async function toggleProject(projectId: string) {
    if (expandedProjectId === projectId) {
      setExpandedProjectId(null)
      return
    }
    setExpandedProjectId(projectId)
    const project = projects.find((item) => item.id === projectId)
    setExpandedConversations(project?.recent_conversations || [])
    try {
      const data = await getProjectConversations(projectId)
      setExpandedConversations(data.items)
    } catch (error) {
      setSidebarError(error instanceof Error ? error.message : '读取项目会话失败')
    }
  }

  async function toggleRecent() {
    if (allRecent) { setAllRecent(null); return }
    try {
      const data = await getConversations()
      setAllRecent(data.items)
    } catch (error) {
      setSidebarError(error instanceof Error ? error.message : '读取历史会话失败')
    }
  }

  async function handleDeleteProject(projectId: string, name: string) {
    if (!window.confirm(`确定要删除项目「${name}」吗？项目下的所有会话也会一并删除。`)) return
    try { await deleteProject(projectId); loadSidebar() }
    catch (error) { setSidebarError(error instanceof Error ? error.message : '删除项目失败') }
  }

  async function handleDeleteConversation(conversationId: string, title: string) {
    if (!window.confirm(`确定要删除会话「${title || '新建对话'}」吗？`)) return
    try { await deleteConversation(conversationId); loadSidebar() }
    catch (error) { setSidebarError(error instanceof Error ? error.message : '删除会话失败') }
  }

  const conversations = allRecent || recent

  function handleLogout() {
    logout()
    setProjects([])
    setRecent([])
    setAllRecent(null)
    setExpandedProjectId(null)
    setExpandedConversations([])
    setConversationTopic('新建对话')
    setAccountOpen(false)
    setAccountInfoPanelOpen(false)
    navigate('/chat', { replace: true })
    if (!authEnabled) {
      // 免登录模式：刷新页面重新以 admin 自动登录
      window.location.reload()
    }
  }

  return (
    <div className="workbench-shell">
      <aside className="sidebar">
        <div className="sidebar-top">
          <NavLink className="brand" to="/market" onClick={() => setMonitorPanelOpen(false)}><span className="brand-mark">B</span><span className="brand-text"><strong>债券信号</strong><small>返回首页</small></span></NavLink>
          <nav className="primary-nav" aria-label="主要功能">
            <NavLink className="new-chat" to="/chat"><span>＋</span><span>新建对话</span></NavLink>
            {PRODUCT_LINKS.map((item) => <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}><span>{item.icon}</span>{item.label}</NavLink>)}
          </nav>
        </div>
        <div className="sidebar-scroll">
          <section className="sidebar-section">
            <div className="sidebar-section-heading"><button className="section-heading" onClick={() => setProjectsOpen((open) => !open)} aria-expanded={projectsOpen}><span>项目<i className="section-caret" /></span></button><button className="section-create" onClick={() => navigate('/projects/new')} aria-label="新建项目" /></div>
            {projectsOpen && projects.map((project) => <div className="project-side-group" key={project.id}>
              <div className="project-side-row">
                <NavLink to={`/projects/${project.id}`} className="side-row"><span>◈</span>{project.name}</NavLink>
                <button className="project-row-caret" onClick={() => void toggleProject(project.id)} aria-label="展开项目会话">⌄</button>
                <span style={{marginLeft:'auto',display:'flex',gap:0}}>
                  {project.role === 'owner' && <button className="project-row-delete" onClick={(e) => { e.preventDefault(); e.stopPropagation(); void handleDeleteProject(project.id, project.name) }} aria-label="删除项目">🗑</button>}
                  {project.role !== 'viewer' && <button className="project-row-create" onClick={() => navigate(`/chat?project=${project.id}`)} aria-label="新建项目会话" style={{marginLeft:0}}>＋</button>}
                </span>
              </div>
              {expandedProjectId === project.id && <div className="project-conversation-list">{expandedConversations.map((conversation) => <div className="conversation-row" key={conversation.id}>
                <NavLink to={`/chat/${conversation.id}`} className="side-row project-conversation" title={conversation.title || '新建对话'}>{conversation.title || '新建对话'}</NavLink>
                <div className="row-action-spacer" />
                {project.role !== 'viewer' && <button className="row-delete" onClick={(e) => { e.preventDefault(); e.stopPropagation(); void handleDeleteConversation(conversation.id, conversation.title) }} aria-label="删除会话">🗑</button>}
              </div>)}</div>}
            </div>)}
          </section>
          <section className="sidebar-section conversations">
            <div className="sidebar-section-heading"><button className="section-heading" onClick={() => setConversationsOpen((open) => !open)} aria-expanded={conversationsOpen}><span>最近会话<i className="section-caret" /></span></button><button className="section-create" onClick={() => navigate('/chat')} aria-label="新建普通会话" /></div>
            {conversationsOpen && <>{conversations.map((conversation) => <div className="conversation-row" key={conversation.id}><NavLink to={`/chat/${conversation.id}`} className="side-row conversation" title={conversation.title || '新建对话'}>{conversation.title || '新建对话'}</NavLink><button className="row-delete" onClick={(e) => { e.preventDefault(); e.stopPropagation(); void handleDeleteConversation(conversation.id, conversation.title) }} aria-label="删除会话">🗑</button></div>)}{recent.length > 0 && <button className="more-button" onClick={() => void toggleRecent()}>{allRecent ? '收起会话' : '查看更多'}</button>}</>}
            {sidebarError && <small className="sidebar-error">{sidebarError}</small>}
          </section>
        </div>
        <div className="sidebar-bottom">
          {isAuthenticated ? <>
            {accountOpen && <div className="account-menu">
              <div className="account-menu-profile"><span className="avatar">你</span><div><strong>{displayName || username || 'admin'}</strong><small>{ROLE_LABELS[role] || role} · BondSense 工作台</small></div></div>
              <button className="account-menu-item" onClick={() => { setAccountInfoPanelOpen(true); setAccountOpen(false) }}><span>◉</span>账户信息<i className="account-menu-caret-right" /></button>
              <button className="account-menu-item" onClick={() => { setDeletedPanelOpen(true); setAccountOpen(false) }}><span>🗑</span>最近删除<i className="account-menu-caret-right" /></button>
              <button className="account-menu-item" onClick={() => { setMonitorPanelOpen(true); setAccountOpen(false) }}><span>▦</span>{isAdmin ? '监控看板' : '我的使用'}<i className="account-menu-caret-right" /></button>
              {isAdmin && <button className="account-menu-item" onClick={() => { setUserManagementOpen(true); setAccountOpen(false) }}><span className="account-menu-user-icon" aria-hidden="true"><svg viewBox="0 0 20 20" fill="none"><path d="M7.5 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2.5 16.5v-1.2c0-2.1 2.2-3.8 5-3.8s5 1.7 5 3.8v1.2M12.5 4.2a2.6 2.6 0 0 1 0 5.1M13.8 11.8c2.1.5 3.7 1.8 3.7 3.5v1.2" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" /></svg></span>用户管理<i className="account-menu-caret-right" /></button>}
              <button className="account-menu-item logout" onClick={handleLogout}><span>↪</span>退出</button>
            </div>}
            <button className={'account-button' + (accountOpen ? ' active' : '')} onClick={() => setAccountOpen((open) => !open)} aria-expanded={accountOpen}><span className="avatar">你</span><span className="account-copy"><strong>{displayName || username || 'admin'}</strong><small>账户与设置</small></span><span className="account-arrow" aria-hidden="true" /></button>
          </> : <button className="login-button" onClick={() => setLoginOpen(true)}><span className="avatar avatar-ghost">未</span><span className="account-copy"><strong>未登录</strong><small>点击登录</small></span></button>}
        </div>
      </aside>
      <main className="workspace-main" style={{ gridTemplateRows: hideWorkflowDetailTopbar ? 'minmax(0,1fr)' : isHome ? '68px 46px minmax(0,1fr)' : '68px minmax(0,1fr)' }}>
        {!hideWorkflowDetailTopbar && <header className="topbar">
          <div className="topbar-title">
            {showWorkflowBack && <button className="topbar-back-button" onClick={() => navigate('/workflow')} aria-label="返回工作流">←</button>}
            <span>{isWorkflowChild ? workflowChildTitle : topbarTitle}</span>
          </div>
          {isHome ? (
            <label className="global-search"><span>⌕</span><input placeholder="搜索债券、新闻、因子或策略…" /></label>
          ) : (
            <span style={{ flex: 1 }} />
          )}
          <button className="topbar-action">通知</button>
        </header>}
        {isHome && (
          <nav className="workspace-tabs" aria-label="市场板块">
            {SECTION_TABS.map((s) => (
              <NavLink key={s.to} to={s.to} className={({ isActive }) => `workspace-tab${isActive ? ' active' : ''}`}>{s.name}</NavLink>
            ))}
          </nav>
        )}
        <div className="workspace-content">
          {homeChatPlaceholder ? (
            <div className="home-chat-workspace">
              <div className="home-chat-scroll"><Outlet /></div>
              <HomeChatDock className="home-agent-chat-dock" placeholder={homeChatPlaceholder} />
            </div>
          ) : <Outlet />}
        </div>
      </main>
      <DeletedItemsPanel open={deletedPanelOpen} onClose={() => setDeletedPanelOpen(false)} />
      <AccountInfoPanel open={accountInfoPanelOpen} onClose={() => setAccountInfoPanelOpen(false)} onLogout={handleLogout} />
      <UserManagementPanel open={userManagementOpen} onClose={() => setUserManagementOpen(false)} />
      <LoginModal isOpen={loginOpen} onClose={() => setLoginOpen(false)} onLoggedIn={loadSidebar} />
      <Suspense fallback={null}>
        <MonitorDashboardPanel open={monitorPanelOpen} onClose={() => setMonitorPanelOpen(false)} />
      </Suspense>
    </div>
  )
}
