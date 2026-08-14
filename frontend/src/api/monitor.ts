/**
 * 监控看板 API（dashboard / behavior / user-profile / token-usage）
 */
import type {
  DashboardCoreData,
  BehaviorStats,
  AuditLogResponse,
  UserBehaviorProfile,
  UserProfileListResponse,
  UserCompareResponse,
  TokenOverview,
  TokenTrendResponse,
  TokenByModelResponse,
  UserTokenListResponse,
} from '@/types'
import { API_PREFIX as BASE, authHeaders } from './client'

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