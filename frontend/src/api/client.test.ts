import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AUTH_INVALIDATED_EVENT, invalidateAuthentication, request } from './client'

describe('API authentication invalidation', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('clears saved login when the backend reports a disabled account', async () => {
    localStorage.setItem('auth_token', JSON.stringify('token'))
    localStorage.setItem('auth_user', JSON.stringify({ username: 'alice' }))
    const listener = vi.fn()
    window.addEventListener(AUTH_INVALIDATED_EVENT, listener)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: '账户不存在或已停用，请重新登录' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        })
      )
    )

    await expect(request('/sapi/workbench/projects/project-1')).rejects.toThrow('已停用')

    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(localStorage.getItem('auth_user')).toBeNull()
    expect(listener).toHaveBeenCalledOnce()
    window.removeEventListener(AUTH_INVALIDATED_EVENT, listener)
  })

  it('does not clear login for an ordinary project permission error', () => {
    localStorage.setItem('auth_token', JSON.stringify('token'))
    invalidateAuthentication(403, '当前用户没有项目写入权限')
    expect(localStorage.getItem('auth_token')).not.toBeNull()
  })
})
