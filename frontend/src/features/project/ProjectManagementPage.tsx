import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Conversation,
  MemoryCategory,
  Project,
  ProjectMember,
  ProjectMemory,
  createProject,
  createProjectMemory,
  deleteConversation,
  deleteProject,
  deleteProjectMemory,
  getProject,
  getProjectConversations,
  listProjectMembers,
  listProjectMemories,
  removeProjectMember,
  updateConversation,
  updateProject,
  updateProjectMemory,
  upsertProjectMember,
} from '@/api/projects'
import { uuid } from '@/utils/helpers'
import './project-management.css'
import './project-detail-refine.css'

type Tab = 'conversations' | 'memories' | 'members'

const CATEGORY_LABELS: Record<MemoryCategory, string> = {
  background: '研究背景',
  goal: '目标',
  constraint: '约束',
  preference: '偏好',
  conclusion: '关键结论',
  other: '其他',
}

const ROLE_LABELS = { owner: '所有者', editor: '编辑者', viewer: '查看者' } as const
const ROLE_SCOPES = {
  owner: '可管理成员、设置和项目内容',
  editor: '可编辑项目内容',
  viewer: '仅查看项目内容',
} as const

function formatTime(value: string | null) {
  if (!value) return '尚未发送消息'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function messageOf(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

export function ProjectManagementPage() {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const isCreating = !projectId || projectId === 'new'
  const [createRequestId] = useState(() => uuid())
  const [project, setProject] = useState<Project | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [archivedConversations, setArchivedConversations] = useState<Conversation[]>([])
  const [memories, setMemories] = useState<ProjectMemory[]>([])
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [tab, setTab] = useState<Tab>('conversations')
  const [loading, setLoading] = useState(!isCreating)
  const [saving, setSaving] = useState(false)
  const [pageError, setPageError] = useState('')
  const [actionError, setActionError] = useState('')
  const [success, setSuccess] = useState('')
  const [showArchived, setShowArchived] = useState(false)
  const [search, setSearch] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [memoryEditorOpen, setMemoryEditorOpen] = useState(false)
  const [editingMemory, setEditingMemory] = useState<ProjectMemory | null>(null)
  const [memoryCategory, setMemoryCategory] = useState<MemoryCategory>('background')
  const [memoryTitle, setMemoryTitle] = useState('')
  const [memoryContent, setMemoryContent] = useState('')
  const [memberUsername, setMemberUsername] = useState('')
  const [memberRole, setMemberRole] = useState<'editor' | 'viewer'>('viewer')

  const canWrite = project?.role === 'owner' || project?.role === 'editor'
  const isOwner = project?.role === 'owner'

  const loadProject = useCallback(async () => {
    if (isCreating || !projectId) return
    setLoading(true)
    setPageError('')
    try {
      const [loadedProject, active, archived, loadedMemories, loadedMembers] = await Promise.all([
        getProject(projectId),
        getProjectConversations(projectId),
        getProjectConversations(projectId, { archived: true }),
        listProjectMemories(projectId),
        listProjectMembers(projectId),
      ])
      setProject(loadedProject)
      setName(loadedProject.name)
      setDescription(loadedProject.description || '')
      setConversations(active.items)
      setArchivedConversations(archived.items)
      setMemories(loadedMemories)
      setMembers(loadedMembers)
    } catch (error) {
      setPageError(messageOf(error, '读取项目失败'))
    } finally {
      setLoading(false)
    }
  }, [isCreating, projectId])

  useEffect(() => {
    void loadProject()
  }, [loadProject])

  function notify(message: string) {
    setSuccess(message)
    setActionError('')
    window.setTimeout(() => setSuccess(''), 3200)
  }

  async function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const cleanName = name.trim()
    if (!cleanName || saving) return
    setSaving(true)
    setActionError('')
    try {
      const created = await createProject({
        name: cleanName,
        description: description.trim() || undefined,
        client_request_id: createRequestId,
      })
      window.dispatchEvent(new Event('bondsense-sidebar-refresh'))
      navigate(`/projects/${created.id}`, { replace: true })
    } catch (error) {
      setActionError(messageOf(error, '创建项目失败'))
    } finally {
      setSaving(false)
    }
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!project || !name.trim() || saving) return
    setSaving(true)
    try {
      const updated = await updateProject(project.id, { name: name.trim(), description: description.trim() || null })
      setProject(updated)
      setSettingsOpen(false)
      window.dispatchEvent(new Event('bondsense-sidebar-refresh'))
      notify('项目设置已保存')
    } catch (error) {
      setActionError(messageOf(error, '保存项目设置失败'))
    } finally {
      setSaving(false)
    }
  }

  async function handleDeleteProject() {
    if (!project || !window.confirm(`确定删除项目「${project.name}」吗？项目会进入最近删除，可恢复。`)) return
    try {
      await deleteProject(project.id)
      window.dispatchEvent(new Event('bondsense-sidebar-refresh'))
      navigate('/home', { replace: true })
    } catch (error) {
      setActionError(messageOf(error, '删除项目失败'))
    }
  }

  async function toggleArchive(conversation: Conversation) {
    try {
      await updateConversation(conversation.id, { archived: conversation.status !== 'archived' })
      await loadProject()
      notify(conversation.status === 'archived' ? '会话已恢复' : '会话已归档')
    } catch (error) {
      setActionError(messageOf(error, '更新会话状态失败'))
    }
  }

  async function handleDeleteConversation(conversation: Conversation) {
    if (!window.confirm(`确定删除会话「${conversation.title || '新建对话'}」吗？`)) return
    try {
      await deleteConversation(conversation.id)
      await loadProject()
      window.dispatchEvent(new Event('bondsense-sidebar-refresh'))
      notify('会话已移入最近删除')
    } catch (error) {
      setActionError(messageOf(error, '删除会话失败'))
    }
  }

  function openMemoryEditor(memory?: ProjectMemory) {
    setEditingMemory(memory || null)
    setMemoryCategory(memory?.category || 'background')
    setMemoryTitle(memory?.title || '')
    setMemoryContent(memory?.content || '')
    setMemoryEditorOpen(true)
    setActionError('')
  }

  async function saveMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!project || !memoryTitle.trim() || !memoryContent.trim() || saving) return
    setSaving(true)
    try {
      if (editingMemory) {
        await updateProjectMemory(project.id, editingMemory.id, {
          category: memoryCategory,
          title: memoryTitle.trim(),
          content: memoryContent.trim(),
        })
      } else {
        await createProjectMemory(project.id, {
          category: memoryCategory,
          title: memoryTitle.trim(),
          content: memoryContent.trim(),
          is_active: true,
        })
      }
      setMemoryEditorOpen(false)
      setEditingMemory(null)
      setMemories(await listProjectMemories(project.id))
      notify(editingMemory ? '项目记忆已更新' : '项目记忆已创建')
    } catch (error) {
      setActionError(messageOf(error, '保存项目记忆失败'))
    } finally {
      setSaving(false)
    }
  }

  async function toggleMemory(memory: ProjectMemory) {
    if (!project) return
    try {
      const updated = await updateProjectMemory(project.id, memory.id, { is_active: !memory.is_active })
      setMemories((items) => items.map((item) => (item.id === updated.id ? updated : item)))
      notify(updated.is_active ? '记忆已启用，将用于后续项目会话' : '记忆已停用，不再用于 AI 上下文')
    } catch (error) {
      setActionError(messageOf(error, '更新项目记忆失败'))
    }
  }

  async function removeMemory(memory: ProjectMemory) {
    if (!project || !window.confirm(`永久删除项目记忆「${memory.title}」吗？此操作无法恢复。`)) return
    try {
      await deleteProjectMemory(project.id, memory.id)
      setMemories((items) => items.filter((item) => item.id !== memory.id))
      notify('项目记忆已删除')
    } catch (error) {
      setActionError(messageOf(error, '删除项目记忆失败'))
    }
  }

  async function saveMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!project || !memberUsername.trim() || saving) return
    setSaving(true)
    try {
      await upsertProjectMember(project.id, memberUsername.trim(), memberRole)
      setMembers(await listProjectMembers(project.id))
      setMemberUsername('')
      notify('成员权限已保存')
    } catch (error) {
      setActionError(messageOf(error, '保存成员失败'))
    } finally {
      setSaving(false)
    }
  }

  async function changeMemberRole(member: ProjectMember, role: 'editor' | 'viewer') {
    if (!project) return
    try {
      await upsertProjectMember(project.id, member.username, role)
      setMembers(await listProjectMembers(project.id))
      notify('成员角色已更新')
    } catch (error) {
      setActionError(messageOf(error, '更新成员角色失败'))
    }
  }

  async function removeMember(member: ProjectMember) {
    if (!project || !window.confirm(`将 ${member.display_name} 从项目中移除吗？`)) return
    try {
      await removeProjectMember(project.id, member.username)
      setMembers(await listProjectMembers(project.id))
      notify('成员已移除')
    } catch (error) {
      setActionError(messageOf(error, '移除成员失败'))
    }
  }

  const visibleConversations = useMemo(() => {
    const source = showArchived ? archivedConversations : conversations
    const term = search.trim().toLocaleLowerCase()
    return term ? source.filter((item) => (item.title || '').toLocaleLowerCase().includes(term)) : source
  }, [archivedConversations, conversations, search, showArchived])

  if (isCreating) {
    return (
      <section className="pm-page">
        <header className="pm-hero">
          <div>
            <h1>新建项目</h1>
            <p>创建一个可持续沉淀研究会话与明确记忆的项目空间。</p>
          </div>
        </header>
        <form className="pm-create-layout" onSubmit={submitProject}>
          <section className="pm-card pm-form-card">
            <h2>项目基本信息</h2>
            <label>
              <strong>项目名称</strong>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={80}
                required
                autoFocus
                placeholder="例如：国债策略研究"
              />
            </label>
            <label>
              <strong>项目说明（可选）</strong>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={1000}
                rows={5}
                placeholder="说明研究背景、目标或范围"
              />
            </label>
            {actionError && (
              <p className="pm-error" role="alert">
                {actionError}
              </p>
            )}
            <button className="pm-button primary" type="submit" disabled={!name.trim() || saving}>
              {saving ? '正在创建…' : '创建项目'}
            </button>
          </section>
          <aside className="pm-card pm-note">
            <h2>创建后</h2>
            <p>项目会话独立归类，不进入全局最近会话。未发送内容的空会话不会进入历史。</p>
          </aside>
        </form>
      </section>
    )
  }

  if (loading)
    return (
      <section className="pm-page pm-state">
        <span className="pm-spinner" />
        正在加载项目…
      </section>
    )
  if (pageError || !project)
    return (
      <section className="pm-page pm-state">
        <h2>无法读取项目</h2>
        <p>{pageError || '项目不存在或当前用户无权访问。'}</p>
        <button className="pm-button" onClick={() => void loadProject()}>
          重试
        </button>
      </section>
    )

  return (
    <section className="pm-page pm-detail-page">
      <header className="pm-hero pm-detail-hero">
        <div className="pm-title-block">
          <span className="pm-eyebrow">项目空间 · {ROLE_LABELS[project.role]}</span>
          <h1>{project.name}</h1>
          <p>{project.description || '围绕项目研究目标持续开展工作。'}</p>
          <div className="pm-title-meta">
            <span>{ROLE_SCOPES[project.role]}</span>
            <span>{project.visibility === 'shared' ? '共享项目' : '私有项目'}</span>
            <span>更新于 {formatTime(project.updated_at)}</span>
          </div>
        </div>
        <div className="pm-actions">
          {canWrite && (
            <button className="pm-button" onClick={() => setSettingsOpen((open) => !open)}>
              项目设置
            </button>
          )}
          {isOwner && (
            <button className="pm-button danger" onClick={() => void handleDeleteProject()}>
              删除项目
            </button>
          )}
          {canWrite && (
            <button className="pm-button primary" onClick={() => navigate(`/chat?project=${project.id}`)}>
              ＋ 新建项目会话
            </button>
          )}
        </div>
      </header>
      <div className="pm-overview" aria-label="项目概览">
        <article>
          <small>进行中会话</small>
          <strong>{conversations.length}</strong>
          <span>仅统计已发送内容</span>
        </article>
        <article>
          <small>已归档</small>
          <strong>{archivedConversations.length}</strong>
          <span>可随时恢复</span>
        </article>
        <article>
          <small>启用记忆</small>
          <strong>{memories.filter((item) => item.is_active).length}</strong>
          <span>用于项目 AI 上下文</span>
        </article>
        <article>
          <small>项目成员</small>
          <strong>{members.length}</strong>
          <span>{project.visibility === 'shared' ? '协作空间' : '仅自己可见'}</span>
        </article>
      </div>

      {success && (
        <div className="pm-success" role="status">
          ✓ {success}
        </div>
      )}
      {actionError && (
        <div className="pm-error pm-banner" role="alert">
          {actionError}
          <button onClick={() => setActionError('')} aria-label="关闭">
            ×
          </button>
        </div>
      )}
      {!canWrite && <div className="pm-readonly">你是查看者：可读取项目会话、记忆和成员，但不能修改内容。</div>}

      {settingsOpen && (
        <form className="pm-card pm-settings" onSubmit={saveSettings}>
          <div>
            <h2>项目设置</h2>
            <p>编辑项目名称和说明。</p>
          </div>
          <label>
            <span>名称</span>
            <input value={name} maxLength={80} required onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            <span>说明</span>
            <textarea
              value={description}
              maxLength={1000}
              rows={3}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <div className="pm-actions">
            <button className="pm-button" type="button" onClick={() => setSettingsOpen(false)}>
              取消
            </button>
            <button className="pm-button primary" disabled={!name.trim() || saving}>
              {saving ? '保存中…' : '保存设置'}
            </button>
          </div>
        </form>
      )}

      <nav className="pm-tabs" aria-label="项目分区">
        <button className={tab === 'conversations' ? 'active' : ''} onClick={() => setTab('conversations')}>
          会话 <span>{conversations.length}</span>
        </button>
        <button className={tab === 'memories' ? 'active' : ''} onClick={() => setTab('memories')}>
          项目记忆 <span>{memories.filter((item) => item.is_active).length}</span>
        </button>
        <button className={tab === 'members' ? 'active' : ''} onClick={() => setTab('members')}>
          成员与权限 <span>{members.length}</span>
        </button>
      </nav>

      {tab === 'conversations' && (
        <section className="pm-card">
          <header className="pm-card-head">
            <div>
              <h2>项目会话</h2>
              <p>只展示实际发送过内容的项目会话。</p>
            </div>
            <div className="pm-toolbar">
              <button className={`pm-chip${!showArchived ? ' active' : ''}`} onClick={() => setShowArchived(false)}>
                进行中
              </button>
              <button className={`pm-chip${showArchived ? ' active' : ''}`} onClick={() => setShowArchived(true)}>
                已归档 {archivedConversations.length}
              </button>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索会话" />
            </div>
          </header>
          {visibleConversations.length === 0 ? (
            <div className="pm-empty">
              <strong>{search ? '没有匹配的会话' : showArchived ? '暂无已归档会话' : '还没有项目会话'}</strong>
              <p>{showArchived ? '归档后的会话会保留在这里。' : '创建会话并发送第一条消息后，它才会出现在历史中。'}</p>
              {canWrite && !showArchived && (
                <button className="pm-button primary" onClick={() => navigate(`/chat?project=${project.id}`)}>
                  新建项目会话
                </button>
              )}
            </div>
          ) : (
            <div className="pm-list">
              {visibleConversations.map((conversation) => (
                <article className="pm-row" key={conversation.id}>
                  <button className="pm-row-main" onClick={() => navigate(`/chat/${conversation.id}`)}>
                    <strong>{conversation.title || '新建对话'}</strong>
                    <span>{formatTime(conversation.last_message_at)}</span>
                  </button>
                  <span className="pm-badge">{showArchived ? '已归档' : '项目会话'}</span>
                  {canWrite && (
                    <div className="pm-row-actions">
                      <button onClick={() => void toggleArchive(conversation)}>{showArchived ? '恢复' : '归档'}</button>
                      <button className="danger" onClick={() => void handleDeleteConversation(conversation)}>
                        删除
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {tab === 'memories' && (
        <section className="pm-card">
          <header className="pm-card-head">
            <div>
              <h2>项目记忆</h2>
              <p>仅启用的条目会作为该项目后续 AI 会话的限长上下文；不会自动保存临时聊天。</p>
            </div>
            {canWrite && (
              <button className="pm-button primary" onClick={() => openMemoryEditor()}>
                ＋ 新建记忆
              </button>
            )}
          </header>
          {memoryEditorOpen && (
            <form className="pm-inline-form" onSubmit={saveMemory}>
              <label>
                <span>类型</span>
                <select
                  value={memoryCategory}
                  onChange={(event) => setMemoryCategory(event.target.value as MemoryCategory)}
                >
                  {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>标题</span>
                <input
                  value={memoryTitle}
                  maxLength={120}
                  required
                  onChange={(event) => setMemoryTitle(event.target.value)}
                />
              </label>
              <label className="wide">
                <span>内容</span>
                <textarea
                  value={memoryContent}
                  maxLength={10000}
                  rows={5}
                  required
                  onChange={(event) => setMemoryContent(event.target.value)}
                />
              </label>
              <div className="pm-actions wide">
                <button className="pm-button" type="button" onClick={() => setMemoryEditorOpen(false)}>
                  取消
                </button>
                <button className="pm-button primary" disabled={saving || !memoryTitle.trim() || !memoryContent.trim()}>
                  {saving ? '保存中…' : editingMemory ? '保存修改' : '创建记忆'}
                </button>
              </div>
            </form>
          )}
          {memories.length === 0 ? (
            <div className="pm-empty">
              <strong>还没有项目记忆</strong>
              <p>人工维护研究背景、目标、约束、偏好或关键结论。</p>
            </div>
          ) : (
            <div className="pm-memory-grid">
              {memories.map((memory) => (
                <article className={`pm-memory${memory.is_active ? '' : ' inactive'}`} key={memory.id}>
                  <div>
                    <span className="pm-badge">{CATEGORY_LABELS[memory.category]}</span>
                    {!memory.is_active && <span className="pm-badge muted">已停用</span>}
                  </div>
                  <h3>{memory.title}</h3>
                  <p>{memory.content}</p>
                  <small>
                    更新于 {formatTime(memory.updated_at)} · {memory.updated_by}
                  </small>
                  {canWrite && (
                    <footer>
                      <button onClick={() => openMemoryEditor(memory)}>编辑</button>
                      <button onClick={() => void toggleMemory(memory)}>{memory.is_active ? '停用' : '启用'}</button>
                      <button className="danger" onClick={() => void removeMemory(memory)}>
                        删除
                      </button>
                    </footer>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {tab === 'members' && (
        <section className="pm-card">
          <header className="pm-card-head">
            <div>
              <h2>成员与权限</h2>
              <p>当前仅支持添加系统内已启用用户，不会发送外部邀请。</p>
            </div>
          </header>
          {isOwner && (
            <form className="pm-member-form" onSubmit={saveMember}>
              <label>
                <span>用户名</span>
                <input
                  value={memberUsername}
                  maxLength={191}
                  required
                  placeholder="输入已有用户名"
                  onChange={(event) => setMemberUsername(event.target.value)}
                />
              </label>
              <label>
                <span>角色</span>
                <select
                  value={memberRole}
                  onChange={(event) => setMemberRole(event.target.value as 'editor' | 'viewer')}
                >
                  <option value="viewer">查看者</option>
                  <option value="editor">编辑者</option>
                </select>
              </label>
              <button className="pm-button primary" disabled={saving || !memberUsername.trim()}>
                {saving ? '保存中…' : '添加或更新成员'}
              </button>
            </form>
          )}
          <div className="pm-list">
            {members.map((member) => (
              <article className="pm-row pm-member" key={member.username}>
                <i>{member.display_name.slice(0, 1).toUpperCase()}</i>
                <div className="pm-row-copy">
                  <strong>{member.display_name}</strong>
                  <span>
                    @{member.username}
                    {member.is_active ? '' : ' · 账号已停用'}
                  </span>
                </div>
                {isOwner && member.role !== 'owner' ? (
                  <select
                    aria-label={`${member.display_name} 的角色`}
                    value={member.role}
                    onChange={(event) => void changeMemberRole(member, event.target.value as 'editor' | 'viewer')}
                  >
                    <option value="editor">编辑者</option>
                    <option value="viewer">查看者</option>
                  </select>
                ) : (
                  <span className="pm-badge">{ROLE_LABELS[member.role]}</span>
                )}
                {isOwner && member.role !== 'owner' && (
                  <button className="pm-link danger" onClick={() => void removeMember(member)}>
                    移除
                  </button>
                )}
              </article>
            ))}
          </div>
          <div className="pm-permissions">
            <h3>权限说明</h3>
            <div>
              <strong>所有者</strong>
              <span>项目设置、记忆、成员、会话与删除</span>
              <strong>编辑者</strong>
              <span>项目设置、记忆与项目会话</span>
              <strong>查看者</strong>
              <span>只读项目、记忆、成员与会话</span>
            </div>
            <p>当前版本不提供所有权转移或外部邀请。</p>
          </div>
        </section>
      )}

    </section>
  )
}
