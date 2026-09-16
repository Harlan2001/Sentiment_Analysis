import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Modal from '@/components/ui/Modal'
import {
  clearMemories,
  createMemory,
  deleteMemory,
  getMemorySettings,
  listMemories,
  MemoryCategory,
  MemorySettings,
  MemoryStatus,
  updateMemory,
  updateMemorySettings,
  UserMemory,
} from '@/api/memories'
import './memory.css'

type Filter = 'all' | MemoryCategory
type StatusFilter = 'all' | MemoryStatus
type MemoryDraft = Pick<UserMemory, 'title' | 'content' | 'category'>

const EMPTY_DRAFT: MemoryDraft = { title: '', content: '', category: 'response_preference' }
const CATEGORY_LABELS: Record<MemoryCategory, string> = {
  response_preference: '表达偏好',
  user_background: '用户背景',
  long_term_interest: '长期兴趣',
  personal_constraint: '长期约束',
}
const STATUS_LABELS: Record<MemoryStatus, string> = { pending: '待确认', active: '已启用', disabled: '已停用' }
const SOURCE_LABELS = { manual: '手动添加', explicit_chat: '会话中明确要求', inferred_chat: '从普通会话发现' }

function dateLabel(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
}

export function MemoryPage() {
  const navigate = useNavigate()
  const [memories, setMemories] = useState<UserMemory[]>([])
  const [settings, setSettings] = useState<MemorySettings | null>(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<Filter>('all')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [editing, setEditing] = useState<UserMemory | null>(null)
  const [draft, setDraft] = useState<MemoryDraft>(EMPTY_DRAFT)
  const [modalOpen, setModalOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function load() {
    setLoading(true)
    setError('')
    Promise.all([listMemories(), getMemorySettings()])
      .then(([memoryData, settingsData]) => { setMemories(memoryData.items); setSettings(settingsData) })
      .catch((requestError: Error) => setError(requestError.message || '个人记忆加载失败'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const visibleMemories = useMemo(() => memories
    .filter(memory => category === 'all' || memory.category === category)
    .filter(memory => status === 'all' || memory.status === status)
    .filter(memory => `${memory.title} ${memory.content} ${SOURCE_LABELS[memory.source_type]}`.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned)), [memories, query, category, status])
  const pendingCount = memories.filter(memory => memory.status === 'pending').length
  const activeCount = memories.filter(memory => memory.status === 'active').length

  function openCreate() { setEditing(null); setDraft(EMPTY_DRAFT); setModalOpen(true) }
  function openEdit(memory: UserMemory) {
    setEditing(memory)
    setDraft({ title: memory.title, content: memory.content, category: memory.category })
    setModalOpen(true)
  }

  async function saveMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft.title.trim() || !draft.content.trim()) return
    setBusy(true)
    setError('')
    try {
      const payload = { ...draft, title: draft.title.trim(), content: draft.content.trim() }
      const saved = editing ? await updateMemory(editing.id, payload) : await createMemory(payload)
      setMemories(current => editing ? current.map(item => item.id === saved.id ? saved : item) : [saved, ...current])
      setModalOpen(false)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '保存失败')
    } finally { setBusy(false) }
  }

  async function patchMemory(memory: UserMemory, changes: Parameters<typeof updateMemory>[1]) {
    setBusy(true)
    setError('')
    try {
      const saved = await updateMemory(memory.id, changes)
      setMemories(current => current.map(item => item.id === saved.id ? saved : item))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '更新失败')
    } finally { setBusy(false) }
  }

  async function removeMemory(memory: UserMemory) {
    if (!window.confirm(`删除“${memory.title}”？删除后将不再用于后续对话。`)) return
    setBusy(true)
    try {
      await deleteMemory(memory.id)
      setMemories(current => current.filter(item => item.id !== memory.id))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '删除失败')
    } finally { setBusy(false) }
  }

  async function toggleSetting(field: 'memory_enabled' | 'auto_extract_enabled', value: boolean) {
    if (!settings) return
    const previous = settings
    setSettings({ ...settings, [field]: value })
    try {
      setSettings(await updateMemorySettings({ [field]: value }))
    } catch (requestError) {
      setSettings(previous)
      setError(requestError instanceof Error ? requestError.message : '设置更新失败')
    }
  }

  async function clearAll() {
    if (!memories.length || !window.confirm('确认清空全部个人记忆？清空后这些内容将不再用于对话。')) return
    setBusy(true)
    try { await clearMemories(); setMemories([]) }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : '清空失败') }
    finally { setBusy(false) }
  }

  return <section className="custom-page memory-page">
    <div className="custom-tabs"><button onClick={() => navigate('/custom/mcp')}>MCP</button><button onClick={() => navigate('/custom/skills')}>Skills</button><button className="active">记忆</button></div>
    <header className="memory-head">
      <div><span className="memory-eyebrow">账号级个人偏好</span><h1>个人记忆</h1><p>保留表达偏好、个人背景和长期兴趣。当前基础版只作用于普通会话，不读取或修改项目记忆。</p></div>
      <div className="memory-head-actions"><button className="memory-add" type="button" onClick={openCreate}>＋ 添加记忆</button><button className="memory-clear" type="button" disabled={busy || !memories.length} onClick={() => void clearAll()}>清空</button></div>
    </header>
    <div className="memory-settings">
      <label className="memory-switch"><span><strong>使用记忆</strong><small>{settings?.memory_enabled ? '普通会话会参考已启用记忆' : '当前不会用于回答'}</small></span><input type="checkbox" checked={settings?.memory_enabled ?? false} disabled={!settings} onChange={event => void toggleSetting('memory_enabled', event.target.checked)} /></label>
      <label className="memory-switch"><span><strong>自动发现</strong><small>{settings?.auto_extract_enabled ? '从普通会话生成待确认候选' : '只保留手动与明确设置'}</small></span><input type="checkbox" checked={settings?.auto_extract_enabled ?? false} disabled={!settings} onChange={event => void toggleSetting('auto_extract_enabled', event.target.checked)} /></label>
    </div>
    <div className="memory-toolbar">
      <label className="memory-search"><span>⌕</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索个人记忆" /></label>
      <div className="memory-filters">{([['all', '全部'], ...Object.entries(CATEGORY_LABELS)] as [Filter, string][]).map(([key, label]) => <button className={category === key ? 'active' : ''} type="button" key={key} onClick={() => setCategory(key)}>{label}</button>)}</div>
      <small>已启用 {activeCount} 条 · 待确认 {pendingCount} 条</small>
    </div>
    <div className="memory-status-filters">{([['all', '全部状态'], ['pending', `待确认 ${pendingCount}`], ['active', '已启用'], ['disabled', '已停用']] as [StatusFilter, string][]).map(([key, label]) => <button key={key} className={status === key ? 'active' : ''} onClick={() => setStatus(key)}>{label}</button>)}</div>
    {settings && !settings.memory_enabled && <div className="memory-paused">记忆引用已暂停。你仍然可以整理、确认和编辑个人记忆。</div>}
    {error && <div className="memory-error">{error}<button type="button" onClick={load}>重试</button></div>}
    {loading ? <div className="memory-empty"><strong>正在加载个人记忆…</strong></div> : <div className="memory-list">{visibleMemories.map(memory => <article className={`memory-card${memory.is_pinned ? ' pinned' : ''}${memory.status === 'pending' ? ' pending' : ''}`} key={memory.id}>
      <div className="memory-card-top"><span className="memory-scope">{CATEGORY_LABELS[memory.category]}</span><span className={`memory-status ${memory.status}`}>{STATUS_LABELS[memory.status]}</span></div>
      <h2>{memory.title}</h2><p>{memory.content}</p>
      <footer><span>{SOURCE_LABELS[memory.source_type]}</span><time>更新于 {dateLabel(memory.updated_at)}</time></footer>
      {memory.source_conversation_id && <Link className="memory-source-link" to={`/chat/${memory.source_conversation_id}`}>查看来源会话</Link>}
      <div className="memory-card-actions">
        {memory.status === 'pending' && <button className="primary" disabled={busy} onClick={() => void patchMemory(memory, { status: 'active' })}>确认使用</button>}
        {memory.status !== 'pending' && <button disabled={busy} onClick={() => void patchMemory(memory, { status: memory.status === 'active' ? 'disabled' : 'active' })}>{memory.status === 'active' ? '停用' : '启用'}</button>}
        <button disabled={busy} className={memory.is_pinned ? 'active' : ''} onClick={() => void patchMemory(memory, { is_pinned: !memory.is_pinned })}>{memory.is_pinned ? '取消置顶' : '置顶'}</button>
        <button disabled={busy} onClick={() => openEdit(memory)}>编辑</button><button disabled={busy} className="memory-delete" onClick={() => void removeMemory(memory)}>删除</button>
      </div>
    </article>)}</div>}
    {!loading && !visibleMemories.length && <div className="memory-empty"><strong>没有匹配的个人记忆</strong><span>可以手动添加，或在普通会话中说“记住……”</span></div>}
    <p className="memory-note">个人记忆与项目记忆相互独立；本页内容不会写入任何项目。</p>
    <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? '编辑个人记忆' : '添加个人记忆'} size="sm" panelClassName="memory-modal" contentClassName="memory-modal-content">
      <form className="memory-form" onSubmit={saveMemory}>
        <p>只记录对多个后续普通会话有帮助的信息，请不要填写密码、验证码或账户凭证。</p>
        <label>标题<input autoFocus required value={draft.title} maxLength={120} onChange={event => setDraft({ ...draft, title: event.target.value })} placeholder="例如：默认先展示结论" /></label>
        <label>分类<select value={draft.category} onChange={event => setDraft({ ...draft, category: event.target.value as MemoryCategory })}>{Object.entries(CATEGORY_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <label>记忆内容<textarea required rows={4} value={draft.content} maxLength={2000} onChange={event => setDraft({ ...draft, content: event.target.value })} placeholder="例如：回答时默认先给出结论，再展开分析。" /></label>
        <div className="memory-form-actions"><button type="button" onClick={() => setModalOpen(false)}>取消</button><button className="primary" type="submit" disabled={busy}>保存</button></div>
      </form>
    </Modal>
  </section>
}
