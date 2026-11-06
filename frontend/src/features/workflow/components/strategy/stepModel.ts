/**
 * 向导式工作台五步模型（S2-2）。
 * 步骤解锁/完成规则集中在这个纯函数里，页面与 StepRail 都只读它的结果，
 * 避免“空态随便跳”（旧实现五个模块在任何状态下都可点）。
 */

export type StepId = 'requirement' | 'intel' | 'confirm' | 'generation' | 'result'

export type StepState = 'done' | 'active' | 'locked'

export type StepDef = {
  id: StepId
  index: number
  label: string
}

export const STEP_DEFS: StepDef[] = [
  { id: 'requirement', index: 0, label: '需求与参数' },
  { id: 'intel', index: 1, label: '情报与因子' },
  { id: 'confirm', index: 2, label: '确认发送' },
  { id: 'generation', index: 3, label: '生成与回测' },
  { id: 'result', index: 4, label: '结果报告' },
]

export type StepSnapshot = {
  /** 是否存在草稿（assistant 消息带提示词或情报快照） */
  hasDraft: boolean
  /** 草稿正等待用户确认 */
  pendingConfirmation: boolean
  /** 远端生成进行中 */
  running: boolean
  /** 本轮已确认发送（成功/失败/超时都算进过第④步） */
  confirmed: boolean
  /** 已有落库版本（无论验收是否通过） */
  hasVersion: boolean
}

export type StepInfo = StepDef & { state: StepState }

export function deriveSteps(snapshot: StepSnapshot): StepInfo[] {
  const unlocked: Record<StepId, boolean> = {
    requirement: true,
    intel: snapshot.hasDraft,
    confirm: snapshot.pendingConfirmation || snapshot.confirmed || snapshot.hasVersion,
    generation: snapshot.confirmed || snapshot.running,
    result: snapshot.hasVersion,
  }
  const done: Record<StepId, boolean> = {
    requirement: snapshot.hasDraft,
    intel: snapshot.confirmed || snapshot.hasVersion,
    confirm: snapshot.confirmed || snapshot.hasVersion,
    generation: snapshot.hasVersion,
    result: false,
  }
  return STEP_DEFS.map((step) => ({
    ...step,
    state: !unlocked[step.id] ? 'locked' : done[step.id] ? 'done' : 'active',
  }))
}

/** 当前数据状态下应该落在的步骤（首次加载/状态推进时用）。 */
export function defaultStep(snapshot: StepSnapshot): StepId {
  if (snapshot.running) return 'generation'
  if (snapshot.hasVersion) return 'result'
  if (snapshot.pendingConfirmation) return 'confirm'
  if (snapshot.hasDraft) return 'intel'
  return 'requirement'
}

/** 旧版 ?view= 模块名到新步骤的映射，兼容历史链接。 */
const LEGACY_VIEW_MAP: Record<string, StepId> = {
  prompt: 'confirm',
  factors: 'intel',
  'strategy-news': 'intel',
  code: 'result',
  'metrics-logs': 'result',
}

export function resolveStepParam(value: string | null): StepId | null {
  if (!value) return null
  if ((STEP_DEFS.map((s) => s.id) as string[]).includes(value)) return value as StepId
  return LEGACY_VIEW_MAP[value] ?? null
}
