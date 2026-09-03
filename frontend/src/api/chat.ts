import { authHeaders, request } from './client'
import type { Conversation, Project } from './projects'
export type { Conversation } from './projects'

// 与主前端同域：开发环境经 Vite 代理转发，部署时可由同域反向代理提供此路径。
const apiBaseUrl = ''

type ListData<T> = { items: T[]; next_cursor?: string | null }

export type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: 'pending' | 'streaming' | 'completed' | 'failed' | 'interrupted'
  error_code?: string | null
  skill_names?: string[]
  created_at: string
  completed_at?: string | null
}

type StreamEvent =
  | { event: 'message.accepted'; data: { message: Message } }
  | { event: 'assistant.started'; data: { message_id: string } }
  | { event: 'assistant.delta'; data: { message_id: string; delta: string } }
  | { event: 'assistant.completed'; data: { message: Message } }
  | { event: 'assistant.failed'; data: { message: Message; error: { code: string; message: string } } }
  | { event: 'stream.done'; data: { conversation_id: string } }

/** 侧边栏数据：项目树（含最近会话）+ 最近会话 */
export function getSidebar() {
  return request<{
    projects: Array<Project & { recent_conversations: Conversation[] }>
    recent_conversations: Conversation[]
    current_user?: { username?: string }
  }>('/sapi/workbench/sidebar')
}

export function getConversations(limit = 50) {
  return request<ListData<Conversation>>(`/sapi/workbench/conversations?limit=${limit}`)
}

export function getConversation(conversationId: string) {
  return request<{ conversation: Conversation; messages: Message[] }>(`/sapi/workbench/conversations/${conversationId}`)
}

export function createConversation(input: { project_id?: string; source: 'home' | 'sidebar' | 'project' }) {
  return request<Conversation>('/sapi/workbench/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export async function sendMessage(
  conversationId: string,
  content: string,
  clientMessageId: string,
  onEvent: (event: StreamEvent) => void,
  skillIds: string[] = [],
) {
  const response = await fetch(apiBaseUrl + `/sapi/workbench/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ content, client_message_id: clientMessageId, skill_ids: skillIds }),
  })
  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => null)
    throw new Error(payload?.detail || '发送消息失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const result = await reader.read()
    if (result.done) break
    buffer += decoder.decode(result.value, { stream: true })
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() || ''
    frames.forEach((frame) => {
      const eventName = frame.match(/^event:\s*(.+)$/m)?.[1]
      const dataText = frame.match(/^data:\s*(.+)$/m)?.[1]
      if (!eventName || !dataText) return
      try {
        onEvent({ event: eventName, data: JSON.parse(dataText) } as StreamEvent)
      } catch {
        // 单个不完整或未知事件不应中断已建立的会话流。
      }
    })
  }
}

export async function sendVisitorMessage(
  content: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }>,
  onDelta: (delta: string) => void,
) {
  const response = await fetch(apiBaseUrl + '/sapi/workbench/conversations/visitor-chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ content, history: history.slice(-10) }),
  })
  if (!response.ok || !response.body) throw new Error('发送消息失败')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const result = await reader.read()
    if (result.done) break
    buffer += decoder.decode(result.value, { stream: true })
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() || ''
    for (const frame of frames) {
      const eventName = frame.match(/^event:\s*(.+)$/m)?.[1]
      const dataText = frame.match(/^data:\s*(.+)$/m)?.[1]
      if (!eventName || !dataText) continue
      const data = JSON.parse(dataText)
      if (eventName === 'assistant.delta') onDelta(data.delta)
      if (eventName === 'assistant.failed') throw new Error(data.error?.message || '发送消息失败')
    }
  }
}