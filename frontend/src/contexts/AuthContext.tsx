import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { storage } from '../utils/helpers'

interface AuthState {
  isAuthenticated: boolean
  isLoading: boolean
  username: string | null
  displayName: string | null
  token: string | null
  authEnabled: boolean
}

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<{ success: boolean; message: string }>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

const TOKEN_KEY = 'auth_token'
const USER_KEY = 'auth_user'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    username: null,
    displayName: null,
    token: null,
    authEnabled: false,
  })

  // 应用启动时检查认证状态
  useEffect(() => {
    checkAuthStatus()
  }, [])

  const checkAuthStatus = async () => {
    const savedToken = storage.get<string>(TOKEN_KEY)

    try {
      const headers: Record<string, string> = {}
      if (savedToken) {
        headers['Authorization'] = `Bearer ${savedToken}`
      }

      const r = await fetch('/api/auth/status', { headers })
      const data = await r.json()

      if (!data.auth_enabled) {
        // 免登录模式
        setState({
          isAuthenticated: true,
          isLoading: false,
          username: null,
          displayName: null,
          token: null,
          authEnabled: false,
        })
      } else if (data.authenticated && savedToken) {
        // 已认证
        const savedUser = storage.get<{ username: string; displayName: string }>(USER_KEY)
        setState({
          isAuthenticated: true,
          isLoading: false,
          username: data.username || savedUser?.username || null,
          displayName: savedUser?.displayName || data.username || null,
          token: savedToken,
          authEnabled: true,
        })
      } else {
        // 需要登录
        storage.remove(TOKEN_KEY)
        storage.remove(USER_KEY)
        setState({
          isAuthenticated: false,
          isLoading: false,
          username: null,
          displayName: null,
          token: null,
          authEnabled: true,
        })
      }
    } catch {
      // API 不可用时的降级处理
      const savedToken = storage.get<string>(TOKEN_KEY)
      if (savedToken) {
        const savedUser = storage.get<{ username: string; displayName: string }>(USER_KEY)
        setState({
          isAuthenticated: true,
          isLoading: false,
          username: savedUser?.username || null,
          displayName: savedUser?.displayName || null,
          token: savedToken,
          authEnabled: true,
        })
      } else {
        setState({
          isAuthenticated: false,
          isLoading: false,
          username: null,
          displayName: null,
          token: null,
          authEnabled: false,
        })
      }
    }
  }

  const login = useCallback(async (username: string, password: string) => {
    try {
      const r = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })

      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: '登录失败' }))
        return { success: false, message: err.detail || '登录失败' }
      }

      const data = await r.json()

      if (data.success && data.token) {
        storage.set(TOKEN_KEY, data.token)
        storage.set(USER_KEY, { username: data.username, displayName: data.display_name })
        setState({
          isAuthenticated: true,
          isLoading: false,
          username: data.username,
          displayName: data.display_name,
          token: data.token,
          authEnabled: true,
        })
        return { success: true, message: '登录成功' }
      }

      return { success: false, message: data.message || '登录失败' }
    } catch (err) {
      return { success: false, message: '网络错误，请检查连接' }
    }
  }, [])

  const logout = useCallback(() => {
    storage.remove(TOKEN_KEY)
    storage.remove(USER_KEY)
    setState(prev => ({
      ...prev,
      isAuthenticated: false,
      username: null,
      displayName: null,
      token: null,
    }))
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}

export default AuthContext
