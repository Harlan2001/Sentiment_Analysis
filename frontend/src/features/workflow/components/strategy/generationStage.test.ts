import { describe, expect, it } from 'vitest'
import {
  elapsedSeconds,
  formatElapsed,
  isPollCapReached,
  POLL_CAP_SECONDS,
  stageAgeSeconds,
  stageLabel,
} from './generationStage'

describe('generationStage', () => {
  it('maps stage codes to Chinese labels and falls back safely', () => {
    expect(stageLabel('preparing')).toBe('提交中')
    expect(stageLabel('generating')).toBe('生成中')
    expect(stageLabel('backtest_checking')).toBe('检查回测中')
    expect(stageLabel('regenerating').includes('重生')).toBe(true)
    expect(stageLabel('revising', 2)).toBe('验收修正 · 第 2 轮')
    expect(stageLabel('revising')).toBe('验收修正中')
    expect(stageLabel(undefined)).toBe('生成中')
    // 未知阶段码不臆造更细的进度，退回兜底文案。
    expect(stageLabel('unknown')).toBe('生成中')
  })

  it('formats elapsed as mm:ss and hh:mm:ss', () => {
    expect(formatElapsed(0)).toBe('0:00')
    expect(formatElapsed(5)).toBe('0:05')
    expect(formatElapsed(65)).toBe('1:05')
    expect(formatElapsed(3723)).toBe('1:02:03')
    expect(formatElapsed(-9)).toBe('0:00')
  })

  it('computes elapsed from ISO anchor; missing/invalid anchor => null', () => {
    const now = Date.parse('2026-11-01T12:16:40+08:00')
    expect(elapsedSeconds('2026-11-01T12:16:40+08:00', now)).toBe(0)
    expect(elapsedSeconds('2026-11-01T12:15:40+08:00', now)).toBe(60)
    expect(elapsedSeconds(undefined, now)).toBeNull()
    expect(elapsedSeconds('not-a-date', now)).toBeNull()
    // 未来时间被钳到 0，不出现负数计时。
    expect(elapsedSeconds('2026-11-01T12:17:40+08:00', now)).toBe(0)
  })

  it('flags the 16-minute poll cap', () => {
    const start = '2026-11-01T12:00:00+08:00'
    expect(isPollCapReached(start, Date.parse('2026-11-01T12:15:59+08:00'))).toBe(false)
    expect(isPollCapReached(start, Date.parse('2026-11-01T12:16:00+08:00'))).toBe(true)
    expect(POLL_CAP_SECONDS).toBe(960)
    expect(isPollCapReached(undefined, Date.now())).toBe(false)
  })

  it('computes stage freshness age', () => {
    const now = Date.parse('2026-11-01T12:16:40+08:00')
    expect(stageAgeSeconds('2026-11-01T12:16:10+08:00', now)).toBe(30)
    expect(stageAgeSeconds(null, now)).toBeNull()
  })
})
