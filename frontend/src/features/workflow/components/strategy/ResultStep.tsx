import { useState } from 'react'
import { CodeHighlight } from '@/features/workflow/components/CodeHighlight'
import { StrategySummary } from '@/features/workflow/components/StrategySummary'
import { ValidationSummary } from '@/features/workflow/components/ValidationSummary'
import type { StrategyWizardApi } from './useStrategyWizard'
import { Fold } from './Fold'
import { backtestCards, cleanStrategySummary, displayMetricLabel, metricTone } from './resultMetrics'

/**
 * 步骤⑤：结果报告。S2-2 先把既有验收/指标/代码/日志收拢到此；
 * 结论英雄区、指标分层、权益曲线与逐笔台账在 S2-4/S2-5 改造
 * （唯一图表数据源是 160055 独立回测，不从日志造数）。
 */
export function ResultStep({ wizard }: { wizard: StrategyWizardApi }) {
  const {
    lastVersion, validation, isDone, loading, error: _error, setError: _setError,
  } = wizard
  const [copiedCode, setCopiedCode] = useState(false)

  const metrics = backtestCards(lastVersion)
  const backtestLog = lastVersion?.backtest_summary?.trim() || ''
  const strategySummary = lastVersion?.description ? cleanStrategySummary(lastVersion.description) : ''
  const hasBacktestResult = lastVersion?.backtest_passed !== null && lastVersion?.backtest_passed !== undefined
  const verdictText = !lastVersion
    ? '待回测'
    : validation
      ? validation.verdict === 'passed'
        ? '验收通过'
        : validation.verdict === 'no_trade'
          ? '无成交（不合格）'
          : validation.verdict === 'backtest_failed'
            ? '回测失败'
            : '回测异常'
      : lastVersion.backtest_passed
        ? '回测通过（未验收）'
        : '回测未通过'
  const verdictTone = !lastVersion
    ? 'neutral'
    : validation
      ? validation.verdict === 'passed' ? 'success' : 'warning'
      : lastVersion.backtest_passed ? 'success' : 'warning'

  async function copyCode() {
    if (!lastVersion?.code) return
    let copied = false
    try {
      await navigator.clipboard.writeText(lastVersion.code)
      copied = true
    } catch {
      const helper = document.createElement('textarea')
      helper.value = lastVersion.code
      helper.style.position = 'fixed'
      helper.style.opacity = '0'
      document.body.appendChild(helper)
      helper.select()
      copied = document.execCommand('copy')
      helper.remove()
    }
    if (!copied) { _setError('复制代码失败，请手动选择代码复制。'); return }
    setCopiedCode(true)
    window.setTimeout(() => setCopiedCode(false), 1800)
  }

  if (!isDone) {
    return (
      <section className="sw-panel" aria-label="结果报告">
        <header className="sw-panel-head">
          <div><h2>结果报告</h2><p>生成并回测完成后展示验收结论、指标与代码。</p></div>
        </header>
        <div className="sw-empty-hint">{loading ? '正在读取…' : '回测完成后本步骤自动解锁。'}</div>
      </section>
    )
  }

  return (
    <section className="sw-panel" aria-label="结果报告">
      <header className="sw-panel-head">
        <div>
          <h2>结果报告</h2>
          <p>验收结论优先于平台回测状态：0 成交一律判为不合格。AI 生成的研究草案，回测结果不代表实盘。</p>
        </div>
        <span className={`sw-badge sw-badge--${verdictTone}`}>{verdictText}</span>
      </header>

      {strategySummary && (
        <div className="sw-result-summary">
          <h3>策略概要</h3>
          <StrategySummary markdown={strategySummary} />
        </div>
      )}

      <ValidationSummary
        validation={validation}
        backtestPassed={lastVersion?.backtest_passed}
        backtestSummary={backtestLog}
      />

      <div className={`sw-result-metrics${hasBacktestResult ? ` sw-result-metrics--${lastVersion?.backtest_passed ? 'passed' : 'failed'}` : ''}`}>
        <header><h3>回测指标</h3><span>{metrics.length} 项</span></header>
        {metrics.length > 0
          ? <div className="sw-metrics-grid">{metrics.map((metric, index) => (
            <div className={`sw-metric sw-metric--${metricTone(metric.label, metric.value)}`} key={`${metric.label}-${index}`}>
              <small>{displayMetricLabel(metric.label)}</small>
              <strong title={metric.value}>{metric.value}</strong>
            </div>
          ))}</div>
          : <p className="sw-inline-empty">回测完成后将在这里显示指标。</p>}
      </div>

      <div className="sw-result-code">
        <header>
          <h3>回测代码 · 版本 {lastVersion?.local_version_no} · Python</h3>
          <button type="button" className="sw-ghost-button" onClick={() => void copyCode()} disabled={!lastVersion?.code}>
            {copiedCode ? '已复制' : '一键复制'}
          </button>
        </header>
        {lastVersion?.code
          ? <CodeHighlight code={lastVersion.code} />
          : <p className="sw-inline-empty">暂无代码。</p>}
      </div>

      <Fold
        title="完整回测日志"
        meta={<span className="sw-fold-meta-text">
          {lastVersion?.backtest_exit_code !== null && lastVersion?.backtest_exit_code !== undefined && lastVersion?.backtest_exit_code !== ''
            ? `退出码 ${lastVersion.backtest_exit_code}`
            : '无退出码'}
        </span>}
      >
        {backtestLog
          ? <pre className="sw-backtest-log">{backtestLog}</pre>
          : <p className="sw-inline-empty">暂无回测日志。</p>}
      </Fold>
    </section>
  )
}
