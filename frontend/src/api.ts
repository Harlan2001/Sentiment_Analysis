import type {
  NewsItem,
  SimilarNews,
  NewsYieldData,
  ForecastResponse,
  ForecastHistoryResponse,
  DiscoverNewsResponse,
  MarketPanelResponse,
  FactorDetailData,
} from '@/types'
import { storage } from '@/utils/helpers'
import { API_PREFIX } from '@/constants'

const BASE = API_PREFIX

/**
 * 获取认证请求头（如果已登录）
 */
function authHeaders(): Record<string, string> {
  const token = storage.get<string>('auth_token')
  if (token) {
    return { Authorization: `Bearer ${token}` }
  }
  return {}
}

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
  structure: Record<string, Record<string, [string, string, string][]>>
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

// ========== Dashboard API ==========

import type {
  DashboardCoreData,
  BehaviorStats,
  AuditLogResponse,
  UserBehaviorProfile,
  UserProfileListResponse,
  UserCompareResponse,
} from './types'

export async function fetchDashboardCore(): Promise<DashboardCoreData> {
  const r = await fetch(`${BASE}/dashboard/core`, { headers: authHeaders() })
  if (!r.ok) {
    const text = await r.text().catch(() => '')
    throw new Error(`服务器错误 ${r.status}${text ? ': ' + text.slice(0, 200) : ''}`)
  }
  return r.json()
}

export async function fetchDashboardHistory(days: number = 7): Promise<any[]> {
  const r = await fetch(`${BASE}/dashboard/history?days=${days}`, { headers: authHeaders() })
  if (!r.ok) throw new Error('历史快照获取失败')
  return r.json()
}

export async function triggerDashboardSnapshot(): Promise<{ success: boolean; snapshot_id: number | null }> {
  const r = await fetch(`${BASE}/dashboard/snapshot`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error('快照生成失败')
  return r.json()
}

export async function fetchBehaviorStats(days: number = 7): Promise<BehaviorStats> {
  const r = await fetch(`${BASE}/dashboard/behavior-stats?days=${days}`, { headers: authHeaders() })
  if (!r.ok) throw new Error('行为统计数据获取失败')
  return r.json()
}

export async function fetchBehaviorLogs(
  params: {
    user_id?: string
    page_route?: string
    action_type?: string
    start?: string
    end?: string
    limit?: number
    offset?: number
  } = {}
): Promise<AuditLogResponse> {
  const searchParams = new URLSearchParams()
  if (params.user_id) searchParams.set('user_id', params.user_id)
  if (params.page_route) searchParams.set('page_route', params.page_route)
  if (params.action_type) searchParams.set('action_type', params.action_type)
  if (params.start) searchParams.set('start', params.start)
  if (params.end) searchParams.set('end', params.end)
  searchParams.set('limit', String(params.limit || 100))
  searchParams.set('offset', String(params.offset || 0))

  const r = await fetch(`${BASE}/dashboard/behavior-logs?${searchParams}`, { headers: authHeaders() })
  if (!r.ok) throw new Error('审计日志获取失败')
  return r.json()
}

// ========== User Profile API ==========

export async function fetchActiveUsers(): Promise<{
  users: {
    id: number
    username: string
    display_name: string
    department: string | null
    company: string | null
    role: string
  }[]
}> {
  const r = await fetch(`${BASE}/dashboard/users/active`, { headers: authHeaders() })
  if (!r.ok) throw new Error('活跃用户列表获取失败')
  return r.json()
}

export async function fetchUserProfiles(
  sortBy: string = 'last_visit',
  order: string = 'desc'
): Promise<UserProfileListResponse> {
  const r = await fetch(`${BASE}/dashboard/behavior/profiles?sort_by=${sortBy}&order=${order}`, {
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error('用户画像列表获取失败')
  return r.json()
}

export async function fetchUserProfile(userId: number): Promise<UserBehaviorProfile> {
  const r = await fetch(`${BASE}/dashboard/behavior/profile/${userId}`, { headers: authHeaders() })
  if (!r.ok) throw new Error('用户画像获取失败')
  return r.json()
}

export async function fetchUserCompare(userIds: number[]): Promise<UserCompareResponse> {
  const r = await fetch(`${BASE}/dashboard/behavior/compare?user_ids=${userIds.join(',')}`, { headers: authHeaders() })
  if (!r.ok) throw new Error('用户对比失败')
  return r.json()
}

export async function triggerProfileCompute(
  userId: number
): Promise<{ user_id: number; username: string; computed: boolean }> {
  const r = await fetch(`${BASE}/dashboard/behavior/compute-profile/${userId}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error('画像计算触发失败')
  return r.json()
}

// ========== Token Usage API ==========

import type { TokenOverview, TokenTrendResponse, TokenByModelResponse, UserTokenListResponse } from './types'

export async function fetchTokenOverview(): Promise<TokenOverview> {
  const r = await fetch(`${BASE}/dashboard/token/overview`, { headers: authHeaders() })
  if (!r.ok) throw new Error('Token概览获取失败')
  return r.json()
}

export async function fetchTokenTrend(days: number = 7): Promise<TokenTrendResponse> {
  const r = await fetch(`${BASE}/dashboard/token/trend?days=${days}`, { headers: authHeaders() })
  if (!r.ok) throw new Error('Token趋势获取失败')
  return r.json()
}

export async function fetchTokenByModel(days: number = 7): Promise<TokenByModelResponse> {
  const r = await fetch(`${BASE}/dashboard/token/by-model?days=${days}`, { headers: authHeaders() })
  if (!r.ok) throw new Error('Token模型分布获取失败')
  return r.json()
}

export async function fetchUserTokenList(
  params: {
    sort_by?: string
    order?: string
    limit?: number
    offset?: number
    search?: string
  } = {}
): Promise<UserTokenListResponse> {
  const sp = new URLSearchParams()
  if (params.sort_by) sp.set('sort_by', params.sort_by)
  if (params.order) sp.set('order', params.order)
  sp.set('limit', String(params.limit || 50))
  sp.set('offset', String(params.offset || 0))
  if (params.search) sp.set('search', params.search)
  const r = await fetch(`${BASE}/dashboard/token/users?${sp}`, { headers: authHeaders() })
  if (!r.ok) throw new Error('用户Token列表获取失败')
  return r.json()
}

// ========== Macro Data API ==========

import type { MacroIndicatorsResponse, MacroDataResponse } from './types'

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

import type { ReturnsCalendarResponse } from '@/types'

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