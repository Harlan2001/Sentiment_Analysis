import { FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Conversation, Message, createConversation, getConversation, sendMessage } from '@/api/workbench'
import { getSkills, Skill } from '@/api/skills'
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
}

function AuthenticatedChatPage() {
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
  const [isReplying, setIsReplying] = useState(false)
  const [error, setError] = useState('')
  const creationStarted = useRef(false)
  const submittedDraft = useRef('')
  const formRef = useRef<HTMLFormElement>(null)

  useEffect(() => {
    getSkills('', 'mine')
      .then(({ items }) => setAvailableSkills(items.filter(skill => skill.status === 'published')))
      .catch(() => setAvailableSkills([]))
  }, [])

  useEffect(() => {
    if (conversationId !== 'new' || creationStarted.current) return
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
    if (conversationId === 'new') return
    setError('')
    setConversation(null)
    setUsedSkillNames({})
    getConversation(conversationId)
      .then((data) => {
        setConversation(data.conversation)
        setMessages(data.messages)
        window.dispatchEvent(new CustomEvent('bondsense-conversation-topic-change', { detail: data.conversation }))
      })
      .catch((requestError: Error) => setError(requestError.message))
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

  function toggleSkill(skillId: string) {
    setSelectedSkillIds(current => current.includes(skillId) ? current.filter(id => id !== skillId) : [...current, skillId].slice(0, 5))
  }

  async function submitMessage(content: string, skillIds = selectedSkillIds) {
    if (!conversation || isReplying) return
    setError('')
    setIsReplying(true)
    const clientMessageId = uuid()
    const selectedNames = availableSkills.filter(skill => skillIds.includes(skill.id)).map(skill => skill.name)
    try {
      await sendMessage(conversation.id, content, clientMessageId, (streamEvent) => {
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
      setConversation(refreshed.conversation)
      setMessages(refreshed.messages)
      window.dispatchEvent(new CustomEvent('bondsense-conversation-topic-change', { detail: refreshed.conversation }))
      refreshSidebar()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '发送消息失败')
    } finally {
      setIsReplying(false)
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
    <form className="chat-composer" onSubmit={submit} ref={formRef}>
      {selectedSkills.length > 0 && <div className="chat-selected-skills">{selectedSkills.map(skill => <button key={skill.id} type="button" onClick={() => toggleSkill(skill.id)}>{skill.name}<span>×</span></button>)}</div>}
      <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); formRef.current?.requestSubmit() } }} placeholder="输入你的债券分析问题…" rows={2} />
      <div className="chat-composer-actions"><span className="composer-status">BondSense · Agent 对话</span><div className="chat-skill-control"><button type="button" className="chat-skill-trigger" onClick={() => setSkillPickerOpen(open => !open)} aria-expanded={skillPickerOpen}>Skills{selectedSkills.length ? ` · ${selectedSkills.length}` : ''}</button>{skillPickerOpen && <div className="chat-skill-picker"><strong>选择本次对话使用的 Skills</strong><small>仅显示已添加到“我的 Skills”的已发布能力，最多选择 5 个。</small>{availableSkills.length ? <div>{availableSkills.map(skill => <label key={skill.id}><input type="checkbox" checked={selectedSkillIds.includes(skill.id)} onChange={() => toggleSkill(skill.id)} disabled={!selectedSkillIds.includes(skill.id) && selectedSkillIds.length >= 5} /><span><b>{skill.name}</b><em>{skill.description}</em></span></label>)}</div> : <p>还没有可用 Skill。请先在系统 Skills 中添加，或新建自己的 Skill。</p>}</div>}</div><button type="submit" disabled={!draft.trim() || isReplying} aria-label="发送消息">→</button></div>
    </form>
  </section>
}

type VisitorMessage = { id: string; role: 'user' | 'assistant'; content: string; created_at: string }

function VisitorChatPage() {
  const [searchParams] = useSearchParams()
  const [draft, setDraft] = useState('')
  const [messages, setMessages] = useState<VisitorMessage[]>(() => {
    const initialQuestion = searchParams.get('draft')?.trim()
    if (!initialQuestion) return []
    const now = new Date().toISOString()
    return [{ id: uuid(), role: 'user', content: initialQuestion, created_at: now }, { id: uuid(), role: 'assistant', content: '这是访客临时会话，用于体验基础问答。登录后可保存会话、使用个人上下文，并在项目中继续讨论。', created_at: now }]
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const content = draft.trim()
    if (!content) return
    const now = new Date().toISOString()
    setMessages(current => [...current, { id: uuid(), role: 'user', content, created_at: now }, { id: uuid(), role: 'assistant', content: '已收到你的问题。当前为访客临时会话，不会保存到历史记录；登录后可获得完整的会话与个人数据能力。', created_at: now }])
    setDraft('')
  }

  const hasMessages = messages.length > 0
  return <section className={'chat-page ' + (hasMessages ? 'has-messages' : 'empty-state')}>
    {!hasMessages && <div className="empty-chat-intro"><span>BondSense</span><h1>我们要一起做些什么？</h1></div>}
    <div className="chat-messages" aria-live="polite">{messages.map(message => <article className={'chat-message ' + message.role} key={message.id}><span className="message-avatar">{message.role === 'assistant' ? 'B' : '你'}</span><div className="message-body"><div className="message-meta"><strong>{message.role === 'assistant' ? 'BondSense' : '你'}</strong><time>{timeLabel(message.created_at)}</time></div><div className="message-bubble">{message.content}</div></div></article>)}</div>
    <form className="chat-composer" onSubmit={submit}><textarea value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} placeholder="输入你的债券分析问题…" rows={2} /><div className="chat-composer-actions"><span className="composer-status">BondSense · Agent 对话 · 访客会话不会保存到历史记录</span><button type="submit" disabled={!draft.trim()} aria-label="发送消息">↑</button></div></form>
  </section>
}

export function ChatPage() {
  const { authEnabled, isAuthenticated } = useAuth()
  return authEnabled && !isAuthenticated ? <VisitorChatPage /> : <AuthenticatedChatPage />
}
