import type { StrategyValidation, ValidationVerdict } from '@/api/strategy'

type Props = {
  validation: StrategyValidation | null | undefined
}

const VERDICT_LABELS: Record<ValidationVerdict, string> = {
  passed: '✓ 验收通过',
  no_trade: '✗ 无成交（不合格）',
  backtest_failed: '✗ 回测失败',
  backtest_error: '✗ 回测异常',
}

const VERDICT_TONES: Record<ValidationVerdict, string> = {
  passed: 'passed',
  no_trade: 'rejected',
  backtest_failed: 'failed',
  backtest_error: 'failed',
}

const STEP_LABELS: Record<string, string> = {
  backtest_finished: '回测正常结束',
  trade_count_parsed: '解析到成交笔数',
  trade_count_positive: '成交笔数大于 0',
  symbol_whitelisted: '标的在白名单内',
  order_type_matched: '下单类型与标的匹配',
}

/** 从回测日志里抠出成交笔数，用于没有 validation 字段的历史版本兜底展示。 */
function fallbackTradeCount(backtestSummary: string): number | null {
  const matched = backtestSummary.match(/成交笔数\s*[:：]\s*(-?\d+)/)
  return matched ? Number(matched[1]) : null
}

/**
 * 验收结论卡片。
 *
 * 对端平台的判定口径是"回测进程正常退出"，0 成交也算通过——所以"回测通过"
 * 这个绿灯本身不可信（实测 25 个历史模板里 21 个 0 成交却全部 passed）。
 * 这里展示的是我方验收门的结论，以及三步判定的逐项依据。
 */
export function ValidationSummary({
  validation,
  backtestPassed,
  backtestSummary,
}: Props & { backtestPassed?: boolean | null; backtestSummary?: string }) {
  if (!validation) {
    // 历史版本没有验收结论：至少把真实的成交笔数摆出来，不要把"回测通过"当成功。
    const trades = fallbackTradeCount(backtestSummary || '')
    return (
      <div className="sf-verify sf-verify--legacy">
        <header>
          <span className="sf-verify-badge sf-verify-badge--legacy">
            {backtestPassed ? '历史版本·回测通过' : '历史版本·回测未通过'}
          </span>
        </header>
        <p>
          {trades === null
            ? '该版本生成于验收门上线之前，未记录我方验收结论。'
            : trades > 0
              ? `该版本生成于验收门上线之前；回测日志显示成交 ${trades} 笔。`
              : '该版本生成于验收门上线之前；回测日志显示 0 成交，按现行标准属不合格。'}
        </p>
      </div>
    )
  }

  const tone = VERDICT_TONES[validation.verdict] ?? 'failed'
  return (
    <div className={`sf-verify sf-verify--${tone}`}>
      <header>
        <span className={`sf-verify-badge sf-verify-badge--${tone}`}>
          {VERDICT_LABELS[validation.verdict] ?? validation.verdict}
        </span>
        {validation.trade_count !== null && (
          <span className="sf-verify-trades">成交 {validation.trade_count} 笔</span>
        )}
      </header>

      <ol className="sf-verify-steps">
        {validation.steps.map((step) => (
          <li key={step.step} className={step.ok ? 'ok' : 'bad'}>
            <span className="sf-verify-step-mark">{step.ok ? '✓' : '✗'}</span>
            <span className="sf-verify-step-label">{STEP_LABELS[step.step] ?? step.step}</span>
            {step.detail && <small>{step.detail}</small>}
          </li>
        ))}
      </ol>

      {validation.reason && <p className="sf-verify-reason">{validation.reason}</p>}
    </div>
  )
}