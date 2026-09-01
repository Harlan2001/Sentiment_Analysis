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
  skill_names?: string[]
  created_at: string
  completed_at?: string | null
}

export type Project = {
  id: string
  name: string
  description: string | null
  role?: 'owner' | 'editor' | 'viewer'
  created_at: string
  updated_at: string
}

export type DeletedProject = Project & { deleted_at: string }
export type DeletedConversation = Conversation & { deleted_at: string }
export type DeletedStrategyConversation = StrategyConversation & { deleted_at: string }
export type DeletedReportTask = {
  id: string
  title: string
  requirement: string
  date_start: string | null
  date_end: string | null
  status: string
  created_at: string
  updated_at: string
  deleted_at: string
}
export type DeletedNewsSummaryTask = Pick<DailyNewsSummaryTask, 'id' | 'start_date' | 'end_date' | 'focus' | 'status' | 'news_count' | 'created_at' | 'updated_at'> & { deleted_at: string }

export type DeletedItemsData = {
  deleted_projects: DeletedProject[]
  deleted_conversations: DeletedConversation[]
  deleted_strategies: DeletedStrategyConversation[]
  deleted_reports: DeletedReportTask[]
  deleted_news_summaries: DeletedNewsSummaryTask[]
}

type ListData<T> = { items: T[]; next_cursor?: string | null }

export type WatchlistObjectType = 'news' | 'factor' | 'macro_signal'

export type WatchlistItem = {
  id: string
  object_type: WatchlistObjectType
  object_id: string
  title: string
  source_url: string | null
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export function getWatchlistItems() {
  return request<{ items: WatchlistItem[] }>('/sapi/watchlist')
}

export function addWatchlistItem(input: {
  object_type: WatchlistObjectType
  object_id: string
  title: string
  source_url?: string
  metadata?: Record<string, unknown>
}) {
  return request<WatchlistItem>('/sapi/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function removeWatchlistItem(itemId: string) {
  return request<{ deleted: boolean }>(`/sapi/watchlist/${itemId}`, { method: 'DELETE' })
}

import { storage } from '@/utils/helpers'
import { buildDemoConversation, buildDemoDetail, buildDemoDraft, clearDemo, DEMO_CONVERSATION_ID, getDemoConversation, isDemoInstrument, markRunning, resetDemo } from '@/features/computer/strategyDemo'

// 与主前端同域：开发环境经 Vite 代理转发，部署时可由同域反向代理提供此路径。
const apiBaseUrl = ''

function authorizationHeader(): Record<string, string> {
  const token = storage.get<string>('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function request<T>(path: string, options: RequestInit = {}) {
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
  skillIds: string[] = [],
) {
  const response = await fetch(apiBaseUrl + `/sapi/workbench/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: { ...authorizationHeader(), 'Content-Type': 'application/json', Accept: 'text/event-stream' },
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

export function deleteProject(projectId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/projects/${projectId}`, { method: 'DELETE' })
}

export function restoreProject(projectId: string) {
  return request<Project>(`/sapi/workbench/projects/${projectId}/restore`, { method: 'POST' })
}

export function permanentlyDeleteProject(projectId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/projects/${projectId}/permanently`, { method: 'DELETE' })
}

export function deleteConversation(conversationId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/conversations/${conversationId}`, { method: 'DELETE' })
}

export function restoreConversation(conversationId: string) {
  return request<Conversation>(`/sapi/workbench/conversations/${conversationId}/restore`, { method: 'POST' })
}

export function permanentlyDeleteConversation(conversationId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/conversations/${conversationId}/permanently`, { method: 'DELETE' })
}

export function getDeletedItems() {
  return request<DeletedItemsData>('/sapi/workbench/deleted-items')
}

export function emptyDeletedItems() {
  return request<Record<string, number>>('/sapi/workbench/deleted-items', { method: 'DELETE' })
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

export async function getStrategyConversations(limit = 50) {
  const demo = getDemoConversation()
  try {
    const data = await request<{ items: StrategyConversation[] }>(`/sapi/ai-strategy-generation/conversations?limit=${limit}`)
    if (!demo) return data
    return { items: [demo, ...data.items.filter((item) => item.id !== DEMO_CONVERSATION_ID)] }
  } catch {
    return { items: demo ? [demo] : [] }
  }
}

export function getStrategyConversation(id: number) {
  if (id === DEMO_CONVERSATION_ID) return Promise.resolve(buildDemoDetail())
  return request<StrategyConversationDetail>(`/sapi/ai-strategy-generation/conversations/${id}`)
}

export function createStrategyConversation(title: string) {
  if (isDemoInstrument(title)) {
    resetDemo()
    return Promise.resolve(buildDemoConversation(title))
  }
  return request<StrategyConversation>('/sapi/ai-strategy-generation/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export function createStrategyDraft(conversationId: number, requirement: string, lookbackDays = 7) {
  if (conversationId === DEMO_CONVERSATION_ID) return Promise.resolve(buildDemoDraft())
  return request<StrategyDraft>(`/sapi/ai-strategy-generation/conversations/${conversationId}/draft`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ requirement, lookback_days: lookbackDays }),
  })
}

export function confirmStrategyDraft(conversationId: number, assistantMessageId: number, editedPrompt: string) {
  if (conversationId === DEMO_CONVERSATION_ID) {
    markRunning()
    return Promise.resolve({} as Record<string, unknown>)
  }
  return request<Record<string, unknown>>(`/sapi/ai-strategy-generation/conversations/${conversationId}/drafts/${assistantMessageId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ edited_prompt: editedPrompt }),
  })
}

export function archiveStrategyConversation(conversationId: number) {
  return request<{ archived: boolean }>(`/sapi/ai-strategy-generation/conversations/${conversationId}/archive`, { method: 'PATCH' })
}

export function deleteStrategyConversation(conversationId: number) {
  if (conversationId === DEMO_CONVERSATION_ID) {
    clearDemo()
    return Promise.resolve({ deleted: true })
  }
  return request<{ deleted: boolean }>(`/sapi/ai-strategy-generation/conversations/${conversationId}`, { method: 'DELETE' })
}

export function restoreStrategyConversation(conversationId: number) {
  return request<StrategyConversation>(`/sapi/ai-strategy-generation/conversations/${conversationId}/restore`, { method: 'POST' })
}

export function permanentlyDeleteStrategyConversation(conversationId: number) {
  return request<{ deleted: boolean }>(`/sapi/ai-strategy-generation/conversations/${conversationId}/permanently`, { method: 'DELETE' })
}

// ── 每日新闻总结 ──────────────────────────────────────────

export type NewsSourceOption = {
  key: string
  name: string
  enabled: boolean
}

export type DailyNewsSummaryReference = {
  news_id: number
  title: string
  publish_time: string
  source: string
  direction: string
  horizon: string
}

export type DailyNewsSummaryTask = {
  id: number
  owner_username: string
  start_date: string
  end_date: string
  sources_json: string[]
  focus: string | null
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'empty'
  news_count: number
  source_stats_json: Record<string, number> | null
  summary: string | null
  references_json: DailyNewsSummaryReference[] | null
  error_message: string | null
  retry_of_id: number | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export async function getNewsSources() {
  const response = await fetch('/sapi/news/sources', {
    headers: authorizationHeader(),
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new Error(payload?.detail || '读取新闻来源失败')
  return payload as { sources: NewsSourceOption[] }
}

export async function getLatestNewsDate() {
  const response = await fetch('/sapi/news/latest-trading-day', {
    headers: authorizationHeader(),
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new Error(payload?.detail || '读取最新新闻日期失败')
  return payload as { latest_date: string }
}

export function getDailyNewsSummaries(limit = 50) {
  return request<{ items: DailyNewsSummaryTask[] }>(`/sapi/daily-news-summaries?limit=${limit}`)
}

export function getDailyNewsSummary(taskId: number) {
  return request<DailyNewsSummaryTask>(`/sapi/daily-news-summaries/${taskId}`)
}

export function createDailyNewsSummary(input: {
  start_date: string
  end_date: string
  sources: string[]
  focus: string
}) {
  return request<DailyNewsSummaryTask>('/sapi/daily-news-summaries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function retryDailyNewsSummary(taskId: number) {
  return request<DailyNewsSummaryTask>(`/sapi/daily-news-summaries/${taskId}/retry`, {
    method: 'POST',
  })
}

export function deleteDailyNewsSummary(taskId: number) {
  return request<{ deleted: boolean }>(`/sapi/daily-news-summaries/${taskId}`, { method: 'DELETE' })
}

export function restoreDailyNewsSummary(taskId: number) {
  return request<DailyNewsSummaryTask>(`/sapi/daily-news-summaries/${taskId}/restore`, { method: 'POST' })
}

export function permanentlyDeleteDailyNewsSummary(taskId: number) {
  return request<{ deleted: boolean }>(`/sapi/daily-news-summaries/${taskId}/permanently`, { method: 'DELETE' })
}

// ── Computer 总览聚合 ──────────────────────────────────────

export type ComputerTask = {
  task_id: string
  task_type: 'report_generation' | 'strategy' | 'daily_news'
  module: '研报分析' | '策略开发' | '每日新闻总结'
  title: string
  description: string
  source: string
  result: string
  status: string
  status_label: string
  date: string | null
  updated_at: string
  needs_action: boolean
}

export function getComputerTasks() {
  return request<{ items: ComputerTask[]; totals: Record<string, number> }>(
    '/sapi/workbench/computer/tasks',
  )
}
