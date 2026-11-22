import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PolicyDocumentItem, PolicyDocumentListResponse } from '@/types'

vi.mock('@/api/client', () => ({
  API_PREFIX: '/sapi',
  request: vi.fn(),
}))

vi.mock('@/components/ui', () => ({
  Modal: ({ isOpen, title, children }: { isOpen: boolean; title: string; children: React.ReactNode }) => (
    isOpen ? <div role="dialog" aria-label={title}>{children}</div> : null
  ),
}))

import { request } from '@/api/client'
import PolicyUploadModal from '../components/PolicyUploadModal'
import PolicyDocumentsPage from './PolicyDocumentsPage'

const requestMock = vi.mocked(request)
let listResponse: PolicyDocumentListResponse
let uploadResult: Record<string, unknown>
let uploadForms: FormData[]

function makeDocument(overrides: Partial<PolicyDocumentItem> = {}): PolicyDocumentItem {
  return {
    id: 1,
    title: '服务端返回的货币政策文件',
    original_filename: 'policy.pdf',
    issuer: '测试机关',
    document_no: '测试〔2026〕1号',
    publish_date: '2026-11-20',
    page_count: 8,
    status: 'completed',
    error_message: null,
    model_name: 'test-model',
    created_at: '2026-11-20T08:00:00Z',
    updated_at: '2026-11-20T08:01:00Z',
    impact_direction: 'bullish',
    stage: 'succeeded',
    focus_title: null,
    analysis_requirement: null,
    retry_count: 0,
    ...overrides,
  }
}

function makeList(items: PolicyDocumentItem[]): PolicyDocumentListResponse {
  return {
    items,
    total: 42,
    page: 1,
    page_size: 6,
    total_pages: 7,
    stats: { total: 42, analyzed: 31, bullish: 20, bearish: 7, neutral: 4 },
  }
}

function renderPage() {
  return render(<MemoryRouter><PolicyDocumentsPage /></MemoryRouter>)
}

function listCalls() {
  return requestMock.mock.calls.filter(([url]) => String(url).startsWith('/sapi/policy-documents?'))
}

function lastListParams(): URLSearchParams {
  const call = listCalls().at(-1)
  if (!call) throw new Error('政策列表尚未请求')
  return new URL(String(call[0]), 'http://localhost').searchParams
}

function pdfFile(name = 'policy.pdf'): File {
  return new File(['%PDF-test'], name, { type: 'application/pdf' })
}

beforeEach(() => {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => false })
  listResponse = makeList([makeDocument()])
  uploadResult = {
    document_id: 2,
    title: '新上传政策',
    status: 'queued',
    is_duplicate: false,
    issuer: null,
    document_no: null,
    publish_date: null,
    page_count: 4,
    warnings: [],
  }
  uploadForms = []
  requestMock.mockImplementation(async (url: string, options?: RequestInit) => {
    if (url.startsWith('/sapi/policy-documents?')) return listResponse as never
    if (url === '/sapi/policy-documents/upload' && options?.method === 'POST') {
      uploadForms.push(options.body as FormData)
      return uploadResult as never
    }
    if (url === '/sapi/policy-documents/1/analyze' && options?.method === 'POST') {
      listResponse = makeList([makeDocument({ status: 'queued', stage: 'queued', impact_direction: null })])
      return { document_id: 1, status: 'queued' } as never
    }
    if (url === '/sapi/policy-documents/1' && options?.method === 'DELETE') {
      return { deleted: true } as never
    }
    throw new Error(`未 mock 的请求：${options?.method ?? 'GET'} ${url}`)
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
  vi.restoreAllMocks()
})

describe('PolicyDocumentsPage · 服务端筛选与统计', () => {
  it('筛选和分页全部进入查询参数，统计使用后端全量 stats，列表不过滤当前页', async () => {
    renderPage()
    expect((await screen.findAllByText('服务端返回的货币政策文件')).length).toBeGreaterThan(0)

    const chips = [...document.querySelectorAll('.policy-stat-row .report-stat-chip')]
    expect(chips).toHaveLength(5)
    const expected = [
      ['文件总数', '42'], ['已解读', '31'], ['利多债券', '20'], ['利空债券', '7'], ['中性', '4'],
    ]
    chips.forEach((chip, index) => {
      expect(chip).toHaveTextContent(expected[index][0])
      expect(chip.querySelector('strong')).toHaveTextContent(expected[index][1])
    })

    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(lastListParams().get('page')).toBe('2'))

    fireEvent.change(screen.getByPlaceholderText('搜索文件标题'), { target: { value: '不会在前端过滤' } })
    await waitFor(() => {
      expect(lastListParams().get('page')).toBe('1')
      expect(lastListParams().get('keyword')).toBe('不会在前端过滤')
    })
    // mock 仍返回同一条服务端数据，页面不得因为标题不匹配而把它过滤掉。
    expect(screen.getAllByText('服务端返回的货币政策文件').length).toBeGreaterThan(0)

    fireEvent.change(screen.getByLabelText('影响方向筛选'), { target: { value: 'bearish' } })
    await waitFor(() => expect(lastListParams().get('direction')).toBe('bearish'))
    fireEvent.change(screen.getByLabelText('开始日期'), { target: { value: '2026-11-01' } })
    await waitFor(() => expect(lastListParams().get('date_start')).toBe('2026-11-01'))
    fireEvent.change(screen.getByLabelText('结束日期'), { target: { value: '2026-11-20' } })
    await waitFor(() => expect(lastListParams().get('date_end')).toBe('2026-11-20'))
    expect(lastListParams().get('page')).toBe('1')
    expect(lastListParams().get('page_size')).toBe('6')
  })

  it('queued 标签为排队中，隐藏时暂停轮询，完成后停止', async () => {
    vi.useFakeTimers()
    let hidden = true
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden })
    listResponse = makeList([makeDocument({ status: 'queued', stage: 'queued', impact_direction: null })])
    renderPage()
    await act(async () => {})
    expect(screen.getAllByText('排队中').length).toBeGreaterThan(0)
    expect(screen.getByText(/已加入队列，等待执行/)).toBeInTheDocument()
    const initialCalls = listCalls().length

    await act(async () => { await vi.advanceTimersByTimeAsync(4000) })
    expect(listCalls()).toHaveLength(initialCalls)

    hidden = false
    listResponse = makeList([makeDocument()])
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    expect(listCalls()).toHaveLength(initialCalls + 1)

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000) })
    expect(listCalls()).toHaveLength(initialCalls + 1)
  })

  it('失败重新解读接收 queued 并立即进入活动任务轮询', async () => {
    listResponse = makeList([makeDocument({ status: 'failed', stage: 'failed', impact_direction: null })])
    renderPage()
    await screen.findAllByText('服务端返回的货币政策文件')
    fireEvent.click(screen.getByRole('button', { name: '重试' }))

    await waitFor(() => expect(requestMock).toHaveBeenCalledWith('/sapi/policy-documents/1/analyze', { method: 'POST' }))
    expect((await screen.findAllByText('排队中')).length).toBeGreaterThan(0)
    expect(screen.getByText(/已加入队列，等待执行/)).toBeInTheDocument()
  })
})

describe('PolicyUploadModal · 真实入队上传', () => {
  it('父页面传入 focus_title/requirement，成功立即显示已加入队列且无 1200ms 假分析定时器', async () => {
    const timeoutSpy = vi.spyOn(window, 'setTimeout')
    renderPage()
    await screen.findAllByText('服务端返回的货币政策文件')
    fireEvent.change(screen.getByPlaceholderText(/分析主题，例如/), { target: { value: '货币政策与长端利率' } })
    fireEvent.change(screen.getByPlaceholderText(/描述你关心的分析角度/), { target: { value: '重点关注十年国债和信用利差' } })
    fireEvent.click(screen.getByRole('button', { name: '＋ 上传 PDF' }))
    const dialog = screen.getByRole('dialog', { name: '上传政策文件 PDF' })
    const input = dialog.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [pdfFile()] } })
    fireEvent.click(screen.getByRole('button', { name: '上传并解读' }))

    expect(await screen.findByText('已加入队列')).toBeInTheDocument()
    expect(screen.queryByText(/AI 正在解读政策文件/)).toBeNull()
    expect(uploadForms).toHaveLength(1)
    expect((uploadForms[0].get('file') as File).name).toBe('policy.pdf')
    expect(uploadForms[0].get('focus_title')).toBe('货币政策与长端利率')
    expect(uploadForms[0].get('requirement')).toBe('重点关注十年国债和信用利差')
    expect(timeoutSpy).not.toHaveBeenCalledWith(expect.any(Function), 1200)
    expect(requestMock.mock.calls.filter(([url]) => String(url).endsWith('/analyze'))).toHaveLength(0)

    fireEvent.click(screen.getByRole('button', { name: '查看任务状态' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '上传政策文件 PDF' })).toBeNull())
  })

  it('重复文件展示后端 message，不自动发起重新分析', async () => {
    uploadResult = {
      document_id: 1,
      title: '已有政策',
      status: 'completed',
      is_duplicate: true,
      message: '文件已存在，未自动重新分析；可在已有文件中确认重新解读',
    }
    const { container } = render(
      <PolicyUploadModal isOpen onClose={vi.fn()} onSubmitted={vi.fn()} focusTitle="主题" requirement="要求" />,
    )
    fireEvent.change(container.querySelector('input[type="file"]') as HTMLInputElement, {
      target: { files: [pdfFile('duplicate.pdf')] },
    })
    fireEvent.click(screen.getByRole('button', { name: '上传并解读' }))

    expect(await screen.findByText('文件已存在')).toBeInTheDocument()
    expect(screen.getByText('文件已存在，未自动重新分析；可在已有文件中确认重新解读')).toBeInTheDocument()
    expect(uploadForms[0].get('focus_title')).toBe('主题')
    expect(uploadForms[0].get('requirement')).toBe('要求')
    expect(requestMock.mock.calls.filter(([url]) => String(url).endsWith('/analyze'))).toHaveLength(0)
  })
})
