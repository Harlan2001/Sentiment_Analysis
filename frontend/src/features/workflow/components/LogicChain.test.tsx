import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { DraftContext, FactorSignal, StrategyValidation } from '@/api/strategy'
import { LogicChain } from '@/features/workflow/components/LogicChain'

afterEach(cleanup)

function factor(overrides: Partial<FactorSignal>): FactorSignal {
  return {
    code: 'F1', name: '因子一', category: 'MACRO', factor_type: 'conceptual',
    direction: 'positive', direction_label: '多', signal_score: 0.72,
    confidence: 0.6, event_count: 2, positive_count: 2, negative_count: 0,
    hit_rate: 0.6, majority_base: 0.55, sample_size: 100, holding_days: 5,
    latest_event_time: '2026-10-27T10:00:00', caliber: 'all_models',
    ...overrides,
  }
}

function baseContext(items: FactorSignal[]): DraftContext {
  return {
    instrument_code: 'FCT_T_MAIN',
    backtest_mode: 'bar',
    candle_interval: '1d',
    prompt_version: 'sentiment-intel-pack-v1',
    token_used: 2823,
    token_budget: 6000,
    reference_time: '2026-10-28T21:30:00',
    factor_panel: {
      items, count: items.length, window_days: 7, model_name: 'glm',
      holding_days: 5, min_samples: 20, caliber: 'all_models',
      reference_time: '2026-10-28T21:30:00',
    },
  }
}

function renderChain(props: Partial<React.ComponentProps<typeof LogicChain>> = {}) {
  return render(
    <LogicChain
      context={baseContext([factor({})])}
      validation={null}
      strategySummary=""
      isDone={false}
      isRunning={false}
      {...props}
    />,
  )
}

describe('LogicChain', () => {
  it('renders all six links of the reasoning chain', () => {
    renderChain()
    expect(screen.getByText('本轮策略的逻辑链条')).toBeInTheDocument()
    expect(screen.getByText('情报装配')).toBeInTheDocument()
    expect(screen.getByText('因子筛选')).toBeInTheDocument()
    expect(screen.getByText('方向汇总')).toBeInTheDocument()
    expect(screen.getByText('门控规则')).toBeInTheDocument()
    expect(screen.getByText('策略落地')).toBeInTheDocument()
    expect(screen.getByText('我方验收')).toBeInTheDocument()
  })

  it('shows the concrete instrument, mode and prompt token usage', () => {
    renderChain()
    expect(screen.getByText('FCT_T_MAIN')).toBeInTheDocument()
    expect(screen.getByText('bar')).toBeInTheDocument()
    expect(screen.getByText('1d')).toBeInTheDocument()
    // token 用量拆成「2823 / 6000 token」，用正则跨元素匹配
    expect(screen.getByText((_, el) => el?.textContent === '2823 / 6000 token')).toBeTruthy()
  })

  it('states the factor panel size and its sample threshold', () => {
    renderChain()
    expect(screen.getByText(/从 381 个因子中筛出/)).toBeInTheDocument()
    expect(screen.getByText(/样本量 ≥ 20/)).toBeInTheDocument()
  })

  it('discloses that hit rates come from a mixed-model caliber', () => {
    renderChain()
    expect(screen.getByText(/doubao \/ deepseek \/ glm/)).toBeInTheDocument()
  })

  it('reports a long bias when long factors outnumber short ones', () => {
    const { container } = renderChain({
      context: baseContext([
        factor({ code: 'A', direction: 'positive' }),
        factor({ code: 'B', direction: 'positive' }),
        factor({ code: 'C', direction: 'negative', direction_label: '空' }),
      ]),
    })
    expect(screen.getAllByText(/偏多，支持做多方向/).length).toBeGreaterThan(0)
    // 顶部统计：2 多 / 1 空 / 3 因子
    const summary = container.querySelector('.sf-chain-summary')
    expect(summary?.textContent).toContain('2')
    expect(summary?.textContent).toContain('1')
  })

  it('warns about conflicting signals when long and short are balanced', () => {
    renderChain({
      context: baseContext([
        factor({ code: 'A', direction: 'positive' }),
        factor({ code: 'B', direction: 'negative', direction_label: '空' }),
      ]),
    })
    expect(screen.getAllByText(/多空相当，方向冲突/).length).toBeGreaterThan(0)
  })

  it('says so plainly when no factor passed the historical test', () => {
    renderChain({ context: baseContext([]) })
    expect(screen.getByText(/没有因子通过历史检验/)).toBeInTheDocument()
  })

  it('warns that a platform pass does not mean trades happened', () => {
    renderChain()
    // 用户最容易误解的一点：平台说"通过"而策略一笔没交易。
    expect(screen.getByText(/0 成交也算通过/)).toBeInTheDocument()
  })

  it('reports the verdict and per-step evidence once validated', () => {
    const validation: StrategyValidation = {
      verdict: 'no_trade', passed: false, retryable: true,
      steps: [
        { step: 'backtest_finished', ok: true },
        { step: 'trade_count_parsed', ok: true },
        { step: 'trade_count_positive', ok: false },
      ],
      trade_count: 0, raw_trade_line: '成交笔数: 0',
      symbol_whitelisted: true,
      reason: '回测正常结束但成交 0 笔，策略未真实运转',
    }
    const { container } = renderChain({ validation, isDone: true })
    expect(screen.getByText(/成交 0 笔，策略未真实运转/)).toBeInTheDocument()
    // 三步判定以列表形式渲染，逐项可核对
    const checks = container.querySelectorAll('.sf-chain-checks li')
    expect(checks).toHaveLength(3)
    expect(checks[0].className).toBe('ok')
    expect(checks[2].className).toBe('bad')
    expect(container.querySelector('.sf-chain-trades em')?.textContent).toBe('0')
  })

  it('admits when validation data is missing instead of implying success', () => {
    renderChain({ validation: null, isDone: true })
    expect(screen.getByText(/尚未返回我方验收结论/)).toBeInTheDocument()
  })

  it('surfaces the factor usage the strategy itself describes', () => {
    renderChain({
      isDone: true,
      strategySummary: '本策略将货币政策周期作为开仓门控条件，仅当因子利多时才允许开仓。',
    })
    expect(screen.getAllByText(/作为开仓门控条件/).length).toBeGreaterThan(0)
  })
})