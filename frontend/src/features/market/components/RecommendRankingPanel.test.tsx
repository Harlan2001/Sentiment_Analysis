import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import RecommendRankingPanel from './RecommendRankingPanel'
import { renderWithProviders } from '@/test/render'
import { server } from '@/test/server'
import { API_PREFIX } from '@/api/client'
import type { RecommendRankingsResponse } from '@/types'

const COLLAPSE_KEY = 'market:recommend-ranking-collapsed'

function emptyRankings(): RecommendRankingsResponse {
  return {
    days: 7,
    top_news: [],
    hot_factors: [],
    direction_board: { positive: [], negative: [] },
    category_distribution: [],
  }
}

function mockRankings(payload: RecommendRankingsResponse) {
  server.use(
    http.get(`${API_PREFIX}/discover/recommend-rankings`, () =>
      HttpResponse.json({ data: payload }),
    ),
  )
}

const noop = () => {}

beforeEach(() => {
  localStorage.clear()
})

describe('RecommendRankingPanel', () => {
  it('渲染新闻榜并把点击透传给 onNewsClick', async () => {
    mockRankings({
      ...emptyRankings(),
      top_news: [
        {
          id: 101, title: '榜首新闻', pub_time: '2026-11-05 09:00', source_name: '数据源1',
          direction: 'positive', importance_score: 88, final_score: 80.1, top_category: 'POLICY',
        },
      ],
    })
    const onNewsClick = vi.fn()
    renderWithProviders(<RecommendRankingPanel days={7} onNewsClick={onNewsClick} onFactorClick={noop} />)

    const row = await screen.findByRole('button', { name: /榜首新闻/ })
    await userEvent.click(row)
    expect(onNewsClick).toHaveBeenCalledWith(101)

    // 副标题展示窗口天数，分值四舍五入为整数
    expect(screen.getByText(/近 7 天/)).toBeInTheDocument()
    expect(screen.getByText('80')).toBeInTheDocument()
  })

  it('空榜展示占位文案', async () => {
    mockRankings(emptyRankings())
    renderWithProviders(<RecommendRankingPanel days={7} onNewsClick={noop} onFactorClick={noop} />)
    expect(await screen.findByText('暂无榜单数据')).toBeInTheDocument()
  })

  it('因子榜切换后渲染因子条目、类别分布并透传 onFactorClick', async () => {
    mockRankings({
      ...emptyRankings(),
      hot_factors: [
        { id: 55, name: '降准因子', category: 'POLICY', news_count: 9, hit_rate: 0.6 },
        { id: 56, name: 'MLF 因子', category: 'LIQUIDITY', news_count: 3, hit_rate: null },
      ],
      category_distribution: [
        { category: 'POLICY', news_count: 9, share: 0.6 },
        { category: 'LIQUIDITY', news_count: 6, share: 0.4 },
      ],
    })
    const onFactorClick = vi.fn()
    renderWithProviders(<RecommendRankingPanel days={7} onNewsClick={noop} onFactorClick={onFactorClick} />)

    await userEvent.click(screen.getByRole('button', { name: '因子榜' }))
    const factorButton = await screen.findByRole('button', { name: /降准因子/ })
    expect(factorButton).toBeInTheDocument()
    await userEvent.click(factorButton)
    expect(onFactorClick).toHaveBeenCalledWith(55)

    // 类别分布走中文标签 + 整数百分比
    expect(screen.getByText('政策监管')).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
    expect(screen.getByText('40%')).toBeInTheDocument()
  })

  it('多空榜分利多/利空两组，点击条目走 onNewsClick', async () => {
    mockRankings({
      ...emptyRankings(),
      direction_board: {
        positive: [{
          id: 201, title: '利多新闻', pub_time: '2026-11-05 09:00', source_name: '数据源1',
          direction: 'positive', importance_score: 70, final_score: 65, top_category: 'MACRO',
        }],
        negative: [{
          id: 202, title: '利空新闻', pub_time: '2026-11-04 09:00', source_name: '数据源2',
          direction: 'negative', importance_score: 72, final_score: 60, top_category: 'RISK',
        }],
      },
    })
    const onNewsClick = vi.fn()
    renderWithProviders(<RecommendRankingPanel days={7} onNewsClick={onNewsClick} onFactorClick={noop} />)

    await userEvent.click(screen.getByRole('button', { name: '多空榜' }))
    expect(await screen.findByRole('heading', { name: '利多 Top 5' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '利空 Top 5' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /利空新闻/ }))
    expect(onNewsClick).toHaveBeenCalledWith(202)
  })

  it('折叠/展开生效并把折叠态持久化到 localStorage', async () => {
    mockRankings({
      ...emptyRankings(),
      top_news: [{
        id: 1, title: '折叠测试新闻', pub_time: '2026-11-05 09:00', source_name: '数据源1',
        direction: 'neutral', importance_score: 50, final_score: 40, top_category: null,
      }],
    })
    const first = renderWithProviders(
      <RecommendRankingPanel days={7} onNewsClick={noop} onFactorClick={noop} />,
    )
    expect(await screen.findByRole('button', { name: /折叠测试新闻/ })).toBeInTheDocument()

    const toggle = screen.getByRole('button', { name: /推荐排行榜/ })
    await userEvent.click(toggle)

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /折叠测试新闻/ })).not.toBeInTheDocument(),
    )
    expect(localStorage.getItem(COLLAPSE_KEY)).toBe('1')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    // 重新挂载：读取 localStorage 后默认折叠
    first.unmount()
    renderWithProviders(<RecommendRankingPanel days={7} onNewsClick={noop} onFactorClick={noop} />)
    expect(screen.queryByRole('button', { name: /折叠测试新闻/ })).not.toBeInTheDocument()
  })

  it('请求失败展示降级提示而非抛错', async () => {
    server.use(
      http.get(
        `${API_PREFIX}/discover/recommend-rankings`,
        () => HttpResponse.json({ detail: '错误' }, { status: 500 }),
      ),
    )
    renderWithProviders(<RecommendRankingPanel days={7} onNewsClick={noop} onFactorClick={noop} />)
    expect(await screen.findByText('排行榜暂不可用，不影响下方新闻流')).toBeInTheDocument()
  })
})
