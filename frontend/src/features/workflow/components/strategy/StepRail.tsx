import type { StepId, StepInfo } from './stepModel'

type StepRailProps = {
  steps: StepInfo[]
  activeStep: StepId
  onSelect: (step: StepId) => void
}

/**
 * 左侧步骤轨（S2-2）。锁定步骤直接 disabled——旧实现五个模块在空态下
 * 也能随便点，是“空态随便跳”缺陷的入口。
 */
export function StepRail({ steps, activeStep, onSelect }: StepRailProps) {
  return (
    <nav className="sw-rail" aria-label="策略生成步骤">
      {steps.map((step) => {
        const locked = step.state === 'locked'
        return (
          <button
            type="button"
            key={step.id}
            className={[
              'sw-rail-item',
              `sw-rail-item--${step.state}`,
              activeStep === step.id ? 'is-active' : '',
            ].filter(Boolean).join(' ')}
            aria-current={activeStep === step.id ? 'step' : undefined}
            aria-disabled={locked || undefined}
            disabled={locked}
            title={locked ? '完成前序步骤后解锁' : undefined}
            onClick={() => { if (!locked) onSelect(step.id) }}
          >
            <span className="sw-rail-marker" aria-hidden="true">
              {step.state === 'done' ? '✓' : step.index + 1}
            </span>
            <span className="sw-rail-label">{step.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
