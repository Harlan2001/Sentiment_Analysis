import type { StrategyVersion } from '@/api/strategy'

export type MetricTier = 'core' | 'quality' | 'risk' | 'other'

export type BacktestMetric = {
  key?: string
  label: string
  value: string
  /** 新数据由后端 backtest_log_parser 标注；历史版本无此字段，走本地兜底分组。 */
  tier?: string
  numeric?: number | null
  /** 计算异常原因（如除式爆炸）；有值时前端必须显⚠，不得洗绿 */
  anomaly?: string
}

const TIER_BY_LABEL: Record<string, MetricTier> = {
  'Total Orders': 'core',
  'Compounding Annual Return': 'core',
  Drawdown: 'core',
  'Win Rate': 'core',
  'Net Profit': 'core',
  'Profit-Loss Ratio': 'quality',
  Expectancy: 'quality',
  'Average Win': 'quality',
  'Average Loss': 'quality',
  'Total Fees': 'quality',
  'Loss Rate': 'quality',
  'Sharpe Ratio': 'risk',
  'Sortino Ratio': 'risk',
  'Probabilistic Sharpe Ratio': 'risk',
  'Annual Standard Deviation': 'risk',
  'Annual Variance': 'risk',
  'Tracking Error': 'risk',
}

export type MetricGroups = Record<MetricTier, BacktestMetric[]>

function asTier(value: string | undefined): MetricTier {
  return value === 'core' || value === 'quality' || value === 'risk' ? value : 'other'
}

/** 把版本指标分四层；核心/质量/风险之外的全部进「其他」折叠。 */
export function groupMetrics(raw: unknown): MetricGroups {
  const groups: MetricGroups = { core: [], quality: [], risk: [], other: [] }
  if (!Array.isArray(raw)) return groups
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const m = item as Record<string, unknown>
    const label = String(m.label || m.name || m.key || '')
    if (!label) continue
    const metric: BacktestMetric = {
      key: m.key ? String(m.key) : undefined,
      label,
      value: String(m.value ?? ''),
      tier: typeof m.tier === 'string' ? m.tier : undefined,
      numeric: typeof m.numeric === 'number' ? m.numeric : null,
      anomaly: m.anomaly ? String(m.anomaly) : undefined,
    }
    const tier = metric.tier ? asTier(metric.tier) : (TIER_BY_LABEL[label] ?? 'other')
    groups[tier].push(metric)
  }
  return groups
}

export function metricsFromVersion(version: StrategyVersion | null): MetricGroups {
  return groupMetrics(version?.backtest_metrics_json)
}

export function anomalousMetrics(metrics: BacktestMetric[]): BacktestMetric[] {
  return metrics.filter((metric) => Boolean(metric.anomaly))
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
