import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DemoNotice } from './DemoNotice'
import { McpPage } from '@/features/custom/McpPage'
import PortfolioPage from '@/features/market/pages/PortfolioPage'

vi.mock('@/api/tasks', () => ({
  getWorkflowTasks: vi.fn(async () => ({ items: [] })),
}))

afterEach(cleanup)

describe('DemoNotice', () => {
  it('clearly identifies demo data and unfinished functionality', () => {
    render(<DemoNotice />)

    expect(screen.getByRole('status', { name: '演示功能提示' })).toBeInTheDocument()
    expect(screen.getByText('演示功能')).toBeInTheDocument()
    expect(screen.getByText('当前页面展示的内容为演示数据，实际功能尚在开发中。')).toBeInTheDocument()
  })

  it('appears on the MCP page', () => {
    render(<MemoryRouter><McpPage /></MemoryRouter>)
    expect(screen.getByRole('status', { name: '演示功能提示' })).toHaveTextContent('MCP 连接为演示版本')
  })

  it('appears on the portfolio page', () => {
    render(<PortfolioPage />)
    expect(screen.getByRole('status', { name: '演示功能提示' })).toHaveTextContent('投资组合为演示功能')
  })
})
