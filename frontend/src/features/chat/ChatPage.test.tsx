import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatPage } from './ChatPage'
import * as chat from '@/api/chat'
import * as fileLibrary from '@/api/fileLibrary'
import * as skillsApi from '@/api/skills'

const authState = vi.hoisted(() => ({ authEnabled: true, isAuthenticated: false, username: undefined as string | undefined }))
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => authState,
}))
vi.mock('@/api/chat', () => ({
  createConversation: vi.fn(), getConversation: vi.fn(), sendMessage: vi.fn(), uploadChatAttachment: vi.fn(), attachChatLibraryFile: vi.fn(),
  sendVisitorMessage: vi.fn(async (_content, _history, onDelta) => onDelta('真实 AI 回复')),
}))
vi.mock('@/api/skills', () => ({ getChatSkills: vi.fn() }))
vi.mock('@/api/fileLibrary', () => ({ fetchFileLibrary: vi.fn() }))
vi.mock('@/features/market/components/WatchlistAction', () => ({ WatchlistAction: () => null }))

function renderVisitorChat(initialEntry = '/chat') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes><Route path="/chat" element={<ChatPage />} /></Routes>
    </MemoryRouter>,
  )
}

describe('visitor chat', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    authState.isAuthenticated = false
    authState.username = undefined
  })

  it('uses the visitor AI endpoint without calling persistent conversation APIs', async () => {
    renderVisitorChat()
    fireEvent.change(screen.getByPlaceholderText('输入你的债券分析问题…'), {
      target: { value: '访客问题' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }))

    expect(screen.getByText('访客问题')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('真实 AI 回复')).toBeInTheDocument())
    expect(chat.sendVisitorMessage).toHaveBeenCalledOnce()
    expect(chat.createConversation).not.toHaveBeenCalled()
    expect(chat.getConversation).not.toHaveBeenCalled()
    expect(chat.sendMessage).not.toHaveBeenCalled()
  })

  it('drops visitor messages after unmount and starts with a fresh web session', async () => {
    const first = renderVisitorChat()
    fireEvent.change(screen.getByPlaceholderText('输入你的债券分析问题…'), {
      target: { value: '不会保留的消息' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }))
    expect(screen.getByText('不会保留的消息')).toBeInTheDocument()
    await waitFor(() => expect(chat.sendVisitorMessage).toHaveBeenCalled())
    first.unmount()

    renderVisitorChat()
    expect(screen.queryByText('不会保留的消息')).not.toBeInTheDocument()
    expect(screen.getByText('我们要一起做些什么？')).toBeInTheDocument()
  })

  it('loads enabled system Skills from the dedicated chat options endpoint', async () => {
    authState.isAuthenticated = true
    authState.username = 'alice'
    vi.mocked(chat.getConversation).mockResolvedValue({
      conversation: {
        id: 'conversation-1', owner_username: 'alice', project_id: null, title: '测试会话',
        module_type: 'chat', source: 'home', status: 'active', created_at: '2026-09-08T00:00:00',
        updated_at: '2026-09-08T00:00:00', last_message_at: null,
      },
      messages: [],
    })
    vi.mocked(skillsApi.getChatSkills).mockResolvedValue({
      items: [{
        id: 'system-1', owner_type: 'system', owner_username: null, name: '宏观政策速读',
        description: '提炼政策传导路径', instructions: '核对政策原文', input_schema_json: [],
        output_format: 'markdown', status: 'published', version_no: 1,
        created_at: '2026-09-08T00:00:00', updated_at: '2026-09-08T00:00:00', is_enabled: true,
      }, {
        id: 'personal-1', owner_type: 'user', owner_username: 'alice', name: '测试输出模板',
        description: '按固定格式输出', instructions: '输出测试完成', input_schema_json: [],
        output_format: 'markdown', status: 'published', version_no: 1,
        created_at: '2026-09-08T00:00:00', updated_at: '2026-09-08T00:00:00',
      }],
    })

    render(
      <MemoryRouter initialEntries={['/chat/conversation-1']}>
        <Routes><Route path="/chat/:conversationId" element={<ChatPage />} /></Routes>
      </MemoryRouter>,
    )

    await waitFor(() => expect(skillsApi.getChatSkills).toHaveBeenCalledOnce())
    fireEvent.click(screen.getByRole('button', { name: 'Skills' }))
    expect(screen.getByRole('dialog', { name: '选择本次对话使用的 Skills' })).toBeInTheDocument()
    expect(await screen.findByText('宏观政策速读')).toBeInTheDocument()
    expect(screen.getByText(/系统 Skill · 提炼政策传导路径/)).toBeInTheDocument()
    expect(screen.getByText(/仅显示当前账号已启用的系统 Skill 和个人 Skill/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '我的 Skill' }))
    expect(screen.queryByText('宏观政策速读')).not.toBeInTheDocument()
    expect(screen.getByText('测试输出模板')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '系统 Skill' }))
    expect(screen.getByText('宏观政策速读')).toBeInTheDocument()
    expect(screen.queryByText('测试输出模板')).not.toBeInTheDocument()
    const skillOption = screen.getByRole('button', { name: /宏观政策速读/ })
    fireEvent.click(skillOption)
    expect(skillOption).toHaveAttribute('aria-pressed', 'true')
    expect(skillOption).toHaveClass('selected')
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '关闭 Skills' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '选择本次对话使用的 Skills' })).not.toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText('输入你的债券分析问题…'), { target: { value: '验证 Skill' } })
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }))
    await waitFor(() => expect(chat.sendMessage).toHaveBeenCalledWith(
      'conversation-1', '验证 Skill', expect.any(String), expect.any(Function), ['system-1'],
    ))
  })

  it('sends an authenticated PDF as a message attachment without requiring text', async () => {
    authState.isAuthenticated = true
    authState.username = 'alice'
    vi.mocked(chat.getConversation).mockResolvedValue({
      conversation: {
        id: 'conversation-1', owner_username: 'alice', project_id: null, title: '论文会话',
        module_type: 'chat', source: 'home', status: 'active', created_at: '2026-09-08T00:00:00',
        updated_at: '2026-09-08T00:00:00', last_message_at: null,
      },
      messages: [],
    })
    vi.mocked(skillsApi.getChatSkills).mockResolvedValue({ items: [] })
    vi.mocked(chat.uploadChatAttachment).mockResolvedValue({
      id: 'paper-1', original_filename: 'paper.pdf', size_bytes: 12, page_count: 2,
    })

    render(
      <MemoryRouter initialEntries={['/chat/conversation-1']}>
        <Routes><Route path="/chat/:conversationId" element={<ChatPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('我们要一起做些什么？')
    const file = new File(['%PDF-test'], 'paper.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText('选择文件附件'), { target: { files: [file] } })
    expect(screen.getByText(/paper\.pdf/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }))

    await waitFor(() => expect(chat.uploadChatAttachment).toHaveBeenCalledWith('conversation-1', file))
    await waitFor(() => expect(chat.sendMessage).toHaveBeenCalledWith(
      'conversation-1', '', expect.any(String), expect.any(Function), [], ['paper-1'],
    ))
  })

  it('shows a persisted paper after reopening the conversation', async () => {
    authState.isAuthenticated = true
    authState.username = 'alice'
    vi.mocked(skillsApi.getChatSkills).mockResolvedValue({ items: [] })
    vi.mocked(chat.getConversation).mockResolvedValue({
      conversation: {
        id: 'conversation-1', owner_username: 'alice', project_id: null, title: '论文会话',
        module_type: 'chat', source: 'home', status: 'active', created_at: '2026-09-08T00:00:00',
        updated_at: '2026-09-08T00:00:00', last_message_at: null,
      },
      messages: [{
        id: 'message-1', role: 'user', content: '请分析附件论文', status: 'completed',
        created_at: '2026-09-08T00:00:00',
        attachments: [{ id: 'paper-1', original_filename: 'rates.pdf', size_bytes: 1024, page_count: 12 }],
      }],
    })

    render(
      <MemoryRouter initialEntries={['/chat/conversation-1']}>
        <Routes><Route path="/chat/:conversationId" element={<ChatPage />} /></Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('rates.pdf')).toBeInTheDocument()
    expect(screen.getByText('12 页')).toBeInTheDocument()
  })

  it('clears the composer on send and mounts multiple text files before the reply finishes', async () => {
    authState.isAuthenticated = true
    authState.username = 'alice'
    vi.mocked(skillsApi.getChatSkills).mockResolvedValue({ items: [] })
    vi.mocked(chat.getConversation).mockResolvedValue({
      conversation: {
        id: 'conversation-1', owner_username: 'alice', project_id: null, title: '资料会话',
        module_type: 'chat', source: 'home', status: 'active', created_at: '2026-09-08T00:00:00',
        updated_at: '2026-09-08T00:00:00', last_message_at: null,
      },
      messages: [],
    })
    vi.mocked(chat.uploadChatAttachment).mockImplementation(async (_id, file) => ({
      id: file.name, original_filename: file.name, size_bytes: file.size, page_count: null,
    }))
    let finishReply!: () => void
    const reply = new Promise<void>(resolve => { finishReply = resolve })
    vi.mocked(chat.sendMessage).mockImplementation(async (_id, _content, _clientId, onEvent) => {
      onEvent({
        event: 'message.accepted',
        data: { message: { id: 'message-1', role: 'user', content: '请审阅', status: 'completed', created_at: '2026-09-08T00:00:00' } },
      })
      await reply
    })

    render(
      <MemoryRouter initialEntries={['/chat/conversation-1']}>
        <Routes><Route path="/chat/:conversationId" element={<ChatPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('我们要一起做些什么？')
    const files = [new File(['research'], 'paper.txt', { type: 'text/plain' }), new File(['# Notes'], 'notes.md', { type: 'text/markdown' })]
    fireEvent.change(screen.getByLabelText('选择文件附件'), { target: { files } })
    fireEvent.change(screen.getByPlaceholderText('输入你的债券分析问题…'), { target: { value: '请审阅' } })
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }))

    expect(screen.getByPlaceholderText('输入你的债券分析问题…')).toHaveValue('')
    await waitFor(() => expect(chat.sendMessage).toHaveBeenCalledWith(
      'conversation-1', '请审阅', expect.any(String), expect.any(Function), [], ['paper.txt', 'notes.md'],
    ))
    expect(screen.queryByRole('button', { name: '移除附件 paper.txt' })).not.toBeInTheDocument()
    expect(screen.getByText('正在回复，可继续输入下一条消息')).toBeInTheDocument()
    finishReply()
    await waitFor(() => expect(screen.queryByText('正在回复，可继续输入下一条消息')).not.toBeInTheDocument())
  })

  it('selects an existing file library item and attaches it to the message', async () => {
    authState.isAuthenticated = true
    authState.username = 'alice'
    vi.mocked(skillsApi.getChatSkills).mockResolvedValue({ items: [] })
    vi.mocked(chat.getConversation).mockResolvedValue({
      conversation: {
        id: 'conversation-1', owner_username: 'alice', project_id: null, title: '文件库会话',
        module_type: 'chat', source: 'home', status: 'active', created_at: '2026-09-08T00:00:00',
        updated_at: '2026-09-08T00:00:00', last_message_at: null,
      },
      messages: [],
    })
    vi.mocked(fileLibrary.fetchFileLibrary).mockResolvedValue({
      items: [{
        id: 'policy:42', name: '政策研究.pdf', format: 'PDF', source: '政策文件分析',
        source_key: 'policy_document', source_ref: '42', created_at: '2026-09-08T00:00:00',
        kind: 'upload', size_bytes: null, open_url: '/computer/policy/42', download_url: null,
        chat_mountable: true,
      }],
      total: 1, page: 1, page_size: 50, sources: ['政策文件分析'], formats: ['PDF'],
      summary: { total: 1, uploaded: 1, generated: 0, formats: [{ format: 'PDF', count: 1 }] },
    })
    vi.mocked(chat.attachChatLibraryFile).mockResolvedValue({
      id: 'chat-file-1', original_filename: '政策研究.txt', size_bytes: 100, page_count: null,
    })

    render(
      <MemoryRouter initialEntries={['/chat/conversation-1']}>
        <Routes><Route path="/chat/:conversationId" element={<ChatPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('我们要一起做些什么？')
    fireEvent.click(screen.getByRole('button', { name: '从文件库添加' }))
    const option = await screen.findByRole('button', { name: /政策研究\.pdf/ })
    fireEvent.click(option)
    expect(option).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: '关闭文件库' }))
    expect(screen.getByRole('button', { name: '移除附件 政策研究.txt' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }))

    await waitFor(() => expect(chat.attachChatLibraryFile).toHaveBeenCalledWith(
      'conversation-1', 'policy_document', '42',
    ))
    await waitFor(() => expect(chat.sendMessage).toHaveBeenCalledWith(
      'conversation-1', '', expect.any(String), expect.any(Function), [], ['chat-file-1'],
    ))
  })

  it('renders persisted and streamed thinking collapsed by default and toggles open on click', async () => {
    authState.isAuthenticated = true
    authState.username = 'alice'
    vi.mocked(skillsApi.getChatSkills).mockResolvedValue({ items: [] })
    vi.mocked(chat.getConversation).mockResolvedValue({
      conversation: {
        id: 'conversation-1', owner_username: 'alice', project_id: null, title: '思维链会话',
        module_type: 'chat', source: 'home', status: 'active', created_at: '2026-09-08T00:00:00',
        updated_at: '2026-09-08T00:00:00', last_message_at: null,
      },
      messages: [{
        id: 'm-user-1', role: 'user', content: '分析十年期国债', status: 'completed', created_at: '2026-09-08T00:00:00',
      }, {
        id: 'm-assistant-1', role: 'assistant', content: '市场偏多。',
        thinking: '先核对利率走势与资金面变化', status: 'completed', created_at: '2026-09-08T00:00:01',
      }],
    })

    render(
      <MemoryRouter initialEntries={['/chat/conversation-1']}>
        <Routes><Route path="/chat/:conversationId" element={<ChatPage />} /></Routes>
      </MemoryRouter>,
    )

    const toggle = await screen.findByRole('button', { name: /显示思路/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('先核对利率走势与资金面变化')).not.toBeInTheDocument()

    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('先核对利率走势与资金面变化')).toBeInTheDocument()
  })
})
