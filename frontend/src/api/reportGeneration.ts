import { request } from './workbench'
import { storage } from '@/utils/helpers'

// 旧 API 不包裹 { data: ... }，直接返回数据体
async function requestLegacy<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = storage.get<string>('auth_token')
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new Error(payload?.detail || '请求失败')
  return payload as T
}

export type ReportSource = {
  id: number
  title: string
  institution: string | null
  publish_date: string | null
  industry: string | null
  report_type: string | null
  ai_summary: string | null
  ai_market_view: string | null
  status: string
}

export type ReportSourceSnapshot = Pick<
  ReportSource,
  'id' | 'title' | 'institution' | 'publish_date' | 'industry' | 'report_type' | 'ai_market_view'
>

export type ReportGenerationStatus = 'queued' | 'running' | 'completed' | 'failed'

export type ReportGenerationTask = {
  id: string
  title: string
  requirement: string
  date_start: string | null
  date_end: string | null
  report_ids_json: number[]
  source_snapshot_json: ReportSourceSnapshot[]
  status: ReportGenerationStatus
  model_name: string | null
  result_markdown?: string | null
  error_message: string | null
  retry_count: number
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export type ReportSourceFilters = {
  keyword?: string
  institution?: string
  industry?: string
  date_start?: string
  date_end?: string
}

function toQuery(input: Record<string, string | number | undefined>) {
  const params = new URLSearchParams()
  Object.entries(input).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  return params.toString()
}

export function getReportSources(filters: ReportSourceFilters) {
  return request<{
    items: ReportSource[]
    filters: { institutions: string[]; industries: string[] }
  }>(`/sapi/report-generation/sources?${toQuery({ ...filters, limit: 12 })}`)
}

export function getReportGenerationTasks(filters: { status?: string; date_start?: string; date_end?: string } = {}) {
  return request<{ items: ReportGenerationTask[] }>(
    `/sapi/report-generation/tasks?${toQuery({ ...filters, limit: 100 })}`,
  )
}

export function getReportGenerationTask(taskId: string) {
  return request<ReportGenerationTask>(`/sapi/report-generation/tasks/${taskId}`)
}

export function createReportGenerationTask(input: {
  title: string
  requirement: string
  report_ids: number[]
  date_start?: string
  date_end?: string
}) {
  return request<ReportGenerationTask>('/sapi/report-generation/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function retryReportGenerationTask(taskId: string) {
  return request<ReportGenerationTask>(`/sapi/report-generation/tasks/${taskId}/retry`, {
    method: 'POST',
  })
}

// ── 研报库 ────────────────────────────────────────────────

export type ResearchSummary = {
  total: number
  analyzed: number
  bullish: number
  bearish: number
  neutral: number
  institutions: number
}

export type ResearchListItem = {
  id: number
  title: string
  institution: string | null
  publish_date: string | null
  industry: string | null
  report_type: string | null
  ai_summary: string | null
  ai_market_view: string | null
  ai_view_strength: number | null
  ai_key_points: unknown
  page_count: number | null
  status: string
  source: string | null
  created_at: string | null
}

export function getResearchSummary() {
  return requestLegacy<ResearchSummary>('/sapi/research/summary')
}

export function getResearchList(params: {
  page?: number
  page_size?: number
  institution?: string
  industry?: string
  market_view?: string
  status?: string
  keyword?: string
}) {
  return requestLegacy<{
    items: ResearchListItem[]
    total: number
    filters: { institutions: string[]; industries: string[] }
  }>(`/sapi/research/list?${toQuery({
    page: params.page ?? 1,
    page_size: params.page_size ?? 20,
    institution: params.institution,
    industry: params.industry,
    market_view: params.market_view,
    status: params.status,
    keyword: params.keyword,
  })}`)
}
