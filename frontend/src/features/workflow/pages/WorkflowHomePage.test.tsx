import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { WorkflowTask, WorkflowTaskListResponse } from '@/api/tasks'

vi.mock('@/api/tasks', () => ({
  getWorkflowTasks: vi.fn(),
  getWorkflowTaskDetail: vi.fn(),
  retryWorkflowTask: vi.fn(),
  downloadWorkflowTaskFile: vi.fn(),
}))

vi.mock('@/features/workflow/components/WorkflowDatePicker', () => ({
  WorkflowDatePicker: ({ onChange }: { onChange: (value: string) => void }) => (
    <button type="button" onClick={() => onChange('2026-11-20')}>选择测试日期</button>
  ),
}))

import {
  downloadWorkflowTaskFile,
  getWorkflowTaskDetail,
  getWorkflowTasks,
  retryWorkflowTask,
} from '@/api/tasks'
import { WorkflowHomePage } from './WorkflowHomePage'

function makeTask(overrides: Partial<WorkflowTask> = {}): WorkflowTask {
  return {
    task_id: 'report_generation:task-1',
    domain_id: 'task-1',
    task_type: 'report_generation',
    module: '综合研报',
    title: '失败的长端利率研报',
    description: '分析长端利率',
    source: '研报分析',
    result: '—',
    status: 'failed',
    domain_status: 'failed',
    status_label: '失败',
    stage: 'failed',
    stage_label: '执行失败',
    error_message: '完整的模型调用错误详情',
    retry_count: 2,
    date: '2026-11-20',
    updated_at: '2026-11-20T08:00:00Z',
    needs_action: true,
    result_url: '/computer/reports/task-1',
    file_id: null,
    download_url: null,
    ...overrides,
  }
}

function makeList(
  items: WorkflowTask[],
  overrides: Partial<WorkflowTaskListResponse> = {},
): WorkflowTaskListResponse {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 20,
    total_pages: 1,
    totals: {
      research_report: 0,
      policy_document: 0,
      report_generation: items.length,
      daily_news: 0,
      strategy: 0,
      total: items.length,
    },
    status_counts: { failed: items.length },
    ...overrides,
  }
}

function renderPage() {
  return render(<MemoryRouter><WorkflowHomePage /></MemoryRouter>)
}

const getTasksMock = vi.mocked(getWorkflowTasks)
const getDetailMock = vi.mocked(getWorkflowTaskDetail)
const retryMock = vi.mocked(retryWorkflowTask)
const downloadMock = vi.mocked(downloadWorkflowTaskFile)

beforeEach(() => {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => false })
  const task = makeTask()
  getTasksMock.mockResolvedValue(makeList([task]))
  getDetailMock.mockResolvedValue({
    task,
    execution: {
      id: 81,
      status: 'failed',
      error_message: '完整的模型调用错误详情',
      started_at: '2026-11-20T07:59:00Z',
      finished_at: '2026-11-20T08:00:00Z',
    },
    items: [
      { id: 1, event_type: 'loading', status: 'succeeded', message: '读取原文完成', created_at: '2026-11-20T07:59:10Z' },
      { id: 2, event_type: 'failed', status: 'failed', message: '模型调用失败', created_at: '2026-11-20T08:00:00Z' },
    ],
  })
  retryMock.mockResolvedValue(makeTask({ status: 'queued', status_label: '排队中', stage_label: '排队等待', error_message: null }))
  downloadMock.mockResolvedValue({ blob: new Blob(['docx']), filename: '研报.docx' })
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, writable: true, value: vi.fn(() => 'blob:task-result') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, writable: true, value: vi.fn() })
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('WorkflowHomePage · 服务端任务中心', () => {
  it('使用真实 total/status_counts，并展示阶段、状态与错误摘要', async () => {
    const task = makeTask({
      title: '执行中的政策解读',
      task_id: 'policy_document:9',
      domain_id: '9',
      task_type: 'policy_document',
      module: '政策文件分析',
      status: 'running',
      domain_status: 'analyzing',
      status_label: '执行中',
      stage: 'analyzing',
      stage_label: 'AI 分析中',
      needs_action: false,
      error_message: '摘要中的真实错误信息',
    })
    getTasksMock.mockResolvedValue(makeList([task], {
      total: 83,
      total_pages: 5,
      status_counts: { queued: 4, running: 5 },
    }))
    renderPage()

    expect(await screen.findByText('执行中的政策解读')).toBeInTheDocument()
    expect(screen.getByText(/AI 分析中/)).toBeInTheDocument()
    expect(screen.getByText('摘要中的真实错误信息')).toBeInTheDocument()
    expect(document.querySelector('.workflow-task-summary')).toHaveTextContent('9')
    expect(document.querySelector('.workflow-task-summary')).toHaveTextContent('共 83 个任务')
    expect(getTasksMock).toHaveBeenCalledWith({
      task_type: undefined,
      status: undefined,
      date: undefined,
      page: 1,
      page_size: 20,
    })
    expect(screen.getByRole('heading', { name: '研报分析' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '政策文件分析' })).toBeInTheDocument()
  })

  it('类型、状态与日期均发送到服务端，分页后变更筛选会重置第一页', async () => {
    getTasksMock.mockImplementation(async (query) => makeList([makeTask()], {
      page: query?.page ?? 1,
      total: 45,
      total_pages: 3,
    }))
    renderPage()
    await screen.findByText('失败的长端利率研报')

    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(getTasksMock.mock.calls.at(-1)?.[0]).toMatchObject({ page: 2 }))

    fireEvent.change(screen.getByLabelText('任务类型'), { target: { value: 'research_report' } })
    await waitFor(() => expect(getTasksMock.mock.calls.at(-1)?.[0]).toMatchObject({
      page: 1,
      task_type: 'research_report',
    }))

    fireEvent.change(screen.getByLabelText('任务状态'), { target: { value: 'failed' } })
    await waitFor(() => expect(getTasksMock.mock.calls.at(-1)?.[0]).toMatchObject({
      page: 1,
      task_type: 'research_report',
      status: 'failed',
    }))

    fireEvent.click(screen.getByRole('button', { name: '选择测试日期' }))
    await waitFor(() => expect(getTasksMock.mock.calls.at(-1)?.[0]).toMatchObject({
      page: 1,
      task_type: 'research_report',
      status: 'failed',
      date: '2026-11-20',
    }))
  })

  it('打开详情查看执行与事件时间线，失败重试后刷新列表和详情', async () => {
    let retried = false
    getTasksMock.mockImplementation(async () => makeList([
      retried
        ? makeTask({ status: 'queued', status_label: '排队中', stage_label: '排队等待', error_message: null, retry_count: 3 })
        : makeTask(),
    ]))
    getDetailMock.mockImplementation(async () => ({
      task: retried
        ? makeTask({ status: 'queued', status_label: '排队中', stage_label: '排队等待', error_message: null, retry_count: 3 })
        : makeTask(),
      execution: retried ? null : {
        id: 81,
        status: 'failed',
        error_message: '完整的模型调用错误详情',
        started_at: '2026-11-20T07:59:00Z',
        finished_at: '2026-11-20T08:00:00Z',
      },
      items: retried ? [] : [
        { id: 1, event_type: 'loading', status: 'succeeded', message: '读取原文完成', created_at: '2026-11-20T07:59:10Z' },
      ],
    }))
    retryMock.mockImplementation(async () => {
      retried = true
      return makeTask({ status: 'queued', status_label: '排队中', stage_label: '排队等待', error_message: null, retry_count: 3 })
    })

    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /失败的长端利率研报/ }))
    const dialog = await screen.findByRole('dialog', { name: '任务详情' })
    expect(within(dialog).getAllByText('完整的模型调用错误详情').length).toBeGreaterThan(0)
    expect(within(dialog).getByText('读取原文完成')).toBeInTheDocument()
    expect(within(dialog).getByText('2 次')).toBeInTheDocument()

    fireEvent.click(within(dialog).getByRole('button', { name: '重试任务' }))
    await waitFor(() => expect(retryMock).toHaveBeenCalledWith('report_generation', 'task-1'))
    expect(await within(dialog).findByText('排队中')).toBeInTheDocument()
    expect(getTasksMock.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(getDetailMock.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('409 显示状态变化提示，404 显示任务不可访问', async () => {
    retryMock.mockRejectedValue(new Error('只有失败任务可以重试'))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /失败的长端利率研报/ }))
    const dialog = await screen.findByRole('dialog', { name: '任务详情' })
    fireEvent.click(within(dialog).getByRole('button', { name: '重试任务' }))
    expect(await within(dialog).findByText('状态已变化，请刷新')).toBeInTheDocument()

    fireEvent.click(within(dialog).getByRole('button', { name: '关闭任务详情' }))
    getDetailMock.mockRejectedValue(new Error('任务不存在或当前用户无权访问'))
    fireEvent.click(screen.getByRole('button', { name: /失败的长端利率研报/ }))
    expect(await screen.findByText('任务不存在或当前用户不可访问')).toBeInTheDocument()
  })

  it('策略历史只读且不重试，成功任务提供结果与认证下载入口', async () => {
    const strategy = makeTask({
      task_id: 'strategy:s1', domain_id: 's1', task_type: 'strategy', module: '策略生成',
      title: '历史策略', status: 'failed', status_label: '失败', result_url: '/strategy/prompt?id=s1',
    })
    getTasksMock.mockResolvedValue(makeList([strategy]))
    getDetailMock.mockResolvedValue({ task: strategy, execution: null, items: [] })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /历史策略/ }))
    let dialog = await screen.findByRole('dialog', { name: '任务详情' })
    expect(within(dialog).queryByRole('button', { name: '重试任务' })).toBeNull()
    expect(within(dialog).getByRole('link', { name: '查看结果' })).toHaveAttribute('href', '/strategy/prompt?id=s1')
    fireEvent.click(within(dialog).getByRole('button', { name: '关闭任务详情' }))

    const succeeded = makeTask({
      title: '已完成研报', status: 'succeeded', domain_status: 'completed', status_label: '已完成',
      stage: 'succeeded', stage_label: '已完成', error_message: null, needs_action: false,
      download_url: '/sapi/report-generation/tasks/task-1/export?format=docx', file_id: 'report:task-1:docx',
    })
    getTasksMock.mockResolvedValue(makeList([succeeded]))
    getDetailMock.mockResolvedValue({ task: succeeded, execution: null, items: [] })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /已完成研报/ }))
    dialog = await screen.findByRole('dialog', { name: '任务详情' })
    expect(within(dialog).getByRole('link', { name: '查看结果' })).toBeVisible()
    fireEvent.click(within(dialog).getByRole('button', { name: '下载文件' }))
    await waitFor(() => expect(downloadMock).toHaveBeenCalledWith(succeeded))
    expect(URL.createObjectURL).toHaveBeenCalled()
    clickSpy.mockRestore()
  })

  it('仅 queued/running 触发轮询，隐藏时暂停且终态后停止', async () => {
    vi.useFakeTimers()
    let hidden = true
    let current = makeTask({ status: 'running', status_label: '执行中', stage_label: 'AI 分析中', error_message: null })
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden })
    getTasksMock.mockImplementation(async () => makeList([current]))
    renderPage()
    await act(async () => {})
    expect(screen.getByText('失败的长端利率研报')).toBeInTheDocument()
    const initialCalls = getTasksMock.mock.calls.length

    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(getTasksMock).toHaveBeenCalledTimes(initialCalls)

    current = makeTask({ status: 'succeeded', status_label: '已完成', stage_label: '已完成', error_message: null })
    hidden = false
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    expect(getTasksMock).toHaveBeenCalledTimes(initialCalls + 1)
    expect(screen.getAllByText('已完成').length).toBeGreaterThan(0)

    await act(async () => { await vi.advanceTimersByTimeAsync(9000) })
    expect(getTasksMock).toHaveBeenCalledTimes(initialCalls + 1)
  })
})

describe('统一任务下载 API', () => {
  it('使用 authHeaders 并解析下载文件名', async () => {
    localStorage.setItem('auth_token', JSON.stringify('task-token'))
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new Blob(['docx']), {
      status: 200,
      headers: { 'Content-Disposition': 'attachment; filename="server-report.docx"' },
    }))
    const actual = await vi.importActual<typeof import('@/api/tasks')>('@/api/tasks')
    const result = await actual.downloadWorkflowTaskFile({ title: '本地标题', download_url: '/sapi/download' })

    expect(fetchSpy).toHaveBeenCalledWith('/sapi/download', {
      headers: { Authorization: 'Bearer task-token' },
    })
    expect(result.filename).toBe('server-report.docx')
  })
})
