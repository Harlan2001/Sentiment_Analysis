import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * 研报库页面测试（TDD，对应 docs/PRD-研报分析功能细化.md）
 * - P1-6 failed 研报在列表上可一键「重新分析」（现状只能重走上传弹窗）
 *
 * it.fails：当前 UI 无此按钮，功能上线后转为通过并去掉 .fails。
 */

vi.mock('@/api/reportGeneration', () => ({
  getResearchList: vi.fn(),
  reanalyzeReport: vi.fn(),
}))
vi.mock('../components/WorkflowDateRangePicker', () => ({
  WorkflowDateRangePicker: () => null,
}))
vi.mock('../components/ReportSourceDetailPanel', () => ({ ReportSourceDetailPanel: () => null }))

import * as api from '@/api/reportGeneration'
import { ReportLibraryPage } from './ReportLibraryPage'

// reanalyzeReport 尚不存在，待功能上线后改为静态引用
const reanalyzeReport = (
  api as unknown as { reanalyzeReport: ReturnType<typeof vi.fn> }
).reanalyzeReport

beforeEach(() => {
  vi.mocked(api.getResearchList).mockResolvedValue({
    items: [
      {
        id: 1, title: '已完成的研报', institution: 'XX 证券', publish_date: '2026-01-02',
        industry: '固收', report_type: 'macro', ai_summary: '', ai_market_view: 'bullish',
        ai_view_strength: 0.8, ai_key_points: [], page_count: 10, status: 'analyzed',
        source: 'web', created_at: null,
      },
      {
        id: 2, title: '分析失败的研报', institution: 'YY 证券', publish_date: '2026-01-03',
        industry: '银行', report_type: 'industry', ai_summary: null, ai_market_view: null,
        ai_view_strength: null, ai_key_points: null, page_count: 8, status: 'failed',
        source: 'web', created_at: null,
      },
    ],
    total: 2, page: 1, page_size: 6, total_pages: 1,
    filters: { institutions: ['XX 证券', 'YY 证券'], industries: ['固收', '银行'] },
  } as never)
  reanalyzeReport.mockResolvedValue({ report_id: 2, status: 'processing' })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ReportLibraryPage · P1-6 失败重试', () => {
  it('failed 研报卡片提供「重新分析」按钮并调用接口', async () => {
    render(
      <MemoryRouter>
        <ReportLibraryPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('分析失败的研报')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /重新分析/ }))

    await waitFor(() => expect(reanalyzeReport).toHaveBeenCalledWith(2))
  })
})
