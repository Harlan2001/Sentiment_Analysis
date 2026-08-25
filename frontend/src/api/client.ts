/**
 * API 客户端公共基础设施
 * - API_PREFIX：后端路由前缀（与 backend/config/config.py 保持一致）
 * - authHeaders()：在已登录时附加 JWT 认证请求头
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