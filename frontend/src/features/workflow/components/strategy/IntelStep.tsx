import { useMemo } from 'react'
import { FactorSignalTable } from '@/features/workflow/components/FactorSignalTable'
import { LogicChain } from '@/features/workflow/components/LogicChain'
import type { StrategyWizardApi } from './useStrategyWizard'
import { StrategyNewsCard } from './StrategyNewsCard'
import { Fold } from './Fold'
import { parsePromptSections } from './promptSections'
import { cleanStrategySummary } from './resultMetrics'

const FALLBACK_TOKEN_BUDGET = 6000
const TOKEN_WARN_RATIO = 0.8

function TokenBar({ used, budget }: { used: number; budget: number }) {
  const ratio = Math.max(0, Math.min(1, used / budget))
  const warn = ratio >= TOKEN_WARN_RATIO
  return (
    <div className={`sw-token${warn ? ' is-warn' : ''}`}>
      <div className="sw-token-head">
        <span>情报包 token 用量</span>
        <strong>{used} / {budget}</strong>
      </div>
      <div className="sw-token-track">
        <i style={{ width: `${Math.round(ratio * 100)}%` }} />
      </div>
      {warn && <small>用量已达 {Math.round(ratio * 100)}%，情报包可能被压缩，优先核对关键因子行。</small>}
    </div>
  )
}

/**
 * 步骤②：情报与因子。因子面板/逻辑链来自草稿快照（防前视锚点在后端装配时
 * 已固定）；任务卡、市场块、纪律等受保护段只读折叠。
 */
export function IntelStep({ wizard, onOpenNews }: {
  wizard: StrategyWizardApi
  onOpenNews: (newsId: number) => void
}) {
  const {
    systemDraft, draft, draftContext, factorPanel, validation, lastVersion,
    isDone, isRunning, newsReferences, hasDraft,
  } = wizard

  const parsed = useMemo(() => parsePromptSections(systemDraft || draft), [systemDraft, draft])
  const strategySummary = lastVersion?.description ? cleanStrategySummary(lastVersion.description) : ''
  const tokenUsed = draftContext?.token_used ?? null
  const tokenBudget = draftContext?.token_budget ?? FALLBACK_TOKEN_BUDGET

  if (!hasDraft) {
    return (
      <section className="sw-panel" aria-label="情报与因子">
        <header className="sw-panel-head">
          <div><h2>情报与因子</h2><p>草稿生成后展示因子信号面板、逻辑链条与引用新闻。</p></div>
        </header>
        <div className="sw-empty-hint">在底部输入一句话策略需求并生成草稿后，本步骤自动解锁。</div>
      </section>
    )
  }

  return (
    <section className="sw-panel" aria-label="情报与因子">
      <header className="sw-panel-head">
        <div>
          <h2>情报与因子</h2>
          <p>按「情报 → 因子 → 门控 → 策略 → 验收」逐环核对本策略的依据；新闻与因子只做门控/过滤，不单独触发交易。</p>
        </div>
        <span className="sw-badge sw-badge--neutral">{factorPanel?.count ? `${factorPanel.count} 个因子` : '因子面板待生成'}</span>
      </header>

      {tokenUsed !== null && <TokenBar used={tokenUsed} budget={tokenBudget || FALLBACK_TOKEN_BUDGET} />}

      <LogicChain
        context={draftContext}
        validation={validation}
        strategySummary={strategySummary}
        backtestPassed={lastVersion?.backtest_passed}
        isDone={isDone}
        isRunning={isRunning}
      />
      <FactorSignalTable panel={factorPanel} />

      <div className="sw-intel-folds">
        {parsed.protectedPrefix && (
          <Fold title="情报包 / 任务卡 / 纪律条款（受保护，只读）" readOnly meta={<span className="sw-fold-meta-text">标记外文本不可修改</span>}>
            <pre className="sw-protected-text">{parsed.protectedPrefix}</pre>
          </Fold>
        )}
        {parsed.protectedSuffix && (
          <Fold title="输出与审计契约（受保护，只读）" readOnly>
            <pre className="sw-protected-text">{parsed.protectedSuffix}</pre>
          </Fold>
        )}
        <Fold
          title="相关新闻"
          defaultOpen
          meta={<span className="sw-fold-meta-text">{newsReferences.length} 条</span>}
        >
          {newsReferences.length > 0
            ? <div className="sw-news-list">{newsReferences.map((news, index) => (
              <StrategyNewsCard key={String(news.news_id || news.id || index)} news={news} onOpen={onOpenNews} />
            ))}</div>
            : <p className="sw-inline-empty">本轮情报包未引用新闻。</p>}
        </Fold>
      </div>
    </section>
  )
}
