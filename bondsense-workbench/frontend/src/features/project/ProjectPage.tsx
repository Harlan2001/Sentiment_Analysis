import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Conversation, Project, createProject, deleteConversation, deleteProject, getProject, getProjectConversations } from '../../api/workbench'

function formatTime(value: string | null) {
  return value ? new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value)) : '尚未发送消息'
}

export function ProjectPage() {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const [project, setProject] = useState<Project | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [tab, setTab] = useState('会话')
  const isCreating = !projectId || projectId === 'new'

  useEffect(() => {
    if (isCreating || !projectId) return
    Promise.all([getProject(projectId), getProjectConversations(projectId)])
      .then(([loadedProject, loadedConversations]) => { setProject(loadedProject); setConversations(loadedConversations.items) })
      .catch((requestError: Error) => setError(requestError.message))
  }, [isCreating, projectId])

  async function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim()) return
    setError('')
    try {
      const created = await createProject({ name: name.trim(), description: description.trim() || undefined })
      window.dispatchEvent(new Event('bondsense-sidebar-refresh'))
      navigate(`/projects/${created.id}`, { replace: true })
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : '创建项目失败') }
  }

  async function handleDeleteProject() {
    if (!project || !window.confirm(`确定要删除项目「${project.name}」吗？项目下的所有会话也会一并删除。`)) return
    try {
      await deleteProject(project.id)
      window.dispatchEvent(new Event('bondsense-sidebar-refresh'))
      navigate('/home', { replace: true })
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : '删除项目失败') }
  }

  async function handleDeleteConversation(conversationId: string, title: string) {
    if (!window.confirm(`确定要删除会话「${title || '新建对话'}」吗？`)) return
    try {
      await deleteConversation(conversationId)
      setConversations((prev) => prev.filter((c) => c.id !== conversationId))
      window.dispatchEvent(new Event('bondsense-sidebar-refresh'))
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : '删除会话失败') }
  }

  if (error && !isCreating) return <section className="project-page"><p className="chat-error">无法读取项目：{error}</p></section>
  const title = isCreating ? '新建项目' : project?.name || '正在读取项目…'
  const subtitle = isCreating ? '创建一个可持续沉淀研究会话的项目空间。' : project?.description || '围绕项目研究目标持续开展工作。'

  return <section className="project-page">
    <header className="project-hero"><div><h1>{title}</h1><p>{subtitle}</p></div>{!isCreating && <div className="project-actions"><span className="project-avatars"><i>你</i></span><button className="computer-button">项目设置</button><button className="computer-button" style={{color:'#d97a6e',borderColor:'#5a3a38'}} onClick={() => void handleDeleteProject()}>🗑 删除项目</button><button className="computer-button primary" onClick={() => navigate(`/chat/new?project=${project?.id}`)}>＋ 新建项目会话</button></div>}</header>
    <div className="project-tabs">{['会话', '项目记忆', '成员与权限'].map((item) => <button className={tab === item ? 'active' : ''} onClick={() => setTab(item)} key={item}>{item}</button>)}<span className="computer-spacer" /></div>
    {isCreating ? <form className="project-main project-create-form" onSubmit={submitProject}>
      <section className="project-card project-conversations"><header><h2>项目基本信息</h2></header><label><strong>项目名称</strong><input value={name} onChange={(event) => setName(event.target.value)} maxLength={80} placeholder="例如：国债策略研究" autoFocus /></label><label><strong>项目说明（可选）</strong><textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={1000} rows={4} placeholder="说明这个项目的研究目标" /></label>{error && <p className="chat-error">{error}</p>}<button className="computer-button primary" type="submit">创建项目</button></section><aside className="project-side"><section className="project-card"><header><h2>创建后可用</h2></header><p>项目会话会独立归类，不出现在全局最近会话中。</p></section></aside>
    </form> : <>
      <div className="project-metrics"><div><small>项目会话</small><strong>{conversations.length}</strong><span>仅显示已发送内容的会话</span></div><div><small>项目记忆</small><strong>—</strong><span>将在后续批次接入</span></div><div><small>项目成员</small><strong>1</strong><span>当前项目所有者</span></div><div><small>可见范围</small><strong>私有</strong><span>仅自己可见</span></div></div>
      {tab === '会话' && <div className="project-main"><section className="project-card project-conversations"><header><h2>最近会话</h2><label><span>⌕</span><input placeholder="搜索项目会话" /></label></header>{conversations.length === 0 ? <p>还没有已发送内容的项目会话。</p> : conversations.map((conversation) => <article key={conversation.id} onClick={() => navigate(`/chat/${conversation.id}`)}><div><strong>{conversation.title || '新建对话'}</strong><p>{formatTime(conversation.last_message_at)}</p></div><span className="project-badge">项目会话</span><button className="row-delete" onClick={(e) => { e.stopPropagation(); void handleDeleteConversation(conversation.id, conversation.title) }} aria-label="删除会话">🗑</button></article>)}<button className="computer-button" onClick={() => navigate(`/chat/new?project=${project?.id}`)}>＋ 新建项目会话</button></section><aside className="project-side"><section className="project-card"><header><h2>项目共享记忆</h2><span className="computer-badge">后续接入</span></header><p>项目记忆功能保留原有入口，待下一批接口接入。</p></section><section className="project-card"><header><h2>成员与权限</h2><span className="computer-count">1 人</span></header><article className="member-item"><i>你</i><div><strong>当前用户</strong><p>项目所有者</p></div><span className="computer-spacer" /><span className="project-badge">所有者</span></article></section></aside></div>}
      {tab !== '会话' && <section className="project-card project-memory-full"><header><h2>{tab}</h2></header><p>此区域保留原有项目页结构，相关数据接口将在后续批次接入。</p></section>}
    </>}
  </section>
}
