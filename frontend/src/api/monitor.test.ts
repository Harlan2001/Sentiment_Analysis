import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { API_PREFIX } from '@/api/client'
import { server } from '@/test/server'
import {
  fetchDashboardCore,
  fetchDashboardHistory,
  triggerDashboardSnapshot,
} from '@/api/monitor'

describe('monitor api — 裸 fetch 封装', () => {
  it('fetchDashboardCore 成功返回 payload', async () => {
    const body = { panels: ['news', 'factor'], generated_at: '2026-09-01 10:00' }
    server.use(http.get(`${API_PREFIX}/dashboard/core`, () => HttpResponse.json(body)))
    const data = await fetchDashboardCore()
    expect(data).toEqual(body)
  })

  it('fetchDashboardCore 非 2xx 抛服务器错误', async () => {
    server.use(
      http.get(`${API_PREFIX}/dashboard/core`, () =>
        HttpResponse.json({ error: 'boom' }, { status: 500 }),
      ),
    )
    await expect(fetchDashboardCore()).rejects.toThrow(/服务器错误 500/)
  })

  it('fetchDashboardHistory 附带 days 参数', async () => {
    let url = ''
    server.use(
      http.get(`${API_PREFIX}/dashboard/history`, (info) => {
        url = info.request.url
        return HttpResponse.json([])
      }),
    )
    await fetchDashboardHistory(14)
    expect(url).toContain('days=14')
  })

  it('fetchDashboardHistory 失败抛固定文案', async () => {
    server.use(
      http.get(`${API_PREFIX}/dashboard/history`, () =>
        HttpResponse.json(null, { status: 400 }),
      ),
    )
    await expect(fetchDashboardHistory()).rejects.toThrow('历史快照获取失败')
  })

  it('triggerDashboardSnapshot POST 成功', async () => {
    server.use(
      http.post(`${API_PREFIX}/dashboard/snapshot`, () =>
        HttpResponse.json({ success: true, snapshot_id: 7 }),
      ),
    )
    const res = await triggerDashboardSnapshot()
    expect(res.snapshot_id).toBe(7)
  })

  it('triggerDashboardSnapshot 失败抛固定文案', async () => {
    server.use(
      http.post(`${API_PREFIX}/dashboard/snapshot`, () =>
        HttpResponse.json(null, { status: 400 }),
      ),
    )
    await expect(triggerDashboardSnapshot()).rejects.toThrow('快照生成失败')
  })
})