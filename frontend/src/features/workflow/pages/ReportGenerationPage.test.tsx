import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * 研报分析工作台测试（TDD，对应 docs/PRD-研报分析功能细化.md）
 * - P0-1 选源链路：勾选研报 → 新建综合研报 → 提交任务
 * - P0-2 发布日期区间必须传给 getResearchList（当前只传了未被渲染的 getReportSources）
 * - 板块三：首屏主区为「我的报告」；底部聊天式 composer 移除；统计改为待办型
 *
 * 待实现用例使用 it.fails：当前必然失败，功能上线后转为通过（届时去掉 .fails）。
 */

vi.mock('@/api/reportGeneration', () => ({
  createReportGenerationTask: vi.fn(),
  deleteReportGenerationTask: vi.fn(),
  getReportGenerationTasks: vi.fn(),
  getReportSources: vi.fn(),
  getResearchList: vi.fn(),
  getResearchSummary: vi.fn(),
  retryReportGenerationTask: vi.fn(),
}))

// 自定义日历不便模拟，替换为一键设定区间的按钮
vi.mock('../components/WorkflowDateRangePicker', () => ({
  WorkflowDateRangePicker: ({ onChange, label }: { onChange: (s: string, e: string) => void; label?: string }) => (
    <button type="button" onClick={() => onChange('2026-01-01', '2026-01-31')}>
      选发布日期{label ? `·${label}` : ''}
    </button>
  ),
}))
vi.mock('../components/WorkflowDatePicker', () => ({ WorkflowDatePicker: () => null }))
vi.mock('../components/ReportSourceDetailPanel', () => ({ ReportSourceDetailPanel: () => null }))

import * as api from '@/api/reportGeneration'
import { ReportGenerationPage } from './ReportGenerationPage'

const analyzedCard = {
  id: 1,
  title: '2026 年利率债策略',
  institution: 'XX 证券',
  publish_date: '2026-01-02',
  industry: '固收',
  report_type: 'macro',
  ai_summary: '摘要',
  ai_market_view: 'bullish',
  ai_view_strength: 0.8,
  ai_key_points: [],
  page_count: 12,
  status: 'analyzed',
  source: 'web_upload',
  created_at: null,
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ReportGenerationPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(api.getResearchList).mockResolvedValue({
    items: [analyzedCard],
    total: 1,
    page: 1,
    page_size: 6,
    total_pages: 1,
    filters: { institutions: ['XX 证券'], industries: ['固收'] },
  } as never)
  vi.mocked(api.getReportGenerationTasks).mockResolvedValue({ items: [] } as never)
  vi.mocked(api.getReportSources).mockResolvedValue({
    items: [],
    filters: { institutions: [], industries: [] },
  } as never)
  vi.mocked(api.getResearchSummary).mockResolvedValue({
    total: 2, analyzed: 1, bullish: 1, bearish: 0, neutral: 0, institutions: 1,
  } as never)
  vi.mocked(api.createReportGenerationTask).mockResolvedValue({ id: 't1' } as never)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ReportGenerationPage · P0-1 选源与创建链路', () => {
  it('勾选研报并通过新建弹窗提交，createReportGenerationTask 收到 report_ids', async () => {
    renderPage()
    expect(await screen.findByText('2026 年利率债策略')).toBeInTheDocument()

    // 唯一创建入口：新建综合研报（板块三：底部 composer 已移除）
    fireEvent.click(screen.getByRole('button', { name: /新建综合研报/ }))

    // 弹窗内勾选已分析研报
    const checkbox = await screen.findByRole('checkbox')
    fireEvent.click(checkbox)
    expect(screen.getByText(/已选\s*1/)).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText(/标题/), { target: { value: '1 月利率债综述' } })
    fireEvent.change(screen.getByPlaceholderText(/分析重点|需求/), { target: { value: '比较机构分歧' } })
    fireEvent.click(screen.getByRole('button', { name: /开始生成|提交|生成/ }))

    await waitFor(() =>
      expect(api.createReportGenerationTask).toHaveBeenCalledWith(
        expect.objectContaining({ title: '1 月利率债综述', report_ids: [1] }),
      ),
    )
  })
})

describe('ReportGenerationPage · P0-2 日期筛选真实生效', () => {
  it('发布日期区间变化时带参请求 getResearchList', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /选发布日期/ }))
    await waitFor(() => {
      const lastCall = vi.mocked(api.getResearchList).mock.calls.at(-1)?.[0] as Record<string, unknown>
      expect(lastCall).toMatchObject({ date_start: '2026-01-01', date_end: '2026-01-31' })
    })
  })
})

describe('ReportGenerationPage · 板块三 信息架构', () => {
  it('首屏主区是「我的报告」', async () => {
    renderPage()
    expect(await screen.findByText(/我的报告/)).toBeInTheDocument()
  })

  it('底部聊天式 composer 已移除', async () => {
    renderPage()
    await screen.findByText('2026 年利率债策略')
    expect(screen.queryByPlaceholderText(/描述分析重点/)).toBeNull()
  })

  it('统计区展示待办型指标（待分析）', async () => {
    renderPage()
    expect(await screen.findByText(/待分析/)).toBeInTheDocument()
  })
})
