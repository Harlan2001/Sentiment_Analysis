import type { WorkflowTask, WorkflowTaskStatus, WorkflowTaskType } from '@/api/tasks'

export const TASK_TYPE_OPTIONS: Array<{ value: WorkflowTaskType; label: string }> = [
  { value: 'research_report', label: '研报解析' },
  { value: 'report_generation', label: '综合研报' },
  { value: 'daily_news', label: '每日新闻' },
  { value: 'policy_document', label: '政策文件' },
  { value: 'strategy', label: '策略历史' },
]

export const TASK_STATUS_OPTIONS: Array<{ value: WorkflowTaskStatus; label: string }> = [
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '执行中' },
  { value: 'succeeded', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'empty', label: '无新闻' },
  { value: 'pending', label: '待处理' },
  { value: 'pending_confirmation', label: '待确认' },
]

export function isPollingTask(task: Pick<WorkflowTask, 'status'>): boolean {
  return task.status === 'queued' || task.status === 'running'
}

export function isHistoryTask(task: Pick<WorkflowTask, 'status'>): boolean {
  return task.status === 'succeeded' || task.status === 'empty'
}

export function taskTone(task: Pick<WorkflowTask, 'status' | 'needs_action'>): string {
  if (task.status === 'failed') return 'failed'
  if (task.status === 'succeeded' || task.status === 'empty') return 'done'
  if (task.needs_action || task.status === 'pending_confirmation') return 'attention'
  return 'running'
}

export function taskStageLabel(task: Pick<WorkflowTask, 'stage_label' | 'status_label'>): string {
  return task.stage_label || task.status_label || '状态未知'
}

export function taskDate(task: Pick<WorkflowTask, 'date' | 'updated_at'>): string {
  if (task.date) return task.date.slice(0, 10)
  const date = new Date(task.updated_at)
  return Number.isNaN(date.getTime()) ? '未知日期' : date.toISOString().slice(0, 10)
}

export function formatTaskTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const now = new Date()
  if (date.toDateString() === now.toDateString()) {
    return new Intl.DateTimeFormat('zh-CN', {
      hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(date)
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date)
}

export function isTaskNotFoundError(reason: unknown): boolean {
  const message = reason instanceof Error ? reason.message : String(reason)
  return /404|不存在|无权访问|Not Found/i.test(message)
}

export function isTaskConflictError(reason: unknown): boolean {
  const message = reason instanceof Error ? reason.message : String(reason)
  return /409|不可重试|只有失败任务|状态已变化|策略历史仅保留只读/i.test(message)
}
