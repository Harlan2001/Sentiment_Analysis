import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { API_PREFIX } from '@/api/client'
import { renderWithProviders } from '@/test/render'
import { server } from '@/test/server'
import type {
  ForecastHistoryItem,
  ForecastPrediction,
  FullForecastReport,
} from '@/types'
import ForecastPage from './ForecastPage'

function prediction(overrides: Partial<ForecastPrediction> = {}): ForecastPrediction {
  return {
    上涨概率: 0.6,
    下跌概率: 0.4,
    上涨基点: 3,
    下跌基点: -2,
    分析理由: '日度分析理由',
    置信度: 0.7,
    假设条件: ['资金面保持平稳'],
    失效条件: ['资金利率持续超预期上行'],
    ...overrides,
  }
}

function fullReport(): FullForecastReport {
  return {
    预测标的: {
      名称: '中债国债到期收益率',
      期限: '10Y',
      方向口径: '上涨/下跌均指10Y国债收益率方向，债券价格方向相反',
    },
    数据状态: { 包含新闻: true, 包含收益率: true, 新闻截至: '2026-11-06', 收益率截至: '2026-11-05' },
    报告摘要: '资金面边际转松，T+5收益率下行为主。',
    核心驱动: [{
      类型: '资金面',
      方向: '下行',
      适用周期: ['周'],
      理由: '公开市场净投放缓解资金压力。',
      证据新闻ID: [101, 101],
    }],
    预测结果: {
      日: prediction(),
      周: prediction({
        上涨概率: 0.25,
        下跌概率: 0.75,
        上涨基点: 4,
        下跌基点: -5.5,
        分析理由: '周度资金利率中枢可能回落。',
        置信度: 0.82,
      }),
      月: prediction({ 上涨概率: 0.55, 下跌概率: 0.45 }),
    },
    情景分析: {
      基准: { 概率: 0.6, 描述: '资金平稳宽松', 触发条件: 'DR007中枢回落', 应对关注: '跟踪公开市场操作' },
    },
    风险提示: '供给节奏可能改变判断。',
    市场概览: '完整市场概览内容',
  }
}

function mockForecast(
  report: FullForecastReport | string | null = fullReport(),
  history: ForecastHistoryItem[] = [],
) {
  server.use(
    http.get(`${API_PREFIX}/forecast`, ({ request }) => {
      const date = new URL(request.url).searchParams.get('date') ?? '2026-11-06'
      return HttpResponse.json({
        data: {
          count: report === null ? 0 : 1,
          reports: report === null ? [] : [{
            trade_date: date,
            model_name: 'glm-test',
            prompt_version: 'v2.4',
            forecast_type: 'full_report',
            prediction: report,
            created_at: '2026-11-06 18:00:00',
          }],
        },
      })
    }),
    http.get(`${API_PREFIX}/forecast/history`, () => HttpResponse.json({ data: { history } })),
  )
}

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="route">{location.pathname}{location.search}</output>
}

function renderForecast(route = '/forecast') {
  return renderWithProviders(
    <Routes>
      <Route path="/forecast" element={<><ForecastPage /><LocationProbe /></>} />
    </Routes>,
    { route, withAuth: false },
  )
}

describe('ForecastPage', () => {
  it('看跌周期使用下跌基点，同时展示双概率、置信度、依据和失效条件', async () => {
    mockForecast()
    renderForecast()

    expect(await screen.findByText('资金面边际转松，T+5收益率下行为主。')).toBeInTheDocument()
    const weekly = screen.getByRole('button', { name: '查看T+5预测依据' })
    expect(weekly).toHaveAttribute('aria-pressed', 'true')
    expect(weekly).toHaveTextContent('收益率下行')
    expect(within(weekly).getByText('25%')).toBeInTheDocument()
    expect(within(weekly).getByText('75%')).toBeInTheDocument()
    expect(within(weekly).getByText('-5.5bp')).toBeInTheDocument()
    expect(within(weekly).queryByText('+4.0bp')).not.toBeInTheDocument()
    expect(weekly).toHaveTextContent('置信度 0.82')

    expect(screen.getByText('glm-test')).toBeInTheDocument()
    expect(screen.getByText('v2.4')).toBeInTheDocument()
    expect(screen.getByText('2026-11-05')).toBeInTheDocument()
    expect(screen.getByText('资金利率持续超预期上行')).toBeInTheDocument()
    expect(screen.getByText('供给节奏可能改变判断。')).toBeInTheDocument()
    expect(screen.getByText('DR007中枢回落')).toBeInTheDocument()
    const evidence = screen.getByRole('link', { name: '证据 · 新闻 101 →' })
    expect(evidence).toHaveAttribute('href', '/news/101?from=forecast&date=2026-11-06')
  })

  it('切换周期更新主判断和驱动，并按主方向基点比较上一期', async () => {
    const prior = fullReport()
    prior.预测结果!.周 = prediction({
      上涨概率: 0.7,
      下跌概率: 0.3,
      上涨基点: 2,
      下跌基点: -3,
    })
    mockForecast(fullReport(), [{ date: '2026-11-05', reports: { full_report: prior } }])
    renderForecast()

    expect(await screen.findByText(/上行 → 下行/)).toHaveTextContent('主方向BP较上期 -7.5bp')
    await userEvent.click(screen.getByRole('button', { name: '查看T+1预测依据' }))
    expect(screen.getByRole('heading', { name: '收益率上行为主' })).toBeInTheDocument()
    expect(screen.getByText('该周期暂无结构化驱动与证据')).toBeInTheDocument()
    expect(screen.getByText('日度分析理由')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '查看T+5预测依据' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('旧报告保留原始内容但明确标注口径和证据缺失', async () => {
    const legacy = fullReport()
    delete legacy.预测标的
    delete legacy.核心驱动
    mockForecast(legacy)
    renderForecast()

    expect(await screen.findByRole('heading', { name: '债券市场预测' })).toBeInTheDocument()
    expect(screen.getByText(/历史报告未明确预测期限与方向口径/)).toBeInTheDocument()
    expect(await screen.findByText('历史报告未提供结构化驱动与证据')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '10Y 国债收益率预测' })).not.toBeInTheDocument()
  })

  it('历史日历支持 Escape、焦点恢复和日期 URL 深链', async () => {
    const current = fullReport()
    const history = [
      { date: '2026-11-06', reports: { full_report: current } },
      { date: '2026-11-05', reports: { full_report: fullReport() } },
    ]
    mockForecast(current, history)
    renderForecast('/forecast?date=2026-11-06')
    const openButton = await screen.findByRole('button', { name: '历史报告' })
    await userEvent.click(openButton)

    expect(screen.getByRole('dialog', { name: '历史预测报告' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '关闭历史报告' })).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(openButton).toHaveFocus()

    await userEvent.click(openButton)
    const dialog = screen.getByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: /^5/ }))
    await waitFor(() => expect(screen.getByTestId('route')).toHaveTextContent('/forecast?date=2026-11-05'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('区分加载、空报告、解析失败和请求失败状态', async () => {
    server.use(
      http.get(`${API_PREFIX}/forecast`, async () => {
        await delay(30)
        return HttpResponse.json({ data: { count: 0, reports: [] } })
      }),
      http.get(`${API_PREFIX}/forecast/history`, () => HttpResponse.json({ data: { history: [] } })),
    )
    const { unmount } = renderForecast()
    expect(screen.getByLabelText('预测报告加载中')).toBeInTheDocument()
    expect(await screen.findByText('该日期暂无预测报告')).toBeInTheDocument()
    unmount()

    mockForecast('{bad json')
    const malformed = renderForecast()
    expect(await screen.findByText('预测报告解析失败或缺少完整报告')).toBeInTheDocument()
    malformed.unmount()

    server.use(http.get(`${API_PREFIX}/forecast`, () => HttpResponse.json({ detail: '失败' }, { status: 500 })))
    renderForecast()
    expect(await screen.findByText('预测报告加载失败，请稍后重试')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新加载' })).toBeInTheDocument()
  })
})
