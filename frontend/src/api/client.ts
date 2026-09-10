/**
 * API 客户端公共基础设施
 * - API_PREFIX：后端路由前缀（与 backend/config/config.py 保持一致）
 * - authHeaders()：在已登录时附加 JWT 认证请求头
 * - request()：唯一的 fetch 封装 —— 自动合并认证头、非 2xx 抛错、解包标准响应壳
 *   `{"data": <payload>}`（后端统一约定）。需要原始响应（blob / SSE 等）的调用
 *   请直接 fetch，不要走本封装。
 */
import { storage } from '@/utils/helpers'

/** API 路由前缀 */
export const API_PREFIX = '/sapi'
export const AUTH_INVALIDATED_EVENT = 'bondsense-auth-invalidated'

/**
 * 获取认证请求头（如果已登录）
 */
export function authHeaders(): Record<string, string> {
  const token = storage.get<string>('auth_token')
  if (token) {
    return { Authorization: `Bearer ${token}` }
  }
  return {}
}

interface ErrorPayload {
  error?: { message?: string }
  detail?: string
  message?: string
}

export function invalidateAuthentication(status: number, detail = ''): void {
  const disabledAccount = status === 403 && /(停用|禁用|账户不存在)/.test(detail)
  if (status !== 401 && !disabledAccount) return
  storage.remove('auth_token')
  storage.remove('auth_user')
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(AUTH_INVALIDATED_EVENT, { detail }))
  }
}

/**
 * 统一请求封装：
 * - 合并 authHeaders 与调用方传入的 headers
 * - 非 2xx 时按 FastAPI 约定从 `detail` 提取错误信息并抛错
 * - 解析后返回 `payload.data`（后端统一 `{"data": <payload>}` 响应壳的且唯一解包点）
 */
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: { ...authHeaders(), ...options.headers },
  })
  const payload = (await response.json().catch(() => null)) as (ErrorPayload & { data?: T }) | null
  if (!response.ok) {
    const detail = payload?.error?.message || payload?.detail || payload?.message
    invalidateAuthentication(response.status, detail)
    throw new Error(detail || '请求失败')
  }
  return payload?.data as T
}
