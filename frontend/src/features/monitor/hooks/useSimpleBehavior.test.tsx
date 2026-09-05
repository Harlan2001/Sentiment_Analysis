import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/test/server'
import { createTestQueryClient } from '@/test/render'
import { useBehaviorLogs, useBehaviorStats } from './useSimpleBehavior'

const wrapper = ({ children }: { children?: ReactNode }) => (
  <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
)

const STATS_URL = '/sapi/dashboard/behavior-stats'

describe('useBehaviorStats — enabled 按需加载', () => {
  it('enabled=false 时不发起请求并保持 idle', async () => {
    let called = 0
    server.use(
      http.get(STATS_URL, () => {
        called += 1
        return HttpResponse.json({})
      }),
    )
    const { result } = renderHook(() => useBehaviorStats(7, false), { wrapper })
    expect(result.current.fetchStatus).toBe('idle')

    await new Promise((r) => setTimeout(r, 150))
    expect(called).toBe(0)
    expect(result.current.fetchStatus).toBe('idle')
  })

  it('enabled=true 时请求成功并返回数据', async () => {
    const body = { total_events: 42, active_users: 3 }
    server.use(http.get(STATS_URL, () => HttpResponse.json(body)))
    const { result } = renderHook(() => useBehaviorStats(7, true), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(body)
  })

  it('enabled=true 且请求失败时 isError', async () => {
    server.use(
      http.get(STATS_URL, () => HttpResponse.json(null, { status: 500 })),
    )
    const { result } = renderHook(() => useBehaviorStats(3, true), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})


describe('useBehaviorLogs — enabled 按需加载', () => {
  const LOGS_URL = '/sapi/dashboard/behavior-logs'

  it('enabled=true 请求成功并返回 items', async () => {
    server.use(http.get(LOGS_URL, () => HttpResponse.json({ items: [{ id: 'l1' }], total: 1 })))
    const { result } = renderHook(() => useBehaviorLogs({ limit: 20 }, true), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.items).toHaveLength(1)
  })

  it('enabled=false 不发起请求', async () => {
    let called = 0
    server.use(
      http.get(LOGS_URL, () => {
        called += 1
        return HttpResponse.json({ items: [] })
      }),
    )
    renderHook(() => useBehaviorLogs({}, false), { wrapper })
    await new Promise((r) => setTimeout(r, 150))
    expect(called).toBe(0)
  })

  it('请求失败时 isError', async () => {
    server.use(http.get(LOGS_URL, () => HttpResponse.json(null, { status: 500 })))
    const { result } = renderHook(() => useBehaviorLogs({}, true), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})