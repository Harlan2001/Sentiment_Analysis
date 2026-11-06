import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/strategy', () => ({
  getStrategyConversations: vi.fn(),
  createStrategyConversation: vi.fn(),
  deleteStrategyConversation: vi.fn(),
}))

import * as api from '@/api/strategy'
import type { StrategyConversation } from '@/api/strategy'
import { StrategyPage } from './StrategyPage'

function makeConversation(
  id: number,
  title: string,
  summary: StrategyConversation['summary'],
  extra: Partial<StrategyConversation> = {},
): StrategyConversation {
  return {
    id,
    title,
    instrument: summary.instrument,
    status: 'active',
    current_local_version_no: 0,
    last_message_at: '2026-10-30T14:22:00+08:00',
    created_at: '2026-10-30T14:00:00+08:00',
    updated_at: '2026-10-30T14:22:00+08:00',
    summary,
    ...extra,
  }
}

const ITEMS: StrategyConversation[] = [
  makeConversation(
    1,
    '10Y国债双均线 + 因子门控',
    {
      turn_status: 'succeeded',
      verdict: 'passed',
      verdict_passed: true,
      failure_reason: null,
      instrument: '中金所10年期国债期货',
      instrument_code: 'FCT_T_MAIN',
      backtest_mode: 'bar',
      candle_interval: '1d',
      trade_count: 29,
      annual_return: '2.1%',
    },
    { current_local_version_no: 3 },
  ),
  makeConversation(2, '30Y国债ATR通道', {
    turn_status: 'succeeded',
    verdict: 'no_trade',
    verdict_passed: false,
    failure_reason: '提交 29 单但没有真实成交盈亏',
    instrument: '中金所30年期国债期货',
    instrument_code: 'FCT_TL_MAIN',
    backtest_mode: 'bar',
    candle_interval: '1d',
    trade_count: 29,
    annual_return: '0.000%',
  }),
  makeConversation(3, '信用债利差策略草稿', {
    turn_status: 'pending_confirmation',
    verdict: null,
    verdict_passed: false,
    failure_reason: null,
    instrument: '中债10年期国开债',
    instrument_code: 'IBK_CDB10_ACTV',
    backtest_mode: 'bar',
    candle_interval: '1d',
    trade_count: null,
    annual_return: null,
  }),
]

function renderPage() {
  return render(
    <MemoryRouter>
      <StrategyPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(api.getStrategyConversations).mockResolvedValue({ items: ITEMS })
  vi.mocked(api.createStrategyConversation).mockResolvedValue({ id: 99 } as StrategyConversation)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('StrategyPage 列表页（S2-1）', () => {
  it('渲染验收徽章、标的模式与成交/年化指标', async () => {
    renderPage()
    expect(await screen.findByText('验收通过')).toBeTruthy()
    expect(screen.getByText('无成交 · 不合格')).toBeTruthy()
    expect(screen.getByText('待确认')).toBeTruthy()
    expect(screen.getByText(/中金所10年期国债期货 · K线 \/ 1d/)).toBeTruthy()
    // 两条卡片成交数都是 29，应各出现一次
    expect(screen.getAllByText('成交 29 笔')).toHaveLength(2)
    expect(screen.getByText('年化 2.1%')).toBeTruthy()
    expect(screen.getByText('v3')).toBeTruthy()
    // 失败原因首句直接上卡片
    expect(screen.getByText('提交 29 单但没有真实成交盈亏')).toBeTruthy()
  })

  it('关键词搜索只保留标题命中的卡片', async () => {
    renderPage()
    await screen.findByText('验收通过')
    fireEvent.change(screen.getByLabelText('搜索策略'), { target: { value: 'ATR' } })
    expect(screen.queryByText('10Y国债双均线 + 因子门控')).toBeNull()
    expect(screen.getByText('30Y国债ATR通道')).toBeTruthy()
  })

  it('状态筛选“待确认”只留待确认草稿', async () => {
    renderPage()
    await screen.findByText('验收通过')
    fireEvent.click(screen.getByRole('button', { name: /状态：全部/ }))
    fireEvent.click(screen.getByRole('button', { name: '待确认' }))
    expect(screen.getByText('信用债利差策略草稿')).toBeTruthy()
    expect(screen.queryByText('30Y国债ATR通道')).toBeNull()
  })

  it('结论筛选“验收通过”只留通过项', async () => {
    renderPage()
    await screen.findByText('验收通过')
    fireEvent.click(screen.getByRole('button', { name: /结论：全部/ }))
    fireEvent.click(screen.getByRole('button', { name: '验收通过' }))
    expect(screen.getByText('10Y国债双均线 + 因子门控')).toBeTruthy()
    expect(screen.queryByText('30Y国债ATR通道')).toBeNull()
  })

  it('空列表显示引导空态', async () => {
    vi.mocked(api.getStrategyConversations).mockResolvedValue({ items: [] })
    renderPage()
    await waitFor(() =>
      expect(screen.getByText('还没有策略会话，在下方输入一句话想法开始')).toBeTruthy(),
    )
  })

  it('输入想法提交后调用创建接口', async () => {
    renderPage()
    await screen.findByText('验收通过')
    const textarea = screen.getByPlaceholderText(/输入一句话策略想法/)
    fireEvent.change(textarea, { target: { value: '做一个5/20金叉策略' } })
    fireEvent.submit(document.querySelector('.sw-composer') as HTMLFormElement)
    await waitFor(() =>
      expect(api.createStrategyConversation).toHaveBeenCalledWith('做一个5/20金叉策略'),
    )
  })
})
