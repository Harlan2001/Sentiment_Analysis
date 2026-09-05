import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AIMarketSummary from './AIMarketSummary'
import type { AIMarketSummaryData } from '@/types'

function makeData(overrides: Partial<AIMarketSummaryData> = {}): AIMarketSummaryData {
  return { direction: 'bullish', text: '摘要文本', title: '', date: '2026-09-01', ...overrides } as AIMarketSummaryData
}

describe('AIMarketSummary', () => {
  it('渲染看涨方向标签、日期与摘要', () => {
    render(<AIMarketSummary data={makeData({ text: '会议释放宽松信号' })} onClick={vi.fn()} />)
    expect(screen.getByText('看涨')).toBeInTheDocument()
    expect(screen.getByText('2026-09-01')).toBeInTheDocument()
    expect(screen.getByText('会议释放宽松信号')).toBeInTheDocument()
  })

  it('看跌方向映射为看跌标签', () => {
    render(<AIMarketSummary data={makeData({ direction: 'bearish' })} onClick={vi.fn()} />)
    expect(screen.getByText('看跌')).toBeInTheDocument()
  })

  it('长文显示展开并可切换收起', async () => {
    render(<AIMarketSummary data={makeData({ text: '长'.repeat(250) })} onClick={vi.fn()} />)
    const expand = screen.getByRole('button', { name: '展开' })
    await userEvent.click(expand)
    expect(screen.getByRole('button', { name: '收起' })).toBeInTheDocument()
  })

  it('短文不显示展开按钮', () => {
    render(<AIMarketSummary data={makeData({ text: '短' })} onClick={vi.fn()} />)
    expect(screen.queryByRole('button', { name: '展开' })).not.toBeInTheDocument()
  })

  it('点击卡片触发 onClick', async () => {
    const onClick = vi.fn()
    render(<AIMarketSummary data={makeData()} onClick={onClick} />)
    await userEvent.click(screen.getByText('AI 市场摘要'))
    expect(onClick).toHaveBeenCalled()
  })
})