import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import DiscoverNewsPanel from './DiscoverNewsPanel'
import { renderWithProviders } from '@/test/render'
import { server } from '@/test/server'
import { API_PREFIX } from '@/api/client'
import type { DiscoverNewsItem, RecommendRankingsResponse } from '@/types'

function makeItem(overrides: Partial<DiscoverNewsItem> = {}): DiscoverNewsItem {
  return {
    id: Math.floor(Math.random() * 1e6),
    title: '测试新闻',
    summary: '',
    direction: 'positive',
    source: 'wallstreetcn',
    source_name: '数据源1',
    pub_time: '2026-09-01 10:00',
    thumbnail: null,
    reason: '',
    factors: [],
    importance_score: null,
    final_score: null,
    score_signals: null,
    top_category: null,
    ...overrides,
  }
}

function emptyRankings(): RecommendRankingsResponse {
  return {
    days: 7,
    top_news: [],
    hot_factors: [],
    direction_board: { positive: [], negative: [] },
    category_distribution: [],
  }
}

// DiscoverNewsPanel 在挂载时创建 IntersectionObserver —— jsdom 没有该 API, 需 stub。
class FakeIntersectionObserver {
  constructor(
    public callback: IntersectionObserverCallback,
    public options?: IntersectionObserverInit,
  ) {}
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()
  takeRecords = vi.fn(() => [])
  root = null
  rootMargin = '0px'
  thresholds = [0]
}

beforeEach(() => {
  vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver as unknown as typeof IntersectionObserver)
  localStorage.clear()
})
afterEach(() => {
  vi.unstubAllGlobals()
})

const capturedUrls: string[] = []

function mockDiscover(items: DiscoverNewsItem[]) {
  capturedUrls.length = 0
  server.use(
    http.get(`${API_PREFIX}/discover/news`, ({ request }) => {
      capturedUrls.push(request.url)
      return HttpResponse.json({
        data: { items, total: items.length, page: 1, page_size: 20, total_pages: 1 },
      })
    }),
  )
}

function mockRankings(payload: RecommendRankingsResponse = emptyRankings()) {
  server.use(
    http.get(`${API_PREFIX}/discover/recommend-rankings`, () =>
      HttpResponse.json({ data: payload }),
    ),
  )
}

const noop = () => {}

describe('DiscoverNewsPanel', () => {
  it('以紧凑行渲染新闻标题并支持点击回调', async () => {
    const items = [
      makeItem({ id: 1, title: '有图新闻', thumbnail: 'http://img.local/1.png' }),
      makeItem({ id: 2, title: '无图新闻' }),
    ]
    mockDiscover(items)
    const onNewsClick = vi.fn()
    renderWithProviders(<DiscoverNewsPanel onNewsClick={onNewsClick} onFactorClick={noop} />)

    await waitFor(() => expect(screen.getAllByText('有图新闻').length).toBeGreaterThan(0))
    const noImg = screen.getByText('无图新闻')
    expect(noImg).toBeInTheDocument()

    await userEvent.click(noImg)
    expect(onNewsClick).toHaveBeenCalledWith(2)
  })

  it('空数据展示占位文案', async () => {
    mockDiscover([])
    renderWithProviders(<DiscoverNewsPanel onNewsClick={vi.fn()} onFactorClick={noop} />)
    await waitFor(() => expect(screen.getByText('暂无新闻数据')).toBeInTheDocument())
  })

  it('请求失败展示加载失败，点击重试后恢复', async () => {
    mockDiscover([makeItem({ id: 1, title: '重试后新闻' })])
    server.use(
      http.get(
        `${API_PREFIX}/discover/news`,
        () => HttpResponse.json({ detail: '错误' }, { status: 500 }),
        { once: true },
      ),
    )
    renderWithProviders(<DiscoverNewsPanel onNewsClick={vi.fn()} onFactorClick={noop} />)
    await waitFor(() => expect(screen.getByText('加载失败')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: '重试' }))
    await waitFor(() => expect(screen.getByText('重试后新闻')).toBeInTheDocument())
  })

  it('默认按时间排序请求并携带 sort=latest', async () => {
    mockDiscover([makeItem({ id: 1 })])
    renderWithProviders(<DiscoverNewsPanel onNewsClick={noop} onFactorClick={noop} />)
    await waitFor(() => expect(capturedUrls).toHaveLength(1))
    expect(capturedUrls[0]).toContain('sort=latest')
  })

  it('推荐排序 URL 下请求 sort=recommend&days=7，展示分值与排行榜', async () => {
    mockDiscover([
      makeItem({
        id: 7,
        title: '推荐新闻',
        final_score: 72.6,
        importance_score: 80,
        reason: '推荐理由摘要',
      }),
    ])
    mockRankings({
      ...emptyRankings(),
      top_news: [{
        id: 7, title: '榜单新闻', pub_time: '2026-11-05 09:00', source_name: '数据源1',
        direction: 'positive', importance_score: 80, final_score: 72.6, top_category: 'POLICY',
      }],
    })

    renderWithProviders(<DiscoverNewsPanel onNewsClick={noop} onFactorClick={noop} />, {
      route: '/market?sort=recommend',
    })

    await waitFor(() => expect(capturedUrls.some((u) => u.includes('sort=recommend'))).toBe(true))
    const recommendUrl = capturedUrls.find((u) => u.includes('sort=recommend'))!
    expect(recommendUrl).toContain('days=7')

    // 行展示整数分值（72.6 → 73）与 reason 摘要；榜单同分也渲染 73，共两处
    await waitFor(() => expect(screen.getByText('推荐新闻')).toBeInTheDocument())
    expect(screen.getAllByText('73')).toHaveLength(2)
    expect(screen.getByText('推荐理由摘要')).toBeInTheDocument()

    // 排行榜折叠面板渲染且榜单条目可点
    expect(screen.getByRole('heading', { name: '推荐排行榜' })).toBeInTheDocument()
    expect(screen.getByText('榜单新闻')).toBeInTheDocument()
  })

  it('点击分段控件切换排序并同步路由参数（aria-pressed 翻转）', async () => {
    mockDiscover([makeItem({ id: 1, title: '切换新闻' })])
    mockRankings()

    renderWithProviders(<DiscoverNewsPanel onNewsClick={noop} onFactorClick={noop} />, {
      route: '/market',
    })
    await waitFor(() => expect(screen.getByText('切换新闻')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: '时间排序' })).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(screen.getByRole('button', { name: '推荐排序' }))
    await waitFor(() =>
      expect(capturedUrls.some((u) => u.includes('sort=recommend'))).toBe(true),
    )
    // MemoryRouter 内 useSearchParams 驱动：分段控件按下态翻转即证明 ?sort= 已同步
    expect(screen.getByRole('button', { name: '推荐排序' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '时间排序' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('方向筛选写入请求参数', async () => {
    mockDiscover([makeItem({ id: 1 })])
    renderWithProviders(<DiscoverNewsPanel onNewsClick={noop} onFactorClick={noop} />)
    expect(await screen.findByText('测试新闻')).toBeInTheDocument()

    const directionDropdown = screen.getByRole('button', { name: /方向/ })
    await userEvent.click(directionDropdown)
    await userEvent.click(screen.getByRole('button', { name: '利多' }))

    await waitFor(() =>
      expect(capturedUrls.some((u) => u.includes('direction=positive'))).toBe(true),
    )
  })

  it('推荐模式空态提供切回时间排序按钮', async () => {
    mockDiscover([])
    mockRankings()
    renderWithProviders(<DiscoverNewsPanel onNewsClick={noop} onFactorClick={noop} />, {
      route: '/market?sort=recommend',
    })

    await waitFor(() => expect(screen.getByText('当前筛选下暂无可推荐新闻')).toBeInTheDocument())
    const back = screen.getByRole('button', { name: '切回时间排序' })
    await userEvent.click(back)
    await waitFor(() =>
      expect(capturedUrls.some((u) => u.includes('sort=latest'))).toBe(true),
    )
    expect(screen.getByRole('button', { name: '时间排序' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('排行榜请求失败只降级提示，新闻流仍可用', async () => {
    mockDiscover([makeItem({ id: 1, title: '不受影响的新闻' })])
    server.use(
      http.get(
        `${API_PREFIX}/discover/recommend-rankings`,
        () => HttpResponse.json({ detail: '错误' }, { status: 500 }),
      ),
    )
    renderWithProviders(<DiscoverNewsPanel onNewsClick={noop} onFactorClick={noop} />, {
      route: '/market?sort=recommend',
    })

    await waitFor(() =>
      expect(screen.getByText('排行榜暂不可用，不影响下方新闻流')).toBeInTheDocument(),
    )
    expect(screen.getByText('不受影响的新闻')).toBeInTheDocument()
  })

  it('因子榜点击透传 onFactorClick', async () => {
    mockDiscover([makeItem({ id: 1, title: '新闻流' })])
    mockRankings({
      ...emptyRankings(),
      hot_factors: [{ id: 55, name: '降准因子', category: 'POLICY', news_count: 9, hit_rate: 0.6 }],
    })
    const onFactorClick = vi.fn()
    renderWithProviders(<DiscoverNewsPanel onNewsClick={noop} onFactorClick={onFactorClick} />, {
      route: '/market?sort=recommend',
    })

    // isLoading 期间组件早返回骨架屏，需等新闻流落屏后排行榜才挂载
    expect(await screen.findByText('新闻流')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '因子榜' }))
    const factorButton = await screen.findByRole('button', { name: /降准因子/ })
    await userEvent.click(factorButton)
    expect(onFactorClick).toHaveBeenCalledWith(55)
  })
})
