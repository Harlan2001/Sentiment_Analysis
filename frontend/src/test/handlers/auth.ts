import { http, HttpResponse } from 'msw'
import { API_PREFIX } from '@/api/client'

/** 认证相关全局拦截：免登录模式 + 登录成功（领域测试需覆盖时用 server.use）。 */
export const authHandlers = [
  http.get(`${API_PREFIX}/auth/status`, () =>
    HttpResponse.json({
      auth_enabled: false,
      user_id: 1,
      is_admin: true,
      role: 'admin',
    }),
  ),
  http.post(`${API_PREFIX}/auth/login`, () =>
    HttpResponse.json({
      success: true,
      token: 'test-token',
      username: 'tester',
      display_name: '测试员',
      is_admin: true,
      role: 'admin',
    }),
  ),
]