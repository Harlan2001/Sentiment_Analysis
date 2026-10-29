import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { StrategyValidation } from '@/api/strategy'
import { ValidationSummary } from '@/features/workflow/components/ValidationSummary'

afterEach(cleanup)

function makeValidation(overrides: Partial<StrategyValidation> = {}): StrategyValidation {
  return {
    verdict: 'passed',
    passed: true,
    retryable: false,
    steps: [
      { step: 'backtest_finished', ok: true, detail: 'passed=True, exit_code=0' },
      { step: 'trade_count_parsed', ok: true, detail: '成交笔数: 27' },
      { step: 'trade_count_positive', ok: true, detail: '成交 27 笔' },
    ],
    trade_count: 27,
    raw_trade_line: '成交笔数: 27',
    symbol_whitelisted: true,
    reason: '回测通过，成交 27 笔',
    ...overrides,
  }
}

describe('ValidationSummary', () => {
  it('shows the passing verdict with its trade count', () => {
    render(<ValidationSummary validation={makeValidation()} />)
    expect(screen.getByText('✓ 验收通过')).toBeInTheDocument()
    // 徽章区和步骤详情都会出现成交笔数，这里断言徽章区那一处。
    expect(screen.getByText('成交 27 笔', { selector: '.sf-verify-trades' })).toBeInTheDocument()
  })

  it('labels zero trades as rejected rather than passed', () => {
    // 平台口径下 0 成交也算"回测通过"，这里必须改口，否则是在误导用户。
    render(
      <ValidationSummary
        validation={makeValidation({
          verdict: 'no_trade',
          passed: false,
          retryable: true,
          trade_count: 0,
          steps: [
            { step: 'backtest_finished', ok: true },
            { step: 'trade_count_parsed', ok: true, detail: '成交笔数: 0' },
            { step: 'trade_count_positive', ok: false, detail: '成交 0 笔' },
          ],
          reason: '回测正常结束但成交 0 笔，策略未真实运转',
        })}
      />,
    )
    expect(screen.getByText('✗ 无成交（不合格）')).toBeInTheDocument()
    expect(screen.queryByText('✓ 验收通过')).not.toBeInTheDocument()
    expect(screen.getByText(/策略未真实运转/)).toBeInTheDocument()
  })

  it('distinguishes a failed backtest from a no-trade result', () => {
    render(
      <ValidationSummary
        validation={makeValidation({
          verdict: 'backtest_failed',
          passed: false,
          trade_count: null,
          steps: [{ step: 'backtest_finished', ok: false, detail: 'passed=False, exit_code=-1' }],
          reason: '回测未正常结束，平台未给回测通过状态',
        })}
      />,
    )
    expect(screen.getByText('✗ 回测失败')).toBeInTheDocument()
  })

  it('shows every step so the verdict can be traced to its evidence', () => {
    render(<ValidationSummary validation={makeValidation()} />)
    expect(screen.getByText('回测正常结束')).toBeInTheDocument()
    expect(screen.getByText('解析到成交笔数')).toBeInTheDocument()
    expect(screen.getByText('成交笔数大于 0')).toBeInTheDocument()
    expect(screen.getByText('成交笔数: 27')).toBeInTheDocument()
  })

  it('flags an order-type mismatch as an error', () => {
    render(
      <ValidationSummary
        validation={makeValidation({
          verdict: 'backtest_error',
          passed: false,
          steps: [
            { step: 'backtest_finished', ok: true },
            { step: 'order_type_matched', ok: false },
          ],
          reason: '下单类型与标的类型不匹配（期货标的用了现券下单类型）',
        })}
      />,
    )
    expect(screen.getByText('✗ 回测异常')).toBeInTheDocument()
    expect(screen.getByText('下单类型与标的匹配')).toBeInTheDocument()
  })

  it('falls back to the raw trade count for versions predating the gate', () => {
    render(
      <ValidationSummary
        validation={null}
        backtestPassed
        backtestSummary={'===== 回测结果 =====\n成交笔数: 0\n总收益率: 0%'}
      />,
    )
    // 历史版本没有验收记录，但也不能把 0 成交当成成功。
    expect(screen.getByText('历史版本·回测通过')).toBeInTheDocument()
    expect(screen.getByText(/0 成交，按现行标准属不合格/)).toBeInTheDocument()
  })

  it('states plainly when a legacy version has no trade data', () => {
    render(<ValidationSummary validation={null} backtestPassed backtestSummary="no metrics" />)
    expect(screen.getByText(/未记录我方验收结论/)).toBeInTheDocument()
  })
})