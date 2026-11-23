import { expect, test, type Page } from '@playwright/test'

type FixtureTask = {
  task_id: string
  domain_id: string
  task_type: 'report_generation' | 'strategy'
  module: string
  title: string
  description: string
  source: string
  result: string
  status: string
  domain_status: string
  status_label: string
  stage: string | null
  stage_label: string | null
  error_message: string | null
  retry_count: number
  date: string
  updated_at: string
  needs_action: boolean
  result_url: string | null
}

function makeTask(overrides: Partial<FixtureTask> = {}): FixtureTask {
  return {
    task_id: 'report_generation:e2e-report',
    domain_id: 'e2e-report',
    task_type: 'report_generation',
    module: '综合研报',
    title: 'E2E 失败任务',
    description: '验证统一任务中心重试链路',
    source: '研报分析',
    result: '—',
    status: 'failed',
    domain_status: 'failed',
    status_label: '失败',
    stage: 'failed',
    stage_label: '执行失败',
    error_message: 'E2E 完整模型错误：上游超时',
    retry_count: 1,
    date: '2026-11-20',
    updated_at: '2026-11-20T08:00:00Z',
    needs_action: true,
    result_url: '/computer/reports/e2e-report',
    ...overrides,
  }
}

function responseBody(task: FixtureTask) {
  return {
    items: [task],
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
    totals: {
      research_report: 0,
      policy_document: 0,
      report_generation: task.task_type === 'report_generation' ? 1 : 0,
      daily_news: 0,
      strategy: task.task_type === 'strategy' ? 1 : 0,
      total: 1,
    },
    status_counts: { [task.status]: 1 },
  }
}

async function mockRetryableTask(page: Page) {
  let task = makeTask()
  const json = (data: unknown, status = 200) => ({
    status,
    contentType: 'application/json',
    body: JSON.stringify({ data }),
  })

  await page.route('**/sapi/workbench/computer/tasks**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    if (path === '/sapi/workbench/computer/tasks' && request.method() === 'GET') {
      return route.fulfill(json(responseBody(task)))
    }
    if (path === '/sapi/workbench/computer/tasks/report_generation/e2e-report/retry' && request.method() === 'POST') {
      if (task.status !== 'failed') {
        return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: '只有失败任务可以重试' }) })
      }
      task = makeTask({
        status: 'running',
        domain_status: 'running',
        status_label: '执行中',
        stage: 'generating',
        stage_label: '生成内容',
        error_message: null,
        retry_count: 2,
        needs_action: false,
        updated_at: '2026-11-20T08:02:00Z',
      })
      return route.fulfill(json(task, 202))
    }
    if (path === '/sapi/workbench/computer/tasks/report_generation/e2e-report' && request.method() === 'GET') {
      return route.fulfill(json({
        task,
        execution: {
          id: 91,
          status: task.status,
          error_message: task.error_message,
          started_at: '2026-11-20T07:59:00Z',
          finished_at: task.status === 'succeeded' || task.status === 'failed' ? task.updated_at : null,
        },
        items: [
          { id: 1, event_type: 'loading', status: 'succeeded', message: 'E2E 原文读取完成', created_at: '2026-11-20T07:59:10Z' },
          { id: 2, event_type: task.stage ?? 'queued', status: task.status, message: task.stage_label ?? task.status_label, created_at: task.updated_at },
        ],
      }))
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'fixture route not found' }) })
  })

  return {
    complete() {
      task = makeTask({
        status: 'succeeded',
        domain_status: 'completed',
        status_label: '已完成',
        stage: 'succeeded',
        stage_label: '已完成',
        error_message: null,
        result: '查看结果',
        retry_count: 2,
        needs_action: false,
        updated_at: '2026-11-20T08:03:00Z',
      })
    },
  }
}

test('统一 AI 任务：失败详情与阶段、重试和完成结果', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('auth_token', JSON.stringify('e2e-task-token'))
  })
  const fixture = await mockRetryableTask(page)
  await page.goto('/workflow')

  await page.getByRole('button', { name: /E2E 失败任务/ }).click()
  let dialog = page.getByRole('dialog', { name: '任务详情' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('执行失败', { exact: true }).first()).toBeVisible()
  await expect(dialog.getByText('E2E 完整模型错误：上游超时', { exact: true }).first()).toBeVisible()
  await expect(dialog.getByText('E2E 原文读取完成')).toBeVisible()

  await dialog.getByRole('button', { name: '重试任务' }).click()
  await expect(dialog.getByText('生成内容', { exact: true }).first()).toBeVisible()
  await expect(dialog.getByText('2 次', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '关闭任务详情' }).click()

  fixture.complete()
  await page.getByRole('button', { name: '刷新任务中心' }).click()
  await page.getByRole('button', { name: /E2E 失败任务/ }).click()
  dialog = page.getByRole('dialog', { name: '任务详情' })
  await expect(dialog.getByText('已完成', { exact: true }).first()).toBeVisible()
  await expect(dialog.getByRole('link', { name: '查看结果' })).toHaveAttribute('href', '/computer/reports/e2e-report')
  await expect(dialog.getByRole('button', { name: '下载文件' })).toHaveCount(0)
})

test('策略历史只有结果链接，不展示重试', async ({ page }) => {
  const strategy = makeTask({
    task_id: 'strategy:strategy-1',
    domain_id: 'strategy-1',
    task_type: 'strategy',
    module: '策略生成',
    source: '策略生成',
    title: 'E2E 历史策略',
    description: '历史策略结果（只读）',
    result_url: '/strategy/prompt?id=strategy-1',
  })
  await page.route('**/sapi/workbench/computer/tasks**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const data = path.endsWith('/strategy/strategy-1')
      ? { task: strategy, execution: null, items: [] }
      : responseBody(strategy)
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data }) })
  })
  await page.goto('/workflow')
  await page.getByRole('button', { name: /E2E 历史策略/ }).click()
  const dialog = page.getByRole('dialog', { name: '任务详情' })
  await expect(dialog.getByRole('link', { name: '查看结果' })).toHaveAttribute('href', '/strategy/prompt?id=strategy-1')
  await expect(dialog.getByText('策略历史只读', { exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: '重试任务' })).toHaveCount(0)
})
