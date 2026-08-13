import { useCallback, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Conversation, DeletedItemsData, Project, deleteConversation, deleteProject, getConversations, getDeletedItems, getProjectConversations, getSidebar, restoreConversation, restoreProject } from '../api/workbench'

const productLinks = [
  { to: '/computer', label: 'Computer', icon: '◉' },
  { to: '/custom/factors', label: '自定义', icon: '◌' },
]

/** 市场板块标签：标签 → 路由（保留原 WorkspaceLayout 的板块页） */
const SECTIONS = [
  { name: '市场', to: '/market' },
  { name: '因子', to: '/factors' },
  { name: '收益', to: '/returns' },
  { name: '预测', to: '/forecast' },
  { name: '关注列表', to: '/watchlist' },
  { name: '投资组合', to: '/portfolio' },
  { name: '工作流', to: '/workflow' },
]

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
  const [accountInfoOpen, setAccountInfoOpen] = useState(false)
  const [deletedOpen, setDeletedOpen] = useState(false)
  const [deletedItems, setDeletedItems] = useState<DeletedItemsData | null>(null)
  const [deletedProjectsOpen, setDeletedProjectsOpen] = useState(true)
  const [deletedConversationsOpen, setDeletedConversationsOpen] = useState(true)
  const isChatPage = location.pathname.startsWith('/chat/')

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
    if (allRecent) {
      setAllRecent(null)
      return
    }
    try {
      const data = await getConversations()
      setAllRecent(data.items)
    } catch (error) {
      setSidebarError(error instanceof Error ? error.message : '读取历史会话失败')
    }
  }

  async function handleDeleteProject(projectId: string, name: string) {
    if (!window.confirm(`确定要删除项目「${name}」吗？项目下的所有会话也会一并删除。`)) return
    try {
      await deleteProject(projectId)
      loadSidebar()
    } catch (error) {
      setSidebarError(error instanceof Error ? error.message : '删除项目失败')
    }
  }

  async function handleDeleteConversation(conversationId: string, title: string) {
    if (!window.confirm(`确定要删除会话「${title || '新建对话'}」吗？`)) return
    try {
      await deleteConversation(conversationId)
      loadSidebar()
    } catch (error) {
      setSidebarError(error instanceof Error ? error.message : '删除会话失败')
    }
  }

  async function loadDeletedItems() {
    try {
      const data = await getDeletedItems()
      setDeletedItems(data)
    } catch (error) {
      setSidebarError(error instanceof Error ? error.message : '读取已删除项失败')
    }
  }

  async function handleRestoreProject(projectId: string) {
    try {
      await restoreProject(projectId)
      loadDeletedItems()
      loadSidebar()
    } catch (error) {
      setSidebarError(error instanceof Error ? error.message : '恢复项目失败')
    }
  }

  async function handleRestoreConversation(conversationId: string) {
    try {
      await restoreConversation(conversationId)
      loadDeletedItems()
      loadSidebar()
    } catch (error) {
      setSidebarError(error instanceof Error ? error.message : '恢复会话失败')
    }
  }

  const conversations = allRecent || recent
  return <div className="workbench-shell">
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
            <div className="project-side-row"><NavLink to={`/projects/${project.id}`} className="side-row"><span>◈</span>{project.name}</NavLink><button className="project-row-caret" onClick={() => void toggleProject(project.id)} aria-label="展开项目会话">⌄</button><button className="project-row-create" onClick={() => navigate(`/chat/new?project=${project.id}`)} aria-label="新建项目会话">＋</button><button className="project-row-delete" onClick={(e) => { e.preventDefault(); e.stopPropagation(); void handleDeleteProject(project.id, project.name) }} aria-label="删除项目">🗑</button></div>
            {expandedProjectId === project.id && <div className="project-conversation-list">{expandedConversations.map((conversation) => <div className="conversation-row" key={conversation.id}><NavLink to={`/chat/${conversation.id}`} className="side-row project-conversation" title={conversation.title || '新建对话'}>{conversation.title || '新建对话'}</NavLink><div className="row-action-spacer" /><button className="row-delete" onClick={(e) => { e.preventDefault(); e.stopPropagation(); void handleDeleteConversation(conversation.id, conversation.title) }} aria-label="删除会话">🗑</button></div>)}</div>}
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
            <button className="account-menu-item" onClick={() => setAccountInfoOpen((open) => !open)}><span>◉</span>账户信息<i className="account-menu-caret" /></button>
            {accountInfoOpen && <div className="account-info-detail">当前方案：基础版<br />登录状态：已登录</div>}
            <button className="account-menu-item" onClick={() => { setDeletedOpen((open) => !open); if (!deletedOpen) loadDeletedItems() }}><span>🗑</span>最近删除<i className="account-menu-caret" /></button>
            {deletedOpen && <div className="deleted-panel">
              {!deletedItems ? <div className="deleted-empty">正在读取…</div> : <>
                <button className="deleted-group-title" onClick={() => setDeletedProjectsOpen((open) => !open)}><span>已删除的项目<i className="deleted-group-caret" /></span></button>
                {deletedProjectsOpen && (deletedItems.deleted_projects.length === 0 ? <div className="deleted-empty">暂无已删除的项目</div> : deletedItems.deleted_projects.map((project) => <div className="deleted-item-row" key={project.id}><span>{project.name}</span><time>{new Date(project.deleted_at).toLocaleDateString('zh-CN')}</time><button className="deleted-restore" onClick={() => void handleRestoreProject(project.id)}>恢复</button></div>))}
                <button className="deleted-group-title" onClick={() => setDeletedConversationsOpen((open) => !open)}><span>已删除的会话<i className="deleted-group-caret" /></span></button>
                {deletedConversationsOpen && (deletedItems.deleted_conversations.length === 0 ? <div className="deleted-empty">暂无已删除的会话</div> : deletedItems.deleted_conversations.map((conversation) => <div className="deleted-item-row" key={conversation.id}><span>{conversation.title || '新建对话'}</span><time>{new Date(conversation.deleted_at).toLocaleDateString('zh-CN')}</time><button className="deleted-restore" onClick={() => void handleRestoreConversation(conversation.id)}>恢复</button></div>))}
              </>}
            </div>}
            <button className="account-menu-item logout" onClick={() => { setIsLoggedIn(false); setAccountOpen(false); setAccountInfoOpen(false); setDeletedOpen(false) }}><span>↪</span>退出</button>
          </div>}
          <button className={'account-button' + (accountOpen ? ' active' : '')} onClick={() => setAccountOpen((open) => !open)} aria-expanded={accountOpen}><span className="avatar">你</span><span className="account-copy"><strong>当前用户</strong><small>账户与设置</small></span><span className="account-arrow" aria-hidden="true" /></button>
        </> : <button className="login-button" onClick={() => { setIsLoggedIn(true); setAccountOpen(true) }}><span>◉</span>登录</button>}
      </div>
    </aside>
    <main className="workspace-main">
      <header className="topbar"><div className="topbar-title">{isChatPage ? `对话主题 · ${conversationTopic}` : '债券市场智能分析'}</div><label className="global-search"><span>⌕</span><input placeholder="搜索债券、新闻、因子或策略…" /></label><button className="topbar-action">通知</button></header>
      <nav className="workspace-tabs" aria-label="市场板块">
        {SECTIONS.map((s) => (
          <NavLink key={s.to} to={s.to} className={({ isActive }) => `workspace-tab${isActive ? ' active' : ''}`}>{s.name}</NavLink>
        ))}
      </nav>
      <div className="workspace-content"><Outlet /></div>
    </main>
  </div>
}
