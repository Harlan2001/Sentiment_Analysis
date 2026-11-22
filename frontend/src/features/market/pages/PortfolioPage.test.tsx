import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { API_PREFIX } from '@/api/client'
import type {
  Holding,
  PortfolioDetail,
  PortfolioListResponse,
  PortfolioMetrics,
  PortfolioSettingsInput,
} from '@/api/portfolio'
import { renderWithProviders } from '@/test/render'
import { server } from '@/test/server'
import PortfolioPage from './PortfolioPage'

const BASE = `${API_PREFIX}/portfolios`

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function metrics(overrides: Partial<PortfolioMetrics> = {}): PortfolioMetrics {
  return {
    invested_weight: 60,
    cash_weight: 40,
    weighted_duration: null,
    duration_coverage: null,
    weighted_yield: 1.85,
    yield_coverage: 60,
    asset_allocations: [{ category: '国债', weight: 60 }],
    max_holding_weight: 60,
    max_holding_share_of_invested: 100,
    risk_items: [
      { code: 'DURATION_MISSING', level: 'medium', title: '久期数据不完整', detail: '部分持仓缺少久期，加权结果不可比。' },
      { code: 'MISSING_DURATION', level: 'info', title: '部分持仓缺少久期', detail: '缺失持仓未纳入加权。' },
    ],
    ...overrides,
  }
}

function holding(overrides: Partial<Holding> = {}): Holding {
  return {
    id: 'h1',
    bond_code: '240004',
    bond_name: '24附息国债04',
    asset_category: '国债',
    weight_pct: 60,
    yield_pct: 1.71,
    duration_years: null,
    sort_order: 0,
    note: null,
    ...overrides,
  }
}

function detail(overrides: Partial<PortfolioDetail> = {}): PortfolioDetail {
  return {
    id: 'p1',
    name: '稳健研究组合',
    description: '利率债研究',
    size_amount: 128_000_000,
    as_of_date: '2026-11-19',
    target_duration: 4.5,
    status: 'active',
    version: 3,
    created_at: '2026-11-01T00:00:00',
    updated_at: '2026-11-19T00:00:00',
    holdings_count: 1,
    invested_weight: 60,
    cash_weight: 40,
    holdings: [holding()],
    metrics: metrics(),
    ...overrides,
  }
}

let portfolios: PortfolioDetail[]
let listRequests: string[]
let detailRequests: number
let archiveBodies: Array<{ expected_version?: number }>

function installDefaultHandlers() {
  server.use(
    http.get(BASE, ({ request }) => {
      listRequests.push(request.url)
      const url = new URL(request.url)
      const includeArchived = url.searchParams.get('include_archived') === 'true'
      const visible = portfolios.filter((item) => includeArchived || item.status === 'active')
      const payload: PortfolioListResponse = {
        items: visible.map(({ holdings: _holdings, metrics: _metrics, ...summary }) => clone(summary)),
        total: visible.length,
        page: Number(url.searchParams.get('page') ?? 1),
        page_size: Number(url.searchParams.get('page_size') ?? 20),
        total_pages: 1,
      }
      return HttpResponse.json({ data: payload })
    }),
    http.get(`${BASE}/:id`, ({ params }) => {
      detailRequests += 1
      const found = portfolios.find((item) => String(item.id) === String(params.id))
      return found
        ? HttpResponse.json({ data: clone(found) })
        : HttpResponse.json({ detail: '组合不存在' }, { status: 404 })
    }),
    http.post(`${BASE}/:id/archive`, async ({ params, request }) => {
      const body = await request.json() as { expected_version?: number }
      archiveBodies.push(body)
      const found = portfolios.find((item) => String(item.id) === String(params.id))
      if (!found) return HttpResponse.json({ detail: '组合不存在' }, { status: 404 })
      found.status = 'archived'
      found.version += 1
      return HttpResponse.json({ data: clone(found) })
    }),
    http.post(`${BASE}/:id/restore`, async ({ params, request }) => {
      const body = await request.json() as { expected_version?: number }
      archiveBodies.push(body)
      const found = portfolios.find((item) => String(item.id) === String(params.id))
      if (!found) return HttpResponse.json({ detail: '组合不存在' }, { status: 404 })
      found.status = 'active'
      found.version += 1
      return HttpResponse.json({ data: clone(found) })
    }),
  )
}

function renderPortfolio(route = '/portfolio') {
  return renderWithProviders(
    <Routes>
      <Route path="/portfolio" element={<PortfolioPage />} />
      <Route path="/portfolio/:portfolioId" element={<PortfolioPage />} />
    </Routes>,
    { route, withAuth: false },
  )
}

beforeEach(() => {
  window.localStorage.clear()
  portfolios = [
    detail(),
    detail({
      id: 'p2',
      name: '已归档全现金组合',
      status: 'archived',
      version: 8,
      holdings_count: 0,
      invested_weight: 0,
      cash_weight: 100,
      holdings: [],
      metrics: metrics({
        invested_weight: 0,
        cash_weight: 100,
        weighted_yield: null,
        yield_coverage: null,
        asset_allocations: [],
        max_holding_weight: null,
        max_holding_share_of_invested: null,
        risk_items: [],
      }),
    }),
  ]
  listRequests = []
  detailRequests = 0
  archiveBodies = []
  installDefaultHandlers()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('PortfolioPage 账号级组合', () => {
  it('展示列表和归档过滤，不读取旧本地草稿或渲染静态建议', async () => {
    window.localStorage.setItem('bondsense-portfolio-draft', JSON.stringify({ allocation: { cash: 99 }, duration: 9 }))
    const getItem = vi.spyOn(Storage.prototype, 'getItem')
    const user = userEvent.setup()
    renderPortfolio()

    expect(await screen.findByRole('link', { name: '稳健研究组合' })).toBeInTheDocument()
    expect(screen.getByText('1.28 亿元')).toBeInTheDocument()
    expect(screen.getByText('60.00%')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '已归档全现金组合' })).not.toBeInTheDocument()
    expect(screen.queryByText('近 30 日收益')).not.toBeInTheDocument()
    expect(screen.queryByText(/AI 配置/)).not.toBeInTheDocument()
    expect(screen.queryByText(/恢复 AI/)).not.toBeInTheDocument()

    await user.click(screen.getByLabelText('显示已归档'))
    expect(await screen.findByRole('link', { name: '已归档全现金组合' })).toBeInTheDocument()
    await waitFor(() => expect(new URL(listRequests.at(-1)!).searchParams.get('include_archived')).toBe('true'))
    expect(getItem.mock.calls.filter(([key]) => key === 'bondsense-portfolio-draft')).toHaveLength(0)
  })

  it('新建组合按万元转元并进入服务端详情', async () => {
    const bodies: PortfolioSettingsInput[] = []
    server.use(http.post(BASE, async ({ request }) => {
      const body = await request.json() as PortfolioSettingsInput
      bodies.push(body)
      const created = detail({
        id: 'new-1',
        name: body.name,
        description: body.description ?? null,
        size_amount: body.size_amount,
        as_of_date: body.as_of_date,
        target_duration: body.target_duration ?? null,
        version: 1,
        holdings_count: 0,
        invested_weight: 0,
        cash_weight: 100,
        holdings: [],
        metrics: metrics({ invested_weight: 0, cash_weight: 100, asset_allocations: [], risk_items: [] }),
      })
      portfolios.push(created)
      return HttpResponse.json({ data: clone(created) }, { status: 201 })
    }))
    const user = userEvent.setup()
    renderPortfolio()
    await user.click(await screen.findByRole('button', { name: '新建组合' }))

    await user.type(screen.getByLabelText('组合名称'), '新利率组合')
    await user.clear(screen.getByLabelText('配置金额（万元）'))
    await user.type(screen.getByLabelText('配置金额（万元）'), '10000')
    await user.click(screen.getByRole('button', { name: '创建组合' }))

    expect(await screen.findByRole('heading', { name: '新利率组合' })).toBeInTheDocument()
    expect(bodies).toHaveLength(1)
    expect(bodies[0].size_amount).toBe(100_000_000)
    expect(screen.getByText('暂无持仓，当前组合以现金为主。')).toBeInTheDocument()
    expect(detailRequests).toBeGreaterThan(0)
  })

  it('详情展示服务端指标、规则风险与 null 覆盖率，不将 null 当 0', async () => {
    renderPortfolio('/portfolio/p1')

    expect(await screen.findByRole('heading', { name: '稳健研究组合' })).toBeInTheDocument()
    expect(screen.getByText('24附息国债04')).toBeInTheDocument()
    const durationCard = screen.getByText('加权久期').parentElement!
    expect(durationCard).toHaveTextContent('—')
    expect(durationCard).toHaveTextContent('久期覆盖率 —')
    expect(durationCard).not.toHaveTextContent('0.00 年')
    expect(screen.getByText('久期数据不完整')).toBeInTheDocument()
    expect(screen.getByText('规则风险项')).toBeInTheDocument()
    expect(screen.getByText('提示', { exact: true })).toBeInTheDocument()
    expect(screen.queryByText('info风险')).not.toBeInTheDocument()
    expect(screen.getAllByText(/指标日期 2026-11-19/).length).toBeGreaterThan(0)
    expect(screen.queryByText('AAA 及以上 92%')).not.toBeInTheDocument()
  })

  it('新增持仓携带 expected_version，并以最新 detail 更新页面', async () => {
    const bodies: Array<Record<string, unknown>> = []
    server.use(http.post(`${BASE}/:id/holdings`, async ({ params, request }) => {
      const body = await request.json() as Record<string, unknown>
      bodies.push(body)
      const found = portfolios.find((item) => String(item.id) === String(params.id))!
      found.holdings.push(holding({
        id: 'h2',
        bond_code: String(body.bond_code),
        bond_name: String(body.bond_name),
        asset_category: String(body.asset_category),
        weight_pct: Number(body.weight_pct),
        yield_pct: Number(body.yield_pct),
        duration_years: Number(body.duration_years),
        sort_order: 1,
      }))
      found.holdings_count = 2
      found.invested_weight = 85
      found.cash_weight = 15
      found.version += 1
      return HttpResponse.json({ data: clone(found) }, { status: 201 })
    }))
    const user = userEvent.setup()
    renderPortfolio('/portfolio/p1')
    await user.click(await screen.findByRole('button', { name: '新增持仓' }))

    await user.type(screen.getByLabelText('债券代码'), '230210')
    await user.type(screen.getByLabelText('债券名称'), '23国开10')
    await user.type(screen.getByLabelText('资产分类'), '政策性金融债')
    await user.type(screen.getByLabelText('持仓权重（%）'), '25')
    await user.type(screen.getByLabelText('到期收益率（%）'), '1.83')
    await user.type(screen.getByLabelText('持仓久期（年）'), '5.72')
    await user.click(screen.getByRole('button', { name: '添加持仓' }))

    expect(await screen.findByText('23国开10')).toBeInTheDocument()
    expect(bodies[0]).toEqual(expect.objectContaining({
      bond_code: '230210',
      bond_name: '23国开10',
      weight_pct: 25,
      yield_pct: 1.83,
      duration_years: 5.72,
      expected_version: 3,
    }))
    expect(screen.getByText('版本 4')).toBeInTheDocument()
  })

  it('CSV 导入逐行展示错误并明确整批未写入', async () => {
    let requestMode = ''
    let requestVersion = ''
    server.use(http.post(`${BASE}/:id/holdings/import`, async ({ request }) => {
      const url = new URL(request.url)
      requestMode = url.searchParams.get('mode') ?? ''
      requestVersion = url.searchParams.get('expected_version') ?? ''
      return HttpResponse.json({
        data: {
          imported_count: 0,
          errors: [
            { row: 2, field: 'weight_pct', message: '权重不能大于 100' },
            { row: 4, field: 'bond_code', message: '债券代码不能为空' },
          ],
          portfolio: portfolios[0],
        },
      })
    }))
    const user = userEvent.setup()
    renderPortfolio('/portfolio/p1')
    await user.click(await screen.findByRole('button', { name: '导入 CSV' }))

    const file = new File(['bond_code,weight_pct\n240004,120\n'], 'bad.csv', { type: 'text/csv' })
    const fileInput = screen.getByLabelText('CSV 文件') as HTMLInputElement
    await user.upload(fileInput, file)
    expect(fileInput.files?.[0]?.name).toBe('bad.csv')
    await user.click(screen.getByLabelText('替换全部持仓'))
    await user.click(screen.getByRole('button', { name: '开始导入' }))

    expect(await screen.findByText(/导入未执行：发现 2 个错误，整批持仓均未写入/)).toBeInTheDocument()
    expect(screen.getByText('权重不能大于 100')).toBeInTheDocument()
    expect(screen.getByText('债券代码不能为空')).toBeInTheDocument()
    expect(screen.getByText('24附息国债04')).toBeInTheDocument()
    expect(requestMode).toBe('replace')
    expect(requestVersion).toBe('3')
  })

  it('归档后从默认列表移除，显示归档后可恢复并携带最新版本', async () => {
    const user = userEvent.setup()
    renderPortfolio()
    await user.click(await screen.findByRole('button', { name: '归档 稳健研究组合' }))

    expect(await screen.findByText('已归档“稳健研究组合”。')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('link', { name: '稳健研究组合' })).not.toBeInTheDocument())
    expect(archiveBodies[0]).toEqual({ expected_version: 3 })

    await user.click(screen.getByLabelText('显示已归档'))
    await user.click(await screen.findByRole('button', { name: '恢复 稳健研究组合' }))
    expect(await screen.findByText('已恢复“稳健研究组合”。')).toBeInTheDocument()
    expect(archiveBodies[1]).toEqual({ expected_version: 4 })
    expect(await screen.findByRole('link', { name: '稳健研究组合' })).toBeInTheDocument()
  })

  it('归档详情和全现金状态只读，可恢复但不能修改持仓', async () => {
    renderPortfolio('/portfolio/p2')

    expect(await screen.findByRole('heading', { name: '已归档全现金组合' })).toBeInTheDocument()
    expect(screen.getByText('当前为全现金组合；新增持仓后，现金与已投资权重将由后端重新计算。')).toBeInTheDocument()
    expect(screen.getByText(/已归档组合为只读/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '新增持仓' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '编辑组合设置' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '恢复组合' })).toBeEnabled()
  })

  it('409 提示版本冲突并重新查询，手动刷新后可继续操作', async () => {
    server.use(http.patch(`${BASE}/:id`, () => HttpResponse.json({ detail: '组合版本已变化，请刷新后重试' }, { status: 409 }), { once: true }))
    const user = userEvent.setup()
    renderPortfolio('/portfolio/p1')
    await user.click(await screen.findByRole('button', { name: '编辑组合设置' }))
    await user.click(screen.getByRole('button', { name: '保存设置' }))

    expect(await screen.findByText('检测到组合版本冲突，其他操作已先更新数据。请刷新组合并重新查询后再试。')).toBeInTheDocument()
    await waitFor(() => expect(detailRequests).toBeGreaterThan(1))
    await user.click(screen.getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: '刷新组合' }))
    expect(await screen.findByText('已刷新为服务端最新组合。')).toBeInTheDocument()
  })

  it('不存在或跨账号组合显示 404 空态', async () => {
    renderPortfolio('/portfolio/missing')
    expect(await screen.findByText('组合不存在或无权访问')).toBeInTheDocument()
    expect(screen.getByText('该组合可能已删除，或不属于当前账号。')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: '返回组合列表' }).length).toBeGreaterThan(0)
  })
})
