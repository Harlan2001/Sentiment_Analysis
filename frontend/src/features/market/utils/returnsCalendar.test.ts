import { describe, expect, it } from 'vitest'
import type { CalendarNewsItem, YieldChangeItem } from '@/types'
import {
  formatBp,
  hasUsableBenchmark,
  isValidDateKey,
  shiftMonth,
  toCalendarNewsRow,
} from './returnsCalendar'

function yieldItem(overrides: Partial<YieldChangeItem>): YieldChangeItem {
  return {
    label: '10年', value: 1.8, previous_date: '2026-11-09', diff_bp: 0, direction: 'flat', ...overrides,
  }
}

describe('returnsCalendar 纯规则', () => {
  it('严格校验真实日期并按月钳日（含闰月）', () => {
    expect(isValidDateKey('2026-02-28')).toBe(true)
    expect(isValidDateKey('2026-02-30')).toBe(false)
    expect(isValidDateKey('2028-02-29')).toBe(true)
    expect(isValidDateKey('11/10/2026')).toBe(false)
    expect(shiftMonth('2026-01-31', 1)).toBe('2026-02-28')
    expect(shiftMonth('2028-01-31', 1)).toBe('2028-02-29')
    expect(shiftMonth('2026-03-31', -1)).toBe('2026-02-28')
  })

  it('区分真实 0 BP、可计算方向与 unavailable/null', () => {
    expect(formatBp(yieldItem({ diff_bp: 0, direction: 'flat' }))).toBe('0 BP')
    expect(formatBp(yieldItem({ diff_bp: null, direction: 'unavailable', previous_date: null }))).toBe('—')
    expect(formatBp(yieldItem({ diff_bp: 2, direction: 'unavailable' }))).toBe('—')
    expect(hasUsableBenchmark(yieldItem({ diff_bp: 2, direction: 'up' }))).toBe(true)
    expect(hasUsableBenchmark(yieldItem({ diff_bp: -2, direction: 'down' }))).toBe(true)
    expect(hasUsableBenchmark(yieldItem({ diff_bp: 0, direction: 'flat' }))).toBe(false)
    expect(hasUsableBenchmark(yieldItem({ diff_bp: null, direction: 'unavailable' }))).toBe(false)
  })

  it('calendar adapter 映射中文方向、来源和最多三个不同因子，不伪造图片或衰减分', () => {
    const item: CalendarNewsItem = {
      id: 1,
      title: '历史新闻',
      pub_time: '2026-01-01 09:05:00',
      source: '来源A',
      direction: '利多',
      reason: '理由',
      horizon: '中期',
      factors: [
        { id: 1, name: '因子一', direction: 'positive' },
        { id: 1, name: '重复因子', direction: 'positive' },
        { id: 2, name: '因子二', direction: 'positive' },
        { id: 3, name: '因子三', direction: 'positive' },
        { id: 4, name: '因子四', direction: 'positive' },
      ],
      importance_score: null,
      score_signals: null,
      top_category: null,
      score_version: null,
      market_alignment: 'unavailable',
    }
    const row = toCalendarNewsRow(item)
    expect(row.direction).toBe('positive')
    expect(row.source_name).toBe('来源A')
    expect(row.factors.map((factor) => factor.id)).toEqual([1, 2, 3])
    expect(row.importance_score).toBeNull()
    expect(row).not.toHaveProperty('thumbnail')
    expect(row).not.toHaveProperty('final_score')
  })
})
