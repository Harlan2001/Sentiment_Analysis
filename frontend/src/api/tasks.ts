import { request } from './client'

/** 工作流首页的任务聚合行（后端 /sapi/workbench/computer/tasks） */
export type WorkflowTask = {
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

export function getWorkflowTasks() {
  return request<{ items: WorkflowTask[]; totals: Record<string, number> }>(
    '/sapi/workbench/computer/tasks',
  )
}