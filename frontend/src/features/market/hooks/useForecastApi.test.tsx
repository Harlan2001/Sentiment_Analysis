import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { API_PREFIX } from '@/api/client'
import { server } from '@/test/server'
import { createTestQueryClient } from '@/test/render'
import { useForecastReport } from './useForecastApi'
import type { ForecastPrediction, ForecastReport } from '@/types'

function report(trade_date: string, forecast_type: string, created_at: string): ForecastReport {
  return {
    trade_date,
    model_name: 'glm',
    prompt_version: 'v1',
    forecast_type,
    prediction: {} as ForecastPrediction,
    created_at,
  }
}

const wrapper = ({ children }: { children?: ReactNode }) => (
  <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
)

describe('useForecastReport', () => {
  it('加载成功后按类型分组 / 日期排序 / 算出最新报告', async () => {
    server.use(
      http.get(`${API_PREFIX}/forecast`, () =>
        HttpResponse.json({
          data: {
            count: 3,
            reports: [
              report('2026-09-02', 'short', '2026-09-02 10:00:00'),
              report('2026-09-01', 'short', '2026-09-01 09:00:00'),
              report('2026-09-01', 'long', '2026-09-01 08:00:00'),
            ],
          },
        }),
      ),
    )
    const { result } = renderHook(() => useForecastReport('2026-09-02'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const data = result.current.data!
    expect(data.predictionsByType.short).toHaveLength(2)
    expect(data.predictionsByType.long).toHaveLength(1)
    expect(data.sortedReports[0].trade_date).toBe('2026-09-02')
    expect(data.latestReport?.trade_date).toBe('2026-09-02')
  })

  it('请求失败时 isError 为真', async () => {
    server.use(
      http.get(`${API_PREFIX}/forecast`, () =>
        HttpResponse.json({ detail: '出错' }, { status: 500 }),
      ),
    )
    const { result } = renderHook(() => useForecastReport(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })
})