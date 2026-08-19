import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { confirmStrategyDraft, createStrategyDraft, getStrategyConversation, StrategyConversationDetail, StrategyDraft, StrategyVersion } from '@/api/workbench'

type TradingParameter = { key: string; label: string; value: string }

const DEFAULT_TRADING_PARAMETERS: TradingParameter[] = [
  { key: 'entry', label: '开仓规则', value: '5日均线上穿20日均线，且收盘价站上20日均线' },
  { key: 'exit', label: '平仓规则', value: '5日均线跌破20日均线，或触发止盈止损' },
  { key: 'position', label: '单笔仓位', value: '20%资金' },
  { key: 'stopLoss', label: '止损', value: '1.5%' },
  { key: 'takeProfit', label: '止盈', value: '3.0%' },
  { key: 'backtestPeriod', label: '回测区间', value: '最近2年' },
  { key: 'frequency', label: '信号频率', value: '日频' },
]

function extractTradingParameters(prompt: string): TradingParameter[] {
  const match = prompt.match(/\[TRADING_PARAMETERS\]\s*([\s\S]*?)\s*\[\/TRADING_PARAMETERS\]/)
  if (!match) return DEFAULT_TRADING_PARAMETERS
  const values = new Map<string, string>()
  for (const line of match[1].split('\n')) {
    const [label, ...rest] = line.replace(/^\s*-\s*/, '').split('：')
    if (label && rest.length) values.set(label.trim(), rest.join('：').trim())
  }
  return DEFAULT_TRADING_PARAMETERS.map((item) => ({ ...item, value: values.get(item.label) || item.value }))
}

function replaceTradingParameters(prompt: string, parameters: TradingParameter[]) {
  const block = `[TRADING_PARAMETERS]\n${parameters.map(({ label, value }) => `- ${label}：${value.trim()}`).join('\n')}\n[/TRADING_PARAMETERS]`
  return prompt.replace(/\[TRADING_PARAMETERS\][\s\S]*?\[\/TRADING_PARAMETERS\]/, block)
}

function extractTags(draftText: string) {
  const tags: { label: string; value: string }[] = []
  const sections = draftText.split(/\n(?=【)/)
  for (const section of sections) {
    const m = section.match(/^【(.+?)】\s*\n?(.+)$/s)
    if (m) {
      const label = m[1]
      const raw = m[2].replace(/\n/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 120)
      if (raw) tags.push({ label, value: raw })
    }
  }
  return tags
}

function backtestCards(version: StrategyVersion | null) {
  if (!version) return []
  const cards: { label: string; value: string }[] = []
  if (version.backtest_passed !== null) cards.push({ label: '回测状态', value: version.backtest_passed ? '✓ 通过' : '✗ 未通过' })
  try {
    const list = (version.backtest_metrics_json as Array<{ name?: string; label?: string; key?: string; value?: unknown }>) || []
    for (const m of list) cards.push({ label: String(m.label || m.name || m.key || ''), value: String(m.value ?? '') })
  } catch { /* */ }
  return cards
}

function metricTone(label: string, value: string) {
  if (/回测状态/.test(label)) return value.startsWith('✓') ? 'positive' : 'negative'
  const numeric = Number(value.replace(/[%,$]/g, '').replace(/,/g, ''))
  if (!Number.isFinite(numeric) || numeric === 0) return 'neutral'
  const isRiskMetric = /drawdown|loss|fee|variance|deviation/i.test(label)
  return (numeric > 0) !== isRiskMetric ? 'positive' : 'negative'
}

const BACKTEST_METRIC_LABELS: Record<string, string> = {
  'Total Orders': '总订单数', 'Average Win': '平均盈利', 'Average Loss': '平均亏损',
  'Compounding Annual Return': '复合年化收益率', 'Drawdown': '最大回撤', 'Expectancy': '期望收益',
  'Start Equity': '初始权益', 'End Equity': '期末权益', 'Net Profit': '净利润',
  'Sharpe Ratio': '夏普比率', 'Sortino Ratio': '索提诺比率', 'Probabilistic Sharpe Ratio': '概率夏普比率',
  'Loss Rate': '亏损率', 'Win Rate': '胜率', 'Profit-Loss Ratio': '盈亏比', 'Alpha': '阿尔法',
  'Beta': '贝塔', 'Annual Standard Deviation': '年化标准差', 'Annual Variance': '年化方差',
  'Information Ratio': '信息比率', 'Tracking Error': '跟踪误差', 'Treynor Ratio': '特雷诺比率',
  'Total Fees': '总手续费', 'Estimated Strategy Capacity': '预计策略容量',
  'Lowest Capacity Asset': '最低容量标的', 'Portfolio Turnover': '组合换手率', 'Drawdown Recovery': '回撤修复期',
  'OrderListHash': '订单列表哈希',
}

function displayMetricLabel(label: string) {
  return BACKTEST_METRIC_LABELS[label] || label
}

function cleanStrategySummary(description: string) {
  const withoutCodeBlocks = description.replace(/```[^\n]*\n[\s\S]*?```/g, '').trim()
  const withoutUnclosedCode = withoutCodeBlocks.includes('```') ? withoutCodeBlocks.split('```', 1)[0].trim() : withoutCodeBlocks
  return withoutUnclosedCode || '策略代码与回测结果已生成，请在下方查看。'
}

export function StrategyPromptPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const conversationId = Number(searchParams.get('id'))
  const formRef = useRef<HTMLFormElement>(null)

  const [detail, setDetail] = useState<StrategyConversationDetail | null>(null)
  const [draft, setDraft] = useState('')
  const [tradingParameters, setTradingParameters] = useState<TradingParameter[]>(DEFAULT_TRADING_PARAMETERS)
  const [systemDraft, setSystemDraft] = useState('')
  const [draftData, setDraftData] = useState<StrategyDraft | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [chatInput, setChatInput] = useState('')
  const [autoDraftDone, setAutoDraftDone] = useState(false)

  const loadDetail = useCallback(() => {
    if (!conversationId) return
    setLoading(true)
    getStrategyConversation(conversationId)
      .then((data) => {
        setDetail(data)
        setError('')
        const lastAssistant = [...data.messages].reverse().find((m) => m.role === 'assistant')
        if (lastAssistant?.system_draft_prompt) {
          const editableDraft = lastAssistant.user_edited_prompt || lastAssistant.system_draft_prompt
          setDraft(editableDraft)
          setTradingParameters(extractTradingParameters(editableDraft))
          setSystemDraft(lastAssistant.system_draft_prompt)
          setDraftData({
            user_message_id: data.messages.find((m) => m.role === 'user' && m.sequence_no === lastAssistant.sequence_no - 1)?.id || 0,
            assistant_message_id: lastAssistant.id,
            status: lastAssistant.status,
            system_draft_prompt: lastAssistant.system_draft_prompt,
            context: (lastAssistant.context_json || {}) as Record<string, unknown>,
          })
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [conversationId])

  useEffect(() => { loadDetail() }, [loadDetail])

  useEffect(() => {
    if (!detail || autoDraftDone) return
    if (detail.messages.length > 0) { setAutoDraftDone(true); return }
    const title = detail.conversation?.title
    if (!title || title === '新策略对话') { setAutoDraftDone(true); return }
    setAutoDraftDone(true)
    setSubmitting(true)
    createStrategyDraft(conversationId, title)
      .then((result) => {
        setDraftData(result); setDraft(result.system_draft_prompt); setTradingParameters(extractTradingParameters(result.system_draft_prompt)); setSystemDraft(result.system_draft_prompt)
        return loadDetail()
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setSubmitting(false))
  }, [detail, autoDraftDone, conversationId, loadDetail])

  /* 确认后轮询：Dream 量化生成是异步的，持续拉取直到结果返回 */
  const lastAssistant = detail ? [...detail.messages].reverse().find((m) => m.role === 'assistant') : null
  const isRunning = lastAssistant?.status === 'running'
  useEffect(() => {
    if (!isRunning) return
    const timer = window.setInterval(() => void loadDetail(), 4000)
    return () => window.clearInterval(timer)
  }, [isRunning, loadDetail])

  async function handleConfirm() {
    if (!draftData) return
    setSubmitting(true)
    try { await confirmStrategyDraft(conversationId, draftData.assistant_message_id, draft); await loadDetail() }
    catch (e) { setError(e instanceof Error ? e.message : '确认失败') }
    finally { setSubmitting(false) }
  }

  function updateTradingParameter(key: string, value: string) {
    setTradingParameters((current) => {
      const next = current.map((item) => item.key === key ? { ...item, value } : item)
      setDraft((currentDraft) => replaceTradingParameters(currentDraft, next))
      return next
    })
  }

  async function handleRegenerate() {
    const title = detail?.conversation?.title || ''
    setSubmitting(true)
    try {
      const result = await createStrategyDraft(conversationId, title)
      setDraftData(result); setDraft(result.system_draft_prompt); setTradingParameters(extractTradingParameters(result.system_draft_prompt)); setSystemDraft(result.system_draft_prompt)
      await loadDetail()
    } catch (e) { setError(e instanceof Error ? e.message : '重新生成失败') }
    finally { setSubmitting(false) }
  }

  async function sendChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const msg = chatInput.trim()
    if (!msg || !conversationId) return
    setChatInput('')
    setSubmitting(true)
    try {
      const result = await createStrategyDraft(conversationId, msg)
      setDraftData(result); setDraft(result.system_draft_prompt); setTradingParameters(extractTradingParameters(result.system_draft_prompt)); setSystemDraft(result.system_draft_prompt)
      await loadDetail()
    } catch (e) { setError(e instanceof Error ? e.message : '发送失败') }
    finally { setSubmitting(false) }
  }

  const lastVersion: StrategyVersion | null = detail?.versions?.[0] || null
  const isDraftReady = draftData?.status === 'pending_confirmation'
  const isDone = !!lastVersion
  const hasTextOnlyReply = !isDraftReady && !isRunning && !isDone && Boolean(lastAssistant?.content)
  const isConfirmationView = !isDone && !isRunning && !hasTextOnlyReply
  const hasBacktestResult = lastVersion?.backtest_passed !== null && lastVersion?.backtest_passed !== undefined
  const isBacktestPassed = Boolean(lastVersion?.backtest_passed)
  const tags = useMemo(() => extractTags(draft || systemDraft || ''), [draft, systemDraft])
  const metrics = useMemo(() => backtestCards(lastVersion), [lastVersion])
  const newsReferences = useMemo(() => {
    const references = lastAssistant?.references_json
    return Array.isArray(references) ? references as Array<Record<string, unknown>> : []
  }, [lastAssistant])
  const backtestLog = lastVersion?.backtest_summary?.trim() || ''
  const strategySummary = lastVersion?.description ? cleanStrategySummary(lastVersion.description) : ''

  const activeStep = isDone ? 4 : isRunning ? 3 : isDraftReady ? 2 : detail && detail.messages.length > 0 ? 1 : 0
  const stepLabels = ['需求确认', '提示词草稿', '用户确认', '代码与回测', '生成完成']

  return (
    <section className={`strategy-prompt-page${isConfirmationView ? ' strategy-prompt-page--confirmation' : ''}`}>
      <div className="strategy-prompt-scroll">
      <header className="strategy-detail-head">
        <button className="computer-button" onClick={() => navigate('/computer/strategies')}>← 返回策略开发</button>
        <div><h1>{detail?.conversation?.title || '新策略对话'}</h1><p>策略会话 #{conversationId}</p></div>
        <span className="computer-spacer" />
        {isDraftReady && <span className="computer-badge warning">待确认</span>}
        {isConfirmationView && !isDraftReady && <span className="computer-badge running">{loading ? '正在读取…' : '生成提示词中…'}</span>}
        {isRunning && <span className="computer-badge running">生成中…</span>}
        {isDone && <span className="computer-badge file">已完成</span>}
      </header>

      <div className="strategy-stepper">
        {stepLabels.map((label, i) => (
          <span key={label} className={i < activeStep ? 'done' : i === activeStep ? 'active' : ''}>{label}</span>
        ))}
      </div>

      {/* 上半区：左=提示词草稿，右=策略概要 */}
      <div className="strategy-prompt-layout">
        <aside className="strategy-requirements">
          <h2>交易参数与提示词草稿</h2>
          {isConfirmationView && <div className="strategy-parameter-grid">
            {tradingParameters.map((parameter) => <label key={parameter.key}>
              <span>{parameter.label}</span>
              <input value={parameter.value} disabled={!isDraftReady || submitting} onChange={(event) => updateTradingParameter(parameter.key, event.target.value)} />
            </label>)}
          </div>}
          {isConfirmationView || isRunning || isDone || hasTextOnlyReply ? (
            <textarea className="strategy-draft-textarea" value={draft || systemDraft} placeholder={isConfirmationView && !isDraftReady ? (loading ? '正在读取策略会话…' : '正在生成提示词草稿…') : undefined} onChange={(e) => isDraftReady && setDraft(e.target.value)} readOnly={!isDraftReady} />
          ) : submitting ? (
            <div className="requirement-box muted">正在生成提示词草稿…</div>
          ) : (
            <div className="requirement-box muted">在下方聊天框输入策略需求以生成提示词草稿</div>
          )}
          {isConfirmationView && (
            <div className="strategy-prompt-actions">
              <button className="computer-button" onClick={() => setDraft(systemDraft)} disabled={!isDraftReady || submitting}>还原系统草稿</button>
              <button className="computer-button" onClick={handleRegenerate} disabled={!isDraftReady || submitting}>重新生成</button>
              <span className="computer-spacer" />
              <button className="computer-button primary" onClick={handleConfirm} disabled={!isDraftReady || submitting}>{isDraftReady ? '确认并生成' : '提示词生成中…'}</button>
            </div>
          )}
          {hasTextOnlyReply && <div className="strategy-prompt-actions">
            <small>本次未生成可回测代码，已保留远端回复。</small>
            <span className="computer-spacer" />
            <button className="computer-button primary" onClick={handleRegenerate} disabled={submitting}>重新生成策略</button>
          </div>}
        </aside>

        <section className="strategy-editor">
          <h2>策略概要</h2>
          <div className="strategy-editor-scroll">
          {isDone && strategySummary ? (
            <div className="strategy-summary-output">{strategySummary}</div>
          ) : hasTextOnlyReply ? (
            <pre className="strategy-backtest-log">{lastAssistant?.content}</pre>
          ) : (
            <p style={{color:'#809188',fontSize:12,margin:'12px 0'}}>
              {isRunning ? '策略生成中…' : '策略概要将在确认后展示'}
            </p>
          )}
          {error && <p className="chat-error" style={{marginTop:12}}>{error}</p>}
          </div>
        </section>
      </div>

      {/* 下半区：回测代码 + 回测结果，全宽 */}
      {(isDone || isRunning || hasTextOnlyReply) && (
        <div className="strategy-output-grid">
          <section className="project-card strategy-output-panel strategy-news-panel">
            <header><h2>相关新闻</h2><span>{newsReferences.length} 条</span></header>
            {newsReferences.length > 0 ? (
              <div className="strategy-news-list">
                {newsReferences.slice(0, 8).map((news, index) => (
                  <article key={String(news.news_id || news.id || index)}>
                    <strong>{String(news.title || '未命名新闻')}</strong>
                    <small>{[news.source, news.publish_time || news.pub_time].filter(Boolean).join(' · ') || '来源信息暂缺'}</small>
                  </article>
                ))}
              </div>
            ) : <p className="strategy-empty-state">本次策略未返回可展示的新闻引用。</p>}
          </section>

          <section className="project-card strategy-output-panel strategy-code-panel">
            <header><h2>回测代码</h2><span>{lastVersion ? `版本 ${lastVersion.local_version_no}` : '生成中'}</span></header>
            {lastVersion?.code ? <textarea className="strategy-code-output" value={lastVersion.code} readOnly /> : hasTextOnlyReply ? (
              <p className="strategy-empty-state">远端未创建策略代码版本，无法执行回测。请重新生成策略。</p>
            ) : (
              <div className="strategy-running-state"><span className="computer-progress"><i /></span><small>正在生成策略代码…</small></div>
            )}
          </section>

          <section className={`project-card strategy-output-panel strategy-metrics-panel ${hasBacktestResult ? isBacktestPassed ? 'backtest-result--passed' : 'backtest-result--failed' : ''}`}>
            <header><h2>回测指标</h2><span>{lastVersion?.backtest_passed === null || !lastVersion ? '待回测' : lastVersion.backtest_passed ? '通过' : '未通过'}</span></header>
            {metrics.length > 0 ? <div className="strategy-metrics-grid">{metrics.map((metric, index) => (
              <div className={`metric-card metric-card--${metricTone(metric.label, metric.value)}`} key={`${metric.label}-${index}`}><small>{displayMetricLabel(metric.label)}</small><strong title={metric.value}>{metric.value}</strong></div>
            ))}</div> : <p className="strategy-empty-state">回测完成后将在这里显示指标。</p>}
          </section>

          <section className="project-card strategy-output-panel strategy-log-panel">
            <header><h2>回测日志</h2><span>{lastVersion?.backtest_exit_code !== null && lastVersion?.backtest_exit_code !== undefined ? `退出码 ${lastVersion.backtest_exit_code}` : '等待输出'}</span></header>
            {backtestLog ? <pre className="strategy-backtest-log">{backtestLog}</pre> : <p className="strategy-empty-state">暂无回测日志。</p>}
          </section>
        </div>
      )}
      </div>

      {/* 底部聊天框 */}
      <form className="report-composer" ref={formRef} onSubmit={sendChat}>
        <textarea value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); formRef.current?.requestSubmit() } }} placeholder={isDone ? '输入新的需求以生成新策略…' : '修改或补充策略需求…'} rows={2} />
        <div><span className="composer-status">策略对话 · 发送后将重新生成提示词</span><button className="report-send" type="submit" disabled={!chatInput.trim() || submitting} aria-label="发送">↑</button></div>
      </form>
    </section>
  )
}
