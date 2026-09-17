import { request } from './client'
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

export function deleteStrategyConversation(conversationId: number) {
  return request<{ deleted: boolean }>(`/sapi/ai-strategy-generation/conversations/${conversationId}`, { method: 'DELETE' })
}

export function restoreStrategyConversation(conversationId: number) {
  return request<StrategyConversation>(`/sapi/ai-strategy-generation/conversations/${conversationId}/restore`, { method: 'POST' })
}

export function permanentlyDeleteStrategyConversation(conversationId: number) {
  return request<{ deleted: boolean }>(`/sapi/ai-strategy-generation/conversations/${conversationId}/permanently`, { method: 'DELETE' })
}
