import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/test/server'
import { createTestQueryClient } from '@/test/render'
import { useCoreDashboard } from './useCoreDashboard'

const wrapper = ({ children }: { children?: ReactNode }) => (
  <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
)

describe('useCoreDashboard', () => {
  it('加载成功返回核心指标', async () => {
    const body = { news: { total: 10 }, factors: { total: 5 }, service_health: 'ok' }
    server.use(http.get('/sapi/dashboard/core', () => HttpResponse.json(body)))
    const { result } = renderHook(() => useCoreDashboard(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(body)
  })

  it('请求失败时 isError 为真', async () => {
    server.use(
      http.get('/sapi/dashboard/core', () => HttpResponse.json(null, { status: 500 })),
    )
    const { result } = renderHook(() => useCoreDashboard(), { wrapper })
    // hook 内 retry: 2 —— isError 要等重试耗尽(指数退避 ~3s)才成立
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 8000 })
  })
})