/**
 * 市场工作台 API（news / factors / forecast / macro-data / discover / returns）
 */
import type {
  NewsItem,
  SimilarNews,
  NewsYieldData,
  ForecastResponse,
  ForecastHistoryResponse,
  MacroIndicatorsResponse,
  MacroDataResponse,
  DiscoverNewsResponse,
  MarketPanelResponse,
  FactorDetailData,
  ReturnsCalendarResponse,
  ForecastDiagnosisResponse,
  FactorPerformanceResponse,
  BacktestOverviewResponse,
} from '@/types'
import { API_PREFIX as BASE, request } from './client'

export async function fetchNewsById(id: number, model?: string, includeAllModels: boolean = false): Promise<NewsItem> {
  let url = `${BASE}/news/${id}`
  const params = new URLSearchParams()
  if (model) {
    params.append('model', model)
  }
  if (includeAllModels) {
    params.append('include_all_models', 'true')
  }
  const query = params.toString()
  if (query) {
    url += `?${query}`
  }
  return request<NewsItem>(url)
}

export function fetchSimilarNews(newsId: number): Promise<SimilarNews[]> {
  return request<SimilarNews[]>(`${BASE}/news/similar?news_id=${newsId}`)
}

export function fetchNewsYieldData(
  newsId: number,
  period: string = '10年',
  windowBefore: number = 10,
  windowAfter: number = 10,
): Promise<NewsYieldData> {
  return request<NewsYieldData>(
    `${BASE}/news/${newsId}/yield?period=${encodeURIComponent(period)}&window_before=${windowBefore}&window_after=${windowAfter}`,
  )
}

export interface FactorDefinition {
  id: number
  code: string
  name: string
  category: string
  factor_type?: string
  news_count: number
  recent_news_count: number
  activity_7d: number
  activity_30d: number
  activity_365d: number
  positive_count: number
  negative_count: number
  neutral_count: number
  current_direction: '利多' | '利空' | '中性'
  heat_level: '高' | '中' | '低'
  trend_7d: number[]
  latest_event_at: string | null
}

export interface AllFactorsResponse {
  factors: FactorDefinition[]
}

export function fetchAllFactors(): Promise<AllFactorsResponse> {
  return request<AllFactorsResponse>(`${BASE}/factors`)
}

export function fetchFactorActivityOverview(): Promise<AllFactorsResponse> {
  return request<AllFactorsResponse>(`${BASE}/factors/activity-overview`)
}

// ========== Forecast Report API ==========

export function fetchForecastReport(date?: string): Promise<ForecastResponse> {
  const params = date ? `?date=${date}` : ''
  return request<ForecastResponse>(`${BASE}/forecast${params}`)
}

export function fetchForecastHistory(limit: number = 30): Promise<ForecastHistoryResponse> {
  return request<ForecastHistoryResponse>(`${BASE}/forecast/history?limit=${limit}`)
}

/** 预测诊断：历史预测与事后实际收益率对账（只读，不建表）。 */
export function fetchForecastDiagnosis(): Promise<ForecastDiagnosisResponse> {
  return request<ForecastDiagnosisResponse>(`${BASE}/forecast/diagnosis`)
}

// ========== Macro Data API ==========

export function fetchMacroIndicators(): Promise<MacroIndicatorsResponse> {
  return request<MacroIndicatorsResponse>(`${BASE}/macro-data/indicators`)
}

export function fetchMacroData(zbcodes: string[], start?: string, end?: string): Promise<MacroDataResponse> {
  const params = new URLSearchParams()
  params.set('zbcode', zbcodes.join(','))
  if (start) params.set('start', start)
  if (end) params.set('end', end)

  return request<MacroDataResponse>(`${BASE}/macro-data/data?${params.toString()}`)
}

// ── Discover 页面 API ────────────────────────────────────────────────

export function fetchDiscoverNews(params: {
  page?: number;
  page_size?: number;
  direction?: string;
  source?: string;
  days?: number;
}): Promise<DiscoverNewsResponse> {
  const sp = new URLSearchParams();
  if (params.page) sp.set('page', String(params.page));
  if (params.page_size) sp.set('page_size', String(params.page_size));
  if (params.direction) sp.set('direction', params.direction);
  if (params.source) sp.set('source', params.source);
  if (params.days) sp.set('days', String(params.days));
  return request<DiscoverNewsResponse>(`${BASE}/discover/news?${sp}`);
}

export function fetchMarketPanel(): Promise<MarketPanelResponse> {
  return request<MarketPanelResponse>(`${BASE}/discover/market-panel`);
}

export function fetchFactorDetail(factorId: number): Promise<FactorDetailData> {
  return request<FactorDetailData>(`${BASE}/discover/factor-detail?factor_id=${factorId}`);
}

// ── 收益日历 API ──────────────────────────────────────────────────

export function fetchReturnsCalendar(params: {
  start: string;
  end: string;
  selected?: string;
}): Promise<ReturnsCalendarResponse> {
  const sp = new URLSearchParams();
  sp.set('start', params.start);
  sp.set('end', params.end);
  if (params.selected) sp.set('selected', params.selected);
  return request<ReturnsCalendarResponse>(`${BASE}/returns/calendar?${sp.toString()}`);
}
/** 因子历史表现（事件研究结果，按因子代码查询）。 */
export function fetchFactorPerformance(factorCode: string): Promise<FactorPerformanceResponse> {
  return request<FactorPerformanceResponse>(
    `${BASE}/factors/${encodeURIComponent(factorCode)}/performance`,
  )
}

/** 回测仿真总览：各因子历史表现 + 整体分布。 */
export function fetchBacktestOverview(
  holdingDays = 5,
  minSamples = 20,
): Promise<BacktestOverviewResponse> {
  return request<BacktestOverviewResponse>(
    `${BASE}/factors/backtest-overview?holding_days=${holdingDays}&min_samples=${minSamples}`,
  )
}
