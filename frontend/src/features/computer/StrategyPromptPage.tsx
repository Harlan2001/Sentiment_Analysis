import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { confirmStrategyDraft, createStrategyDraft, getStrategyConversation, StrategyConversationDetail, StrategyDraft, StrategyVersion } from '../../api/workbench'

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
    const list = (version.backtest_metrics_json as Array<{ name?: string; key?: string; value?: unknown }>) || []
    for (const m of list.slice(0, 8)) cards.push({ label: String(m.name || m.key || ''), value: String(m.value ?? '') })
  } catch { /* */ }
  return cards
}

export function StrategyPromptPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const conversationId = Number(searchParams.get('id'))
  const formRef = useRef<HTMLFormElement>(null)

  const [detail, setDetail] = useState<StrategyConversationDetail | null>(null)
  const [draft, setDraft] = useState('')
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
          setDraft(lastAssistant.user_edited_prompt || lastAssistant.system_draft_prompt)
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
        setDraftData(result); setDraft(result.system_draft_prompt); setSystemDraft(result.system_draft_prompt)
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

  async function handleRegenerate() {
    const title = detail?.conversation?.title || ''
    setSubmitting(true)
    try {
      const result = await createStrategyDraft(conversationId, title)
      setDraftData(result); setDraft(result.system_draft_prompt); setSystemDraft(result.system_draft_prompt)
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
      setDraftData(result); setDraft(result.system_draft_prompt); setSystemDraft(result.system_draft_prompt)
      await loadDetail()
    } catch (e) { setError(e instanceof Error ? e.message : '发送失败') }
    finally { setSubmitting(false) }
  }

  const lastVersion: StrategyVersion | null = detail?.versions?.[0] || null
  const isDraftReady = draftData?.status === 'pending_confirmation'
  const isDone = !!lastVersion
  const tags = useMemo(() => extractTags(draft || systemDraft || ''), [draft, systemDraft])
  const metrics = useMemo(() => backtestCards(lastVersion), [lastVersion])
  const newsReferences = useMemo(() => {
    const references = lastAssistant?.references_json
    return Array.isArray(references) ? references as Array<Record<string, unknown>> : []
  }, [lastAssistant])
  const backtestLog = lastVersion?.backtest_summary?.trim() || ''

  const activeStep = isDone ? 4 : isRunning ? 3 : isDraftReady ? 2 : detail && detail.messages.length > 0 ? 1 : 0
  const stepLabels = ['需求确认', '提示词草稿', '用户确认', '代码与回测', '生成完成']

  if (loading && !detail) return <section className="strategy-prompt-page"><div className="computer-list-head"><span style={{color:'#809188'}}>正在读取…</span></div></section>
  if (error && !detail) return <section className="strategy-prompt-page"><p className="chat-error">无法读取：{error}</p></section>

  return (
    <section className={`strategy-prompt-page${isDraftReady ? ' strategy-prompt-page--confirmation' : ''}`}>
      <div className="strategy-prompt-scroll">
      <header className="strategy-detail-head">
        <button className="computer-button" onClick={() => navigate('/computer/strategies')}>← 返回策略开发</button>
        <div><h1>{detail?.conversation?.title || '新策略对话'}</h1><p>策略会话 #{conversationId}</p></div>
        <span className="computer-spacer" />
        {isDraftReady && <span className="computer-badge warning">待确认</span>}
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
          <h2>提示词草稿</h2>
          {isDraftReady || isRunning || isDone ? (
            <textarea className="strategy-draft-textarea" value={draft || systemDraft} onChange={(e) => isDraftReady && setDraft(e.target.value)} readOnly={!isDraftReady} />
          ) : submitting ? (
            <div className="requirement-box muted">正在生成提示词草稿…</div>
          ) : (
            <div className="requirement-box muted">在下方聊天框输入策略需求以生成提示词草稿</div>
          )}
          {isDraftReady && (
            <div className="strategy-prompt-actions">
              <button className="computer-button" onClick={() => setDraft(systemDraft)}>还原系统草稿</button>
              <button className="computer-button" onClick={handleRegenerate} disabled={submitting}>重新生成</button>
              <span className="computer-spacer" />
              <button className="computer-button primary" onClick={handleConfirm} disabled={submitting}>确认并生成</button>
            </div>
          )}
        </aside>

        <section className="strategy-editor">
          <h2>策略概要</h2>
          <div className="strategy-editor-scroll">
          {isDone && lastVersion?.description ? (
            <p className="requirement-box" style={{marginTop:0}}>{lastVersion.description}</p>
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
      {(isDone || isRunning) && (
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
            {lastVersion?.code ? <textarea className="strategy-code-output" value={lastVersion.code} readOnly /> : (
              <div className="strategy-running-state"><span className="computer-progress"><i /></span><small>正在生成策略代码…</small></div>
            )}
          </section>

          <section className="project-card strategy-output-panel strategy-metrics-panel">
            <header><h2>回测指标</h2><span>{lastVersion?.backtest_passed === null || !lastVersion ? '待回测' : lastVersion.backtest_passed ? '通过' : '未通过'}</span></header>
            {metrics.length > 0 ? <div className="strategy-metrics-grid">{metrics.map((metric, index) => (
              <div className="metric-card" key={`${metric.label}-${index}`}><small>{metric.label}</small><strong>{metric.value}</strong></div>
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