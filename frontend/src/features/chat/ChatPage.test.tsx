import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatPage } from './ChatPage'
import * as workbench from '@/api/workbench'

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ authEnabled: true, isAuthenticated: false }),
}))
vi.mock('@/api/workbench', () => ({
  createConversation: vi.fn(), getConversation: vi.fn(), sendMessage: vi.fn(),
  sendVisitorMessage: vi.fn(async (_content, _history, onDelta) => onDelta('真实 AI 回复')),
}))
vi.mock('@/api/skills', () => ({ getSkills: vi.fn() }))
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
  })

  it('uses the visitor AI endpoint without calling persistent conversation APIs', async () => {
    renderVisitorChat()
    fireEvent.change(screen.getByPlaceholderText('输入你的债券分析问题…'), {
      target: { value: '访客问题' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }))

    expect(screen.getByText('访客问题')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('真实 AI 回复')).toBeInTheDocument())
    expect(workbench.sendVisitorMessage).toHaveBeenCalledOnce()
    expect(workbench.createConversation).not.toHaveBeenCalled()
    expect(workbench.getConversation).not.toHaveBeenCalled()
    expect(workbench.sendMessage).not.toHaveBeenCalled()
  })

  it('drops visitor messages after unmount and starts with a fresh web session', async () => {
    const first = renderVisitorChat()
    fireEvent.change(screen.getByPlaceholderText('输入你的债券分析问题…'), {
      target: { value: '不会保留的消息' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }))
    expect(screen.getByText('不会保留的消息')).toBeInTheDocument()
    await waitFor(() => expect(workbench.sendVisitorMessage).toHaveBeenCalled())
    first.unmount()

    renderVisitorChat()
    expect(screen.queryByText('不会保留的消息')).not.toBeInTheDocument()
    expect(screen.getByText('我们要一起做些什么？')).toBeInTheDocument()
  })
})
