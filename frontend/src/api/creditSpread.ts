/**
 * 信用利差 API。
 *
 * 数据源：中债中短期票据收益率曲线（与国债曲线同一接口）。
 * 利差 = 信用债收益率 − 同期限国债收益率。
 *
 * 限制：该源只提供整体曲线，**不能按 AAA/AA 分档**。
 */
import { API_PREFIX as BASE, request } from './client'
import type { CreditSpreadOverview, CreditSpreadSyncResult, CreditSpreadTerms } from '@/types'

export function fetchCreditSpreadOverview(term = '10Y'): Promise<CreditSpreadOverview> {
  return request<CreditSpreadOverview>(
    `${BASE}/credit-spread/overview?term=${encodeURIComponent(term)}`,
  )
}

export function fetchCreditSpreadTerms(): Promise<CreditSpreadTerms> {
  return request<CreditSpreadTerms>(`${BASE}/credit-spread/terms`)
}

export function syncCreditSpread(days = 365): Promise<CreditSpreadSyncResult> {
  return request<CreditSpreadSyncResult>(`${BASE}/credit-spread/sync?days=${days}`, {
    method: 'POST',
  })
}