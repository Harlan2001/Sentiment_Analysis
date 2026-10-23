/**
 * 国债期货持仓 API（中金所成交持仓排名）。
 *
 * 仅覆盖 T(10年) / TF(5年) / TS(2年) / TL(30年) 四个国债期货品种。
 * 数据为每日快照，按交易日积累。
 */
import { API_PREFIX as BASE, request } from './client'
import type {
  FuturesOverviewResponse,
  FuturesRankingResponse,
  FuturesSyncResult,
  FuturesTrendResponse,
} from '@/types'

export function fetchFuturesOverview(): Promise<FuturesOverviewResponse> {
  return request<FuturesOverviewResponse>(`${BASE}/futures/overview`)
}

export function fetchFuturesRanking(
  contract: string,
  tradeDate?: string,
): Promise<FuturesRankingResponse> {
  const params = new URLSearchParams({ contract })
  if (tradeDate) params.set('trade_date', tradeDate)
  return request<FuturesRankingResponse>(`${BASE}/futures/ranking?${params.toString()}`)
}

export function fetchFuturesTrend(
  variety: string,
  limit = 60,
): Promise<FuturesTrendResponse> {
  return request<FuturesTrendResponse>(
    `${BASE}/futures/trend?variety=${encodeURIComponent(variety)}&limit=${limit}`,
  )
}

/** 抓取指定交易日（缺省今天）的持仓排名并入库。 */
export function syncFuturesPositions(tradeDate?: string): Promise<FuturesSyncResult> {
  const suffix = tradeDate ? `?trade_date=${tradeDate}` : ''
  return request<FuturesSyncResult>(`${BASE}/futures/sync${suffix}`, { method: 'POST' })
}