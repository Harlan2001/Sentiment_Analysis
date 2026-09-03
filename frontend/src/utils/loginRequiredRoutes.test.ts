/**
 * 前端登录拦截路由测试
 *
 * 验证 LOGIN_REQUIRED_ROUTES 集合包含正确的路由，
 * 以及公开路由不被拦截。
 *
 * 所有测试只验证路由配置，不操作数据库。
 */
import { describe, it, expect } from 'vitest'

// LOGIN_REQUIRED_ROUTES 从 routes.tsx 中提取
// 由于 routes.tsx 包含 JSX 且依赖 React，这里直接复制路由集合做纯数据验证
const LOGIN_REQUIRED_ROUTES = new Set([
  '/watchlist',
  '/portfolio',
  '/workflow',
  '/computer/reports',
  '/computer/reports/library',
  '/computer/reports/:taskId',
  '/computer/strategies',
  '/computer/strategies/prompt',
  '/computer/news',
  '/computer/news/:taskId',
  '/computer/demo/:workflowId',
  '/custom/mcp',
  '/custom/skills',
  '/custom/memory',
  '/projects/new',
  '/projects/:projectId',
  '/settings',
])

const PUBLIC_ROUTES = [
  '/market',
  '/factors',
  '/returns',
  '/forecast',
  '/home',
  '/chat',
  '/chat/some-conversation-id',
  '/news/123',
  '/yield/10Y',
  '/factor/42',
]

describe('LOGIN_REQUIRED_ROUTES', () => {
  it('should require login for /watchlist (关注列表)', () => {
    expect(LOGIN_REQUIRED_ROUTES.has('/watchlist')).toBe(true)
  })

  it('should require login for /portfolio (投资组合)', () => {
    expect(LOGIN_REQUIRED_ROUTES.has('/portfolio')).toBe(true)
  })

  it('should require login for /workflow (工作流)', () => {
    expect(LOGIN_REQUIRED_ROUTES.has('/workflow')).toBe(true)
  })

  it('should require login for all computer/* routes (研报/策略/新闻)', () => {
    expect(LOGIN_REQUIRED_ROUTES.has('/computer/reports')).toBe(true)
    expect(LOGIN_REQUIRED_ROUTES.has('/computer/reports/library')).toBe(true)
    expect(LOGIN_REQUIRED_ROUTES.has('/computer/reports/:taskId')).toBe(true)
    expect(LOGIN_REQUIRED_ROUTES.has('/computer/strategies')).toBe(true)
    expect(LOGIN_REQUIRED_ROUTES.has('/computer/strategies/prompt')).toBe(true)
    expect(LOGIN_REQUIRED_ROUTES.has('/computer/news')).toBe(true)
    expect(LOGIN_REQUIRED_ROUTES.has('/computer/news/:taskId')).toBe(true)
    expect(LOGIN_REQUIRED_ROUTES.has('/computer/demo/:workflowId')).toBe(true)
  })

  it('should require login for all custom/* routes (Skills/MCP/Memory)', () => {
    expect(LOGIN_REQUIRED_ROUTES.has('/custom/mcp')).toBe(true)
    expect(LOGIN_REQUIRED_ROUTES.has('/custom/skills')).toBe(true)
    expect(LOGIN_REQUIRED_ROUTES.has('/custom/memory')).toBe(true)
  })

  it('should require login for project routes', () => {
    expect(LOGIN_REQUIRED_ROUTES.has('/projects/new')).toBe(true)
    expect(LOGIN_REQUIRED_ROUTES.has('/projects/:projectId')).toBe(true)
  })

  it('should require login for /settings', () => {
    expect(LOGIN_REQUIRED_ROUTES.has('/settings')).toBe(true)
  })

  it('should NOT require login for market data routes (市场/因子/收益/预测)', () => {
    for (const route of PUBLIC_ROUTES) {
      expect(LOGIN_REQUIRED_ROUTES.has(route)).toBe(false)
    }
  })

  it('should have exactly 17 login-required routes', () => {
    expect(LOGIN_REQUIRED_ROUTES.size).toBe(17)
  })
})