import { FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Conversation, Message, attachChatLibraryFile, createConversation, getConversation, sendMessage, sendVisitorMessage, uploadChatAttachment } from '@/api/chat'
import { fetchFileLibrary, type FileLibraryItem, type FileLibraryResponse } from '@/api/fileLibrary'
import { getChatSkills, Skill } from '@/api/skills'
import { uuid } from '@/utils/helpers'
import { WatchlistAction } from '@/features/market/components/WatchlistAction'
import { useAuth } from '@/contexts/AuthContext'
import './chat-skills.css'

type ChatMessage = Message & { id: string }

function timeLabel(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
}

function fileSizeLabel(size: number) {
  return size < 1024 * 1024 ? `${Math.ceil(size / 1024)} KB` : `${(size / 1024 / 1024).toFixed(2)} MB`
}

function libraryMountName(item: FileLibraryItem) {
  return item.source_key === 'policy_document' ? `${item.name.replace(/\.[^.]+$/, '')}.txt` : item.name
}

function splitThinkContent(raw: string): { thinking: string; answer: string } {
  if (!raw.includes('<think>')) return { thinking: '', answer: raw }
  const thinkParts: string[] = []
  let answer = raw.replace(/<think>([\s\S]*?)<\/think>/g, (_match, inner: string) => {
    if (inner.trim()) thinkParts.push(inner.trim())
    return ''
  })
  const openIndex = answer.indexOf('<think>')
  if (openIndex !== -1) {
    const partial = answer.slice(openIndex + 7).trim()
    if (partial) thinkParts.push(partial)
    answer = answer.slice(0, openIndex)
  }
  return { thinking: thinkParts.join('\n\n'), answer: answer.trimStart() }
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
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [pendingLibraryFiles, setPendingLibraryFiles] = useState<FileLibraryItem[]>([])
  const [isDraggingFile, setIsDraggingFile] = useState(false)
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false)
  const [libraryPage, setLibraryPage] = useState(1)
  const [libraryData, setLibraryData] = useState<FileLibraryResponse | null>(null)
  const [libraryLoading, setLibraryLoading] = useState(false)
  const [libraryError, setLibraryError] = useState('')
  const [availableSkills, setAvailableSkills] = useState<Skill[]>([])
  const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([])
  const [usedSkillNames, setUsedSkillNames] = useState<Record<string, string[]>>({})
  const [thinkingByMessage, setThinkingByMessage] = useState<Record<string, string>>({})
  const [thinkingExpanded, setThinkingExpanded] = useState<Record<string, boolean>>({})
  const [skillPickerOpen, setSkillPickerOpen] = useState(false)
  const [skillSourceFilter, setSkillSourceFilter] = useState<'all' | 'system' | 'mine'>('all')
  const [skillError, setSkillError] = useState('')
  const [skillLoadError, setSkillLoadError] = useState('')
  const [isReplying, setIsReplying] = useState(false)
  const [isUploadingFile, setIsUploadingFile] = useState(false)
  const [error, setError] = useState('')
  const [memoryNotice, setMemoryNotice] = useState('')
  const creationStarted = useRef(false)
  const submittedDraft = useRef('')
  const formRef = useRef<HTMLFormElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const uploadedFilesRef = useRef(new Map<File, { conversationId: string; id: string }>())
  const importedFilesRef = useRef(new Map<string, { conversationId: string; id: string }>())
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
    if (!libraryPickerOpen) return
    let active = true
    setLibraryLoading(true)
    fetchFileLibrary({ purpose: 'chat_attachment', page: libraryPage, page_size: 50 })
      .then(data => { if (active) { setLibraryData(data); setLibraryError('') } })
      .catch((reason: Error) => { if (active) { setLibraryData(null); setLibraryError(reason.message || '读取文件库失败') } })
      .finally(() => { if (active) setLibraryLoading(false) })
    return () => { active = false }
  }, [libraryPickerOpen, libraryPage])

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
    setMemoryNotice('')
    setConversation(null)
    setMessages([])
    setDraft('')
    setPendingFiles([])
    setPendingLibraryFiles([])
    uploadedFilesRef.current.clear()
    importedFilesRef.current.clear()
    setUsedSkillNames({})
    setThinkingByMessage({})
    setThinkingExpanded({})
    setSkillPickerOpen(false)
    setLibraryPickerOpen(false)
    setIsReplying(false)
    setIsUploadingFile(false)
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

  async function submitMessage(content: string, skillIds = selectedSkillIds, files = pendingFiles, libraryItems = pendingLibraryFiles) {
    if (!conversation || isReplying || isReadOnlyProjectConversation) return
    const targetConversationId = conversation.id
    const isCurrentConversation = () => activeConversationId.current === targetConversationId
    setError('')
    setDraft('')
    setIsReplying(true)
    setIsUploadingFile(files.length + libraryItems.length > 0)
    const clientMessageId = uuid()
    const selectedNames = availableSkills.filter(skill => skillIds.includes(skill.id)).map(skill => skill.name)
    let messageAccepted = false
    try {
      const attachmentIds: string[] = []
      for (const file of files) {
        const cached = uploadedFilesRef.current.get(file)
        const id = cached?.conversationId === conversation.id
          ? cached.id
          : (await uploadChatAttachment(conversation.id, file)).id
        uploadedFilesRef.current.set(file, { conversationId: conversation.id, id })
        attachmentIds.push(id)
      }
      for (const item of libraryItems) {
        const cached = importedFilesRef.current.get(item.id)
        const id = cached?.conversationId === conversation.id
          ? cached.id
          : (await attachChatLibraryFile(conversation.id, item.source_key, item.source_ref)).id
        importedFilesRef.current.set(item.id, { conversationId: conversation.id, id })
        attachmentIds.push(id)
      }
      if (isCurrentConversation()) setIsUploadingFile(false)
      const onEvent: Parameters<typeof sendMessage>[3] = (streamEvent) => {
        if (!isCurrentConversation()) return
        if (streamEvent.event === 'message.accepted') {
          messageAccepted = true
          setPendingFiles(current => current.filter(file => !files.includes(file)))
          setPendingLibraryFiles(current => current.filter(item => !libraryItems.some(selected => selected.id === item.id)))
          files.forEach(file => uploadedFilesRef.current.delete(file))
          libraryItems.forEach(item => importedFilesRef.current.delete(item.id))
          if (fileInputRef.current) fileInputRef.current.value = ''
          setMessages((current) => current.some((message) => message.id === streamEvent.data.message.id) ? current : [...current, streamEvent.data.message])
        }
        if (streamEvent.event === 'assistant.started') {
          if (selectedNames.length) setUsedSkillNames(current => ({ ...current, [streamEvent.data.message_id]: selectedNames }))
          setMessages((current) => [...current, { id: streamEvent.data.message_id, role: 'assistant', content: '', status: 'pending', created_at: new Date().toISOString() }])
        }
        if (streamEvent.event === 'assistant.thinking') {
          const { message_id: messageId, kind, delta, tool_name: toolName, duration_ms: durationMs } = streamEvent.data
          const chunk = kind === 'reasoning'
            ? (delta || '')
            : kind === 'tool_start'
              ? `\n- 正在调用工具：\`${toolName}\`\n`
              : `- 已完成：\`${toolName}\`${durationMs != null ? ` (${durationMs}ms)` : ''}\n`
          if (chunk) {
            setThinkingByMessage((current) => ({ ...current, [messageId]: (current[messageId] || '') + chunk }))
          }
        }
        if (streamEvent.event === 'assistant.delta') {
          setMessages((current) => current.map((message) => message.id === streamEvent.data.message_id ? { ...message, content: message.content + streamEvent.data.delta } : message))
        }
        if (streamEvent.event === 'assistant.completed' || streamEvent.event === 'assistant.failed') {
          setMessages((current) => current.map((message) => message.id === streamEvent.data.message.id ? streamEvent.data.message : message))
        }
        if (streamEvent.event === 'memory.saved') setMemoryNotice(`已记住：${streamEvent.data.memory.title}`)
        if (streamEvent.event === 'memory.candidate') setMemoryNotice(`发现一条待确认的个人记忆：${streamEvent.data.memory.title}`)
        if (streamEvent.event === 'memory.removed') setMemoryNotice(streamEvent.data.deleted ? `已忘记与“${streamEvent.data.query}”相关的个人记忆` : '没有找到匹配的个人记忆')
      }
      if (attachmentIds.length) {
        await sendMessage(conversation.id, content, clientMessageId, onEvent, skillIds, attachmentIds)
      } else {
        await sendMessage(conversation.id, content, clientMessageId, onEvent, skillIds)
      }
      const refreshed = await getConversation(conversation.id)
      if (!isCurrentConversation()) return
      setConversation(refreshed.conversation)
      setMessages(refreshed.messages)
      setPendingFiles(current => current.filter(file => !files.includes(file)))
      setPendingLibraryFiles(current => current.filter(item => !libraryItems.some(selected => selected.id === item.id)))
      files.forEach(file => uploadedFilesRef.current.delete(file))
      libraryItems.forEach(item => importedFilesRef.current.delete(item.id))
      window.dispatchEvent(new CustomEvent('bondsense-conversation-topic-change', { detail: refreshed.conversation }))
      refreshSidebar()
    } catch (requestError) {
      if (!isCurrentConversation()) return
      if (!messageAccepted) setDraft(current => current || content)
      setError(requestError instanceof Error ? requestError.message : '发送消息失败')
    } finally {
      if (isCurrentConversation()) {
        setIsReplying(false)
        setIsUploadingFile(false)
      }
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const content = draft.trim()
    if (!content && !pendingFiles.length && !pendingLibraryFiles.length) return
    setSkillPickerOpen(false)
    setLibraryPickerOpen(false)
    void submitMessage(content)
  }

  function chooseFiles(files: File[]) {
    if (!files.length) return
    const allowed = /\.(pdf|docx|txt|md|csv)$/i
    if (files.some(file => !allowed.test(file.name) || file.size === 0 || file.size > 10 * 1024 * 1024)) {
      setError('仅支持非空且不超过 10 MB 的 PDF、DOCX、TXT、MD、CSV 文件。')
      return
    }
    const additions = files.filter(file => !pendingFiles.some(current => current.name === file.name && current.size === file.size && current.lastModified === file.lastModified))
    if (pendingFiles.length + pendingLibraryFiles.length + additions.length > 3) {
      setError('单条消息最多挂载 3 个文件。')
      return
    }
    setError('')
    setPendingFiles(current => [...current, ...additions])
  }

  function toggleLibraryFile(item: FileLibraryItem) {
    setPendingLibraryFiles(current => {
      if (current.some(selected => selected.id === item.id)) {
        setLibraryError('')
        return current.filter(selected => selected.id !== item.id)
      }
      if (current.length + pendingFiles.length >= 3) {
        setLibraryError('单条消息最多挂载 3 个文件。')
        return current
      }
      setLibraryError('')
      return [...current, item]
    })
  }

  if (conversationId === 'new') return <section className="chat-page chat-loading"><span>{error || '正在创建新会话…'}</span></section>
  if (error && !conversation) return <section className="chat-page chat-loading"><span>无法打开会话：{error}</span></section>

  const hasMessages = messages.length > 0 || isReplying
  const skillNamesForMessage = (message: ChatMessage) => message.skill_names?.length ? message.skill_names : usedSkillNames[message.id] ?? []
  return <section className={'chat-page ' + (hasMessages ? 'has-messages' : 'empty-state')}>
    {!hasMessages && <div className="empty-chat-intro"><span>BondSense</span><h1>我们要一起做些什么？</h1></div>}
    <div className="chat-messages" aria-live="polite">
      {messages.map((message) => {
        const parsed = message.role === 'assistant' ? splitThinkContent(message.content || '') : { thinking: '', answer: message.content }
        const streamThinking = thinkingByMessage[message.id] || message.thinking || ''
        const combinedThinking = [streamThinking.trim(), parsed.thinking.trim()].filter(Boolean).join('\n\n')
        const hasThinking = message.role === 'assistant' && (Boolean(combinedThinking) || message.status === 'pending')
        const isThinkingPhase = message.status === 'pending' && !parsed.answer
        const isExpanded = Boolean(thinkingExpanded[message.id])
        return <article className={'chat-message ' + message.role} key={message.id}>
          <span className="message-avatar">{message.role === 'assistant' ? 'B' : '你'}</span>
          <div className="message-body">
            <div className="message-meta"><strong>{message.role === 'assistant' ? 'BondSense' : '你'}</strong><time>{timeLabel(message.created_at)}</time></div>
            {hasThinking && <div className="message-thinking">
              <button type="button" className={'message-thinking-toggle' + (isThinkingPhase ? ' is-active' : '')} aria-expanded={isExpanded} onClick={() => setThinkingExpanded(current => ({ ...current, [message.id]: !isExpanded }))}>
                <span className="thinking-dot" aria-hidden="true" />
                <span>{isThinkingPhase ? '正在思考…' : '显示思路'}</span>
                <span className="thinking-caret" aria-hidden="true">{isExpanded ? '▴' : '▾'}</span>
              </button>
              {isExpanded && <div className="message-thinking-body">
                {combinedThinking ? <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{combinedThinking}</ReactMarkdown> : <p>正在分析问题并调用市场数据工具…</p>}
              </div>}
            </div>}
            {(parsed.answer || message.role === 'assistant') && <div className="message-bubble"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{parsed.answer || (message.status === 'pending' ? '' : '')}</ReactMarkdown></div>}
            {message.attachments?.map(attachment => <div className="chat-message-attachment" key={attachment.id}><span className="chat-file-kind">{attachment.original_filename.split('.').pop()?.toUpperCase()}</span><span className="chat-attachment-name" title={attachment.original_filename}>{attachment.original_filename}</span><span className="chat-attachment-meta">{attachment.page_count ? `${attachment.page_count} 页` : fileSizeLabel(attachment.size_bytes)}</span></div>)}
            {skillNamesForMessage(message).length ? <div className="message-skill-usage">本次使用：{skillNamesForMessage(message).join('、')}</div> : null}
            {message.status === 'failed' && <small>回复未完成：{message.error_code || '服务暂时不可用'}</small>}
          </div>
        </article>
      })}
    </div>
    {error && <p className="chat-error">{error}</p>}
    {memoryNotice && <p className="chat-memory-notice">{memoryNotice} <Link to="/custom/memory">查看记忆</Link><button type="button" aria-label="关闭记忆提示" onClick={() => setMemoryNotice('')}>×</button></p>}
    {isReadOnlyProjectConversation && <p className="chat-error">这是其他成员的项目会话，管理者仅可查看，不能继续发送或修改。</p>}
    {!isReadOnlyProjectConversation && <form className={'chat-composer' + (isDraggingFile ? ' is-dragging' : '')} onSubmit={submit} ref={formRef} onDragOver={event => { if (isReplying) return; event.preventDefault(); setIsDraggingFile(true) }} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setIsDraggingFile(false) }} onDrop={event => { event.preventDefault(); setIsDraggingFile(false); if (!isReplying) chooseFiles(Array.from(event.dataTransfer.files)) }}>
      {(selectedSkills.length > 0 || pendingFiles.length > 0 || pendingLibraryFiles.length > 0) && <div className="chat-composer-chips">
        {selectedSkills.map(skill => <button key={skill.id} className="chat-skill-chip" type="button" onClick={() => toggleSkill(skill.id)} aria-label={`移除 Skill ${skill.name}`} title={`移除 ${skill.name}`}><span className="chip-icon">✳</span><span className="chip-label">{skill.name}</span><span className="chip-remove">×</span></button>)}
        {pendingFiles.map(file => <div className="chat-file-chip" key={`${file.name}-${file.size}-${file.lastModified}`} title={file.name}><span className="chat-file-kind">{file.name.split('.').pop()?.toUpperCase()}</span><span className="chip-label">{file.name}</span><span className="chip-size">{isUploadingFile ? '解析中' : fileSizeLabel(file.size)}</span><button type="button" onClick={() => { setPendingFiles(current => current.filter(item => item !== file)); uploadedFilesRef.current.delete(file) }} disabled={isReplying} aria-label={`移除附件 ${file.name}`}>×</button></div>)}
        {pendingLibraryFiles.map(item => <div className="chat-file-chip" key={item.id} title={`${item.source} · ${item.name}`}><span className="chat-file-kind">{libraryMountName(item).split('.').pop()?.toUpperCase()}</span><span className="chip-label">{libraryMountName(item)}</span><span className="chip-size">文件库{isUploadingFile ? ' · 挂载中' : ''}</span><button type="button" onClick={() => { setPendingLibraryFiles(current => current.filter(selected => selected.id !== item.id)); importedFilesRef.current.delete(item.id) }} disabled={isReplying} aria-label={`移除附件 ${libraryMountName(item)}`}>×</button></div>)}
      </div>}
      <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); formRef.current?.requestSubmit() } }} placeholder="输入你的债券分析问题…" rows={2} />
      <div className="chat-composer-actions">
        <div className="chat-composer-toolbar">
          <button type="button" className="chat-skill-trigger" onClick={() => setSkillPickerOpen(open => { if (!open) setSkillSourceFilter('all'); return !open })} aria-expanded={skillPickerOpen} aria-label="Skills">✳ <span>Skills</span></button>
          <input ref={fileInputRef} type="file" accept=".pdf,.docx,.txt,.md,.csv" multiple className="chat-file-input" aria-label="选择文件附件" onChange={event => { chooseFiles(Array.from(event.target.files || [])); event.target.value = '' }} />
          <button type="button" className="chat-file-trigger" onClick={() => fileInputRef.current?.click()} disabled={isReplying || pendingFiles.length + pendingLibraryFiles.length >= 3} aria-label="添加文件附件" title="支持 PDF、DOCX、TXT、MD、CSV，最多 3 个">📎 <span>添加文件</span></button>
          <button type="button" className="chat-library-trigger" onClick={() => { setLibraryPage(1); setLibraryError(''); setLibraryPickerOpen(true); setSkillPickerOpen(false) }} disabled={isReplying || pendingFiles.length + pendingLibraryFiles.length >= 3} aria-label="从文件库添加">▤ <span>文件库</span></button>
        </div>
        <span className="composer-status">{isDraggingFile ? '松开以挂载文件' : isReplying ? '正在回复，可继续输入下一条消息' : 'BondSense · Agent 对话'}</span>
        <button type="submit" disabled={(!draft.trim() && !pendingFiles.length && !pendingLibraryFiles.length) || isReplying} aria-label="发送消息">→</button>
      </div>
    </form>}
    {skillPickerOpen && createPortal(<div className="chat-skill-modal-layer">
      <button type="button" className="chat-skill-modal-backdrop" aria-label="关闭 Skills 选择器" onClick={() => setSkillPickerOpen(false)} />
      <aside className="chat-skill-picker" role="dialog" aria-label="选择本次对话使用的 Skills">
        <header><strong>选择本次对话使用的 Skills</strong><button type="button" className="chat-skill-close" aria-label="关闭 Skills" onClick={() => setSkillPickerOpen(false)}>×</button></header>
        <small>仅显示当前账号已启用的系统 Skill 和个人 Skill，最多选择 3 个，指令合计不超过 8000 字符。</small>
        <nav className="chat-skill-source-filter" aria-label="Skill 来源筛选">{([['all', '全部'], ['system', '系统 Skill'], ['mine', '我的 Skill']] as const).map(([key, label]) => <button key={key} type="button" className={skillSourceFilter === key ? 'active' : ''} aria-pressed={skillSourceFilter === key} onClick={() => setSkillSourceFilter(key)}>{label}</button>)}</nav>
        {skillLoadError && <p className="chat-error">{skillLoadError}<button type="button" onClick={loadChatSkillOptions}>重试</button></p>}
        {skillError && <p className="chat-error">{skillError}</p>}
        {visibleSkills.length ? <div className="chat-skill-list">{visibleSkills.map(skill => <button type="button" key={skill.id} className={'chat-skill-option' + (selectedSkillIds.includes(skill.id) ? ' selected' : '')} aria-pressed={selectedSkillIds.includes(skill.id)} onClick={() => toggleSkill(skill.id)} disabled={!selectedSkillIds.includes(skill.id) && selectedSkillIds.length >= 3}><span className="chat-skill-option-icon">✳</span><span className="chat-skill-option-copy"><b>{skill.name}</b><em>{skill.owner_type === 'system' ? '系统 Skill' : '个人 Skill'} · {skill.description}</em></span></button>)}</div> : !skillLoadError && <p>{availableSkills.length ? '当前来源下没有可用 Skill。' : '还没有可用 Skill。请先启用系统 Skill，或新建并启用个人 Skill。'}</p>}
      </aside>
    </div>, document.body)}
    {libraryPickerOpen && createPortal(<div className="chat-skill-modal-layer">
      <button type="button" className="chat-skill-modal-backdrop" aria-label="关闭文件库选择器" onClick={() => setLibraryPickerOpen(false)} />
      <aside className="chat-skill-picker chat-library-picker" role="dialog" aria-label="从文件库选择附件">
        <header><strong>从文件库选择附件</strong><button type="button" className="chat-skill-close" aria-label="关闭文件库" onClick={() => setLibraryPickerOpen(false)}>×</button></header>
        <small>可选当前账号的 PDF、DOCX、TXT、MD、CSV；政策文件使用已解析文本。单条消息最多挂载 3 个文件。</small>
        {libraryError && <p className="chat-error" role="alert">{libraryError}</p>}
        {libraryLoading ? <p>正在读取文件库…</p> : libraryData?.items.length ? <div className="chat-skill-list chat-library-list">{libraryData.items.map(item => {
          const selected = pendingLibraryFiles.some(file => file.id === item.id)
          return <button type="button" key={item.id} className={'chat-skill-option chat-library-option' + (selected ? ' selected' : '')} aria-pressed={selected} onClick={() => toggleLibraryFile(item)} disabled={!selected && pendingFiles.length + pendingLibraryFiles.length >= 3}><span className="chat-file-kind">{libraryMountName(item).split('.').pop()?.toUpperCase()}</span><span className="chat-skill-option-copy"><b title={item.name}>{item.name}</b><em>{item.source}{item.source_key === 'policy_document' ? ' · 解析文本' : ''}{item.size_bytes ? ` · ${fileSizeLabel(item.size_bytes)}` : ''}</em></span></button>
        })}</div> : <p>文件库中没有可挂载的文件。可先在对话中上传，或在其他功能中添加文件。</p>}
        <footer className="chat-library-footer"><div><button type="button" onClick={() => setLibraryPage(page => Math.max(1, page - 1))} disabled={libraryLoading || libraryPage <= 1}>上一页</button><span>{libraryPage} / {Math.max(1, Math.ceil((libraryData?.total ?? 0) / 50))}</span><button type="button" onClick={() => setLibraryPage(page => page + 1)} disabled={libraryLoading || libraryPage >= Math.ceil((libraryData?.total ?? 0) / 50)}>下一页</button></div><button type="button" onClick={() => setLibraryPickerOpen(false)}>完成</button></footer>
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
