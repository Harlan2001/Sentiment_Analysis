import { describe, expect, it } from 'vitest'
import { STEP_DEFS, StepSnapshot, defaultStep, deriveSteps, resolveStepParam } from './stepModel'

function statesOf(snapshot: StepSnapshot) {
  return Object.fromEntries(deriveSteps(snapshot).map((step) => [step.id, step.state]))
}

describe('stepModel 步骤解锁（S2-2）', () => {
  it('空会话：只有①需求与参数可进，其余锁定', () => {
    const states = statesOf({
      hasDraft: false,
      pendingConfirmation: false,
      running: false,
      confirmed: false,
      hasVersion: false,
    })
    expect(states.requirement).toBe('active')
    expect(states.intel).toBe('locked')
    expect(states.confirm).toBe('locked')
    expect(states.generation).toBe('locked')
    expect(states.result).toBe('locked')
    expect(defaultStep({
      hasDraft: false, pendingConfirmation: false, running: false, confirmed: false, hasVersion: false,
    })).toBe('requirement')
  })

  it('草稿待确认：①②已完成可回看，③激活，④⑤锁定', () => {
    const snapshot: StepSnapshot = {
      hasDraft: true, pendingConfirmation: true, running: false, confirmed: false, hasVersion: false,
    }
    const states = statesOf(snapshot)
    expect(states.requirement).toBe('done')
    expect(states.intel).toBe('active')
    expect(states.confirm).toBe('active')
    expect(states.generation).toBe('locked')
    expect(states.result).toBe('locked')
    expect(defaultStep(snapshot)).toBe('confirm')
  })

  it('生成中：①②③完成回看，④激活，⑤锁定', () => {
    const snapshot: StepSnapshot = {
      hasDraft: true, pendingConfirmation: false, running: true, confirmed: true, hasVersion: false,
    }
    const states = statesOf(snapshot)
    expect(states.requirement).toBe('done')
    expect(states.intel).toBe('done')
    expect(states.confirm).toBe('done')
    expect(states.generation).toBe('active')
    expect(states.result).toBe('locked')
    expect(defaultStep(snapshot)).toBe('generation')
  })

  it('有版本：①–④完成可回看，⑤激活', () => {
    const snapshot: StepSnapshot = {
      hasDraft: true, pendingConfirmation: false, running: false, confirmed: true, hasVersion: true,
    }
    const states = statesOf(snapshot)
    expect(states.requirement).toBe('done')
    expect(states.intel).toBe('done')
    expect(states.confirm).toBe('done')
    expect(states.generation).toBe('done')
    expect(states.result).toBe('active')
    expect(defaultStep(snapshot)).toBe('result')
  })

  it('失败但无版本：④保持激活（内嵌错误面板重试），不跳到⑤', () => {
    const snapshot: StepSnapshot = {
      hasDraft: true, pendingConfirmation: false, running: false, confirmed: true, hasVersion: false,
    }
    const states = statesOf(snapshot)
    expect(states.generation).toBe('active')
    expect(states.result).toBe('locked')
  })

  it('旧 ?view= 链接映射到新步骤', () => {
    expect(resolveStepParam('prompt')).toBe('confirm')
    expect(resolveStepParam('factors')).toBe('intel')
    expect(resolveStepParam('strategy-news')).toBe('intel')
    expect(resolveStepParam('code')).toBe('result')
    expect(resolveStepParam('metrics-logs')).toBe('result')
    expect(resolveStepParam('generation')).toBe('generation')
    expect(resolveStepParam('nonsense')).toBeNull()
  })

  it('步骤定义固定为五步且顺序不变', () => {
    expect(STEP_DEFS.map((step) => step.id)).toEqual([
      'requirement', 'intel', 'confirm', 'generation', 'result',
    ])
  })
})
