import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  confirmStrategyDraft,
  createStrategyDraft,
  getStrategyConversation,
  DraftContext,
  StrategyConversationDetail,
  StrategyDraft,
  StrategyValidation,
  StrategyVersion,
} from '@/api/strategy'
import { CodeHighlight } from '@/features/workflow/components/CodeHighlight'
import { FactorSignalTable } from '@/features/workflow/components/FactorSignalTable'
import { LogicChain } from '@/features/workflow/components/LogicChain'
import { StrategySummary } from '@/features/workflow/components/StrategySummary'
import { ValidationSummary } from '@/features/workflow/components/ValidationSummary'

type TradingParameter = { key: string; label: string; value: string }
type StrategyModule = 'prompt' | 'factors' | 'strategy-news' | 'code' | 'metrics-logs'
type StrategyNewsReference = {
  news_id?: number
  id?: number
  title?: string
  source?: string
  publish_time?: string
  pub_time?: string
  reason?: string
  usage?: string
}

/**
 * 可交易标的白名单。
 *
 * 只列利率债口径的品种——我们的因子方向是"利多债券=收益率下行"，
 * 黄金（FCT_AU_MAIN）需要另行做方向映射，本期不进白名单。
 * FCT_T_MAIN 是历史实证里唯一跑出过成交的标的，故设为默认。
 */
const INSTRUMENT_OPTIONS = [
  { code: 'FCT_T_MAIN', label: '中金所10年期国债期货（默认）' },
  { code: 'FCT_TS_MAIN', label: '中金所2年期国债期货' },
  { code: 'FCT_TL_MAIN', label: '中金所30年期国债期货' },
  { code: 'IBK_G10Y_ACTV', label: '银行间10Y国债活跃券' },
  { code: 'IBK_CDB10_ACTV', label: '银行间10Y国开活跃券' },
] as const

const BACKTEST_MODE_OPTIONS = [
  { code: 'bar', label: 'bar（K线）' },
  { code: 'tick', label: 'tick（逐笔）' },
] as const

const CANDLE_INTERVAL_OPTIONS = [
  { code: '1d', label: '1d（日频）' },
  { code: '1h', label: '1h（小时）' },
  { code: '30m', label: '30m（30分钟）' },
  { code: '5m', label: '5m（5分钟）' },
  { code: '1m', label: '1m（1分钟）' },
] as const

const STRATEGY_MODULES: Array<{ id: StrategyModule; label: string }> = [
  { id: 'prompt', label: '提示词与确认' },
  { id: 'factors', label: '因子与逻辑' },
  { id: 'strategy-news', label: '策略与新闻' },
  { id: 'code', label: '回测代码' },
  { id: 'metrics-logs', label: '指标与日志' },
]

function isStrategyModule(value: string | null): value is StrategyModule {
  return STRATEGY_MODULES.some((module) => module.id === value)
}

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

function StrategyNewsCard({ news, onOpen }: { news: StrategyNewsReference; onOpen: (newsId: number) => void }) {
  const newsId = Number(news.news_id || news.id || 0)
  const title = String(news.title || '未命名新闻')
  const meta = [news.source, news.publish_time || news.pub_time].filter(Boolean).join(' · ')
  const description = String(news.reason || '')

  return (
    <button type="button" className="strategy-news-card" onClick={() => newsId > 0 && onOpen(newsId)} disabled={!newsId}>
      <span className="strategy-news-copy">
        <strong>{title}</strong>
        <small>{meta || '来源信息暂缺'}</small>
        {description && <p>{description}</p>}
      </span>
      <span className="strategy-news-link">查看详情 →</span>
    </button>
  )
}

export function StrategyPromptPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const listPath = '/strategy'
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
  const [confirmedPromptMessageId, setConfirmedPromptMessageId] = useState<number | null>(null)
  const requestedModule = searchParams.get('view')
  const activeModule: StrategyModule = isStrategyModule(requestedModule) ? requestedModule : 'prompt'
  const [copiedCode, setCopiedCode] = useState(false)
  // 标的/模式/周期由用户显式选择；没有这三个输入正是历史上"模型自己选标的"的
  // 事故来源，所以它们必须出现在表单里而不是藏在提示词里。
  const [instrumentCode, setInstrumentCode] = useState<string>('FCT_T_MAIN')
  const [backtestMode, setBacktestMode] = useState<string>('bar')
  const [candleInterval, setCandleInterval] = useState<string>('1d')

  const selectModule = useCallback((module: StrategyModule) => {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('view', module)
    setSearchParams(nextParams, { replace: true })
  }, [searchParams, setSearchParams])

  /** 生成草稿时一并提交标的与模式，让后端的白名单校验能生效。 */
  const draftOptions = useCallback(
    () => ({ instrumentCode, backtestMode, candleInterval }),
    [instrumentCode, backtestMode, candleInterval],
  )

  const loadDetail = useCallback(() => {
    if (!conversationId) return
    setLoading(true)
    getStrategyConversation(conversationId)
      .then((data) => {
        setDetail(data)
        setError('')
        const lastAssistant = [...data.messages].reverse().find((m) => m.role === 'assistant')
        // 回填上次选定的标的与模式，避免用户每次重新选、也避免与已存草稿不一致。
        if (lastAssistant?.context_json) {
          const snapshot = lastAssistant.context_json as DraftContext
          if (snapshot.instrument_code) setInstrumentCode(snapshot.instrument_code)
          if (snapshot.backtest_mode) setBacktestMode(snapshot.backtest_mode)
          if (snapshot.candle_interval) setCandleInterval(snapshot.candle_interval)
        }
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
            context: (lastAssistant.context_json || {}) as DraftContext,
          })
          const isPersistedAsConfirmed = lastAssistant.status !== 'pending_confirmation' || Boolean(lastAssistant.final_sent_prompt)
          setConfirmedPromptMessageId((current) => {
            if (isPersistedAsConfirmed) return lastAssistant.id
            // A detail request started before confirmation may return stale pending data.
            // Do not let it roll the same confirmed prompt back to "in progress".
            return current === lastAssistant.id ? current : null
          })
        } else setConfirmedPromptMessageId(null)
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
    createStrategyDraft(conversationId, title, 7, draftOptions())
      .then((result) => {
        setDraftData(result); setDraft(result.system_draft_prompt); setTradingParameters(extractTradingParameters(result.system_draft_prompt)); setSystemDraft(result.system_draft_prompt)
        setConfirmedPromptMessageId(null)
        selectModule('prompt')
        return loadDetail()
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setSubmitting(false))
  }, [detail, autoDraftDone, conversationId, loadDetail, selectModule])

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
    try {
      await confirmStrategyDraft(conversationId, draftData.assistant_message_id, draft)
      setDraftData((current) => current ? { ...current, status: 'running' } : current)
      setConfirmedPromptMessageId(draftData.assistant_message_id)
      selectModule('strategy-news')
      await loadDetail()
    }
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
      const result = await createStrategyDraft(conversationId, title, 7, draftOptions())
      setDraftData(result); setDraft(result.system_draft_prompt); setTradingParameters(extractTradingParameters(result.system_draft_prompt)); setSystemDraft(result.system_draft_prompt)
      setConfirmedPromptMessageId(null)
      selectModule('prompt')
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
      const result = await createStrategyDraft(conversationId, msg, 7, draftOptions())
      setDraftData(result); setDraft(result.system_draft_prompt); setTradingParameters(extractTradingParameters(result.system_draft_prompt)); setSystemDraft(result.system_draft_prompt)
      setConfirmedPromptMessageId(null)
      selectModule('prompt')
      await loadDetail()
    } catch (e) { setError(e instanceof Error ? e.message : '发送失败') }
    finally { setSubmitting(false) }
  }

  const lastVersion: StrategyVersion | null = detail?.versions?.[0] || null
  const isDraftReady = draftData?.status === 'pending_confirmation'
  const isDone = !!lastVersion
  const hasTextOnlyReply = !isDraftReady && !isRunning && !isDone && Boolean(lastAssistant?.content)
  const generationFailureMessage = lastAssistant?.public_error_message || lastAssistant?.content || '策略生成失败，请重新生成策略。'
  const isConfirmationView = !isDone && !isRunning && !hasTextOnlyReply
  const hasBacktestResult = lastVersion?.backtest_passed !== null && lastVersion?.backtest_passed !== undefined
  const isBacktestPassed = Boolean(lastVersion?.backtest_passed)
  const metrics = useMemo(() => backtestCards(lastVersion), [lastVersion])
  const newsReferences = useMemo(() => {
    const references = lastAssistant?.references_json
    return Array.isArray(references) ? references as StrategyNewsReference[] : []
  }, [lastAssistant])
  const backtestLog = lastVersion?.backtest_summary?.trim() || ''
  const strategySummary = lastVersion?.description ? cleanStrategySummary(lastVersion.description) : ''
  // 因子面板与验收结论都来自草稿快照 / 消息内容，历史版本没有时组件自身会优雅降级。
  const factorPanel = useMemo(() => {
    const snapshot = (lastAssistant?.context_json || {}) as DraftContext
    return snapshot.factor_panel ?? null
  }, [lastAssistant])
  // 逻辑链条要读标的/模式/token 用量，与因子面板同源于草稿快照。
  const draftContext = useMemo<DraftContext | null>(() => {
    const snapshot = draftData?.context || (lastAssistant?.context_json as DraftContext | undefined)
    return snapshot && typeof snapshot === 'object' ? snapshot : null
  }, [draftData, lastAssistant])
  const validation = useMemo<StrategyValidation | null>(() => {
    const raw = lastAssistant?.validation_json
    return raw && typeof raw === 'object' ? raw : null
  }, [lastAssistant])
  // 徽章文案由后端 verdict 决定，前端不自行推断——三步判定逻辑在后端，
  // 两边各算一套必然漂移。
  const verdictBadgeText = useMemo(() => {
    if (!lastVersion) return '待回测'
    if (validation) {
      if (validation.verdict === 'passed') return '验收通过'
      if (validation.verdict === 'no_trade') return '无成交（不合格）'
      if (validation.verdict === 'backtest_failed') return '回测失败'
      return '回测异常'
    }
    return lastVersion.backtest_passed ? '回测通过（未验收）' : '回测未通过'
  }, [lastVersion, validation])
  const verdictBadgeTone = useMemo(() => {
    if (!lastVersion) return 'file'
    if (validation) {
      if (validation.verdict === 'passed') return 'file'
      return 'warning'
    }
    return lastVersion.backtest_passed ? 'file' : 'warning'
  }, [lastVersion, validation])
  // Reaching any later content stage means the prompt/confirmation stage is complete.
  // Keep this independent of eventual-consistency delays in the message status API.
  const hasReachedPostConfirmationStage = activeModule !== 'prompt'
  const isPromptConfirmed = hasReachedPostConfirmationStage
    || confirmedPromptMessageId === draftData?.assistant_message_id
    || Boolean(lastAssistant?.final_sent_prompt)
    || Boolean(draftData && draftData.status !== 'pending_confirmation')
    || isRunning
    || isDone

  const moduleProgress = (module: StrategyModule): 'done' | 'running' | 'pending' => {
    if (isDone) return 'done'
    if (module === 'prompt' && isPromptConfirmed) return 'done'
    if (isRunning && module !== 'prompt') return 'running'
    return 'pending'
  }

  const moduleProgressLabel = (module: StrategyModule) => {
    const progress = moduleProgress(module)
    if (progress === 'done') return '已完成'
    if (progress === 'running') return '生成中'
    if (module === 'prompt' && isDraftReady) return '待确认'
    return '待生成'
  }

  async function copyCode() {
    if (!lastVersion?.code) return
    let copied = false
    try {
      await navigator.clipboard.writeText(lastVersion.code)
      copied = true
    } catch {
      const helper = document.createElement('textarea')
      helper.value = lastVersion.code
      helper.style.position = 'fixed'
      helper.style.opacity = '0'
      document.body.appendChild(helper)
      helper.select()
      copied = document.execCommand('copy')
      helper.remove()
    }
    if (!copied) { setError('复制代码失败，请手动选择代码复制。'); return }
    setCopiedCode(true)
    window.setTimeout(() => setCopiedCode(false), 1800)
  }

  function openStrategyNews(newsId: number) {
    navigate(`/news/${newsId}?strategyId=${conversationId}`)
  }

  return (
    <section className={`strategy-prompt-page${isConfirmationView ? ' strategy-prompt-page--confirmation' : ''}`}>
      <div className="strategy-prompt-scroll">
      <header className="strategy-detail-head">
        <button className="computer-button" onClick={() => navigate(listPath)}>← 返回策略生成</button>
        <div><h1>{detail?.conversation?.title || '新策略对话'}</h1><p>策略会话 #{conversationId}</p></div>
        <span className="computer-spacer" />
        {isDraftReady && <span className="computer-badge warning">待确认</span>}
        {isConfirmationView && !isDraftReady && <span className="computer-badge running">{loading ? '正在读取…' : '生成提示词中…'}</span>}
        {isRunning && <span className="computer-badge running">生成中…</span>}
        {isDone && <span className="computer-badge file">已完成</span>}
      </header>

      <div className="strategy-stepper strategy-module-nav" aria-label="策略内容模块">
        {STRATEGY_MODULES.map((module) => {
          const progress = moduleProgress(module.id)
          return (
          <button type="button" key={module.id} className={`${progress}${activeModule === module.id ? ' selected' : ''}`} onClick={() => selectModule(module.id)} aria-current={activeModule === module.id ? 'page' : undefined} aria-label={`${module.label}，${moduleProgressLabel(module.id)}`}>
            <span className="strategy-step-marker" aria-hidden="true">{progress === 'done' ? '✓' : '●'}</span>
            <strong>{module.label}</strong>
          </button>
          )
        })}
      </div>

      <div className="strategy-module-content">
        {activeModule === 'prompt' && <section className="strategy-module-panel strategy-prompt-module">
          <header><div><h2>提示词与确认</h2><p>直接编辑提示词或修改交易参数；参数变化会同步更新提示词。</p></div>{isDraftReady ? <span className="computer-badge warning">待确认</span> : <span className="computer-badge file">{isDone || isRunning ? '已确认' : '待生成'}</span>}</header>
          <div className="strategy-prompt-confirm-layout">
            <div className="strategy-prompt-editor-pane">
              <h3>提示词草稿</h3>
              {draft || systemDraft || isConfirmationView || isRunning || isDone ? (
                <textarea
                  className="strategy-draft-textarea"
                  value={draft || systemDraft}
                  placeholder={loading ? '正在读取策略会话…' : '正在生成提示词草稿…'}
                  onChange={(event) => isDraftReady && setDraft(event.target.value)}
                  readOnly={!isDraftReady}
                />
              ) : <div className="strategy-module-empty">在下方聊天框输入策略需求以生成提示词草稿。</div>}
            </div>
            <aside className="strategy-parameter-pane">
              <div><h3>交易参数</h3><p>标的与模式决定任务卡，修改后需重新生成草稿。</p></div>
              <div className="strategy-parameter-grid">
                <label>
                  <span>交易标的</span>
                  <select
                    value={instrumentCode}
                    disabled={submitting || isRunning}
                    onChange={(event) => setInstrumentCode(event.target.value)}
                  >
                    {INSTRUMENT_OPTIONS.map((option) => (
                      <option key={option.code} value={option.code}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>策略模式</span>
                  <select
                    value={backtestMode}
                    disabled={submitting || isRunning}
                    onChange={(event) => setBacktestMode(event.target.value)}
                  >
                    {BACKTEST_MODE_OPTIONS.map((option) => (
                      <option key={option.code} value={option.code}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>K线周期</span>
                  <select
                    value={candleInterval}
                    disabled={submitting || isRunning}
                    onChange={(event) => setCandleInterval(event.target.value)}
                  >
                    {CANDLE_INTERVAL_OPTIONS.map((option) => (
                      <option key={option.code} value={option.code}>{option.label}</option>
                    ))}
                  </select>
                </label>
                {tradingParameters.map((parameter) => <label key={parameter.key}>
                  <span>{parameter.label}</span>
                  <input value={parameter.value} disabled={!isDraftReady || submitting} onChange={(event) => updateTradingParameter(parameter.key, event.target.value)} />
                </label>)}
              </div>
              <p className="strategy-instrument-note">
                标的限定为利率债口径品种。黄金等需另做方向映射，本期不支持。
              </p>
            </aside>
          </div>
          <footer className="strategy-prompt-actions">
            <button className="computer-button" onClick={() => setDraft(systemDraft)} disabled={!isDraftReady || submitting}>还原系统草稿</button>
            <button className="computer-button" onClick={handleRegenerate} disabled={!isDraftReady || submitting}>重新生成</button>
            <span className="computer-spacer" />
            <button className="computer-button primary" onClick={handleConfirm} disabled={!isDraftReady || submitting}>{isDraftReady ? '确认并生成' : isRunning ? '策略生成中…' : '已确认'}</button>
          </footer>
        </section>}

        {activeModule === 'factors' && <section className="strategy-module-panel strategy-factors-module">
          <header>
            <div><h2>因子与逻辑</h2><p>按「情报 → 因子 → 门控 → 策略 → 验收」逐环核对本策略的依据。</p></div>
            <span className="computer-badge file">{factorPanel?.count ? `${factorPanel.count} 个因子` : '待生成'}</span>
          </header>
          <div className="strategy-module-scroll">
            <LogicChain
              context={draftContext}
              validation={validation}
              strategySummary={strategySummary}
              backtestPassed={lastVersion?.backtest_passed}
              isDone={isDone}
              isRunning={isRunning}
            />
            <FactorSignalTable panel={factorPanel} />
          </div>
        </section>}

        {activeModule === 'strategy-news' && <section className="strategy-module-panel strategy-news-module">
          <header><div><h2>策略与新闻</h2><p>查看策略概要及本次生成所引用的相关新闻。</p></div><span className="computer-badge file">{isDone ? '已生成' : isRunning ? '生成中' : '待生成'}</span></header>
          <div className="strategy-news-layout">
              <article className="strategy-news-card-list">
                <header><h3>相关新闻</h3><span>{newsReferences.length} 条</span></header>
                {newsReferences.length > 0
                  ? <div>{newsReferences.map((news, index) => <StrategyNewsCard key={String(news.news_id || news.id || index)} news={news} onOpen={openStrategyNews} />)}</div>
                  : <p className="strategy-empty-state">
                      {isRunning ? '正在整理相关新闻…' : '本轮情报包未引用新闻。可点「提示词与确认」查看完整情报包原文。'}
                    </p>}
              </article>
              <article className="strategy-summary-card">
                {/* 卡片保留"策略概要"标题；模型输出里同名的 ## 标题已由组件过滤，不会重复 */}
                <h3>策略概要</h3>
                {isDone && strategySummary
                  ? <div className="strategy-summary-output">
                      <StrategySummary markdown={strategySummary} />
                    </div>
                  : hasTextOnlyReply
                    ? <p className="strategy-empty-state">{generationFailureMessage}</p>
                    : <div className="strategy-running-state">
                        <span className="computer-progress"><i /></span>
                        <small>{isRunning ? '正在生成策略概要…' : '确认生成后，此处显示模型给出的策略逻辑说明'}</small>
                      </div>}
              </article>
          </div>
        </section>}

        {activeModule === 'code' && <section className="strategy-module-panel strategy-code-module">
          <header><div><h2>回测代码</h2><p>{lastVersion ? `版本 ${lastVersion.local_version_no} · Python` : '策略生成完成后可查看完整代码'}</p></div><button className="computer-button" onClick={() => void copyCode()} disabled={!lastVersion?.code}>{copiedCode ? '已复制' : '一键复制'}</button></header>
          {lastVersion?.code ? <CodeHighlight code={lastVersion.code} /> : hasTextOnlyReply ? <p className="strategy-empty-state">{generationFailureMessage}</p> : <div className="strategy-running-state"><span className="computer-progress"><i /></span><small>{isRunning ? '正在生成回测代码…' : '确认提示词后生成回测代码'}</small></div>}
        </section>}

        {activeModule === 'metrics-logs' && <section className="strategy-module-panel strategy-metrics-logs-module">
          <header>
            <div><h2>指标与日志</h2><p>验收结论优先于平台回测状态：0 成交一律判为不合格。</p></div>
            <span className={`computer-badge ${verdictBadgeTone}`}>{verdictBadgeText}</span>
          </header>
          <div className="strategy-metrics-logs-layout">
            <ValidationSummary
              validation={validation}
              backtestPassed={lastVersion?.backtest_passed}
              backtestSummary={backtestLog}
            />
            <article className={`strategy-module-subpanel ${hasBacktestResult ? isBacktestPassed ? 'backtest-result--passed' : 'backtest-result--failed' : ''}`}>
                <header><h3>回测指标</h3><span>{metrics.length} 项</span></header>
                {metrics.length > 0 ? <div className="strategy-metrics-grid">{metrics.map((metric, index) => <div className={`metric-card metric-card--${metricTone(metric.label, metric.value)}`} key={`${metric.label}-${index}`}><small>{displayMetricLabel(metric.label)}</small><strong title={metric.value}>{metric.value}</strong></div>)}</div> : <p className="strategy-empty-state">回测完成后将在这里显示指标。</p>}
              </article>
              <article className="strategy-module-subpanel strategy-log-panel">
                <header><h3>回测日志</h3><span>{lastVersion?.backtest_exit_code !== null && lastVersion?.backtest_exit_code !== undefined ? `退出码 ${lastVersion.backtest_exit_code}` : '等待输出'}</span></header>
                {backtestLog ? <pre className="strategy-backtest-log">{backtestLog}</pre> : <p className="strategy-empty-state">暂无回测日志。</p>}
            </article>
          </div>
        </section>}
        {error && <p className="chat-error strategy-module-error">{error}</p>}
      </div>
      </div>

      {/* 底部聊天框 */}
      <form className="report-composer" ref={formRef} onSubmit={sendChat}>
        <textarea value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); formRef.current?.requestSubmit() } }} placeholder={isDone ? '输入新的需求以生成新策略…' : '修改或补充策略需求…'} rows={2} />
        <div><span className="composer-status">策略对话 · 发送后将重新生成提示词</span><button className="report-send" type="submit" disabled={!chatInput.trim() || submitting} aria-label="发送">↑</button></div>
      </form>
    </section>
  )
}
