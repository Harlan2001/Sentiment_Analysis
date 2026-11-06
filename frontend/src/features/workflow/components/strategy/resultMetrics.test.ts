import { describe, expect, it } from 'vitest'
import {
  anomalousMetrics,
  displayMetricLabel,
  groupMetrics,
  metricTone,
} from './resultMetrics'

describe('groupMetrics', () => {
  it('按后端 tier 字段分层并保留 anomaly/numeric', () => {
    const groups = groupMetrics([
      { key: 'total_orders', label: 'Total Orders', value: '29', tier: 'core', numeric: 29 },
      { key: 'expectancy', label: 'Expectancy', value: '0', tier: 'quality', numeric: 0 },
      { key: 'sharpe_ratio', label: 'Sharpe Ratio', value: '-42182.563', tier: 'risk', numeric: -42182.563, anomaly: '除式爆炸' },
    ])

    expect(groups.core.map((m) => m.label)).toEqual(['Total Orders'])
    expect(groups.quality.map((m) => m.label)).toEqual(['Expectancy'])
    expect(groups.risk[0].anomaly).toBe('除式爆炸')
    expect(groups.other).toEqual([])
  })

  it('历史版本无 tier：按英文标签兜底分组，未知指标进其他', () => {
    const groups = groupMetrics([
      { label: 'Total Orders', value: '29' },
      { label: 'Sharpe Ratio', value: '1.3' },
      { label: 'OrderListHash', value: 'abc' },
      { label: 'Some Future Metric', value: '1' },
    ])

    expect(groups.core.map((m) => m.label)).toEqual(['Total Orders'])
    expect(groups.risk.map((m) => m.label)).toEqual(['Sharpe Ratio'])
    expect(groups.other.map((m) => m.label)).toEqual(['OrderListHash', 'Some Future Metric'])
  })

  it('非法/空输入安全降级', () => {
    expect(groupMetrics(null)).toEqual({ core: [], quality: [], risk: [], other: [] })
    expect(groupMetrics('nope').core).toEqual([])
    const groups = groupMetrics([null, {}, { label: '', value: '1' }, { label: 'Win Rate', value: '64%' }])
    expect(groups.core).toHaveLength(1)
    expect(groups.core[0].numeric).toBeNull()
  })

  it('非法 tier 值归入其他', () => {
    const groups = groupMetrics([{ label: 'X', value: '1', tier: 'bogus' }])
    expect(groups.other).toHaveLength(1)
  })
})

describe('anomalousMetrics', () => {
  it('只返回带 anomaly 原因的指标', () => {
    const groups = groupMetrics([
      { label: 'Sharpe Ratio', value: '-42182.563', tier: 'risk', anomaly: '除式爆炸' },
      { label: 'Sortino Ratio', value: '1.8', tier: 'risk' },
    ])
    const flagged = anomalousMetrics([...groups.risk, ...groups.other])
    expect(flagged).toHaveLength(1)
    expect(flagged[0].label).toBe('Sharpe Ratio')
  })
})

describe('metricTone', () => {
  it('收益为正标绿、回撤为正标红', () => {
    expect(metricTone('Compounding Annual Return', '2.1%')).toBe('positive')
    expect(metricTone('Drawdown', '1.8%')).toBe('negative')
    expect(metricTone('Sharpe Ratio', '0')).toBe('neutral')
  })
})

describe('displayMetricLabel', () => {
  it('已知指标给中文，未知原样返回', () => {
    expect(displayMetricLabel('Total Orders')).toBe('总订单数')
    expect(displayMetricLabel('New Metric')).toBe('New Metric')
  })
})
