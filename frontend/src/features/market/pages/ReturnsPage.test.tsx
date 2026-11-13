import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { API_PREFIX } from '@/api/client'
import { renderWithProviders } from '@/test/render'
import { server } from '@/test/server'
import type {
  CalendarNewsItem,
  ReturnsCalendarResponse,
  YieldChangeItem,
} from '@/types'
import ReturnsPage from './ReturnsPage'

const SELECTED = '2026-11-10'
const TODAY = '2026-11-11'
const PERIODS = ['3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '30Y']
const LABELS: Record<string, string> = {
  '3M': '3月', '6M': '6月', '1Y': '1年', '2Y': '2年', '3Y': '3年',
  '5Y': '5年', '7Y': '7年', '10Y': '10年', '30Y': '30年',
}

function makeYield(overrides: Partial<YieldChangeItem> = {}): YieldChangeItem {
  return {
    label: '10年',
    value: 1.812,
    diff_bp: 2.5,
    direction: 'up',
    previous_date: '2026-11-09',
    ...overrides,
  } as YieldChangeItem
}

function makeNews(overrides: Partial<CalendarNewsItem> = {}): CalendarNewsItem {
  return {
    id: 1,
    title: '同向新闻 1',
    pub_time: '2026-11-10 09:05:59',
    source: '测试来源',
    direction: '利空',
    reason: '资金价格上行，压制债券表现',
    horizon: '短期',
    factors: [
      { id: 11, name: '资金面', direction: 'negative' },
      { id: 12, name: '货币政策', direction: 'negative' },
      { id: 13, name: '利率债', direction: 'negative' },
    ],
    importance_score: 88.4,
    score_signals: { direction: 0.8 },
    top_category: 'LIQUIDITY',
    score_version: 'v1',
    market_alignment: 'supporting',
    ...overrides,
  } as CalendarNewsItem
}

function yieldsFor(date = SELECTED, tenYear = makeYield()) {
  return {
    [date]: Object.fromEntries(PERIODS.map((period, index) => [
      period,
      period === '10Y'
        ? tenYear
        : makeYield({ label: LABELS[period], value: 1.5 + index / 100, diff_bp: index % 2 ? -0.5 : 0 }),
    ])),
  }
}

function makeResponse(overrides: Partial<ReturnsCalendarResponse> = {}): ReturnsCalendarResponse {
  return {
    days: [{
      date: SELECTED,
      weekday: '周二',
      bullish_count: 1,
      bearish_count: 8,
      neutral_count: 1,
      active_factors: [{ id: 51, name: '资金面因子', category: 'LIQUIDITY', news_count: 9 }],
    }, {
      date: TODAY,
      weekday: '周三',
      bullish_count: 2,
      bearish_count: 3,
      neutral_count: 0,
      active_factors: [],
    }],
    yields_by_date: yieldsFor(),
    news_by_date: { [SELECTED]: [makeNews()] },
    macro_by_month: {},
    query: { start: '2026-11-01', end: '2026-11-30' },
    ...overrides,
  } as ReturnsCalendarResponse
}

function LocationProbe() {
  const location = useLocation()
  return (
    <>
      <output data-testid="location">{`${location.pathname}${location.search}`}</output>
      <output data-testid="return-from">{(location.state as { from?: string } | null)?.from ?? ''}</output>
    </>
  )
}

function renderReturns(route = `/returns?date=${SELECTED}`) {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/returns" element={<><ReturnsPage /><LocationProbe /></>} />
        <Route path="/news/:newsId" element={<LocationProbe />} />
        <Route path="/factor/:factorId" element={<LocationProbe />} />
      </Routes>
    </>,
    { route, withAuth: false },
  )
}

let requestUrls: string[]

function mockCalendar(
  response: ReturnsCalendarResponse | ((start: string, end: string) => ReturnsCalendarResponse) = makeResponse(),
) {
  server.use(
    http.get(`${API_PREFIX}/returns/calendar`, ({ request }) => {
      requestUrls.push(request.url)
      const url = new URL(request.url)
      const start = url.searchParams.get('start') ?? ''
      const end = url.searchParams.get('end') ?? ''
      const payload = typeof response === 'function' ? response(start, end) : response
      return HttpResponse.json({ data: payload })
    }),
  )
}

async function openEvidence(name: RegExp) {
  await userEvent.click(screen.getByRole('button', { name }))
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 10, 11, 8, 0, 0))
  requestUrls = []
})

afterEach(() => {
  vi.useRealTimers()
})

describe('ReturnsPage — URL 与月历', () => {
  it('以有效 date 初始化月份和选中日，请求自然月且不发送 selected，提供完整 aria 状态', async () => {
    mockCalendar()
    renderReturns()

    expect(await screen.findByText('同向新闻 1')).toBeInTheDocument()
    const initialUrl = new URL(requestUrls[0])
    expect(initialUrl.searchParams.get('start')).toBe('2026-11-01')
    expect(initialUrl.searchParams.get('end')).toBe('2026-11-30')
    expect(initialUrl.searchParams.has('selected')).toBe(false)

    const selected = screen.getByRole('button', { name: /2026年11月10日/ })
    expect(selected).toHaveAttribute('aria-pressed', 'true')
    expect(selected).toHaveAttribute('aria-label', expect.stringContaining('10Y +2.5 BP'))
    expect(selected).toHaveAttribute('aria-label', expect.stringContaining('利多 1 条'))
    expect(selected).toHaveAttribute('aria-label', expect.stringContaining('利空 8 条'))

    const today = screen.getByRole('button', { name: /2026年11月11日/ })
    expect(today).toHaveAttribute('aria-current', 'date')
    expect(today).toHaveAttribute('aria-pressed', 'false')
    selected.focus()
    expect(selected).toHaveFocus()
    expect(screen.getByRole('heading', { name: '2026年11月 收益日历' })).toBeInTheDocument()
  })

  it('无有效 date 时回到今天并规范化 URL', async () => {
    mockCalendar(makeResponse({
      yields_by_date: yieldsFor(TODAY),
      news_by_date: { [TODAY]: [makeNews({ pub_time: '2026-11-11 09:05:59' })] },
    }))
    renderReturns('/returns?date=2026-02-30')

    expect(await screen.findByText('同向新闻 1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: new RegExp(`2026年11月11日`) })).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(`/returns?date=${TODAY}`))
    expect(new URL(requestUrls[0]).searchParams.get('start')).toBe('2026-11-01')
  })

  it('同月选日只更新 URL 并复用缓存，可通过键盘选择', async () => {
    mockCalendar()
    renderReturns()
    expect(await screen.findByText('同向新闻 1')).toBeInTheDocument()
    expect(requestUrls).toHaveLength(1)

    const today = screen.getByRole('button', { name: /2026年11月11日/ })
    today.focus()
    await userEvent.keyboard('{Enter}')

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(`/returns?date=${TODAY}`))
    expect(today).toHaveAttribute('aria-pressed', 'true')
    expect(requestUrls).toHaveLength(1)
    expect(screen.getByText('该日期暂无方向性新闻')).toBeInTheDocument()
  })

  it('月切换保留日期并钳到月末，请求新月自然月范围', async () => {
    mockCalendar((start, end) => makeResponse({
      days: [], yields_by_date: {}, news_by_date: {}, query: { start, end },
    }))
    renderReturns('/returns?date=2026-01-31')
    await waitFor(() => expect(requestUrls).toHaveLength(1))

    await userEvent.click(screen.getByRole('button', { name: '下个月' }))

    await waitFor(() => expect(requestUrls).toHaveLength(2))
    const nextUrl = new URL(requestUrls[1])
    expect(nextUrl.searchParams.get('start')).toBe('2026-02-01')
    expect(nextUrl.searchParams.get('end')).toBe('2026-02-28')
    expect(screen.getByTestId('location')).toHaveTextContent('/returns?date=2026-02-28')
    expect(screen.getByRole('button', { name: /2026年2月28日/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('回到今天恢复今天所在月份和选中日', async () => {
    mockCalendar((start, end) => makeResponse({
      days: [], yields_by_date: {}, news_by_date: {}, query: { start, end },
    }))
    renderReturns('/returns?date=2026-10-31')
    await waitFor(() => expect(requestUrls).toHaveLength(1))

    await userEvent.click(screen.getByRole('button', { name: '回到今天' }))

    await waitFor(() => expect(requestUrls).toHaveLength(2))
    expect(new URL(requestUrls[1]).searchParams.get('start')).toBe('2026-11-01')
    expect(screen.getByTestId('location')).toHaveTextContent(`/returns?date=${TODAY}`)
    expect(screen.getByRole('button', { name: /2026年11月11日/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('加载失败可重试恢复，成功响应分别展示行情、新闻和因子空态', async () => {
    mockCalendar()
    server.use(http.get(`${API_PREFIX}/returns/calendar`, () =>
      HttpResponse.json({ detail: 'boom' }, { status: 500 }), { once: true }))
    renderReturns()

    expect(await screen.findByText('收益数据加载失败，请稍后重试')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByText('同向新闻 1')).toBeInTheDocument()

    server.resetHandlers()
    mockCalendar(makeResponse({ days: [], yields_by_date: {}, news_by_date: {} }))
    renderReturns('/returns?date=2026-11-12')
    expect(await screen.findByText('该日期暂无国债收益率数据')).toBeInTheDocument()
    expect(screen.getByText('该日期暂无方向性新闻')).toBeInTheDocument()
    expect(screen.getByText('暂无活跃因子')).toBeInTheDocument()
    expect(screen.queryByText('非交易日')).not.toBeInTheDocument()
  })
})

describe('ReturnsPage — 市场摘要与新闻证据', () => {
  it('突出 10Y 和上一有效交易日，展示九期限、对齐计数及非因果说明', async () => {
    const supporting = Array.from({ length: 7 }, (_, index) => makeNews({
      id: index + 1,
      title: `同向新闻 ${index + 1}`,
      importance_score: index === 0 ? null : 90 - index,
    }))
    const opposing = makeNews({
      id: 20, title: '反向新闻', direction: '利多', market_alignment: 'opposing',
      pub_time: '2026-11-10 10:20:00', reason: '反向证据理由', importance_score: 70,
    })
    const neutral = makeNews({
      id: 30, title: '中性新闻', direction: '中性', market_alignment: 'neutral',
      pub_time: '2026-11-10 11:30:00', importance_score: null,
    })
    mockCalendar(makeResponse({ news_by_date: { [SELECTED]: [...supporting, opposing, neutral] } }))
    renderReturns()

    expect(await screen.findByText('同向新闻 1')).toBeInTheDocument()
    expect(screen.getAllByText('1.812%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('+2.5 BP').length).toBeGreaterThan(0)
    expect(screen.getByText('较 2026-11-09（上一有效交易日）')).toBeInTheDocument()
    expect(screen.getByText('30年')).toBeInTheDocument()
    expect(screen.getByText('同向 7')).toBeInTheDocument()
    expect(screen.getByText('反向 1')).toBeInTheDocument()
    expect(screen.getByText('中性 1')).toBeInTheDocument()
    expect(screen.getByText('AI 新闻方向与 10Y 收益率变动的方向对照，不代表因果归因')).toBeInTheDocument()
    expect(screen.getByText('静态分，未叠加相对当前时间的衰减')).toBeInTheDocument()

    for (const index of [1, 2, 3, 4, 5]) {
      expect(screen.getByText(`同向新闻 ${index}`)).toBeInTheDocument()
    }
    expect(screen.queryByText('同向新闻 6')).not.toBeInTheDocument()
    expect(screen.queryByText('同向新闻 7')).not.toBeInTheDocument()
    expect(screen.queryByText('反向新闻')).not.toBeInTheDocument()
    expect(screen.queryByText('中性新闻')).not.toBeInTheDocument()
    expect(screen.getAllByText('暂未评分')).toHaveLength(1)
    expect(screen.getAllByText('09:05').length).toBeGreaterThan(0)
    expect(screen.getAllByText('资金价格上行，压制债券表现').length).toBeGreaterThan(0)
    expect(screen.getAllByText('短期').length).toBeGreaterThan(0)
    expect(screen.getAllByText('测试来源').length).toBeGreaterThan(0)
    expect(screen.getAllByText('利率债').length).toBeGreaterThan(0)

    await userEvent.click(screen.getByRole('button', { name: '展开全部 7 条' }))
    expect(screen.getByText('同向新闻 6')).toBeInTheDocument()
    expect(screen.getByText('同向新闻 7')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '收起重点同向新闻' })).toHaveAttribute('aria-expanded', 'true')

    await openEvidence(/反向证据 1/)
    expect(screen.getByText('反向新闻')).toBeInTheDocument()
    expect(screen.getByText('反向证据理由')).toBeInTheDocument()
    await openEvidence(/中性及其他 1/)
    expect(screen.getByText('中性新闻')).toBeInTheDocument()
  })

  it('无 10Y 可计算基准时退化为利多/利空/中性普通分组，null BP 显示 —', async () => {
    const tenYear = makeYield({ diff_bp: null, direction: 'unavailable', previous_date: null })
    mockCalendar(makeResponse({
      yields_by_date: yieldsFor(SELECTED, tenYear),
      news_by_date: { [SELECTED]: [
        makeNews({ id: 1, title: '普通利空', direction: '利空', market_alignment: 'unavailable' }),
        makeNews({ id: 2, title: '普通利多', direction: 'positive', market_alignment: 'unavailable' }),
        makeNews({ id: 3, title: '普通中性', direction: '中性', market_alignment: 'unavailable' }),
      ] },
    }))
    renderReturns()

    expect(await screen.findByText('普通利空')).toBeInTheDocument()
    expect(screen.getAllByText('暂无前值').length).toBeGreaterThan(0)
    expect(screen.queryByText(/同向 \d/)).not.toBeInTheDocument()
    expect(screen.queryByText(/不代表因果归因/)).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '方向性新闻' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '利空新闻 1' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '利多新闻 1' })).toBeInTheDocument()
    expect(screen.getByText('普通利多')).toBeInTheDocument()
    expect(screen.queryByText('普通中性')).not.toBeInTheDocument()
    await openEvidence(/中性新闻 1/)
    expect(screen.getByText('普通中性')).toBeInTheDocument()
    expect(screen.queryByText('null')).not.toBeInTheDocument()
    expect(screen.queryByText('unavailable')).not.toBeInTheDocument()
  })

  it('没有同向新闻但有反向证据时明确展示空态', async () => {
    mockCalendar(makeResponse({ news_by_date: { [SELECTED]: [makeNews({
      id: 20, title: '仅有反向', direction: '利多', market_alignment: 'opposing',
    })] } }))
    renderReturns()

    expect(await screen.findByText('未发现同向新闻')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /反向证据 1/ })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('仅有反向')).not.toBeInTheDocument()
  })

  it('新闻深链携带收益日期', async () => {
    mockCalendar()
    renderReturns()

    await userEvent.click(await screen.findByText('同向新闻 1'))
    expect(screen.getByTestId('location')).toHaveTextContent(`/news/1?from=returns&date=${SELECTED}`)
  })

  it('活跃因子保留 location.state.from 且不截断 API TopN', async () => {
    const factors = Array.from({ length: 6 }, (_, index) => ({
      id: 51 + index, name: `活跃因子 ${index + 1}`, category: 'LIQUIDITY', news_count: 9 - index,
    }))
    mockCalendar(makeResponse({
      days: [{ date: SELECTED, weekday: '周二', bullish_count: 0, bearish_count: 1, neutral_count: 0, active_factors: factors }],
    }))
    renderReturns()

    expect(await screen.findByText('活跃因子 6')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /活跃因子 3/ }))
    expect(screen.getByTestId('location')).toHaveTextContent('/factor/53')
    expect(screen.getByTestId('return-from')).toHaveTextContent(`/returns?date=${SELECTED}`)
  })
})
