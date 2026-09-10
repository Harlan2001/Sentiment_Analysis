import { FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Conversation, Message, createConversation, getConversation, sendMessage, sendVisitorMessage } from '@/api/chat'
import { getChatSkills, Skill } from '@/api/skills'
import { uuid } from '@/utils/helpers'
import { WatchlistAction } from '@/features/market/components/WatchlistAction'
import { useAuth } from '@/contexts/AuthContext'
import './chat-skills.css'

type ChatMessage = Message & { id: string }

function timeLabel(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
}

function refreshSidebar() {
  window.dispatchEvent(new Event('bondsense-sidebar-refresh'))
}

function FactorLink({ href, children }: { href?: string; children: ReactNode }) {
  const match = href?.match(/^\/factor\/(\d+)$/)
  const title = typeof children === 'string' ? children : '该因子'
  if (!match || !href) return <Link to={href || '/factors'}>{children}</Link>
  return <span className="flex w-full items-center justify-between gap-2"><Link to={href} className="min-w-0 truncate">{children}</Link><WatchlistAction objectType="factor" objectId={match[1]} title={title} sourceUrl={href} className="shrink-0" /></span>
}

const markdownComponents: Components = {
  a({ href, children }) {
    if (href?.startsWith('/factor/')) return <FactorLink href={href}>{children}</FactorLink>
    if (href && href.startsWith('/')) return <Link to={href}>{children}</Link>
    if (href) return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
    return <>{children}</>
  },
  table({ children, ...props }) {
    return <div className="message-table-scroll"><table {...props}>{children}</table></div>
  },
}

function AuthenticatedChatPage() {
  const { username } = useAuth()
  const navigate = useNavigate()
  const { conversationId = 'new' } = useParams()
  const [searchParams] = useSearchParams()
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [availableSkills, setAvailableSkills] = useState<Skill[]>([])
  const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([])
  const [usedSkillNames, setUsedSkillNames] = useState<Record<string, string[]>>({})
  const [skillPickerOpen, setSkillPickerOpen] = useState(false)
  const [skillSourceFilter, setSkillSourceFilter] = useState<'all' | 'system' | 'mine'>('all')
  const [skillError, setSkillError] = useState('')
  const [skillLoadError, setSkillLoadError] = useState('')
  const [isReplying, setIsReplying] = useState(false)
  const [error, setError] = useState('')
  const creationStarted = useRef(false)
  const submittedDraft = useRef('')
  const formRef = useRef<HTMLFormElement>(null)
  const activeConversationId = useRef<string | null>(null)

  function loadChatSkillOptions() {
    getChatSkills()
      .then(({ items }) => { setAvailableSkills(items); setSkillLoadError('') })
      .catch((requestError: Error) => { setAvailableSkills([]); setSkillLoadError(requestError.message || 'Skills 加载失败') })
  }

  useEffect(() => {
    loadChatSkillOptions()
  }, [])

  useEffect(() => {
    if (conversationId !== 'new') {
      creationStarted.current = false
      return
    }
    if (creationStarted.current) return
    creationStarted.current = true
    const projectId = searchParams.get('project') || undefined
    createConversation({ project_id: projectId, source: projectId ? 'project' : 'home' })
      .then((created) => {
        refreshSidebar()
        const draftValue = searchParams.get('draft')
        const suffix = draftValue ? `?draft=${encodeURIComponent(draftValue)}` : ''
        navigate(`/chat/${created.id}${suffix}`, { replace: true })
      })
      .catch((requestError: Error) => setError(requestError.message))
  }, [conversationId, navigate, searchParams])

  useEffect(() => {
    setError('')
    setConversation(null)
    setMessages([])
    setDraft('')
    setUsedSkillNames({})
    setSkillPickerOpen(false)
    setIsReplying(false)
    activeConversationId.current = conversationId === 'new' ? null : conversationId

    if (conversationId === 'new') {
      window.dispatchEvent(new CustomEvent('bondsense-conversation-topic-change', { detail: { title: '新建对话' } }))
      return
    }

    let cancelled = false
    getConversation(conversationId)
      .then((data) => {
        if (cancelled) return
        setConversation(data.conversation)
        setMessages(data.messages)
        window.dispatchEvent(new CustomEvent('bondsense-conversation-topic-change', { detail: data.conversation }))
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message)
      })
    return () => {
      cancelled = true
    }
  }, [conversationId])

  useEffect(() => {
    const question = searchParams.get('draft')?.trim()
    const key = `${conversationId}:${question}`
    if (!question || !conversation || submittedDraft.current === key) return
    submittedDraft.current = key
    navigate(`/chat/${conversationId}`, { replace: true })
    void submitMessage(question)
  }, [conversation, conversationId, navigate, searchParams])

  const selectedSkills = useMemo(() => availableSkills.filter(skill => selectedSkillIds.includes(skill.id)), [availableSkills, selectedSkillIds])
  const visibleSkills = useMemo(() => availableSkills.filter(skill => (
    skillSourceFilter === 'all' || (skillSourceFilter === 'system' ? skill.owner_type === 'system' : skill.owner_type === 'user')
  )), [availableSkills, skillSourceFilter])
  const isReadOnlyProjectConversation = Boolean(
    conversation?.project_id && username && conversation.owner_username !== username
  )

  function toggleSkill(skillId: string) {
    setSelectedSkillIds(current => {
      if (current.includes(skillId)) {
        setSkillError('')
        return current.filter(id => id !== skillId)
      }
      const candidate = availableSkills.find(skill => skill.id === skillId)
      const selectedFormats = new Set(availableSkills.filter(skill => current.includes(skill.id)).map(skill => skill.output_format))
      if (candidate && selectedFormats.size && !selectedFormats.has(candidate.output_format)) {
        setSkillError('Markdown 与纯文本 Skill 不能在同一条消息中混用。')
        return current
      }
      if (current.length >= 3) {
        setSkillError('单条消息最多选择 3 个 Skill。')
        return current
      }
      const instructionChars = availableSkills
        .filter(skill => current.includes(skill.id) || skill.id === skillId)
        .reduce((total, skill) => total + skill.instructions.length, 0)
      if (instructionChars > 8000) {
        setSkillError('所选 Skill 的分析指令合计不能超过 8000 个字符。')
        return current
      }
      setSkillError('')
      return [...current, skillId]
    })
  }

  async function submitMessage(content: string, skillIds = selectedSkillIds) {
    if (!conversation || isReplying || isReadOnlyProjectConversation) return
    const targetConversationId = conversation.id
    const isCurrentConversation = () => activeConversationId.current === targetConversationId
    setError('')
    setIsReplying(true)
    const clientMessageId = uuid()
    const selectedNames = availableSkills.filter(skill => skillIds.includes(skill.id)).map(skill => skill.name)
    try {
      await sendMessage(conversation.id, content, clientMessageId, (streamEvent) => {
        if (!isCurrentConversation()) return
        if (streamEvent.event === 'message.accepted') {
          setMessages((current) => current.some((message) => message.id === streamEvent.data.message.id) ? current : [...current, streamEvent.data.message])
        }
        if (streamEvent.event === 'assistant.started') {
          if (selectedNames.length) setUsedSkillNames(current => ({ ...current, [streamEvent.data.message_id]: selectedNames }))
          setMessages((current) => [...current, { id: streamEvent.data.message_id, role: 'assistant', content: '', status: 'pending', created_at: new Date().toISOString() }])
        }
        if (streamEvent.event === 'assistant.delta') {
          setMessages((current) => current.map((message) => message.id === streamEvent.data.message_id ? { ...message, content: message.content + streamEvent.data.delta } : message))
        }
        if (streamEvent.event === 'assistant.completed' || streamEvent.event === 'assistant.failed') {
          setMessages((current) => current.map((message) => message.id === streamEvent.data.message.id ? streamEvent.data.message : message))
        }
      }, skillIds)
      const refreshed = await getConversation(conversation.id)
      if (!isCurrentConversation()) return
      setConversation(refreshed.conversation)
      setMessages(refreshed.messages)
      window.dispatchEvent(new CustomEvent('bondsense-conversation-topic-change', { detail: refreshed.conversation }))
      refreshSidebar()
    } catch (requestError) {
      if (!isCurrentConversation()) return
      setError(requestError instanceof Error ? requestError.message : '发送消息失败')
    } finally {
      if (isCurrentConversation()) setIsReplying(false)
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const content = draft.trim()
    if (!content) return
    setDraft('')
    setSkillPickerOpen(false)
    void submitMessage(content)
  }

  if (conversationId === 'new') return <section className="chat-page chat-loading"><span>{error || '正在创建新会话…'}</span></section>
  if (error && !conversation) return <section className="chat-page chat-loading"><span>无法打开会话：{error}</span></section>

  const hasMessages = messages.length > 0 || isReplying
  const skillNamesForMessage = (message: ChatMessage) => message.skill_names?.length ? message.skill_names : usedSkillNames[message.id] ?? []
  return <section className={'chat-page ' + (hasMessages ? 'has-messages' : 'empty-state')}>
    {!hasMessages && <div className="empty-chat-intro"><span>BondSense</span><h1>我们要一起做些什么？</h1></div>}
    <div className="chat-messages" aria-live="polite">
      {messages.map((message) => <article className={'chat-message ' + message.role} key={message.id}>
        <span className="message-avatar">{message.role === 'assistant' ? 'B' : '你'}</span>
        <div className="message-body"><div className="message-meta"><strong>{message.role === 'assistant' ? 'BondSense' : '你'}</strong><time>{timeLabel(message.created_at)}</time></div><div className="message-bubble"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{message.content || (message.status === 'pending' ? '正在整理债券市场信号…' : '')}</ReactMarkdown></div>{skillNamesForMessage(message).length ? <div className="message-skill-usage">本次使用：{skillNamesForMessage(message).join('、')}</div> : null}{message.status === 'failed' && <small>回复未完成：{message.error_code || '服务暂时不可用'}</small>}</div>
      </article>)}
    </div>
    {error && <p className="chat-error">{error}</p>}
    {isReadOnlyProjectConversation && <p className="chat-error">这是其他成员的项目会话，管理者仅可查看，不能继续发送或修改。</p>}
    {!isReadOnlyProjectConversation && <form className="chat-composer" onSubmit={submit} ref={formRef}>
      {selectedSkills.length > 0 && <div className="chat-selected-skills">{selectedSkills.map(skill => <button key={skill.id} type="button" onClick={() => toggleSkill(skill.id)}>{skill.name}<span>×</span></button>)}</div>}
      <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); formRef.current?.requestSubmit() } }} placeholder="输入你的债券分析问题…" rows={2} />
      <div className="chat-composer-actions"><span className="composer-status">BondSense · Agent 对话</span><div className="chat-skill-control"><button type="button" className="chat-skill-trigger" onClick={() => setSkillPickerOpen(open => { if (!open) setSkillSourceFilter('all'); return !open })} aria-expanded={skillPickerOpen}>Skills{selectedSkills.length ? ` · ${selectedSkills.length}` : ''}</button></div><button type="submit" disabled={!draft.trim() || isReplying} aria-label="发送消息">→</button></div>
    </form>}
    {skillPickerOpen && createPortal(<div className="chat-skill-modal-layer">
      <button type="button" className="chat-skill-modal-backdrop" aria-label="关闭 Skills 选择器" onClick={() => setSkillPickerOpen(false)} />
      <aside className="chat-skill-picker" role="dialog" aria-label="选择本次对话使用的 Skills">
        <header><strong>选择本次对话使用的 Skills</strong><button type="button" className="chat-skill-close" aria-label="关闭 Skills" onClick={() => setSkillPickerOpen(false)}>×</button></header>
        <small>仅显示当前账号已启用的系统 Skill 和个人 Skill，最多选择 3 个，指令合计不超过 8000 字符。</small>
        <nav className="chat-skill-source-filter" aria-label="Skill 来源筛选">{([['all', '全部'], ['system', '系统 Skill'], ['mine', '我的 Skill']] as const).map(([key, label]) => <button key={key} type="button" className={skillSourceFilter === key ? 'active' : ''} aria-pressed={skillSourceFilter === key} onClick={() => setSkillSourceFilter(key)}>{label}</button>)}</nav>
        {skillLoadError && <p className="chat-error">{skillLoadError}<button type="button" onClick={loadChatSkillOptions}>重试</button></p>}
        {skillError && <p className="chat-error">{skillError}</p>}
        {visibleSkills.length ? <div className="chat-skill-list">{visibleSkills.map(skill => <label key={skill.id}><input type="checkbox" checked={selectedSkillIds.includes(skill.id)} onChange={() => toggleSkill(skill.id)} disabled={!selectedSkillIds.includes(skill.id) && selectedSkillIds.length >= 3} /><span><b>{skill.name}</b><em>{skill.owner_type === 'system' ? '系统 Skill' : '个人 Skill'} · {skill.description}</em></span></label>)}</div> : !skillLoadError && <p>{availableSkills.length ? '当前来源下没有可用 Skill。' : '还没有可用 Skill。请先启用系统 Skill，或新建并启用个人 Skill。'}</p>}
      </aside>
    </div>, document.body)}
  </section>
}

type VisitorMessage = { id: string; role: 'user' | 'assistant'; content: string; created_at: string }

function VisitorChatPage() {
  const [searchParams] = useSearchParams()
  const [draft, setDraft] = useState('')
  const [messages, setMessages] = useState<VisitorMessage[]>([])
  const [isReplying, setIsReplying] = useState(false)
  const [error, setError] = useState('')
  const initialSubmitted = useRef(false)

  useEffect(() => {
    const initialQuestion = searchParams.get('draft')?.trim()
    if (!initialQuestion || initialSubmitted.current) return
    initialSubmitted.current = true
    void submitMessage(initialQuestion)
  }, [searchParams])

  async function submitMessage(content: string) {
    if (isReplying) return
    const now = new Date().toISOString()
    const assistantId = uuid()
    const history = messages.map(({ role, content: messageContent }) => ({ role, content: messageContent }))
    setMessages(current => [...current,
      { id: uuid(), role: 'user', content, created_at: now },
      { id: assistantId, role: 'assistant', content: '', created_at: now },
    ])
    setError('')
    setIsReplying(true)
    try {
      await sendVisitorMessage(content, history, delta => {
        setMessages(current => current.map(message => message.id === assistantId ? { ...message, content: message.content + delta } : message))
      })
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '发送消息失败')
      setMessages(current => current.filter(message => message.id !== assistantId))
    } finally {
      setIsReplying(false)
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const content = draft.trim()
    if (!content || isReplying) return
    setDraft('')
    void submitMessage(content)
  }

  const hasMessages = messages.length > 0
  return <section className={'chat-page ' + (hasMessages ? 'has-messages' : 'empty-state')}>
    {!hasMessages && <div className="empty-chat-intro"><span>BondSense</span><h1>我们要一起做些什么？</h1></div>}
    <div className="chat-messages" aria-live="polite">{messages.map(message => <article className={'chat-message ' + message.role} key={message.id}><span className="message-avatar">{message.role === 'assistant' ? 'B' : '你'}</span><div className="message-body"><div className="message-meta"><strong>{message.role === 'assistant' ? 'BondSense' : '你'}</strong><time>{timeLabel(message.created_at)}</time></div><div className="message-bubble">{message.content}</div></div></article>)}</div>
    {error && <p className="chat-error">{error}</p>}
    <form className="chat-composer" onSubmit={submit}><textarea value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} placeholder="输入你的债券分析问题…" rows={2} /><div className="chat-composer-actions"><span className="composer-status">BondSense · Agent 对话 · 访客会话不会保存到历史记录</span><button type="submit" disabled={!draft.trim() || isReplying} aria-label="发送消息">↑</button></div></form>
  </section>
}

export function ChatPage() {
  const { authEnabled, isAuthenticated } = useAuth()
  return authEnabled && !isAuthenticated ? <VisitorChatPage /> : <AuthenticatedChatPage />
}
