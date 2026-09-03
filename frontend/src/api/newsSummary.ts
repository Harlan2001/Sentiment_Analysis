import { request } from './client'

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

export function getNewsSources() {
  return request<{ sources: NewsSourceOption[] }>('/sapi/news/sources')
}

export async function getLatestNewsDate() {
  return request<{ latest_date: string }>('/sapi/news/latest-trading-day')
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