import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatPage } from './ChatPage'
import * as chat from '@/api/chat'
import * as skillsApi from '@/api/skills'

const authState = vi.hoisted(() => ({ authEnabled: true, isAuthenticated: false, username: undefined as string | undefined }))
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => authState,
}))
vi.mock('@/api/chat', () => ({
  createConversation: vi.fn(), getConversation: vi.fn(), sendMessage: vi.fn(),
  sendVisitorMessage: vi.fn(async (_content, _history, onDelta) => onDelta('真实 AI 回复')),
}))
vi.mock('@/api/skills', () => ({ getChatSkills: vi.fn() }))
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
    fireEvent.click(screen.getByRole('checkbox', { name: /宏观政策速读/ }))
    fireEvent.click(screen.getByRole('button', { name: '关闭 Skills' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '选择本次对话使用的 Skills' })).not.toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText('输入你的债券分析问题…'), { target: { value: '验证 Skill' } })
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }))
    await waitFor(() => expect(chat.sendMessage).toHaveBeenCalledWith(
      'conversation-1', '验证 Skill', expect.any(String), expect.any(Function), ['system-1'],
    ))
  })
})
