/**
 * API 客户端公共基础设施
 * - API_PREFIX：后端路由前缀（与 backend/config/config.py 保持一致）
 * - authHeaders()：在已登录时附加 JWT 认证请求头
 * - request<T>()：通用 JSON 请求助手（新代码统一入口）
 */
import { storage } from '@/utils/helpers'

/** API 路由前缀 */
export const API_PREFIX = '/sapi'

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

/** 通用 JSON 请求助手：自动加认证头、JSON 序列化、非 2xx 抛错 */
export async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}