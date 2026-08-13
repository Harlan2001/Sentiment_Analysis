import { useCallback, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Conversation, Project, deleteConversation, deleteProject, getConversations, getProjectConversations, getSidebar } from '../api/workbench'
import { DeletedItemsPanel } from '../features/computer/DeletedItemsPanel'
import { AccountInfoPanel } from '../features/computer/AccountInfoPanel'

const productLinks = [
  { to: '/computer', label: 'Computer', icon: '◉' },
  { to: '/custom/mcp', label: '自定义', icon: '◌' },
]

/** 市场板块标签 */
const SECTIONS = [
  { name: '市场', to: '/market' },
  { name: '收益', to: '/returns' },
  { name: '预测', to: '/forecast' },
  { name: '关注列表', to: '/watchlist' },
  { name: '投资组合', to: '/portfolio' },
  { name: '工作流', to: '/workflow' },
]

const HOME_PATHS = new Set(SECTIONS.map((s) => s.to).concat(['/home', '/']))

function resolveTitle(pathname: string, conversationTopic: string): string {
  if (pathname.startsWith('/chat/')) return `对话 · ${conversationTopic}`
  if (pathname.startsWith('/computer/strategies')) return 'Computer · 策略开发'
  if (pathname.startsWith('/computer/reports')) return 'Computer · 研报生成'
  if (pathname.startsWith('/computer/news')) return 'Computer · 每日新闻总结'
  if (pathname.startsWith('/computer')) return 'Computer'
  if (pathname.startsWith('/custom/mcp')) return '自定义 · MCP 连接'
  if (pathname.startsWith('/custom/skills')) return '自定义 · Skills'
  if (pathname.startsWith('/custom')) return '自定义'
  if (pathname.startsWith('/projects/new')) return '项目 · 新建'
  if (pathname.startsWith('/projects/')) return '项目空间'
  if (pathname.startsWith('/settings')) return '设置'
  return '债券市场智能分析'
}

type SidebarProject = Project & { recent_conversations: Conversation[] }

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
  const [isLoggedIn, setIsLoggedIn] = useState(true)
  const [accountOpen, setAccountOpen] = useState(false)
  const [accountInfoPanelOpen, setAccountInfoPanelOpen] = useState(false)
  const [deletedPanelOpen, setDeletedPanelOpen] = useState(false)
  const isHome = HOME_PATHS.has(location.pathname) || SECTIONS.some((s) => location.pathname === s.to)
  const topbarTitle = resolveTitle(location.pathname, conversationTopic)

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

  return (
    <div className="workbench-shell">
      <aside className="sidebar">
        <div className="sidebar-top">
          <NavLink className="brand" to="/market"><span className="brand-mark">B</span><strong>债券信号</strong></NavLink>
          <nav className="primary-nav" aria-label="主要功能">
            <NavLink className="new-chat" to="/chat/new"><span>＋</span><span>新建对话</span></NavLink>
            {productLinks.map((item) => <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}><span>{item.icon}</span>{item.label}</NavLink>)}
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
                  {project.role !== 'viewer' && <button className="project-row-create" onClick={() => navigate(`/chat/new?project=${project.id}`)} aria-label="新建项目会话" style={{marginLeft:0}}>＋</button>}
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
            <div className="sidebar-section-heading"><button className="section-heading" onClick={() => setConversationsOpen((open) => !open)} aria-expanded={conversationsOpen}><span>最近会话<i className="section-caret" /></span></button><button className="section-create" onClick={() => navigate('/chat/new')} aria-label="新建普通会话" /></div>
            {conversationsOpen && <>{conversations.map((conversation) => <div className="conversation-row" key={conversation.id}><NavLink to={`/chat/${conversation.id}`} className="side-row conversation" title={conversation.title || '新建对话'}>{conversation.title || '新建对话'}</NavLink><button className="row-delete" onClick={(e) => { e.preventDefault(); e.stopPropagation(); void handleDeleteConversation(conversation.id, conversation.title) }} aria-label="删除会话">🗑</button></div>)}{recent.length > 0 && <button className="more-button" onClick={() => void toggleRecent()}>{allRecent ? '收起会话' : '查看更多'}</button>}</>}
            {sidebarError && <small className="sidebar-error">{sidebarError}</small>}
          </section>
        </div>
        <div className="sidebar-bottom">
          {isLoggedIn ? <>
            {accountOpen && <div className="account-menu">
              <div className="account-menu-profile"><span className="avatar">你</span><div><strong>当前用户</strong><small>BondSense 工作台</small></div></div>
              <button className="account-menu-item" onClick={() => { setAccountInfoPanelOpen(true); setAccountOpen(false) }}><span>◉</span>账户信息<i className="account-menu-caret-right" /></button>
              <button className="account-menu-item" onClick={() => { setDeletedPanelOpen(true); setAccountOpen(false) }}><span>🗑</span>最近删除<i className="account-menu-caret-right" /></button>
              <button className="account-menu-item logout" onClick={() => { setIsLoggedIn(false); setAccountOpen(false) }}><span>↪</span>退出</button>
            </div>}
            <button className={'account-button' + (accountOpen ? ' active' : '')} onClick={() => setAccountOpen((open) => !open)} aria-expanded={accountOpen}><span className="avatar">你</span><span className="account-copy"><strong>当前用户</strong><small>账户与设置</small></span><span className="account-arrow" aria-hidden="true" /></button>
          </> : <button className="login-button" onClick={() => { setIsLoggedIn(true); setAccountOpen(true) }}><span>◉</span>登录</button>}
        </div>
      </aside>
      <main className="workspace-main" style={{ gridTemplateRows: isHome ? '68px 46px minmax(0,1fr)' : '68px minmax(0,1fr)' }}>
        <header className="topbar">
          <div className="topbar-title">{topbarTitle}</div>
          {isHome ? (
            <label className="global-search"><span>⌕</span><input placeholder="搜索债券、新闻、因子或策略…" /></label>
          ) : (
            <span style={{ flex: 1 }} />
          )}
          <button className="topbar-action">通知</button>
        </header>
        {isHome && (
          <nav className="workspace-tabs" aria-label="市场板块">
            {SECTIONS.map((s) => (
              <NavLink key={s.to} to={s.to} className={({ isActive }) => `workspace-tab${isActive ? ' active' : ''}`}>{s.name}</NavLink>
            ))}
          </nav>
        )}
        <div className="workspace-content"><Outlet /></div>
      </main>
      <DeletedItemsPanel open={deletedPanelOpen} onClose={() => setDeletedPanelOpen(false)} />
      <AccountInfoPanel open={accountInfoPanelOpen} onClose={() => setAccountInfoPanelOpen(false)} onLogout={() => setIsLoggedIn(false)} />
    </div>
  )
}