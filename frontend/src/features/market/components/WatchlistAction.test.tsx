import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { WatchlistAction } from './WatchlistAction'
import { server } from '@/test/server'

const WATCH = '/sapi/watchlist'

afterEach(() => {
  vi.restoreAllMocks()
})

function stubWatchlist(items: unknown[]) {
  server.use(http.get(WATCH, () => HttpResponse.json({ data: { items } })))
}

describe('WatchlistAction', () => {
  it('未关注时显示 + 关注, 点击后调 API 并变已关注', async () => {
    // 用可变数组模拟真实后端: 关注成功后 GET 也能看到新项(触发 watchlist-changed 刷新)
    const items: unknown[] = []
    server.use(
      http.get(WATCH, () => HttpResponse.json({ data: { items } })),
      http.post(WATCH, async (info) => {
        const body = (await info.request.json()) as {
          object_type: string
          object_id: string
          title: string
        }
        items.push(body)
        return HttpResponse.json({ data: { id: 'w1', ...body } })
      }),
    )
    render(<WatchlistAction objectType="news" objectId="1" title="某新闻" />)

    const btn = await screen.findByRole('button', { name: '+ 关注' })
    await userEvent.click(btn)
    expect(await screen.findByText('已关注')).toBeInTheDocument()
  })

  it('已在自选列表时直接显示已关注', async () => {
    stubWatchlist([{ object_type: 'news', object_id: '1', title: '新闻' }])
    render(<WatchlistAction objectType="news" objectId="1" title="新闻" />)
    expect(await screen.findByText('已关注')).toBeInTheDocument()
  })

  it('加载失败时显示可重试', async () => {
    server.use(http.get(WATCH, () => HttpResponse.json(null, { status: 500 })))
    render(<WatchlistAction objectType="factor" objectId="F1" title="利率" />)
    expect(await screen.findByText('重试关注')).toBeInTheDocument()
  })

  it('关注失败后变为重试关注', async () => {
    stubWatchlist([])
    server.use(http.post(WATCH, () => HttpResponse.json({ detail: 'err' }, { status: 400 })))
    render(<WatchlistAction objectType="news" objectId="2" title="新闻二" />)

    const btn = await screen.findByRole('button', { name: '+ 关注' })
    await userEvent.click(btn)
    expect(await screen.findByText('重试关注')).toBeInTheDocument()
  })
})