import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { FactorSignalPanel } from '@/api/strategy'
import { FactorSignalTable } from '@/features/workflow/components/FactorSignalTable'

afterEach(cleanup)

function makePanel(overrides: Partial<FactorSignalPanel> = {}): FactorSignalPanel {
  return {
    items: [],
    count: 0,
    window_days: 7,
    model_name: 'glm',
    holding_days: 5,
    min_samples: 20,
    caliber: 'all_models',
    reference_time: '2026-10-28T21:30:00',
    ...overrides,
  }
}

const SAMPLE_ITEMS: FactorSignalPanel['items'] = [
  {
    code: 'MONETARY_POLICY_CYCLE',
    name: '货币政策周期',
    category: 'POLICY',
    factor_type: 'conceptual',
    direction: 'positive',
    direction_label: '多',
    signal_score: 0.72,
    confidence: 0.61,
    event_count: 3,
    positive_count: 2,
    negative_count: 1,
    hit_rate: 0.618,
    majority_base: 0.606,
    sample_size: 170,
    holding_days: 5,
    latest_event_time: '2026-10-27T14:12:00',
    caliber: 'all_models',
  },
  {
    code: 'UNDERWEIGHT_PRESSURE',
    name: '欠配压力',
    category: 'SENTIMENT',
    factor_type: 'conceptual',
    direction: 'negative',
    direction_label: '空',
    signal_score: -0.55,
    confidence: 0.44,
    event_count: 2,
    positive_count: 0,
    negative_count: 2,
    hit_rate: 0.591,
    majority_base: 0.584,
    sample_size: 88,
    holding_days: 5,
    latest_event_time: '2026-10-25T09:00:00',
    caliber: 'all_models',
  },
]

describe('FactorSignalTable', () => {
  it('shows an explicit "insufficient evidence" state instead of a blank area', () => {
    render(<FactorSignalTable panel={makePanel()} />)
    expect(screen.getByText('证据不足')).toBeInTheDocument()
    expect(screen.getByText(/样本量 ≥ 20/)).toBeInTheDocument()
  })

  it('tells the user when no panel was produced at all', () => {
    render(<FactorSignalTable panel={null} />)
    expect(screen.getByText('本轮未生成因子信号面板。')).toBeInTheDocument()
  })

  it('renders each factor with its hit rate next to the majority baseline', () => {
    render(<FactorSignalTable panel={makePanel({ items: SAMPLE_ITEMS, count: 2 })} />)

    expect(screen.getByText('货币政策周期')).toBeInTheDocument()
    expect(screen.getByText('MONETARY_POLICY_CYCLE')).toBeInTheDocument()
    // 命中率与基准必须同屏，否则用户无法判断这个因子是否真的有效。
    expect(screen.getByText('0.618')).toBeInTheDocument()
    expect(screen.getByText('基准 0.606')).toBeInTheDocument()
    expect(screen.getByText('170')).toBeInTheDocument()
  })

  it('labels each factor direction in bond-market terms', () => {
    render(<FactorSignalTable panel={makePanel({ items: SAMPLE_ITEMS, count: 2 })} />)
    expect(screen.getByText('多')).toBeInTheDocument()
    expect(screen.getByText('空')).toBeInTheDocument()
    expect(screen.getByText(/多 = 利多债券/)).toBeInTheDocument()
  })

  it('discloses that historical hit rates are a mixed-model caliber', () => {
    render(<FactorSignalTable panel={makePanel({ items: SAMPLE_ITEMS, count: 2 })} />)
    expect(screen.getByText('历史表现：全模型口径')).toBeInTheDocument()
  })

  it('shows the sampling window and model so the numbers are reproducible', () => {
    render(<FactorSignalTable panel={makePanel({ items: SAMPLE_ITEMS, count: 2 })} />)
    expect(screen.getByText(/窗口 7 天/)).toBeInTheDocument()
    expect(screen.getByText(/抽取模型 glm/)).toBeInTheDocument()
    expect(screen.getByText(/持有期 T\+5/)).toBeInTheDocument()
  })
})