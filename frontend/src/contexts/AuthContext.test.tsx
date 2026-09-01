import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

function Probe() {
  const auth = useAuth()
  return <div>
    <span data-testid="loading">{String(auth.isLoading)}</span>
    <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
    <span data-testid="username">{auth.username ?? ''}</span>
    <button onClick={auth.logout}>退出登录</button>
  </div>
}

describe('AuthProvider logout', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('auth_token', JSON.stringify('valid-token'))
    localStorage.setItem('auth_user', JSON.stringify({
      username: 'user1', displayName: '用户一', isAdmin: false, role: 'member',
    }))
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({
        auth_enabled: true, authenticated: true, username: 'user1',
        user_id: '1', is_admin: false, role: 'member',
      }),
    }))
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('removes both persisted auth records and clears the in-memory identity', async () => {
    const queryClient = new QueryClient()
    queryClient.setQueryData(['private', 'user1'], { secret: 'user1 data' })
    render(<QueryClientProvider client={queryClient}><AuthProvider><Probe /></AuthProvider></QueryClientProvider>)
    await waitFor(() => expect(screen.getByTestId('username')).toHaveTextContent('user1'))

    fireEvent.click(screen.getByRole('button', { name: '退出登录' }))

    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(localStorage.getItem('auth_user')).toBeNull()
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(screen.getByTestId('username')).toHaveTextContent('')
    expect(queryClient.getQueryData(['private', 'user1'])).toBeUndefined()
  })
})
