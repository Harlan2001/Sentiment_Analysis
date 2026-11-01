/**
 * ④ 生成与回测步骤的阶段口径（B1 / S2-3）。
 * 纯函数，便于单测；阶段取值与 sql/026_ai_strategy_progress.sql 注释对齐。
 */

export const RUNNING_STAGE_LABELS: Record<string, string> = {
  preparing: '提交中',
  generating: '生成中',
  backtest_checking: '检查回测中',
  regenerating: '对端重生中',
  revising: '验收修正中',
  validating: '验收中',
}

/**
 * 轮询上限与后端 sweep_stale_running 的 16 分钟口径对齐。
 * 对端自身超时是 900s，正常任务在此之前必然终态；停轮询只是兜底，
 * 后端把行置成终态后用户手动刷新仍能取回结果。
 */
export const POLL_CAP_SECONDS = 16 * 60

export function stageLabel(stage?: string | null, revisionRound = 0): string {
  if (stage === 'revising' && revisionRound > 0) {
    return `验收修正 · 第 ${revisionRound} 轮`
  }
  if (stage && RUNNING_STAGE_LABELS[stage]) return RUNNING_STAGE_LABELS[stage]
  // 旧消息/未回写阶段时的兜底，不臆造更细的阶段。
  return '生成中'
}

export function formatElapsed(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  const pad = (value: number) => String(value).padStart(2, '0')
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(rest)}` : `${minutes}:${pad(rest)}`
}

function parseTime(value?: string | null): number | null {
  if (!value) return null
  const time = Date.parse(value)
  return Number.isNaN(time) ? null : time
}

/** 自确认开跑以来的秒数；锚点缺失时返回 null（调用方退化为本地计时）。 */
export function elapsedSeconds(
  runStartedAt?: string | null,
  nowMs: number = Date.now(),
): number | null {
  const startedAt = parseTime(runStartedAt)
  if (startedAt === null) return null
  return Math.max(0, (nowMs - startedAt) / 1000)
}

/** 阶段最后更新距今秒数；无法解析时返回 null。 */
export function stageAgeSeconds(
  stageUpdatedAt?: string | null,
  nowMs: number = Date.now(),
): number | null {
  const updatedAt = parseTime(stageUpdatedAt)
  if (updatedAt === null) return null
  return Math.max(0, Math.round((nowMs - updatedAt) / 1000))
}

export function isPollCapReached(
  runStartedAt?: string | null,
  nowMs: number = Date.now(),
): boolean {
  const elapsed = elapsedSeconds(runStartedAt, nowMs)
  return elapsed !== null && elapsed >= POLL_CAP_SECONDS
}
