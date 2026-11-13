import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { McpPage } from '@/features/custom/McpPage'
import { HomePage } from '@/features/home/HomePage'
import PortfolioPage from '@/features/market/pages/PortfolioPage'

vi.mock('@/api/tasks', () => ({
  getWorkflowTasks: vi.fn(async () => ({ items: [] })),
}))

afterEach(cleanup)

describe('demo content cleanup', () => {
  it.each([
    ['MCP', <McpPage />],
    ['投资组合', <PortfolioPage />],
    ['首页', <HomePage />],
  ])('%s 页面不展示演示或 Mock 标记', (_name, page) => {
    const { container } = render(<MemoryRouter>{page}</MemoryRouter>)

    expect(screen.queryByRole('status', { name: '演示功能提示' })).not.toBeInTheDocument()
    expect(container).not.toHaveTextContent(/演示功能|演示数据|演示版本|演示配置|模拟授权|Mock 数据|DEMO/)
  })
})
