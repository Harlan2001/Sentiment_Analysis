import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { render, type RenderOptions } from '@testing-library/react'
import { AuthProvider } from '@/contexts/AuthContext'

/** 每个用例独立 QueryClient（retry:false + 立即 GC, 避免并发/幽灵重试拖慢或污染断言）。 */
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  })
}

interface ProvidersOptions {
  route?: string
  withAuth?: boolean
}

/**
 * 统一的 Provider 包装：QueryClientProvider + MemoryRouter + 可选 AuthProvider。
 * 所有走 react-query / react-router / useAuth 的组件、hook 测试都通过它渲染。
 * AuthProvider 挂载时会请求 /sapi/auth/status，由全局 handler 兜底（免登录模式）。
 */
export function renderWithProviders(
  ui: ReactElement,
  {
    route = '/',
    withAuth = true,
    ...renderOpts
  }: ProvidersOptions & Omit<RenderOptions, 'wrapper'> = {},
) {
  const queryClient = createTestQueryClient()
  const Wrapper = ({ children }: { children?: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        {withAuth ? <AuthProvider>{children}</AuthProvider> : children}
      </MemoryRouter>
    </QueryClientProvider>
  )
  return { ...render(ui, { wrapper: Wrapper, ...renderOpts }), queryClient }
}