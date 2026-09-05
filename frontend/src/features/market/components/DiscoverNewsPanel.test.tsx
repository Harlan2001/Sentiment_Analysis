import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import DiscoverNewsPanel from './DiscoverNewsPanel'
import { renderWithProviders } from '@/test/render'
import { server } from '@/test/server'
import { API_PREFIX } from '@/api/client'
import type { DiscoverNewsItem } from '@/types'

function makeItem(overrides: Partial<DiscoverNewsItem> = {}): DiscoverNewsItem {
  return {
    id: Math.floor(Math.random() * 1e6),
    title: '测试新闻',
    direction: 'positive',
    source: '来源',
    pub_time: '2026-09-01 10:00',
    thumbnail: null,
    summary: '摘要',
    ...overrides,
  } as DiscoverNewsItem
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
})
afterEach(() => {
  vi.unstubAllGlobals()
})

function mockDiscover(items: DiscoverNewsItem[]) {
  server.use(
    http.get(`${API_PREFIX}/discover/news`, () =>
      HttpResponse.json({
        data: {
          items,
          total: items.length,
          page: 1,
          page_size: 20,
          total_pages: 1,
        },
      }),
    ),
  )
}

describe('DiscoverNewsPanel', () => {
  it('渲染新闻标题并支持点击回调', async () => {
    const items = [
      makeItem({ id: 1, title: '有图新闻', thumbnail: 'http://img.local/1.png' }),
      makeItem({ id: 2, title: '无图新闻' }),
    ]
    mockDiscover(items)
    const onClick = vi.fn()
    renderWithProviders(<DiscoverNewsPanel onNewsClick={onClick} />)

    await waitFor(() => expect(screen.getAllByText('有图新闻').length).toBeGreaterThan(0))
    const noImg = screen.getByText('无图新闻')
    expect(noImg).toBeInTheDocument()

    await userEvent.click(noImg)
    expect(onClick).toHaveBeenCalledWith(2)
  })

  it('空数据展示占位文案', async () => {
    mockDiscover([])
    renderWithProviders(<DiscoverNewsPanel onNewsClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('暂无新闻数据')).toBeInTheDocument())
  })

  it('请求失败展示加载失败', async () => {
    server.use(
      http.get(`${API_PREFIX}/discover/news`, () =>
        HttpResponse.json({ detail: '错误' }, { status: 500 }),
      ),
    )
    renderWithProviders(<DiscoverNewsPanel onNewsClick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('加载失败')).toBeInTheDocument())
  })
})