import { useEffect, useState } from 'react'
import type { StrategyWizardApi } from './useStrategyWizard'

function formatElapsed(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m${String(s).padStart(2, '0')}s`
}

/** 进入“生成中”后的本地计时器；远端阶段进度（B1）在 S2-3 接入。 */
function ElapsedTimer({ running }: { running: boolean }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    if (!running) return
    setSeconds(0)
    const timer = window.setInterval(() => setSeconds((v) => v + 1), 1000)
    return () => window.clearInterval(timer)
  }, [running])
  return <span className="sw-gen-elapsed">已用 {formatElapsed(seconds)}</span>
}

const TERMINAL_FAILURE_STATUSES = new Set(['failed', 'timed_out', 'cancelled'])

/**
 * 步骤④：生成与回测。失败不是独立步骤——错误以内嵌面板呈现，可直接重生。
 * 真实阶段进度/日志尾部/放弃等待在 S2-3（后端 B1）接入。
 */
export function GenerationStep({ wizard }: { wizard: StrategyWizardApi }) {
  const {
    isRunning, lastAssistant, hasTextOnlyReply, failureMessage, regenerate, submitting,
  } = wizard
  const failed = Boolean(lastAssistant && TERMINAL_FAILURE_STATUSES.has(lastAssistant.status))
  const showFailure = failed || hasTextOnlyReply

  return (
    <section className="sw-panel" aria-label="生成与回测">
      <header className="sw-panel-head">
        <div>
          <h2>生成与回测</h2>
          <p>Dream 量化宿主装配情报、生成代码并运行回测，通常需要 2–16 分钟；本页每 4 秒自动刷新。</p>
        </div>
        {isRunning && <span className="sw-badge sw-badge--info">生成中</span>}
        {showFailure && <span className="sw-badge sw-badge--danger">本轮失败</span>}
      </header>

      {isRunning && (
        <div className="sw-gen-running">
          <span className="computer-progress" aria-hidden="true"><i /></span>
          <div className="sw-gen-meta">
            <strong>正在生成策略并运行回测…</strong>
            <ElapsedTimer running={isRunning} />
            <small>阶段级进度与日志尾部将在下一版接入；请勿重复确认。</small>
          </div>
        </div>
      )}

      {showFailure && (
        <div className="sw-gen-failure" role="alert">
          <div className="sw-gen-failure-head">
            <strong>{lastAssistant?.status === 'timed_out' ? '等待超时' : '生成失败'}</strong>
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
          {lastAssistant?.status === 'timed_out' && (
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
