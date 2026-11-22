import { expect, test, type Page } from '@playwright/test'

type FixtureHolding = {
  id: number
  bond_code: string
  bond_name: string
  asset_category: string
  weight_pct: number
  yield_pct: number | null
  duration_years: number | null
  sort_order: number
  note: string | null
}

type FixturePortfolio = {
  id: number
  name: string
  description: string | null
  size_amount: number
  as_of_date: string
  target_duration: number | null
  status: 'active' | 'archived'
  version: number
  created_at: string
  updated_at: string
  holdings_count: number
  invested_weight: number
  cash_weight: number
  holdings: FixtureHolding[]
  metrics: Record<string, unknown>
}

function recalculate(portfolio: FixturePortfolio) {
  const invested = portfolio.holdings.reduce((sum, item) => sum + item.weight_pct, 0)
  portfolio.holdings_count = portfolio.holdings.length
  portfolio.invested_weight = invested
  portfolio.cash_weight = 100 - invested
  const allocationMap = new Map<string, number>()
  for (const item of portfolio.holdings) {
    allocationMap.set(item.asset_category, (allocationMap.get(item.asset_category) ?? 0) + item.weight_pct)
  }
  const coveredYield = portfolio.holdings.filter((item) => item.yield_pct !== null)
  const coveredDuration = portfolio.holdings.filter((item) => item.duration_years !== null)
  const weighted = (items: FixtureHolding[], field: 'yield_pct' | 'duration_years') => {
    const weight = items.reduce((sum, item) => sum + item.weight_pct, 0)
    return weight ? items.reduce((sum, item) => sum + Number(item[field]) * item.weight_pct, 0) / weight : null
  }
  portfolio.metrics = {
    invested_weight: invested,
    cash_weight: 100 - invested,
    weighted_duration: weighted(coveredDuration, 'duration_years'),
    duration_coverage: invested ? coveredDuration.reduce((sum, item) => sum + item.weight_pct, 0) / invested * 100 : null,
    weighted_yield: weighted(coveredYield, 'yield_pct'),
    yield_coverage: invested ? coveredYield.reduce((sum, item) => sum + item.weight_pct, 0) / invested * 100 : null,
    asset_allocations: [...allocationMap].map(([category, weight]) => ({ category, weight })),
    max_holding_weight: portfolio.holdings.length ? Math.max(...portfolio.holdings.map((item) => item.weight_pct)) : null,
    max_holding_share_of_invested: invested ? Math.max(...portfolio.holdings.map((item) => item.weight_pct)) / invested * 100 : null,
    risk_items: [],
  }
}

/** 无组合 seed：用内存 fixture 模拟服务端，所有业务数据仍通过 UI 创建。 */
async function mockPortfolioApi(page: Page) {
  const portfolios = new Map<number, FixturePortfolio>()

  await page.route('**/sapi/portfolios**', async (route) => {
    const request = route.request()
    const method = request.method()
    const url = new URL(request.url())
    const path = url.pathname
    const json = (data: unknown, status = 200) => route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify({ data }),
    })

    if (path === '/sapi/portfolios' && method === 'GET') {
      const items = [...portfolios.values()].map(({ holdings: _holdings, metrics: _metrics, ...summary }) => summary)
      return json({ items, total: items.length, page: 1, page_size: 20, total_pages: 1 })
    }

    if (path === '/sapi/portfolios' && method === 'POST') {
      const body = request.postDataJSON() as { name: string; description?: string; size_amount: number; as_of_date: string; target_duration?: number | null }
      const id = portfolios.size + 1
      const portfolio: FixturePortfolio = {
        id,
        name: body.name,
        description: body.description ?? null,
        size_amount: body.size_amount,
        as_of_date: body.as_of_date,
        target_duration: body.target_duration ?? null,
        status: 'active',
        version: 1,
        created_at: '2026-11-20T08:00:00',
        updated_at: '2026-11-20T08:00:00',
        holdings_count: 0,
        invested_weight: 0,
        cash_weight: 100,
        holdings: [],
        metrics: {},
      }
      recalculate(portfolio)
      portfolios.set(id, portfolio)
      return json(portfolio, 201)
    }

    const detailMatch = path.match(/^\/sapi\/portfolios\/(\d+)$/)
    if (detailMatch && method === 'GET') {
      const portfolio = portfolios.get(Number(detailMatch[1]))
      return portfolio ? json(portfolio) : json({ detail: '组合不存在' }, 404)
    }

    const holdingsMatch = path.match(/^\/sapi\/portfolios\/(\d+)\/holdings$/)
    if (holdingsMatch && method === 'POST') {
      const portfolio = portfolios.get(Number(holdingsMatch[1]))!
      const body = request.postDataJSON() as Omit<FixtureHolding, 'id' | 'sort_order'> & { expected_version: number }
      if (body.expected_version !== portfolio.version) return json({ detail: '组合版本冲突' }, 409)
      portfolio.holdings.push({
        id: portfolio.holdings.length + 1,
        bond_code: body.bond_code,
        bond_name: body.bond_name,
        asset_category: body.asset_category,
        weight_pct: body.weight_pct,
        yield_pct: body.yield_pct,
        duration_years: body.duration_years,
        note: body.note,
        sort_order: portfolio.holdings.length,
      })
      portfolio.version += 1
      recalculate(portfolio)
      return json(portfolio, 201)
    }

    const holdingMatch = path.match(/^\/sapi\/portfolios\/(\d+)\/holdings\/(\d+)$/)
    if (holdingMatch && method === 'PATCH') {
      const portfolio = portfolios.get(Number(holdingMatch[1]))!
      const item = portfolio.holdings.find((holding) => holding.id === Number(holdingMatch[2]))!
      const body = request.postDataJSON() as Partial<FixtureHolding> & { expected_version: number }
      if (body.expected_version !== portfolio.version) return json({ detail: '组合版本冲突' }, 409)
      Object.assign(item, {
        bond_code: body.bond_code,
        bond_name: body.bond_name,
        asset_category: body.asset_category,
        weight_pct: body.weight_pct,
        yield_pct: body.yield_pct,
        duration_years: body.duration_years,
        note: body.note,
      })
      portfolio.version += 1
      recalculate(portfolio)
      return json(portfolio)
    }

    const exportMatch = path.match(/^\/sapi\/portfolios\/(\d+)\/export$/)
    if (exportMatch && method === 'GET') {
      const portfolio = portfolios.get(Number(exportMatch[1]))!
      const rows = portfolio.holdings.map((item) => [item.bond_code, item.bond_name, item.asset_category, item.weight_pct, item.yield_pct ?? '', item.duration_years ?? '', item.note ?? ''].join(','))
      return route.fulfill({
        status: 200,
        contentType: 'text/csv; charset=utf-8',
        headers: { 'Content-Disposition': 'attachment; filename="portfolio.csv"' },
        body: `bond_code,bond_name,asset_category,weight_pct,yield_pct,duration_years,note\n${rows.join('\n')}\n`,
      })
    }

    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'fixture route not found' }) })
  })
}

test('研究组合主路径：创建、手动持仓、编辑、刷新持久化与导出', async ({ page }) => {
  await mockPortfolioApi(page)
  await page.goto('/portfolio')

  await page.getByRole('button', { name: '新建组合' }).first().click()
  await page.getByLabel('组合名称').fill('E2E 研究组合')
  await page.getByLabel('配置金额（万元）').fill('1000')
  await page.getByLabel('指标日期').fill('2026-11-20')
  await page.getByLabel('目标久期（年）').fill('3.5')
  await page.getByRole('button', { name: '创建组合' }).click()

  await expect(page).toHaveURL(/\/portfolio\/1$/)
  await expect(page.getByRole('heading', { name: 'E2E 研究组合' })).toBeVisible()
  await expect(page.getByText('暂无持仓，当前组合以现金为主。')).toBeVisible()

  await page.getByRole('button', { name: '新增持仓' }).click()
  await page.getByLabel('债券代码').fill('240004')
  await page.getByLabel('债券名称').fill('E2E 国债')
  await page.getByLabel('资产分类').fill('国债')
  await page.getByLabel('持仓权重（%）').fill('25')
  await page.getByLabel('到期收益率（%）').fill('1.75')
  await page.getByLabel('持仓久期（年）').fill('4.2')
  await page.getByRole('button', { name: '添加持仓' }).click()
  await expect(page.getByText('E2E 国债', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: '编辑 E2E 国债' }).click()
  await page.getByLabel('持仓权重（%）').fill('60')
  await page.getByLabel('持仓备注').fill('刷新后仍应保留')
  await page.getByRole('button', { name: '保存持仓' }).click()
  await expect(page.getByText('持仓已更新。')).toBeVisible()

  await page.reload()
  await expect(page.getByRole('heading', { name: 'E2E 研究组合' })).toBeVisible()
  const holdingRow = page.getByRole('row').filter({ hasText: 'E2E 国债' })
  await expect(holdingRow).toContainText('60.00%')
  await expect(holdingRow).toContainText('刷新后仍应保留')
  await expect(page.getByText('版本 3')).toBeVisible()

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出 CSV' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/^E2E 研究组合-2026-11-20\.csv$/)
  const stream = await download.createReadStream()
  let csv = ''
  for await (const chunk of stream!) csv += chunk.toString()
  expect(csv).toContain('240004,E2E 国债,国债,60,1.75,4.2,刷新后仍应保留')
})
