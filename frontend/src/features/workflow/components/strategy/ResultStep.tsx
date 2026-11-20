import { useEffect, useMemo, useRef, useState } from 'react'
import { CodeHighlight } from '@/features/workflow/components/CodeHighlight'
import { StrategySummary } from '@/features/workflow/components/StrategySummary'
import { ValidationSummary } from '@/features/workflow/components/ValidationSummary'
import type { StrategyWizardApi } from './useStrategyWizard'
import { Fold } from './Fold'
import {
  type BacktestMetric,
  type MetricGroups,
  anomalousMetrics,
  cleanStrategySummary,
  displayMetricLabel,
  metricTone,
  metricsFromVersion,
} from './resultMetrics'

const CORE_HERO_KEYS = [
  { key: 'total_orders', fallbackLabel: 'Total Orders' },
  { key: 'compounding_annual_return', fallbackLabel: 'Compounding Annual Return' },
  { key: 'drawdown', fallbackLabel: 'Drawdown' },
  { key: 'win_rate', fallbackLabel: 'Win Rate' },
  { key: 'net_profit', fallbackLabel: 'Net Profit' },
]

function heroOneLiner(wizard: StrategyWizardApi): string {
  const { resultValidation, selectedVersion } = wizard
  if (resultValidation) {
    if (resultValidation.verdict === 'passed') return '已通过我方验收门（有成交），以下为回测表现概览。'
    if (resultValidation.verdict === 'no_trade') return '验收未通过：回测 0 成交，本版本不合格。'
    if (resultValidation.verdict === 'backtest_failed') return '验收未通过：平台回测执行失败。'
    return '验收未通过：回测过程异常，详见验收明细。'
  }
  if (selectedVersion?.backtest_passed) return '平台回测通过，但尚未经过我方验收门复核。'
  return '平台回测未通过，详见验收明细。'
}

function MetricCard({ metric }: { metric: BacktestMetric }) {
  const tone = metric.anomaly ? 'anomaly' : metricTone(metric.label, metric.value)
  return (
    <div
      className={`sw-metric sw-metric--${tone}`}
      title={metric.anomaly ? `${metric.label}：${metric.anomaly}` : metric.value}
    >
      <small>{displayMetricLabel(metric.label)}</small>
      <strong>{metric.value || '—'}</strong>
      {metric.anomaly && <em className="sw-metric-anomaly">⚠ 计算异常</em>}
    </div>
  )
}

function MetricTierSection({ title, metrics }: { title: string; metrics: BacktestMetric[] }) {
  if (metrics.length === 0) return null
  return (
    <div className="sw-metric-tier">
      <h4>{title}</h4>
      <div className="sw-metrics-grid">
        {metrics.map((metric, index) => (
          <MetricCard metric={metric} key={`${metric.key ?? metric.label}-${index}`} />
        ))}
      </div>
    </div>
  )
}

/**
 * 步骤⑤：结果报告。S2-4 起为「结论英雄区 + 指标分层」：
 * 核心 5 项大字，质量/风险分层展示，风险调整指标除式爆炸标⚠不洗绿，
 * 其余工程指标默认折叠。权益曲线与逐笔台账在 S2-5 接入（唯一图表
 * 数据源是 160055 独立回测，不从日志造数）。
 */
export function ResultStep({ wizard }: { wizard: StrategyWizardApi }) {
  const {
    detail, lastVersion, selectedVersion, setSelectedVersionId, resultValidation,
    isDone, loading, error: _error, setError: _setError,
  } = wizard
  const [copiedCode, setCopiedCode] = useState(false)
  const copyResetTimer = useRef<number | null>(null)

  useEffect(() => {
    setCopiedCode(false)
    return () => {
      if (copyResetTimer.current !== null) {
        window.clearTimeout(copyResetTimer.current)
        copyResetTimer.current = null
      }
    }
  }, [selectedVersion?.id])

  const groups: MetricGroups = useMemo(() => metricsFromVersion(selectedVersion), [selectedVersion])
  const allMetrics = useMemo(
    () => [...groups.core, ...groups.quality, ...groups.risk, ...groups.other],
    [groups],
  )
  const anomalies = useMemo(() => anomalousMetrics(allMetrics), [allMetrics])
  const coreByKey = useMemo(() => {
    const map = new Map<string, BacktestMetric>()
    for (const metric of groups.core) {
      if (metric.key) map.set(metric.key, metric)
    }
    return map
  }, [groups.core])

  const backtestLog = selectedVersion?.backtest_summary?.trim() || ''
  const strategySummary = selectedVersion?.description ? cleanStrategySummary(selectedVersion.description) : ''
  const hasBacktestResult = selectedVersion?.backtest_passed !== null && selectedVersion?.backtest_passed !== undefined
  const verdictText = !selectedVersion
    ? '待回测'
    : resultValidation
      ? resultValidation.verdict === 'passed'
        ? '验收通过'
        : resultValidation.verdict === 'no_trade'
          ? '无成交（不合格）'
          : resultValidation.verdict === 'backtest_failed'
            ? '回测失败'
            : '回测异常'
      : selectedVersion.backtest_passed
        ? '回测通过（未验收）'
        : '回测未通过'
  const verdictTone = !selectedVersion
    ? 'neutral'
    : resultValidation
      ? resultValidation.verdict === 'passed' ? 'success' : 'warning'
      : selectedVersion.backtest_passed ? 'success' : 'warning'

  async function copyCode() {
    if (!selectedVersion?.code) return
    let copied = false
    try {
      await navigator.clipboard.writeText(selectedVersion.code)
      copied = true
    } catch {
      const helper = document.createElement('textarea')
      helper.value = selectedVersion.code
      helper.style.position = 'fixed'
      helper.style.opacity = '0'
      document.body.appendChild(helper)
      helper.select()
      copied = document.execCommand('copy')
      helper.remove()
    }
    if (!copied) { _setError('复制代码失败，请手动选择代码复制。'); return }
    setCopiedCode(true)
    if (copyResetTimer.current !== null) window.clearTimeout(copyResetTimer.current)
    copyResetTimer.current = window.setTimeout(() => {
      setCopiedCode(false)
      copyResetTimer.current = null
    }, 1800)
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
      <header className="sw-panel-head sw-result-head">
        <div>
          <h2>结果报告</h2>
          <p>验收结论优先于平台回测状态：0 成交一律判为不合格。AI 生成的研究草案，回测结果不代表实盘。</p>
        </div>
        <div className="sw-result-head-actions">
          {detail && detail.versions.length > 1 && (
            <label className="sw-field sw-result-version-field">
              <span>结果版本</span>
              <select
                aria-label="选择结果版本"
                value={selectedVersion?.id ?? ''}
                onChange={(event) => setSelectedVersionId(Number(event.target.value))}
              >
                {detail.versions.map((version) => (
                  <option key={version.id} value={version.id}>
                    版本 {version.local_version_no}{version.id === lastVersion?.id ? '（最新）' : ''}
                  </option>
                ))}
              </select>
            </label>
          )}
          <span className={`sw-badge sw-badge--${verdictTone}`}>{verdictText}</span>
        </div>
      </header>

      <div className={`sw-result-hero${hasBacktestResult ? ` sw-result-hero--${selectedVersion?.backtest_passed ? 'passed' : 'failed'}` : ''}`}>
        <p className="sw-hero-oneliner">{heroOneLiner(wizard)}</p>
        <div className="sw-hero-metrics">
          {CORE_HERO_KEYS.map(({ key, fallbackLabel }) => {
            const metric = coreByKey.get(key)
            return (
              <div
                className={metric?.anomaly ? 'sw-hero-metric is-anomaly' : 'sw-hero-metric'}
                key={key}
                title={metric?.anomaly ? `${metric.label}：${metric.anomaly}` : undefined}
              >
                <small>{metric ? displayMetricLabel(metric.label) : displayMetricLabel(fallbackLabel)}</small>
                <strong>{metric?.value || '—'}</strong>
              </div>
            )
          })}
        </div>
      </div>

      {anomalies.length > 0 && (
        <div className="sw-anomaly-banner" role="alert">
          <h4>⚠ 计算异常（{anomalies.length}）</h4>
          <ul>
            {anomalies.map((metric) => (
              <li key={metric.key ?? metric.label}>
                <strong>{displayMetricLabel(metric.label)}</strong>
                <span>{metric.anomaly}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {strategySummary && (
        <div className="sw-result-summary">
          <h3>策略概要</h3>
          <StrategySummary markdown={strategySummary} />
        </div>
      )}

      <ValidationSummary
        validation={resultValidation}
        backtestPassed={selectedVersion?.backtest_passed}
        backtestSummary={backtestLog}
      />

      <div className={`sw-result-metrics${hasBacktestResult ? ` sw-result-metrics--${selectedVersion?.backtest_passed ? 'passed' : 'failed'}` : ''}`}>
        <header><h3>回测指标</h3><span>{allMetrics.length} 项</span></header>
        {allMetrics.length > 0
          ? <>
            <MetricTierSection title="收益质量" metrics={groups.quality} />
            <MetricTierSection title="风险" metrics={groups.risk} />
            {groups.other.length > 0 && (
              <Fold
                title={`其他指标（${groups.other.length} 项）`}
                meta={<span className="sw-fold-meta-text">工程 / 容量 / 哈希等</span>}
              >
                <MetricTierSection title="其他" metrics={groups.other} />
              </Fold>
            )}
          </>
          : <p className="sw-inline-empty">回测完成后将在这里显示指标。</p>}
      </div>

      <div className="sw-result-code">
        <header>
          <h3>回测代码 · 版本 {selectedVersion?.local_version_no} · Python</h3>
          <button type="button" className="sw-ghost-button" onClick={() => void copyCode()} disabled={!selectedVersion?.code}>
            {copiedCode ? '已复制' : '一键复制'}
          </button>
        </header>
        {selectedVersion?.code
          ? <CodeHighlight code={selectedVersion.code} />
          : <p className="sw-inline-empty">暂无代码。</p>}
      </div>

      <Fold
        title="完整回测日志"
        meta={<span className="sw-fold-meta-text">
          {selectedVersion?.backtest_exit_code !== null && selectedVersion?.backtest_exit_code !== undefined && selectedVersion?.backtest_exit_code !== ''
            ? `退出码 ${selectedVersion.backtest_exit_code}`
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
