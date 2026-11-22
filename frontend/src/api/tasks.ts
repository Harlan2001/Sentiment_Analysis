import { API_PREFIX, authHeaders, request } from './client'

export type WorkflowTaskType =
  | 'research_report'
  | 'policy_document'
  | 'report_generation'
  | 'daily_news'
  | 'strategy'

export type WorkflowTaskStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'empty'
  | 'pending'
  | 'pending_confirmation'

/** 工作流首页的任务聚合行（后端 /sapi/workbench/computer/tasks）。 */
export type WorkflowTask = {
  task_id: string
  domain_id: string
  task_type: WorkflowTaskType
  module: string
  title: string
  description: string
  source: string
  result: string
  status: WorkflowTaskStatus
  domain_status: string
  status_label: string
  stage: string | null
  stage_label: string | null
  error_message: string | null
  retry_count: number
  date: string | null
  updated_at: string
  needs_action: boolean
  result_url: string | null
  file_id: string | null
  download_url: string | null
}

export type WorkflowTaskTotals = Record<WorkflowTaskType, number> & { total: number }

export type WorkflowTaskListResponse = {
  items: WorkflowTask[]
  total: number
  page: number
  page_size: number
  total_pages: number
  totals: WorkflowTaskTotals
  status_counts: Record<string, number>
}

export type WorkflowTaskQuery = {
  task_type?: WorkflowTaskType
  status?: WorkflowTaskStatus
  date?: string
  page?: number
  page_size?: number
}

export type WorkflowTaskExecution = {
  id: number
  status: string
  error_message: string | null
  started_at: string | null
  finished_at: string | null
}

export type WorkflowTaskEvent = {
  id: number
  event_type: string
  status: string
  message: string
  created_at: string
}

export type WorkflowTaskDetailResponse = {
  task: WorkflowTask
  execution: WorkflowTaskExecution | null
  items: WorkflowTaskEvent[]
}

const TASKS_URL = `${API_PREFIX}/workbench/computer/tasks`

/**
 * 读取统一任务中心。保留无参数调用，供旧页面和调用方直接获取第一页。
 * 类型筛选严格使用后端的单值协议，不在当前页拼接或伪造多选筛选。
 */
export function getWorkflowTasks(params: WorkflowTaskQuery = {}) {
  const search = new URLSearchParams()
  if (params.task_type) search.set('task_type', params.task_type)
  if (params.status) search.set('status', params.status)
  if (params.date) search.set('date', params.date)
  if (params.page != null) search.set('page', String(params.page))
  if (params.page_size != null) search.set('page_size', String(params.page_size))
  const query = search.toString()
  return request<WorkflowTaskListResponse>(`${TASKS_URL}${query ? `?${query}` : ''}`)
}

export function getWorkflowTaskDetail(taskType: WorkflowTaskType, domainId: string) {
  return request<WorkflowTaskDetailResponse>(
    `${TASKS_URL}/${encodeURIComponent(taskType)}/${encodeURIComponent(domainId)}`,
  )
}

export function retryWorkflowTask(taskType: WorkflowTaskType, domainId: string) {
  return request<WorkflowTask>(
    `${TASKS_URL}/${encodeURIComponent(taskType)}/${encodeURIComponent(domainId)}/retry`,
    { method: 'POST' },
  )
}

export type WorkflowTaskDownload = {
  blob: Blob
  filename: string
}

function filenameFromDisposition(value: string | null): string | null {
  if (!value) return null
  const encoded = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) {
    try {
      return decodeURIComponent(encoded.replace(/^"|"$/g, ''))
    } catch {
      // 服务端文件名编码异常时继续使用普通 filename 或任务标题。
    }
  }
  return value.match(/filename="?([^";]+)"?/i)?.[1] ?? null
}

/** 下载必须显式携带 JWT，不能使用会丢失认证头的普通 href。 */
export async function downloadWorkflowTaskFile(
  task: Pick<WorkflowTask, 'title' | 'download_url'>,
): Promise<WorkflowTaskDownload> {
  if (!task.download_url) throw new Error('当前任务没有可下载文件')
  const response = await fetch(task.download_url, { headers: authHeaders() })
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string; message?: string; error?: { message?: string } }
      | null
    throw new Error(payload?.error?.message || payload?.detail || payload?.message || '文件下载失败')
  }
  return {
    blob: await response.blob(),
    filename: filenameFromDisposition(response.headers.get('Content-Disposition')) || `${task.title}.docx`,
  }
}
