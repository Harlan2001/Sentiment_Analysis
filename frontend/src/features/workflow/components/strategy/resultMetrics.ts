import type { StrategyVersion } from '@/api/strategy'

export type MetricCard = { label: string; value: string }

/** 把 versions.backtest_metrics_json 摊平成指标卡；S2-4 再做分层与异常标记。 */
export function backtestCards(version: StrategyVersion | null): MetricCard[] {
  if (!version) return []
  const cards: MetricCard[] = []
  if (version.backtest_passed !== null && version.backtest_passed !== undefined) {
    cards.push({ label: '回测状态', value: version.backtest_passed ? '✓ 通过' : '✗ 未通过' })
  }
  const list = version.backtest_metrics_json as
    | Array<{ name?: string; label?: string; key?: string; value?: unknown }>
    | null
  if (Array.isArray(list)) {
    for (const m of list) {
      cards.push({ label: String(m.label || m.name || m.key || ''), value: String(m.value ?? '') })
    }
  }
  return cards
}

export type MetricTone = 'positive' | 'negative' | 'neutral'

export function metricTone(label: string, value: string): MetricTone {
  if (/回测状态/.test(label)) return value.startsWith('✓') ? 'positive' : 'negative'
  const numeric = Number(value.replace(/[%,$]/g, '').replace(/,/g, ''))
  if (!Number.isFinite(numeric) || numeric === 0) return 'neutral'
  const isRiskMetric = /drawdown|loss|fee|variance|deviation/i.test(label)
  return (numeric > 0) !== isRiskMetric ? 'positive' : 'negative'
}

const BACKTEST_METRIC_LABELS: Record<string, string> = {
  'Total Orders': '总订单数', 'Average Win': '平均盈利', 'Average Loss': '平均亏损',
  'Compounding Annual Return': '复合年化收益率', 'Drawdown': '最大回撤', 'Expectancy': '期望收益',
  'Start Equity': '初始权益', 'End Equity': '期末权益', 'Net Profit': '净利润',
  'Sharpe Ratio': '夏普比率', 'Sortino Ratio': '索提诺比率', 'Probabilistic Sharpe Ratio': '概率夏普比率',
  'Loss Rate': '亏损率', 'Win Rate': '胜率', 'Profit-Loss Ratio': '盈亏比', 'Alpha': '阿尔法',
  'Beta': '贝塔', 'Annual Standard Deviation': '年化标准差', 'Annual Variance': '年化方差',
  'Information Ratio': '信息比率', 'Tracking Error': '跟踪误差', 'Treynor Ratio': '特雷诺比率',
  'Total Fees': '总手续费', 'Estimated Strategy Capacity': '预计策略容量',
  'Lowest Capacity Asset': '最低容量标的', 'Portfolio Turnover': '组合换手率', 'Drawdown Recovery': '回撤修复期',
  'OrderListHash': '订单列表哈希',
}

export function displayMetricLabel(label: string): string {
  return BACKTEST_METRIC_LABELS[label] || label
}

/** 模型概要里去掉代码块，避免概要区重复展示整段策略代码。 */
export function cleanStrategySummary(description: string): string {
  const withoutCodeBlocks = description.replace(/```[^\n]*\n[\s\S]*?```/g, '').trim()
  const withoutUnclosedCode = withoutCodeBlocks.includes('```')
    ? withoutCodeBlocks.split('```', 1)[0].trim()
    : withoutCodeBlocks
  return withoutUnclosedCode || '策略代码与回测结果已生成，请在下方查看。'
}
