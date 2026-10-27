/**
 * 中美利差 API。
 *
 * 数据源：美国财政部官方 CSV（合规、免密钥）。
 * 利差 = 中债 10Y − 美债 10Y，只在双方都有数据的日期计算（不插值）。
 */
import { API_PREFIX as BASE, request } from './client'
import type { TreasurySpreadOverview, TreasurySyncResult } from '@/types'

export function fetchTreasurySpread(term = '10Y'): Promise<TreasurySpreadOverview> {
  return request<TreasurySpreadOverview>(`${BASE}/treasury/overview?term=${encodeURIComponent(term)}`)
}

export function syncTreasury(year?: number): Promise<TreasurySyncResult> {
  const suffix = year ? `?year=${year}` : ''
  return request<TreasurySyncResult>(`${BASE}/treasury/sync${suffix}`, { method: 'POST' })
}