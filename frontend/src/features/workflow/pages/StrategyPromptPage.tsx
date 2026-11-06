import { FormEvent, useCallback, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ConfirmStep } from '../components/strategy/ConfirmStep'
import { GenerationStep } from '../components/strategy/GenerationStep'
import { IntelStep } from '../components/strategy/IntelStep'
import { RequirementStep } from '../components/strategy/RequirementStep'
import { ResultStep } from '../components/strategy/ResultStep'
import { StepRail } from '../components/strategy/StepRail'
import {
  defaultStep,
  deriveSteps,
  resolveStepParam,
  type StepId,
  type StepSnapshot,
} from '../components/strategy/stepModel'
import { useStrategyWizard } from '../components/strategy/useStrategyWizard'
import './strategy-wizard.css'

/**
 * 策略详情页：五步向导式工作台（S2-2 改版）。
 * 本组件只做 URL 步骤态、锁定与布局；数据在 useStrategyWizard，
 * 各步骤内容在 components/strategy/ 下。
 */
export function StrategyPromptPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const conversationId = Number(searchParams.get('id'))
  const formRef = useRef<HTMLFormElement>(null)

  const go = useCallback((step: StepId) => {
    const next = new URLSearchParams(searchParams)
    next.delete('view')
    next.set('step', step)
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const wizard = useStrategyWizard(conversationId, go)
  const {
    detail, loading, error, isDraftReady, isRunning, isDone,
    hasDraft, isPromptConfirmed, chatInput, setChatInput, sendChat,
  } = wizard

  const snapshot: StepSnapshot = {
    hasDraft,
    pendingConfirmation: isDraftReady,
    running: isRunning,
    confirmed: isPromptConfirmed,
    hasVersion: isDone,
  }
  const steps = deriveSteps(snapshot)
  const stateById = Object.fromEntries(steps.map((step) => [step.id, step.state]))

  // 兼容旧 ?view= 深链；锁定步骤不渲染（回退到当前应处步骤），杜绝空态前跳。
  const requested = resolveStepParam(searchParams.get('step'))
    ?? resolveStepParam(searchParams.get('view'))
  const fallbackStep = defaultStep(snapshot)
  const activeStep: StepId = requested && stateById[requested] !== 'locked'
    ? requested
    : fallbackStep

  // 状态推进时的自动跳转：只在用户还停留在“即将完成”的步骤时接管。
  useEffect(() => {
    if (isRunning && (activeStep === 'confirm' || activeStep === 'intel')) go('generation')
  }, [isRunning, activeStep, go])
  useEffect(() => {
    if (isDone && activeStep === 'generation') go('result')
  }, [isDone, activeStep, go])

  function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void sendChat(chatInput)
  }

  function openStrategyNews(newsId: number) {
    navigate(`/news/${newsId}?strategyId=${conversationId}`)
  }

  const statusBadge = isDone
    ? <span className="sw-badge sw-badge--success">已完成</span>
    : isRunning
      ? <span className="sw-badge sw-badge--info">生成中…</span>
      : isDraftReady
        ? <span className="sw-badge sw-badge--warning">待确认</span>
        : <span className="sw-badge sw-badge--neutral">{loading && !detail ? '正在读取…' : '生成提示词中…'}</span>

  return (
    <section className="sw-wizard">
      <div className="sw-wizard-scroll">
        <header className="sw-wizard-head">
          <button type="button" className="sw-ghost-button" onClick={() => navigate('/strategy')}>← 返回策略生成</button>
          <div className="sw-wizard-title">
            <h1>{detail?.conversation?.title || '新策略对话'}</h1>
            <p>策略会话 #{conversationId} · AI 生成的研究草案，回测结果不代表实盘</p>
          </div>
          <span className="sw-wizard-head-spacer" />
          {statusBadge}
        </header>

        <div className="sw-wizard-body">
          <StepRail steps={steps} activeStep={activeStep} onSelect={go} />
          <div className="sw-wizard-main">
            {activeStep === 'requirement' && <RequirementStep wizard={wizard} />}
            {activeStep === 'intel' && <IntelStep wizard={wizard} onOpenNews={openStrategyNews} />}
            {activeStep === 'confirm' && <ConfirmStep wizard={wizard} />}
            {activeStep === 'generation' && <GenerationStep wizard={wizard} />}
            {activeStep === 'result' && <ResultStep wizard={wizard} />}
            {error && <p className="sw-wizard-error" role="alert">{error}</p>}
          </div>
        </div>
      </div>

      <form className="sw-composer sw-wizard-composer" ref={formRef} onSubmit={submitChat}>
        <textarea
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              formRef.current?.requestSubmit()
            }
          }}
          placeholder={isDone ? '输入新的需求以开启新一轮…' : '修改或补充策略需求（发送后重新生成提示词草稿）…'}
          rows={2}
        />
        <div className="sw-composer-foot">
          <span className="sw-composer-hint">Enter 发送 · Shift+Enter 换行 · 发送新需求将开启新一轮，步骤轨回到①</span>
          <button type="submit" className="sw-primary-button" disabled={!chatInput.trim() || wizard.submitting}>
            发送 ↑
          </button>
        </div>
      </form>
    </section>
  )
}
