import { useEffect, useMemo, useRef, useState } from 'react'
import type { StrategyWizardApi } from './useStrategyWizard'
import { Fold } from './Fold'
import {
  elapsedSeconds,
  formatElapsed,
  stageAgeSeconds,
  stageLabel,
} from './generationStage'

const TERMINAL_FAILURE_STATUSES = new Set(['failed', 'timed_out', 'cancelled'])

/** 运行中 1s 心跳：驱动已用时长与阶段新鲜度，不触发请求。 */
function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    setNow(Date.now())
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [active])
  return now
}

const STAGE_CHAIN = [
  { label: '提交' },
  { label: '生成' },
  { label: '回测检查' },
  { label: '验收' },
] as const

const STAGE_CHAIN_INDEX: Record<string, number> = {
  preparing: 0,
  generating: 1,
  regenerating: 1,
  backtest_checking: 2,
  revising: 3,
  validating: 3,
}

const STAGE_TAG: Record<string, string> = {
  regenerating: '对端自动重生中',
  revising: '验收未过 · 带原因修正',
}

function StageChain({ stage }: { stage?: string | null }) {
  const current = stage ? STAGE_CHAIN_INDEX[stage] : undefined
  const activeIndex = current ?? 1
  return (
    <ol className="sw-gen-stages" aria-label="生成阶段">
      {STAGE_CHAIN.map((item, index) => (
        <li
          key={item.label}
          className={
            index === activeIndex
              ? 'is-active'
              : index < activeIndex
                ? 'is-done'
                : 'is-todo'
          }
        >
          <span className="sw-gen-stage-dot" aria-hidden="true" />
          {item.label}
        </li>
      ))}
    </ol>
  )
}

/**
 * 步骤④：生成与回测。失败不是独立步骤——错误以内嵌面板呈现，可直接重生。
 */
export function GenerationStep({ wizard }: { wizard: StrategyWizardApi }) {
  const {
    isRunning,
    lastAssistant,
    hasTextOnlyReply,
    failureMessage,
    regenerate,
    submitting,
    revisionRound,
    pollCapReached,
    cancelWait,
    cancellingWait,
    refreshNow,
  } = wizard
  const now = useNow(isRunning)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const mountedAt = useRef(Date.now())

  // 新一轮运行开始时收起放弃确认。
  useEffect(() => {
    if (!isRunning) setConfirmCancel(false)
  }, [isRunning])

  const failed = Boolean(lastAssistant && TERMINAL_FAILURE_STATUSES.has(lastAssistant.status))
  const showFailure = failed || hasTextOnlyReply
  const cancelled = lastAssistant?.status === 'cancelled'

  const elapsed = useMemo(() => {
    if (!isRunning) return 0
    return (
      elapsedSeconds(lastAssistant?.run_started_at, now)
      ?? Math.max(0, Math.floor((now - mountedAt.current) / 1000))
    )
  }, [isRunning, lastAssistant?.run_started_at, now])

  const stageAge = isRunning ? stageAgeSeconds(lastAssistant?.stage_updated_at, now) : null
  const stageTag = lastAssistant?.stage ? STAGE_TAG[lastAssistant.stage] : null
  const logTail = lastAssistant?.log_tail?.trim() || ''

  return (
    <section className="sw-panel" aria-label="生成与回测">
      <header className="sw-panel-head">
        <div>
          <h2>生成与回测</h2>
          <p>Dream 量化宿主装配情报、生成代码并运行回测，通常需要 2–16 分钟；本页每 4 秒自动刷新。</p>
        </div>
        {isRunning && (
          <span className="sw-badge sw-badge--info">
            {stageLabel(lastAssistant?.stage, revisionRound)}
          </span>
        )}
        {showFailure && (
          <span className="sw-badge sw-badge--danger">
            {cancelled ? '已放弃等待' : '本轮失败'}
          </span>
        )}
      </header>

      {isRunning && (
        <div className="sw-gen-running">
          <span className="computer-progress" aria-hidden="true"><i /></span>
          <div className="sw-gen-meta">
            <div className="sw-gen-meta-line">
              <strong>正在生成策略并运行回测…</strong>
              <span className="sw-gen-elapsed">已用 {formatElapsed(elapsed)}</span>
              <span className="sw-gen-elapsed-cap">/ 上限 16:00</span>
            </div>
            <StageChain stage={lastAssistant?.stage} />
            <div className="sw-gen-stage-line">
              <span>当前阶段：{stageLabel(lastAssistant?.stage, revisionRound)}</span>
              {stageTag && <span className="sw-gen-stage-tag">{stageTag}</span>}
              {stageAge !== null && stageAge >= 10 && (
                <small className="sw-gen-stage-age">阶段 {stageAge} 秒未更新（仍在等待对端推送）</small>
              )}
            </div>
            {logTail && (
              <Fold title="回测日志尾部（最近约 28 行，随轮询刷新）" defaultOpen>
                <pre className="sw-gen-log">{logTail}</pre>
              </Fold>
            )}

            {pollCapReached ? (
              <div className="sw-gen-timeout" role="alert">
                <strong>已等待超过 16 分钟，已停止自动刷新。</strong>
                <p>
                  对端任务可能仍在运行；你可以手动刷新一次状态，或放弃本轮重新生成。
                  请勿重复确认同一份提示词。
                </p>
                <div className="sw-gen-actions">
                  <button
                    type="button"
                    className="sw-ghost-button"
                    onClick={() => void refreshNow()}
                    disabled={submitting}
                  >
                    刷新状态
                  </button>
                  <button
                    type="button"
                    className="sw-primary-button"
                    onClick={() => void regenerate()}
                    disabled={submitting}
                  >
                    重新生成
                  </button>
                </div>
              </div>
            ) : (
              <div className="sw-gen-cancel">
                {confirmCancel ? (
                  <div className="sw-gen-cancel-confirm" role="alert">
                    <p>
                      确认放弃等待？协议没有取消命令，<strong>对端仍会跑完本轮生成，但结果不再回收</strong>；
                      本轮提示词也不会自动重发。
                    </p>
                    <div className="sw-gen-actions">
                      <button
                        type="button"
                        className="sw-danger-button"
                        onClick={() => {
                          setConfirmCancel(false)
                          void cancelWait()
                        }}
                        disabled={cancellingWait}
                      >
                        {cancellingWait ? '放弃中…' : '确认放弃'}
                      </button>
                      <button
                        type="button"
                        className="sw-ghost-button"
                        onClick={() => setConfirmCancel(false)}
                        disabled={cancellingWait}
                      >
                        继续等待
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="sw-gen-cancel-trigger"
                    onClick={() => setConfirmCancel(true)}
                  >
                    放弃等待
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {showFailure && (
        <div className="sw-gen-failure" role="alert">
          <div className="sw-gen-failure-head">
            <strong>
              {cancelled ? '已放弃等待' : lastAssistant?.status === 'timed_out' ? '等待超时' : '生成失败'}
            </strong>
            <button
              type="button"
              className="sw-primary-button"
              onClick={() => void regenerate()}
              disabled={submitting}
            >
              重新生成
            </button>
          </div>
          <pre className="sw-gen-error-text">{failureMessage}</pre>
          {(lastAssistant?.status === 'timed_out' || cancelled) && (
            <small>对端可能仍会跑完但结果不再回收；重新生成会开启新一轮。</small>
          )}
        </div>
      )}

      {!isRunning && !showFailure && (
        <div className="sw-empty-hint">在「确认发送」步骤确认后，于此查看生成与回测进度。</div>
      )}
    </section>
  )
}
