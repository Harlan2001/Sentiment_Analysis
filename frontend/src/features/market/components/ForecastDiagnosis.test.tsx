import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { API_PREFIX } from '@/api/client'
import { server } from '@/test/server'
import { createTestQueryClient } from '@/test/render'
import ForecastDiagnosis from './ForecastDiagnosis'
import type { ForecastDiagnosisResponse, ForecastHorizonDiagnosis } from '@/types'

function horizon(overrides: Partial<ForecastHorizonDiagnosis> = {}): ForecastHorizonDiagnosis {
  return {
    horizon: '日',
    holding_days: 1,
    sample_size: 76,
    hit_count: 47,
    hit_rate: 0.618,
    majority_base: 0.803,
    delta: -0.185,
    avg_abs_error_bp: 2.06,
    predicted_up_share: 0.368,
    actual_up_share: 0.197,
    confidence_interval: [0.506, 0.731],
    quality: 'risk',
    confidence_buckets: [],
    calibration: [],
    ...overrides,
  }
}

function payload(horizons: ForecastHorizonDiagnosis[]): ForecastDiagnosisResponse {
  return {
    period: '10Y',
    report_count: 117,
    horizons,
    generated_at: '2026-10-22',
  }
}

const wrapper = ({ children }: { children?: ReactNode }) => (
  <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
)

function mockDiagnosis(data: ForecastDiagnosisResponse) {
  server.use(http.get(`${API_PREFIX}/forecast/diagnosis`, () => HttpResponse.json({ data })))
}

const THREE = [
  horizon({ horizon: '日', hit_rate: 0.618, majority_base: 0.803, delta: -0.185 }),
  horizon({ horizon: '周', hit_rate: 0.384, majority_base: 0.685, delta: -0.301 }),
  horizon({ horizon: '月', hit_rate: 0.286, majority_base: 0.825, delta: -0.539 }),
]

describe('ForecastDiagnosis', () => {
  it('命中率旁同时显示多数类基准 —— 不能只给一个无参照的数字', async () => {
    mockDiagnosis(payload([horizon()]))
    render(<ForecastDiagnosis />, { wrapper })

    expect(await screen.findByText(/命中率/)).toBeInTheDocument()
    // 命中率同时出现在指标行与对照条，故断言存在而非唯一
    expect(screen.getAllByText('61.8%').length).toBeGreaterThan(0)
    // 基准必须与命中率同屏出现，否则读者会误读为"接近随机"
    // 紧凑版文案为"基准"（表头另用"多数类基准"），故用正则匹配
    expect(screen.getAllByText(/基准/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('80.3%').length).toBeGreaterThan(0)
    expect(screen.getByText('-18.5pt')).toBeInTheDocument()
  })

  it('默认展示日度，周期以切换方式呈现而非并列堆叠', async () => {
    mockDiagnosis(payload(THREE))
    render(<ForecastDiagnosis />, { wrapper })

    expect(await screen.findByRole('button', { name: '日度' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '周度' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '月度' })).toBeInTheDocument()
    // 默认选中日度：主指标区显示日度命中率
    expect(screen.getAllByText('61.8%').length).toBeGreaterThan(0)
  })

  it('切换到周度后主指标随之更新，且不丢失其它周期的横向参照', async () => {
    mockDiagnosis(payload(THREE))
    render(<ForecastDiagnosis />, { wrapper })
    await screen.findByRole('button', { name: '周度' })

    await userEvent.click(screen.getByRole('button', { name: '周度' }))

    // 主指标切到周度
    expect(screen.getAllByText('38.4%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('68.5%').length).toBeGreaterThan(0)
    // 其它周期仍作为参照可见（避免丢失周期之间的程度差异）
    const others = screen.getByText('其它周期')
    expect(others).toBeInTheDocument()
  })

  it('点击底部参照项也能切换周期', async () => {
    mockDiagnosis(payload(THREE))
    render(<ForecastDiagnosis />, { wrapper })
    await screen.findByRole('button', { name: '月度' })

    // 底部参照项文本形如「月度 28.6% 基准 82.5% 风险」，按正则匹配
    await userEvent.click(screen.getByRole('button', { name: /月度\s*28\.6%/ }))

    expect(screen.getAllByText('82.5%').length).toBeGreaterThan(0)
  })

  it('按三档标签给出结论，跑输基准时标为风险', async () => {
    mockDiagnosis(payload([horizon({ quality: 'risk' })]))
    render(<ForecastDiagnosis />, { wrapper })
    expect(await screen.findAllByText('风险')).not.toHaveLength(0)
  })

  it('样本不足的置信度分档不展示，避免小样本误导', async () => {
    mockDiagnosis(
      payload([
        horizon({
          confidence_buckets: [
            {
              label: '≥0.65',
              sample_size: 10,
              sufficient: false,
              hit_rate: 0.3,
              majority_base: 0.68,
              avg_abs_error_bp: 4.1,
            },
          ],
        }),
      ]),
    )
    render(<ForecastDiagnosis />, { wrapper })

    expect(await screen.findByText(/样本均不足 20/)).toBeInTheDocument()
    expect(screen.queryByText('30.0%')).not.toBeInTheDocument()
  })

  it('无样本不臆断，给出可评估为空的提示', async () => {
    mockDiagnosis(payload([horizon({ sample_size: 0, hit_rate: null, majority_base: null })]))
    render(<ForecastDiagnosis />, { wrapper })
    expect(await screen.findByText(/暂无可评估的历史预测/)).toBeInTheDocument()
  })

  it('接口失败时展示错误态而非空白', async () => {
    server.use(
      http.get(`${API_PREFIX}/forecast/diagnosis`, () => new HttpResponse(null, { status: 500 })),
    )
    render(<ForecastDiagnosis />, { wrapper })
    expect(await screen.findByText(/诊断数据加载失败/)).toBeInTheDocument()
  })
})