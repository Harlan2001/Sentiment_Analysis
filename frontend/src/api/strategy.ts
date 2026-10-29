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
  /** 我方验收门结论；验收门上线前的历史消息为 null */
  validation_json?: StrategyValidation | null
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

/** 因子信号面板的一行；字段与后端 signal_panel.FactorSignal.to_dict() 对应 */
export type FactorSignal = {
  code: string
  name: string
  category: string
  factor_type: string
  direction: 'positive' | 'negative' | 'neutral'
  direction_label: string
  signal_score: number
  confidence: number
  event_count: number
  positive_count: number
  negative_count: number
  hit_rate: number | null
  majority_base: number | null
  sample_size: number
  holding_days: number
  latest_event_time: string | null
  /** 口径标注：历史命中率来自全部模型混合的事件研究 */
  caliber: string
}

export type FactorSignalPanel = {
  items: FactorSignal[]
  count: number
  window_days: number
  model_name: string
  holding_days: number
  min_samples: number
  caliber: string
  reference_time: string | null
}

/** 验收门三步判定的单项结果 */
export type ValidationStep = {
  step: string
  ok: boolean
  detail?: string
}

export type ValidationVerdict = 'passed' | 'no_trade' | 'backtest_failed' | 'backtest_error'

export type StrategyValidation = {
  verdict: ValidationVerdict
  passed: boolean
  retryable: boolean
  steps: ValidationStep[]
  trade_count: number | null
  raw_trade_line: string | null
  symbol_whitelisted: boolean
  reason: string
}

/** 草稿快照里可还原的情报元信息 */
export type DraftContext = {
  instrument?: string | null
  instrument_code?: string | null
  backtest_mode?: string | null
  candle_interval?: string | null
  model_name?: string | null
  prompt_version?: string | null
  reference_time?: string | null
  factor_panel?: FactorSignalPanel | null
  token_used?: number | null
  token_budget?: number | null
  [key: string]: unknown
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
  context: DraftContext
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

export function createStrategyDraft(
  conversationId: number,
  requirement: string,
  lookbackDays = 7,
  options: { instrumentCode?: string; backtestMode?: string; candleInterval?: string } = {},
) {
  return request<StrategyDraft>(`/sapi/ai-strategy-generation/conversations/${conversationId}/draft`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      requirement,
      lookback_days: lookbackDays,
      ...(options.instrumentCode ? { instrument_code: options.instrumentCode } : {}),
      ...(options.backtestMode ? { backtest_mode: options.backtestMode } : {}),
      ...(options.candleInterval ? { candle_interval: options.candleInterval } : {}),
    }),
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
