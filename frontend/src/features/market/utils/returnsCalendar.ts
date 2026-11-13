import type { CalendarNewsItem, YieldChangeItem } from '@/types'

const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/
const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

export function dateKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function parseDateKey(value: string | null | undefined) {
  const match = value?.match(DATE_PATTERN)
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const date = new Date(year, month - 1, day)
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null
  return { year, month, day, date }
}

export function isValidDateKey(value: string | null | undefined): value is string {
  return parseDateKey(value) !== null
}

export function monthRange(value: string): { start: string; end: string } {
  const parsed = parseDateKey(value)!
  return {
    start: dateKey(new Date(parsed.year, parsed.month - 1, 1)),
    end: dateKey(new Date(parsed.year, parsed.month, 0)),
  }
}

/** 保留当前“日”，目标月没有该日时钳到月末。 */
export function shiftMonth(value: string, offset: number): string {
  const parsed = parseDateKey(value)!
  const targetMonth = new Date(parsed.year, parsed.month - 1 + offset, 1)
  const lastDay = new Date(targetMonth.getFullYear(), targetMonth.getMonth() + 1, 0).getDate()
  return dateKey(new Date(targetMonth.getFullYear(), targetMonth.getMonth(), Math.min(parsed.day, lastDay)))
}

/** 周一开头的自然月日期格；空格用于对齐第一周。 */
export function monthCells(value: string): (string | null)[] {
  const parsed = parseDateKey(value)!
  const firstWeekday = (new Date(parsed.year, parsed.month - 1, 1).getDay() + 6) % 7
  const daysInMonth = new Date(parsed.year, parsed.month, 0).getDate()
  return [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => dateKey(new Date(parsed.year, parsed.month - 1, index + 1))),
  ]
}

export function fullDateLabel(value: string): string {
  const parsed = parseDateKey(value)!
  return `${parsed.year}年${parsed.month}月${parsed.day}日 星期${WEEKDAYS[parsed.date.getDay()]}`
}

export function shortDateLabel(value: string): string {
  const parsed = parseDateKey(value)!
  return `${parsed.month}月${parsed.day}日 · 星期${WEEKDAYS[parsed.date.getDay()]}`
}

export function formatYieldValue(item: YieldChangeItem | undefined): string {
  return item && Number.isFinite(item.value) ? `${item.value.toFixed(3)}%` : '—'
}

export function formatBp(item: YieldChangeItem | undefined): string {
  if (!item || item.diff_bp === null || item.direction === 'unavailable' || !Number.isFinite(item.diff_bp)) return '—'
  return `${item.diff_bp > 0 ? '+' : ''}${item.diff_bp} BP`
}

export function bpArrow(item: YieldChangeItem | undefined): string {
  if (!item || item.diff_bp === null || item.direction === 'unavailable') return ''
  return item.direction === 'up' ? '↑' : item.direction === 'down' ? '↓' : '→'
}

export function hasUsableBenchmark(item: YieldChangeItem | undefined): boolean {
  return Boolean(item && item.diff_bp !== null && (item.direction === 'up' || item.direction === 'down'))
}

export function normalizeCalendarDirection(value: string | null | undefined): 'positive' | 'negative' | 'neutral' | null {
  if (value === '利多' || value === 'positive') return 'positive'
  if (value === '利空' || value === 'negative') return 'negative'
  if (value === '中性' || value === 'neutral') return 'neutral'
  return null
}

/** Calendar API → 通用 NewsListRow 最小结构；不伪造缩略图或衰减分。 */
export function toCalendarNewsRow(item: CalendarNewsItem) {
  const seen = new Set<number>()
  const factors = (item.factors ?? []).filter((factor) => {
    if (seen.has(factor.id)) return false
    seen.add(factor.id)
    return true
  }).slice(0, 3).map(({ id, name }) => ({ id, name }))
  return {
    id: item.id,
    title: item.title,
    pub_time: item.pub_time,
    source_name: item.source,
    direction: normalizeCalendarDirection(item.direction),
    reason: item.reason,
    horizon: item.horizon,
    factors,
    importance_score: item.importance_score,
    score_version: item.score_version,
  }
}
