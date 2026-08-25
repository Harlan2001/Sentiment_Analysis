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
} from '@/types'
import { API_PREFIX as BASE, authHeaders } from './client'

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
  const r = await fetch(url, { headers: authHeaders() })
  return r.json()
}

export async function fetchSimilarNews(newsId: number): Promise<SimilarNews[]> {
  const r = await fetch(`${BASE}/news/similar?news_id=${newsId}`, { headers: authHeaders() })
  return r.json()
}

export async function fetchNewsYieldData(
  newsId: number,
  period: string = '10年',
  windowBefore: number = 10,
  windowAfter: number = 10
): Promise<NewsYieldData> {
  const r = await fetch(
    `${BASE}/news/${newsId}/yield?period=${period}&window_before=${windowBefore}&window_after=${windowAfter}`,
    { headers: authHeaders() }
  )
  return r.json()
}

export interface FactorDefinition {
  code: string
  name: string
  category: string
}

export interface AllFactorsResponse {
  factors: FactorDefinition[]
}

export async function fetchAllFactors(): Promise<AllFactorsResponse> {
  const r = await fetch(`${BASE}/factors`, { headers: authHeaders() })
  return r.json()
}

// ========== Forecast Report API ==========

export async function fetchForecastReport(date?: string): Promise<ForecastResponse> {
  const params = date ? `?date=${date}` : ''
  const r = await fetch(`${BASE}/forecast${params}`, { headers: authHeaders() })
  return r.json()
}

export async function fetchForecastHistory(limit: number = 30): Promise<ForecastHistoryResponse> {
  const r = await fetch(`${BASE}/forecast/history?limit=${limit}`, { headers: authHeaders() })
  return r.json()
}

// ========== Macro Data API ==========

export async function fetchMacroIndicators(): Promise<MacroIndicatorsResponse> {
  const r = await fetch(`${BASE}/macro-data/indicators`, { headers: authHeaders() })
  if (!r.ok) throw new Error('获取指标列表失败')
  return r.json()
}

export async function fetchMacroData(zbcodes: string[], start?: string, end?: string): Promise<MacroDataResponse> {
  const params = new URLSearchParams()
  params.set('zbcode', zbcodes.join(','))
  if (start) params.set('start', start)
  if (end) params.set('end', end)

  const r = await fetch(`${BASE}/macro-data/data?${params.toString()}`, {
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error('获取宏观数据失败')
  return r.json()
}

// ── Discover 页面 API ────────────────────────────────────────────────

export async function fetchDiscoverNews(params: {
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
  const r = await fetch(`${BASE}/discover/news?${sp}`, { headers: authHeaders() });
  return r.json();
}

export async function fetchMarketPanel(): Promise<MarketPanelResponse> {
  const r = await fetch(`${BASE}/discover/market-panel`, { headers: authHeaders() });
  return r.json();
}

export async function fetchFactorDetail(factorId: number): Promise<FactorDetailData> {
  const r = await fetch(`${BASE}/discover/factor-detail?factor_id=${factorId}`, { headers: authHeaders() });
  return r.json();
}

// ── 收益日历 API ──────────────────────────────────────────────────

export async function fetchReturnsCalendar(params: {
  start: string;
  end: string;
  selected?: string;
}): Promise<ReturnsCalendarResponse> {
  const sp = new URLSearchParams();
  sp.set('start', params.start);
  sp.set('end', params.end);
  if (params.selected) sp.set('selected', params.selected);
  const r = await fetch(`${BASE}/returns/calendar?${sp.toString()}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('收益日历加载失败');
  return r.json();
}