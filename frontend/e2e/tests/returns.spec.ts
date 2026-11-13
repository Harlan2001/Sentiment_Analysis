import { expect, test, type Page } from '@playwright/test'

const selectedDate = '2026-11-10'
const otherDate = '2026-11-11'

function news(id: number, title: string, alignment: 'supporting' | 'opposing') {
  return {
    id,
    title,
    pub_time: `${selectedDate} ${id === 101 ? '09:05' : '10:20'}:00`,
    source: '测试来源',
    direction: alignment === 'supporting' ? '利空' : '利多',
    reason: alignment === 'supporting' ? '同向证据理由' : '反向证据理由',
    horizon: '短期',
    factors: [{ id: 11, name: '资金面', direction: 'negative' }],
    importance_score: id === 101 ? 88 : 72,
    score_signals: null,
    top_category: 'LIQUIDITY',
    score_version: 'e2e-v1',
    market_alignment: alignment,
  }
}

function calendarPayload() {
  const newsByDate = [news(101, '重点同向证据新闻', 'supporting'), news(102, '反向证据新闻', 'opposing')]
  const tenYear = { label: '10年', value: 1.812, previous_date: '2026-11-09', diff_bp: 2.5, direction: 'up' }
  return {
    days: [selectedDate, otherDate].map((date) => ({
      date,
      weekday: '周二',
      bullish_count: 1,
      bearish_count: 1,
      neutral_count: 0,
      active_factors: [{ id: 51, name: '资金面因子', category: 'LIQUIDITY', news_count: 2 }],
    })),
    yields_by_date: {
      [selectedDate]: { '10Y': tenYear },
      [otherDate]: { '10Y': tenYear },
    },
    news_by_date: { [selectedDate]: newsByDate, [otherDate]: newsByDate },
    macro_by_month: {},
    query: { start: '2026-11-01', end: '2026-11-30' },
  }
}

async function mockReturnsAndNews(page: Page) {
  await page.route('**/sapi/returns/calendar?**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: calendarPayload() }) })
  })
  await page.route('**/sapi/news/similar?**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [] }) })
  })
  await page.route('**/sapi/news/102/yield?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { news_id: 102, period: '10年', publish_date: selectedDate, data: [], relative_changes: [], window_before: 10, window_after: 10, window_start: selectedDate, window_end: selectedDate } }),
    })
  })
  await page.route('**/sapi/news/102', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { id: 102, title: '反向证据新闻', source: '测试来源', publish_time: `${selectedDate} 10:20:00`, direction: 'positive', reason: '反向证据理由', horizon: '短期', factors: [] } }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await mockReturnsAndNews(page)
})

test('收益主路径：选日、展开反向证据、打开新闻并返回原日期', async ({ page }) => {
  await page.goto(`/returns?date=${otherDate}`)
  await expect(page.getByRole('heading', { name: '重点同向新闻 1' })).toBeVisible()
  const calendar = await page.locator('.returns-calendar-area').boundingBox()
  const factors = await page.locator('.returns-factors-area').boundingBox()
  expect(calendar).not.toBeNull()
  expect(factors).not.toBeNull()
  const sidebarGap = factors!.y - (calendar!.y + calendar!.height)
  expect(sidebarGap).toBeGreaterThanOrEqual(0)
  expect(sidebarGap).toBeLessThanOrEqual(24)

  await page.getByRole('button', { name: /2026年11月10日/ }).click()
  await expect(page).toHaveURL(new RegExp(`/returns\\?date=${selectedDate}$`))
  const opposingToggle = page.getByRole('button', { name: /反向证据 1/ })
  await expect(opposingToggle).toHaveAttribute('aria-expanded', 'false')
  await opposingToggle.click()
  await expect(opposingToggle).toHaveAttribute('aria-expanded', 'true')

  await page.getByText('反向证据新闻', { exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`/news/102\\?from=returns&date=${selectedDate}$`))
  await page.getByRole('button', { name: '返回收益日历' }).click()
  await expect(page).toHaveURL(new RegExp(`/returns\\?date=${selectedDate}$`))
  await expect(page.getByRole('heading', { name: '重点同向新闻 1' })).toBeVisible()
})

test('390px 移动视口按日历、市场新闻、因子排序且无横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/returns?date=${selectedDate}`)
  await expect(page.getByRole('heading', { name: '重点同向新闻 1' })).toBeVisible()

  const calendar = await page.locator('.returns-calendar-area').boundingBox()
  const daily = await page.locator('.returns-daily').boundingBox()
  const factors = await page.locator('.returns-factors-area').boundingBox()
  expect(calendar).not.toBeNull()
  expect(daily).not.toBeNull()
  expect(factors).not.toBeNull()
  expect(calendar!.y).toBeLessThan(daily!.y)
  expect(daily!.y).toBeLessThan(factors!.y)

  const widths = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    returns: document.querySelector('.returns-page')?.scrollWidth ?? 0,
  }))
  expect(widths.document).toBeLessThanOrEqual(widths.viewport)
  expect(widths.returns).toBeLessThanOrEqual(widths.viewport)

  await page.getByRole('button', { name: /反向证据 1/ }).click()
  await expect(page.getByText('反向证据新闻', { exact: true })).toBeVisible()
})
