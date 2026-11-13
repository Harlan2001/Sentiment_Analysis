import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '@/test/render'
import NewsDetailPage from './NewsDetailPage'

vi.mock('../components/NewsDetailPanel', () => ({
  default: ({ newsId, closeLabel, onClose, onNewsClick }: {
    newsId: number
    closeLabel?: string
    onClose: () => void
    onNewsClick: (id: number) => void
  }) => (
    <div>
      <span>新闻 {newsId}</span>
      <button type="button" onClick={onClose}>{closeLabel ?? '返回发现页'}</button>
      <button type="button" onClick={() => onNewsClick(99)}>打开相似新闻</button>
    </div>
  ),
}))

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>
}

function renderDetail(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/news/:newsId" element={<><NewsDetailPage /><LocationProbe /></>} />
      <Route path="/returns" element={<LocationProbe />} />
      <Route path="/forecast" element={<LocationProbe />} />
      <Route path="/market" element={<LocationProbe />} />
      <Route path="/strategy/prompt" element={<LocationProbe />} />
    </Routes>,
    { route, withAuth: false },
  )
}

describe('NewsDetailPage — 来源上下文', () => {
  it('收益日历新闻和相似新闻均保留返回日期', async () => {
    renderDetail('/news/1?from=returns&date=2026-11-10')

    expect(screen.getByRole('button', { name: '返回收益日历' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '打开相似新闻' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/news/99?from=returns&date=2026-11-10')
    expect(screen.getByText('新闻 99')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '返回收益日历' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/returns?date=2026-11-10')
  })

  it('预测证据和相似新闻均保留原报告日期', async () => {
    renderDetail('/news/1?from=forecast&date=2026-11-06')

    expect(screen.getByRole('button', { name: '返回预测' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '打开相似新闻' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/news/99?from=forecast&date=2026-11-06')

    await userEvent.click(screen.getByRole('button', { name: '返回预测' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/forecast?date=2026-11-06')
  })

  it('保持策略详情返回和相似新闻 strategyId 旧行为', async () => {
    renderDetail('/news/1?strategyId=7')

    expect(screen.getByRole('button', { name: '返回策略生成' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '打开相似新闻' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/news/99?strategyId=7')

    await userEvent.click(screen.getByRole('button', { name: '返回策略生成' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/strategy/prompt?id=7&view=strategy-news')
  })

  it('策略上下文优先于预测来源', async () => {
    renderDetail('/news/1?strategyId=7&from=forecast&date=2026-11-06')

    await userEvent.click(screen.getByRole('button', { name: '打开相似新闻' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/news/99?strategyId=7')
    await userEvent.click(screen.getByRole('button', { name: '返回策略生成' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/strategy/prompt?id=7&view=strategy-news')
  })

  it('无来源上下文时仍返回发现页', async () => {
    renderDetail('/news/1')
    await userEvent.click(screen.getByRole('button', { name: '返回发现页' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/market')
  })
})
