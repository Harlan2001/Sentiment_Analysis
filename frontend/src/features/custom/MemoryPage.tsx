import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Modal from '@/components/ui/Modal'
import { DemoNotice } from '@/components/ui/DemoNotice'
import { uuid } from '@/utils/helpers'
import './memory.css'

type MemoryScope = '偏好' | '项目' | '研究'

type Memory = {
  id: string
  title: string
  content: string
  scope: MemoryScope
  source: string
  updatedAt: string
  pinned: boolean
}

type MemoryDraft = Pick<Memory, 'title' | 'content' | 'scope'>

const STORAGE_KEY = 'bondsense-conversation-memories'
const EMPTY_DRAFT: MemoryDraft = { title: '', content: '', scope: '偏好' }
const STARTER_MEMORIES: Memory[] = [
  { id: 'preference-language', title: '默认使用中文回答', content: '解释与研究结论优先使用中文；必要的英文术语保留原文。', scope: '偏好', source: '会话偏好', updatedAt: '刚刚', pinned: true },
  { id: 'research-focus', title: '关注信用债风险信号', content: '后续分析优先提示主体基本面、估值异动和潜在信用风险。', scope: '研究', source: '投研会话', updatedAt: '今天 10:24', pinned: true },
  { id: 'project-context', title: '当前项目：债券市场智能分析', content: '围绕债券市场数据、情绪因子与投资研究工作流持续协作。', scope: '项目', source: '项目上下文', updatedAt: '昨天', pinned: false },
]

function readMemories(): Memory[] {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) : STARTER_MEMORIES
  } catch {
    return STARTER_MEMORIES
  }
}

function nowLabel() {
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date())
}

export function MemoryPage() {
  const navigate = useNavigate()
  const [memories, setMemories] = useState<Memory[]>(readMemories)
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState<'全部' | MemoryScope>('全部')
  const [enabled, setEnabled] = useState(true)
  const [editing, setEditing] = useState<Memory | null>(null)
  const [draft, setDraft] = useState<MemoryDraft>(EMPTY_DRAFT)
  const [modalOpen, setModalOpen] = useState(false)

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(memories))
  }, [memories])

  const visibleMemories = useMemo(() => memories
    .filter((memory) => scope === '全部' || memory.scope === scope)
    .filter((memory) => `${memory.title} ${memory.content} ${memory.source}`.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => Number(b.pinned) - Number(a.pinned)), [memories, query, scope])

  function openCreate() {
    setEditing(null)
    setDraft(EMPTY_DRAFT)
    setModalOpen(true)
  }

  function openEdit(memory: Memory) {
    setEditing(memory)
    setDraft({ title: memory.title, content: memory.content, scope: memory.scope })
    setModalOpen(true)
  }

  function saveMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft.title.trim() || !draft.content.trim()) return
    const updatedAt = nowLabel()
    if (editing) {
      setMemories((current) => current.map((memory) => memory.id === editing.id ? { ...memory, ...draft, title: draft.title.trim(), content: draft.content.trim(), updatedAt } : memory))
    } else {
      setMemories((current) => [{ id: uuid(), ...draft, title: draft.title.trim(), content: draft.content.trim(), source: '手动添加', updatedAt, pinned: false }, ...current])
    }
    setModalOpen(false)
  }

  function togglePinned(id: string) {
    setMemories((current) => current.map((memory) => memory.id === id ? { ...memory, pinned: !memory.pinned } : memory))
  }

  function removeMemory(id: string) {
    setMemories((current) => current.filter((memory) => memory.id !== id))
  }

  const pinnedCount = memories.filter((memory) => memory.pinned).length

  return <section className="custom-page memory-page">
    <div className="custom-tabs">
      <button onClick={() => navigate('/custom/mcp')}>MCP</button>
      <button onClick={() => navigate('/custom/skills')}>Skills</button>
      <button className="active">记忆</button>
    </div>

    <DemoNotice
      title="记忆功能为演示版本"
      description="当前页面使用当前浏览器中的演示数据，不会形成真实的账号记忆或自动用于后续对话；实际功能尚在开发中。"
    />

    <header className="memory-head">
      <div>
        <span className="memory-eyebrow">会话上下文</span>
        <h1>记忆</h1>
        <p>保留重要偏好、项目背景和研究结论，让后续会话延续必要的上下文。</p>
      </div>
      <div className="memory-head-actions">
        <button className="memory-add" type="button" onClick={openCreate}>＋ 添加记忆</button>
        <label className="memory-switch"><span><strong>使用记忆</strong><small>{enabled ? '会在后续会话中作为参考' : '当前不会用于对话'}</small></span><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /></label>
      </div>
    </header>

    <div className="memory-toolbar">
      <label className="memory-search"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索记忆" /></label>
      <div className="memory-filters">{(['全部', '偏好', '项目', '研究'] as const).map((item) => <button className={scope === item ? 'active' : ''} type="button" key={item} onClick={() => setScope(item)}>{item}</button>)}</div>
      <small>共 {memories.length} 条 · 已置顶 {pinnedCount} 条</small>
    </div>

    {!enabled && <div className="memory-paused">记忆引用已暂停。你仍可以在这里整理和编辑记忆。</div>}
    <div className="memory-list">{visibleMemories.map((memory) => <article className={'memory-card' + (memory.pinned ? ' pinned' : '')} key={memory.id}>
      <div className="memory-card-top"><span className={'memory-scope ' + memory.scope}>{memory.scope}</span><div><button type="button" className={memory.pinned ? 'active' : ''} onClick={() => togglePinned(memory.id)}>{memory.pinned ? '已置顶' : '置顶'}</button><button type="button" onClick={() => openEdit(memory)}>编辑</button><button type="button" className="memory-delete" onClick={() => removeMemory(memory.id)}>删除</button></div></div>
      <h2>{memory.title}</h2>
      <p>{memory.content}</p>
      <footer><span>{memory.source}</span><time>更新于 {memory.updatedAt}</time></footer>
    </article>)}</div>
    {!visibleMemories.length && <div className="memory-empty"><strong>没有匹配的记忆</strong><span>试试调整筛选条件，或添加一条新的重要记忆。</span></div>}
    <p className="memory-note">第一版仅保存在当前浏览器，不会自动从会话中提取内容。</p>

    <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? '编辑记忆' : '添加记忆'} size="sm" panelClassName="memory-modal" contentClassName="memory-modal-content">
      <form className="memory-form" onSubmit={saveMemory}>
        <p>只记录对后续会话有帮助且可以长期保留的信息。</p>
        <label>标题<input autoFocus required value={draft.title} maxLength={50} onChange={(event) => setDraft({ ...draft, title: event.target.value })} placeholder="例如：默认以简洁要点展示结论" /></label>
        <label>分类<select value={draft.scope} onChange={(event) => setDraft({ ...draft, scope: event.target.value as MemoryScope })}>{(['偏好', '项目', '研究'] as const).map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>记忆内容<textarea required rows={4} value={draft.content} maxLength={240} onChange={(event) => setDraft({ ...draft, content: event.target.value })} placeholder="描述需要在以后对话中延续的背景、偏好或结论" /></label>
        <div className="memory-form-actions"><button type="button" onClick={() => setModalOpen(false)}>取消</button><button className="primary" type="submit">保存记忆</button></div>
      </form>
    </Modal>
  </section>
}
