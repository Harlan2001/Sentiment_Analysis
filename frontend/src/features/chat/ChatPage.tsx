import { FormEvent, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Conversation, Message, createConversation, getConversation, sendMessage } from '@/api/workbench'

type ChatMessage = Message & { id: string }

function timeLabel(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
}

function refreshSidebar() {
  window.dispatchEvent(new Event('bondsense-sidebar-refresh'))
}

export function ChatPage() {
  const navigate = useNavigate()
  const { conversationId = 'new' } = useParams()
  const [searchParams] = useSearchParams()
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [isReplying, setIsReplying] = useState(false)
  const [error, setError] = useState('')
  const creationStarted = useRef(false)
  const submittedDraft = useRef('')
  const formRef = useRef<HTMLFormElement>(null)

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

  async function submitMessage(content: string) {
    if (!conversation || isReplying) return
    setError('')
    setIsReplying(true)
    const clientMessageId = crypto.randomUUID()
    try {
      await sendMessage(conversation.id, content, clientMessageId, (streamEvent) => {
        if (streamEvent.event === 'message.accepted') {
          setMessages((current) => current.some((message) => message.id === streamEvent.data.message.id) ? current : [...current, streamEvent.data.message])
        }
        if (streamEvent.event === 'assistant.started') {
          setMessages((current) => [...current, { id: streamEvent.data.message_id, role: 'assistant', content: '', status: 'pending', created_at: new Date().toISOString() }])
        }
        if (streamEvent.event === 'assistant.delta') {
          setMessages((current) => current.map((message) => message.id === streamEvent.data.message_id ? { ...message, content: message.content + streamEvent.data.delta } : message))
        }
        if (streamEvent.event === 'assistant.completed' || streamEvent.event === 'assistant.failed') {
          setMessages((current) => current.map((message) => message.id === streamEvent.data.message.id ? streamEvent.data.message : message))
        }
      })
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
    void submitMessage(content)
  }

  if (conversationId === 'new') return <section className="chat-page chat-loading"><span>{error || '正在创建新会话…'}</span></section>
  if (error && !conversation) return <section className="chat-page chat-loading"><span>无法打开会话：{error}</span></section>

  const hasMessages = messages.length > 0 || isReplying
  return <section className={'chat-page ' + (hasMessages ? 'has-messages' : 'empty-state')}>
    {!hasMessages && <div className="empty-chat-intro"><span>BondSense</span><h1>我们要一起做些什么？</h1></div>}
    <div className="chat-messages" aria-live="polite">
      {messages.map((message) => <article className={'chat-message ' + message.role} key={message.id}>
        <span className="message-avatar">{message.role === 'assistant' ? 'B' : '你'}</span>
        <div className="message-body"><div className="message-meta"><strong>{message.role === 'assistant' ? 'BondSense' : '你'}</strong><time>{timeLabel(message.created_at)}</time></div><div className="message-bubble"><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || (message.status === 'pending' ? '正在整理债券市场信号…' : '')}</ReactMarkdown></div>{message.status === 'failed' && <small>回复未完成：{message.error_code || '服务暂时不可用'}</small>}</div>
      </article>)}
    </div>
    {error && <p className="chat-error">{error}</p>}
    <form className="chat-composer" onSubmit={submit} ref={formRef}>
      <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); formRef.current?.requestSubmit() } }} placeholder="输入你的债券分析问题…" rows={2} />
      <div className="chat-composer-actions"><span className="composer-status">BondSense · Agent 对话</span><button type="submit" disabled={!draft.trim() || isReplying} aria-label="发送消息">→</button></div>
    </form>
  </section>
}
