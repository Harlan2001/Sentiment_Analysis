export type Conversation = {
  id: string
  project_id: string | null
  title: string
  module_type: string
  source: string
  status: string
  created_at: string
  updated_at: string
  last_message_at: string | null
}

export type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: 'pending' | 'streaming' | 'completed' | 'failed' | 'interrupted'
  error_code?: string | null
  created_at: string
  completed_at?: string | null
}

export type Project = {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export type DeletedProject = Project & { deleted_at: string }
export type DeletedConversation = Conversation & { deleted_at: string }

export type DeletedItemsData = {
  deleted_projects: DeletedProject[]
  deleted_conversations: DeletedConversation[]
}

type ListData<T> = { items: T[]; next_cursor?: string | null }

import { storage } from '../utils/helpers'

// 与主前端同域：开发环境经 Vite 代理转发，部署时可由同域反向代理提供此路径。
const apiBaseUrl = ''

function authorizationHeader(): Record<string, string> {
  const token = storage.get<string>('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, options: RequestInit = {}) {
  const response = await fetch(apiBaseUrl + path, {
    ...options,
    headers: { ...authorizationHeader(), ...options.headers },
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || payload?.message || '请求工作台服务失败')
  return payload.data as T
}

export function getSidebar() {
  return request<{ projects: Array<Project & { recent_conversations: Conversation[] }>; recent_conversations: Conversation[]; current_user?: { username?: string } }>('/sapi/workbench/sidebar')
}

export function getConversations(limit = 50) {
  return request<ListData<Conversation>>(`/sapi/workbench/conversations?limit=${limit}`)
}

export function getProjectConversations(projectId: string, limit = 50) {
  return request<ListData<Conversation>>(`/sapi/workbench/projects/${projectId}/conversations?limit=${limit}`)
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

export function createProject(input: { name: string; description?: string }) {
  return request<Project>('/sapi/workbench/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function getProject(projectId: string) {
  return request<Project>(`/sapi/workbench/projects/${projectId}`)
}

type StreamEvent =
  | { event: 'message.accepted'; data: { message: Message } }
  | { event: 'assistant.started'; data: { message_id: string } }
  | { event: 'assistant.delta'; data: { message_id: string; delta: string } }
  | { event: 'assistant.completed'; data: { message: Message } }
  | { event: 'assistant.failed'; data: { message: Message; error: { code: string; message: string } } }
  | { event: 'stream.done'; data: { conversation_id: string } }

export async function sendMessage(
  conversationId: string,
  content: string,
  clientMessageId: string,
  onEvent: (event: StreamEvent) => void,
) {
  const response = await fetch(apiBaseUrl + `/sapi/workbench/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: { ...authorizationHeader(), 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ content, client_message_id: clientMessageId }),
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

export function deleteProject(projectId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/projects/${projectId}`, { method: 'DELETE' })
}

export function restoreProject(projectId: string) {
  return request<Project>(`/sapi/workbench/projects/${projectId}/restore`, { method: 'POST' })
}

export function deleteConversation(conversationId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/conversations/${conversationId}`, { method: 'DELETE' })
}

export function restoreConversation(conversationId: string) {
  return request<Conversation>(`/sapi/workbench/conversations/${conversationId}/restore`, { method: 'POST' })
}

export function getDeletedItems() {
  return request<DeletedItemsData>('/sapi/workbench/deleted-items')
}

// ── 策略会话 ──────────────────────────────────────────────

export type StrategyConversation = {
  id: number
  title: string
  instrument: string | null
  status: string
  current_local_version_no: number
  last_message_at: string | null
  created_at: string
  updated_at: string
}

export type StrategyMessage = {
  id: number
  sequence_no: number
  role: 'user' | 'assistant'
  content: string
  status: string
  generated_prompt?: string
  system_draft_prompt?: string
  user_edited_prompt?: string
  final_sent_prompt?: string
  references_json?: unknown
  context_json?: unknown
  public_error_message?: string | null
  created_at: string
  updated_at: string
}

export type StrategyVersion = {
  id: number
  source_message_id: number
  local_version_no: number
  name: string
  description: string
  code: string
  backtest_passed: boolean | null
  backtest_exit_code: string | null
  backtest_summary: string
  backtest_metrics_json: unknown
  created_at: string
}

export type StrategyConversationDetail = {
  conversation: StrategyConversation
  messages: StrategyMessage[]
  versions: StrategyVersion[]
}

export type StrategyDraft = {
  user_message_id: number
  assistant_message_id: number
  status: string
  system_draft_prompt: string
  context: Record<string, unknown>
}

export function getStrategyConversations(limit = 50) {
  return request<{ items: StrategyConversation[] }>(`/sapi/ai-strategy-generation/conversations?limit=${limit}`)
}

export function getStrategyConversation(id: number) {
  return request<StrategyConversationDetail>(`/sapi/ai-strategy-generation/conversations/${id}`)
}

export function createStrategyConversation(title: string) {
  return request<StrategyConversation>('/sapi/ai-strategy-generation/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export function createStrategyDraft(conversationId: number, requirement: string, lookbackDays = 7) {
  return request<StrategyDraft>(`/sapi/ai-strategy-generation/conversations/${conversationId}/draft`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ requirement, lookback_days: lookbackDays }),
  })
}

export function confirmStrategyDraft(conversationId: number, assistantMessageId: number, editedPrompt: string) {
  return request<Record<string, unknown>>(`/sapi/ai-strategy-generation/conversations/${conversationId}/drafts/${assistantMessageId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ edited_prompt: editedPrompt }),
  })
}

export function archiveStrategyConversation(conversationId: number) {
  return request<{ archived: boolean }>(`/sapi/ai-strategy-generation/conversations/${conversationId}/archive`, { method: 'PATCH' })
}
