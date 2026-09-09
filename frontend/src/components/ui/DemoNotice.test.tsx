import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DemoNotice } from './DemoNotice'
import { WorkflowHomePage } from '@/features/workflow/pages/WorkflowHomePage'
import { WorkflowDemoPage } from '@/features/workflow/pages/WorkflowDemoPage'
import { McpPage } from '@/features/custom/McpPage'
import { MemoryPage } from '@/features/custom/MemoryPage'
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

  it.each([
    ['MCP 连接为演示版本', <McpPage />],
    ['记忆功能为演示版本', <MemoryPage />],
  ])('appears on the %s page', (title, page) => {
    render(<MemoryRouter>{page}</MemoryRouter>)
    expect(screen.getByRole('status', { name: '演示功能提示' })).toHaveTextContent(title)
  })

  it('appears on every mock workflow detail route', () => {
    render(
      <MemoryRouter initialEntries={['/computer/demo/credit']}>
        <Routes>
          <Route path="/computer/demo/:workflowId" element={<WorkflowDemoPage />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByRole('status', { name: '演示功能提示' })).toHaveTextContent('信用风险扫描为演示功能')
  })

  it('distinguishes real and demo capabilities on the workflow landing page', () => {
    render(<MemoryRouter><WorkflowHomePage /></MemoryRouter>)
    expect(screen.getByRole('status', { name: '演示功能提示' })).toHaveTextContent('研报分析、新闻总结和策略生成已接入真实服务')
    expect(screen.getAllByText('演示')).toHaveLength(5)
  })

  it('appears on the portfolio page', () => {
    render(<PortfolioPage />)
    expect(screen.getByRole('status', { name: '演示功能提示' })).toHaveTextContent('投资组合为演示功能')
  })
})
