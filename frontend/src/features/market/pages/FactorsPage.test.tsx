import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import FactorsPage from './FactorsPage'
import { renderWithProviders } from '@/test/render'
import { server } from '@/test/server'
import type { FactorDefinition } from '@/api/market'

function makeFactor(overrides: Partial<FactorDefinition> = {}): FactorDefinition {
  return {
    id: 1,
    code: 'RATE',
    name: '利率因子',
    category: 'MACRO',
    factor_type: 'quantitative',
    news_count: 10,
    recent_news_count: 3,
    activity_7d: 1,
    activity_30d: 3,
    activity_365d: 10,
    positive_count: 2,
    negative_count: 1,
    neutral_count: 0,
    current_direction: '利多',
    heat_level: '中',
    trend_7d: [1, 2, 3],
    latest_event_at: '2026-09-01 10:00',
    ...overrides,
  } as FactorDefinition
}

const OVERVIEW = '/sapi/factors/activity-overview'

describe('FactorsPage — 因子信号视图', () => {
  it('渲染因子列表并展示名称/方向/热度', async () => {
    server.use(
      http.get(OVERVIEW, () =>
        HttpResponse.json({ data: { factors: [makeFactor()] } }),
      ),
    )
    renderWithProviders(<FactorsPage />)

    // 因子名同时出现在表格行与侧栏 Top10 排名, 故用 findAllByText
    expect((await screen.findAllByText('利率因子')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('利多').length).toBeGreaterThan(0)
    expect(screen.getByText('RATE')).toBeInTheDocument()
  })

  it('搜索无命中时显示 0 个因子', async () => {
    server.use(
      http.get(OVERVIEW, () =>
        HttpResponse.json({
          data: { factors: [makeFactor(), makeFactor({ id: 2, code: 'CPI', name: '通胀因子' })] },
        }),
      ),
    )
    renderWithProviders(<FactorsPage />)
    expect((await screen.findAllByText('通胀因子')).length).toBeGreaterThan(0)

    await userEvent.type(screen.getByPlaceholderText('搜索因子名称或代码'), '完全不存在')
    await waitFor(() => expect(screen.getByText('0 个因子')).toBeInTheDocument())
  })

  it('加载失败展示错误文案', async () => {
    server.use(
      http.get(OVERVIEW, () => HttpResponse.json({ detail: 'boom' }, { status: 500 })),
    )
    renderWithProviders(<FactorsPage />)
    expect(await screen.findByText('因子数据加载失败')).toBeInTheDocument()
  })
})