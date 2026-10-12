import { request } from './client'

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
  version_no: number
  parent_task_id: string | null
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
  model?: string
}) {
  return request<ReportGenerationTask>('/sapi/report-generation/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

/** 基于历史任务改需求/来源再生成（新版本号，原任务保留）（P1-7） */
export function regenerateReportGenerationTask(
  taskId: string,
  input: { requirement: string; report_ids?: number[]; model?: string },
) {
  return request<ReportGenerationTask>(`/sapi/report-generation/tasks/${taskId}/regenerate`, {
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

export function deleteReportGenerationTask(taskId: string) {
  return request<{ deleted: boolean }>(`/sapi/report-generation/tasks/${taskId}`, { method: 'DELETE' })
}

export function restoreReportGenerationTask(taskId: string) {
  return request<ReportGenerationTask>(`/sapi/report-generation/tasks/${taskId}/restore`, { method: 'POST' })
}

export function permanentlyDeleteReportGenerationTask(taskId: string) {
  return request<{ deleted: boolean }>(`/sapi/report-generation/tasks/${taskId}/permanently`, { method: 'DELETE' })
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
  return request<ResearchSummary>('/sapi/research/summary')
}

export function getResearchList(params: {
  page?: number
  page_size?: number
  institution?: string
  industry?: string
  market_view?: string
  status?: string
  keyword?: string
  date_start?: string
  date_end?: string
}) {
  return request<{
    items: ResearchListItem[]
    total: number
    page: number
    page_size: number
    total_pages: number
    filters: { institutions: string[]; industries: string[] }
  }>(`/sapi/research/list?${toQuery({
    page: params.page ?? 1,
    page_size: params.page_size ?? 20,
    institution: params.institution,
    industry: params.industry,
    market_view: params.market_view,
    status: params.status,
    keyword: params.keyword,
    date_start: params.date_start,
    date_end: params.date_end,
  })}`)
}

// ── 重新分析（P0-3） ─────────────────────────────────────

/** 对单篇研报（重新）触发 AI 分析；已分析研报必须显式 force=true。 */
export function reanalyzeReport(reportId: number, model = 'glm') {
  return request<{ report_id: number; status: string; message?: string }>(
    `/sapi/research/${reportId}/analyze?model=${encodeURIComponent(model)}&force=true`,
    { method: 'POST' },
  )
}

export type BatchReanalyzeFilters = {
  institution?: string
  industry?: string
  market_view?: string
  keyword?: string
  date_start?: string
  date_end?: string
  model?: string
}

/** 按筛选条件批量重跑已分析研报，返回触发/跳过计数。 */
export function batchReanalyzeReports(filters: BatchReanalyzeFilters) {
  return request<{ triggered: number; skipped: number; report_ids: number[] }>(
    '/sapi/research/reanalyze/batch',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filters),
    },
  )
}
