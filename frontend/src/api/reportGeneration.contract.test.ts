import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { API_PREFIX } from '@/api/client'
import { server } from '@/test/server'
import { batchReanalyzeReports, reanalyzeReport } from '@/api/reportGeneration'

/**
 * 板块二 P0-3 前端 API 契约
 * - reanalyzeReport：单篇重新分析，必须显式带 force=true
 * - batchReanalyzeReports：按筛选批量重跑，筛选条件原样作为 JSON body
 */

describe('reportGeneration api · P0-3 重新分析', () => {
  it('reanalyzeReport 以 force=true 提交重新分析', async () => {
    let url = ''
    server.use(
      http.post(`${API_PREFIX}/research/2/analyze`, (info) => {
        url = info.request.url
        return HttpResponse.json({ data: { report_id: 2, status: 'processing' } })
      }),
    )

    const result = await reanalyzeReport(2)

    expect(url).toContain('/research/2/analyze')
    expect(url).toContain('force=true')
    expect(result.status).toBe('processing')
  })

  it('batchReanalyzeReports 按筛选条件批量触发并重传筛选', async () => {
    let body: unknown = null
    server.use(
      http.post(`${API_PREFIX}/research/reanalyze/batch`, async (info) => {
        body = await info.request.json()
        return HttpResponse.json({ data: { triggered: 3, skipped: 1 } })
      }),
    )

    const result = await batchReanalyzeReports({ institution: 'XX 证券' })

    expect(body).toEqual({ institution: 'XX 证券' })
    expect(result.triggered).toBe(3)
  })
})
