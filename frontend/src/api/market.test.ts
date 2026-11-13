import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { API_PREFIX } from '@/api/client'
import { server } from '@/test/server'
import { fetchAllFactors, fetchNewsById, fetchReturnsCalendar, fetchSimilarNews } from '@/api/market'

const NEWS_BASE = `${API_PREFIX}/news`

describe('market api — request 封装', () => {
  it('fetchNewsById 成功解包 data', async () => {
    const payload = { news_id: 42, title: '央行降息', content: '…' }
    server.use(http.get(`${NEWS_BASE}/42`, () => HttpResponse.json({ data: payload })))
    const item = await fetchNewsById(42)
    expect(item).toEqual(payload)
  })

  it('fetchNewsById 附加 model / include_all_models 参数', async () => {
    let url = ''
    server.use(
      http.get(`${NEWS_BASE}/1`, (info) => {
        url = info.request.url
        return HttpResponse.json({ data: { news_id: 1 } })
      }),
    )
    await fetchNewsById(1, 'glm', true)
    const u = new URL(url)
    expect(u.searchParams.get('model')).toBe('glm')
    expect(u.searchParams.get('include_all_models')).toBe('true')
  })

  it('非 2xx 抛 FastAPI detail 错误', async () => {
    server.use(
      http.get(`${NEWS_BASE}/404`, () =>
        HttpResponse.json({ detail: '新闻不存在' }, { status: 404 }),
      ),
    )
    await expect(fetchNewsById(404)).rejects.toThrow('新闻不存在')
  })

  it('后端异常(500)抛通用错误', async () => {
    server.use(
      http.get(`${NEWS_BASE}/500`, () => HttpResponse.json({ data: null }, { status: 500 })),
    )
    await expect(fetchNewsById(500)).rejects.toThrow('请求失败')
  })

  it('fetchAllFactors 解包 data.factors', async () => {
    const factors = [{ id: 1, code: 'RATE', name: '利率' }]
    server.use(http.get(`${API_PREFIX}/factors`, () => HttpResponse.json({ data: { factors } })))
    const res = await fetchAllFactors()
    expect(res.factors).toHaveLength(1)
    expect(res.factors[0].code).toBe('RATE')
  })

  it('fetchReturnsCalendar 只发送自然月 start/end，不发送无效 selected 参数', async () => {
    let url = ''
    server.use(http.get(`${API_PREFIX}/returns/calendar`, (info) => {
      url = info.request.url
      return HttpResponse.json({ data: { days: [], yields_by_date: {}, news_by_date: {}, macro_by_month: {}, query: { start: '2026-11-01', end: '2026-11-30' } } })
    }))
    await fetchReturnsCalendar({ start: '2026-11-01', end: '2026-11-30' })
    const parsed = new URL(url)
    expect(parsed.searchParams.get('start')).toBe('2026-11-01')
    expect(parsed.searchParams.get('end')).toBe('2026-11-30')
    expect(parsed.searchParams.has('selected')).toBe(false)
    expect([...parsed.searchParams.keys()].sort()).toEqual(['end', 'start'])
  })

  it('fetchSimilarNews 解析 data 数组', async () => {
    server.use(
      http.get(`${API_PREFIX}/news/similar`, () =>
        HttpResponse.json({ data: [{ id: 2, title: '相似新闻' }] }),
      ),
    )
    const list = await fetchSimilarNews(99)
    expect(Array.isArray(list)).toBe(true)
    expect(list).toHaveLength(1)
  })
})