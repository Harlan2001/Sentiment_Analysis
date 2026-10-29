import type { ReactNode } from 'react'
import type { DraftContext, FactorSignal, StrategyValidation } from '@/api/strategy'

type Props = {
  context: DraftContext | null
  validation: StrategyValidation | null
  strategySummary?: string
  backtestPassed?: boolean | null
  isDone: boolean
  isRunning: boolean
}

/** 从策略摘要里粗提模型自述的因子使用方式（门控 / 过滤 / 不使用）。 */
function detectFactorUsage(summary: string): string | null {
  if (!summary) return null
  const rules: Array<[RegExp, string]> = [
    [/门控|过滤条件|开仓许可|同向才|仅当/, '作为开仓门控条件'],
    [/风险过滤|风险降级|提高开仓阈值|降低仓位/, '作为风险过滤/降仓依据'],
    [/不使用|未使用|纯技术|仅技术/, '未使用（纯技术策略）'],
  ]
  for (const [pattern, label] of rules) {
    if (pattern.test(summary)) return label
  }
  return null
}

const STEP_LABELS: Record<string, string> = {
  backtest_finished: '回测正常结束',
  trade_count_parsed: '解析到成交笔数',
  trade_count_positive: '成交笔数 > 0',
  symbol_whitelisted: '标的在白名单内',
  order_type_matched: '下单类型匹配',
}

/** 一个环节卡片：左侧序号，右侧标题 + 关键指标 + 说明。 */
function Step({ index, title, tone, badge, children }: {
  index: number
  title: string
  tone: 'good' | 'warn' | 'bad' | 'muted'
  badge?: ReactNode
  children: ReactNode
}) {
  return (
    <li className={`sf-chain-step sf-chain-step--${tone}`}>
      <span className="sf-chain-index">{index}</span>
      <div className="sf-chain-body">
        <div className="sf-chain-head">
          <strong className="sf-chain-title">{title}</strong>
          {badge}
        </div>
        <div className="sf-chain-content">{children}</div>
      </div>
    </li>
  )
}

/** 一行「标签 — 值」，用于结构化展示关键事实。 */
function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="sf-chain-fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

/**
 * 逻辑链条：把「情报 → 因子 → 门控 → 策略 → 验收」逐环摊开。
 *
 * 用户要相信一条 AI 生成的策略，光看「通过」两个字没有说服力——必须能一路看到
 * 当时的新闻方向、哪些因子过了历史检验、这些因子给了什么方向、最终回测有没有
 * 真的成交。每一环都给出可核对的数字和来源，而不是结论本身。
 */
export function LogicChain({
  context,
  validation,
  strategySummary = '',
  backtestPassed,
  isDone,
  isRunning,
}: Props) {
  const panel = context?.factor_panel
  const factors: FactorSignal[] = panel?.items ?? []
  const longCount = factors.filter((f) => f.direction === 'positive').length
  const shortCount = factors.filter((f) => f.direction === 'negative').length
  const usage = detectFactorUsage(strategySummary)
  const tokenUsed = context?.token_used
  const tokenBudget = context?.token_budget
  const tokenPct = tokenUsed && tokenBudget ? Math.min(100, Math.round((tokenUsed / tokenBudget) * 100)) : 0

  // 因子阵营判断：多空数量相等说明方向冲突，本应空仓。
  const bias: 'none' | 'balanced' | 'long' | 'short' = factors.length === 0
    ? 'none'
    : longCount === shortCount
      ? 'balanced'
      : longCount > shortCount
        ? 'long'
        : 'short'

  const biasText = {
    none: '无可用因子，本轮不含情绪门控',
    balanced: '多空相当，方向冲突，应空仓或仅做纯技术',
    long: '偏多，支持做多方向',
    short: '偏空，支持做空方向',
  }[bias]

  const tradeCount = validation?.trade_count ?? null
  const tradingTone: 'good' | 'warn' | 'bad' | 'muted' =
    !isDone ? 'muted'
      : tradeCount === null ? 'warn'
        : tradeCount > 0 ? 'good' : 'bad'

  const anchor = context?.reference_time
    ? String(context.reference_time).slice(0, 16).replace('T', ' ')
    : '—'

  return (
    <section className="sf-chain">
      <header className="sf-chain-heading">
        <div>
          <h3>本轮策略的逻辑链条</h3>
          <p>逐环可核对：每一步都给出当时的实际数据，而不是结论本身。</p>
        </div>
        {panel && (
          <div className="sf-chain-summary">
            <span className="sf-chain-summary-item sf-chain-summary-item--long">
              <em>{longCount}</em>多
            </span>
            <span className="sf-chain-summary-item sf-chain-summary-item--short">
              <em>{shortCount}</em>空
            </span>
            <span className="sf-chain-summary-item">
              <em>{factors.length}</em>因子
            </span>
          </div>
        )}
      </header>

      <ol className="sf-chain-list">
        <Step
          index={1}
          title="情报装配"
          tone={tokenUsed ? 'good' : 'muted'}
          badge={<span className="sf-chain-badge">{context?.prompt_version || '—'}</span>}
        >
          <div className="sf-chain-facts">
            <Fact label="交易标的" value={<code>{context?.instrument_code || '—'}</code>} />
            <Fact label="回测模式" value={<code>{context?.backtest_mode || '—'}</code>} />
            <Fact label="K线周期" value={<code>{context?.candle_interval || '—'}</code>} />
            <Fact label="情报锚点" value={anchor} />
          </div>
          {tokenUsed ? (
            <div className="sf-chain-budget">
              <div className="sf-chain-budget-head">
                <span>提示词预算</span>
                <strong>{tokenUsed} / {tokenBudget ?? '—'} token</strong>
              </div>
              <div className="sf-chain-budget-track">
                <i style={{ width: `${tokenPct}%` }} />
              </div>
            </div>
          ) : null}
        </Step>

        <Step
          index={2}
          title="因子筛选"
          tone={factors.length > 0 ? 'good' : 'warn'}
          badge={<span className="sf-chain-badge">{factors.length} 个入选</span>}
        >
          {factors.length > 0 ? (
            <>
              <p>
                从 381 个因子中筛出 <strong>{factors.length}</strong> 个通过历史检验的因子：
                {`窗口 ${panel?.window_days ?? '—'} 天`}、
                {`样本量 ≥ ${panel?.min_samples ?? 20}`}、命中率须高于多数类基准。
              </p>
              <p className="sf-chain-meta">
                口径说明：历史命中率来自全部抽取模型（doubao / deepseek / glm）混合的事件研究，
                与当前在线模型 glm 的单一口径不同，仅作方向可靠性参考。
              </p>
            </>
          ) : (
            <p>本轮没有因子通过历史检验，策略不含情绪门控，仅依据技术信号生成。</p>
          )}
        </Step>

        <Step
          index={3}
          title="方向汇总"
          tone={bias === 'none' ? 'muted' : bias === 'balanced' ? 'warn' : 'good'}
          badge={
            <span className={`sf-chain-badge sf-chain-badge--${bias === 'none' ? 'muted' : bias === 'balanced' ? 'warn' : 'good'}`}>
              {biasText}
            </span>
          }
        >
          {factors.length > 0 ? (
            <>
              {/* 用一句话把「多少因子 → 什么方向 → 导致什么约束」讲清楚，
                  而不是罗列每个因子的数值。数值留在下方因子面板里可查。 */}
              <p className="sf-chain-flow">
                <strong>{factors.length}</strong> 个通过检验的因子中，
                <em className="long">{longCount} 个利多债券</em>、
                <em className="short">{shortCount} 个利空债券</em>，
                合计<b>{biasText}</b>。
              </p>
              <p className="sf-chain-meta">
                传导含义：
                {bias === 'long'
                  ? '因子阵营支持收益率下行，与技术做多信号同向时应允许开仓；方向冲突时空仓。'
                  : bias === 'short'
                    ? '因子阵营指向收益率上行，技术做多信号与之冲突时应空仓或降仓。'
                    : '多空力量相当，因子无法给出明确方向，本轮应只依赖技术信号且降低仓位。'}
              </p>
            </>
          ) : (
            <p className="sf-chain-meta">无因子可供方向汇总，本轮不启用情绪门控。</p>
          )}
        </Step>

        <Step
          index={4}
          title="门控规则"
          tone={usage && usage.includes('未使用') ? 'warn' : isDone ? 'good' : 'muted'}
          badge={usage ? <span className="sf-chain-badge">{usage}</span> : undefined}
        >
          {/* 把「因子 → 策略」的传导规则画成一条链 */}
          <ol className="sf-chain-flowline">
            <li>
              <span className="sf-chain-flowline-node">因子方向</span>
              <small>{bias === 'none' ? '无因子' : biasText}</small>
            </li>
            <li>
              <span className="sf-chain-flowline-node">门控条件</span>
              <small>{usage || (isDone ? '见策略概要' : '待生成')}</small>
            </li>
            <li>
              <span className="sf-chain-flowline-node">允许开仓</span>
              <small>{bias === 'balanced' || bias === 'none' ? '否（方向不明确）' : '是（需技术信号同向）'}</small>
            </li>
            <li>
              <span className="sf-chain-flowline-node">冲突处置</span>
              <small>空仓或降仓</small>
            </li>
          </ol>
          <p className="sf-chain-meta">
            硬性约束：因子只做方向确认与风险过滤，不单独触发交易。
          </p>
        </Step>

        <Step
          index={5}
          title="策略落地"
          tone={isDone ? 'good' : 'muted'}
          badge={
            isDone ? (
              <span className={`sf-chain-badge sf-chain-badge--${backtestPassed ? 'good' : 'warn'}`}>
                平台回测{backtestPassed ? '通过' : backtestPassed === false ? '未通过' : '未知'}
              </span>
            ) : undefined
          }
        >
          <p>
            {isDone
              ? '策略已生成并提交回测。'
              : isRunning
                ? '生成中…'
                : '尚未生成。'}
          </p>
          <p className="sf-chain-meta">
            注意：平台「回测通过」只代表回测进程正常退出，<strong>0 成交也算通过</strong>，
            因此成交与否以下一步的我方验收为准。
          </p>
        </Step>

        <Step
          index={6}
          title="我方验收"
          tone={tradingTone}
          badge={
            validation ? (
              <span className={`sf-chain-badge sf-chain-badge--${tradingTone === 'good' ? 'good' : tradingTone === 'bad' ? 'bad' : 'warn'}`}>
                {validation.verdict === 'passed' ? '通过' : validation.verdict === 'no_trade' ? '无成交' : '未通过'}
              </span>
            ) : undefined
          }
        >
          {validation ? (
            <>
              {tradeCount !== null && (
                <div className="sf-chain-trades">
                  <em>{tradeCount}</em>
                  <span>成交笔数</span>
                </div>
              )}
              <p>{validation.reason}</p>
              <ul className="sf-chain-checks">
                {validation.steps.map((s) => (
                  <li key={s.step} className={s.ok ? 'ok' : 'bad'}>
                    <span>{s.ok ? '✓' : '✗'}</span>
                    {STEP_LABELS[s.step] ?? s.step}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p>
              {isDone
                ? '本次生成尚未返回我方验收结论（验收门升级前的历史版本，或验收数据未落库）。'
                : '确认生成并完成回测后，此处给出我方验收结论。'}
            </p>
          )}
        </Step>
      </ol>

      <footer className="sf-chain-foot">
        结论只由数据推出：因子方向来自事件流聚合，命中率来自事件研究，成交与否来自回测日志解析。
        任一环节数据缺失时此处会如实说明，不做推断。
      </footer>
    </section>
  )
}