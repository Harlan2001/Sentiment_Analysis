import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  cancelWaitStrategyGeneration,
  confirmStrategyDraft,
  createStrategyDraft,
  getSupportedInstruments,
  getStrategyConversation,
  type DraftContext,
  type StrategyConversationDetail,
  type StrategyDraft,
  type StrategyValidation,
  type StrategyVersion,
  type SupportedInstruments,
} from '@/api/strategy'
import { isPollCapReached } from './generationStage'
import type { StepId } from './stepModel'

export type StrategyNewsReference = {
  news_id?: number
  id?: number
  title?: string
  source?: string
  publish_time?: string
  pub_time?: string
  reason?: string
  usage?: string
}

const LOOKBACK_DAYS = 7

/** 在④内嵌失败面板收尾的消息状态（GenerationStep 同口径）。 */
const FAILED_TURN_STATUSES = new Set(['failed', 'timed_out', 'cancelled'])

/**
 * 向导详情页的数据编排（S2-2 从 597 行的 StrategyPromptPage 抽出）。
 * 只管数据与动作；步骤解锁/跳转由 stepModel + 页面负责。
 */
export function useStrategyWizard(conversationId: number, go: (step: StepId) => void) {
  const [detail, setDetail] = useState<StrategyConversationDetail | null>(null)
  const [draft, setDraft] = useState('')
  const [systemDraft, setSystemDraft] = useState('')
  const [draftData, setDraftData] = useState<StrategyDraft | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [chatInput, setChatInput] = useState('')
  const [autoDraftDone, setAutoDraftDone] = useState(false)
  const [confirmedPromptMessageId, setConfirmedPromptMessageId] = useState<number | null>(null)
  // 标的来自后端白名单端点（B9）；模式/周期仍走固定枚举（后端同口径常量）。
  const [instruments, setInstruments] = useState<SupportedInstruments | null>(null)
  const [instrumentCode, setInstrumentCode] = useState('')
  const [backtestMode, setBacktestMode] = useState('bar')
  const [candleInterval, setCandleInterval] = useState('1d')
  const goRef = useRef(go)
  goRef.current = go

  useEffect(() => {
    getSupportedInstruments()
      .then((data) => {
        setInstruments(data)
        setInstrumentCode((current) => current || data.default)
      })
      .catch(() => setInstruments(null))
  }, [])

  const draftOptions = useCallback(
    () => ({ instrumentCode, backtestMode, candleInterval }),
    [instrumentCode, backtestMode, candleInterval],
  )

  const applyDraftResult = useCallback((result: StrategyDraft) => {
    setDraftData(result)
    setDraft(result.system_draft_prompt)
    setSystemDraft(result.system_draft_prompt)
    setConfirmedPromptMessageId(null)
  }, [])

  const loadDetail = useCallback(() => {
    if (!conversationId) return Promise.resolve()
    setLoading(true)
    return getStrategyConversation(conversationId)
      .then((data) => {
        setDetail(data)
        setError('')
        const lastAssistant = [...data.messages].reverse().find((m) => m.role === 'assistant')
        // 回填上次选定的标的/模式/周期，避免与已存草稿不一致。
        if (lastAssistant?.context_json) {
          const snapshot = lastAssistant.context_json as DraftContext
          if (snapshot.instrument_code) setInstrumentCode(snapshot.instrument_code)
          if (snapshot.backtest_mode) setBacktestMode(snapshot.backtest_mode)
          if (snapshot.candle_interval) setCandleInterval(snapshot.candle_interval)
        }
        if (lastAssistant?.system_draft_prompt) {
          const editableDraft = lastAssistant.user_edited_prompt || lastAssistant.system_draft_prompt
          setDraft(editableDraft)
          setSystemDraft(lastAssistant.system_draft_prompt)
          setDraftData({
            user_message_id: data.messages.find(
              (m) => m.role === 'user' && m.sequence_no === lastAssistant.sequence_no - 1,
            )?.id || 0,
            assistant_message_id: lastAssistant.id,
            status: lastAssistant.status,
            system_draft_prompt: lastAssistant.system_draft_prompt,
            context: (lastAssistant.context_json || {}) as DraftContext,
          })
          const isPersistedAsConfirmed =
            lastAssistant.status !== 'pending_confirmation' || Boolean(lastAssistant.final_sent_prompt)
          setConfirmedPromptMessageId((current) => {
            if (isPersistedAsConfirmed) return lastAssistant.id
            // 确认前发出的详情请求可能带回陈旧的 pending 数据，不能把已确认提示词回滚。
            return current === lastAssistant.id ? current : null
          })
        } else {
          setConfirmedPromptMessageId(null)
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [conversationId])

  useEffect(() => { void loadDetail() }, [loadDetail])

  // 空会话（从列表带标题进入）自动生成首轮草稿。
  useEffect(() => {
    if (!detail || autoDraftDone) return
    if (detail.messages.length > 0) { setAutoDraftDone(true); return }
    const title = detail.conversation?.title
    if (!title || title === '新策略对话') { setAutoDraftDone(true); return }
    setAutoDraftDone(true)
    setSubmitting(true)
    createStrategyDraft(conversationId, title, LOOKBACK_DAYS, draftOptions())
      .then((result) => {
        applyDraftResult(result)
        goRef.current('intel')
        return loadDetail()
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setSubmitting(false))
  }, [detail, autoDraftDone, conversationId, loadDetail, draftOptions, applyDraftResult])

  const lastAssistant = detail ? [...detail.messages].reverse().find((m) => m.role === 'assistant') : null
  const isRunning = lastAssistant?.status === 'running'

  // 「验收修正 · 第 N 轮」的 N：在本次挂载内按阶段转换到 revising 的次数计数，
  // 跨轮询去重（连续两次轮询都停在 revising 不重复计数）。
  const revisionTracker = useRef<{ id: number | null; count: number; prevStage: string }>({
    id: null,
    count: 0,
    prevStage: '',
  })
  if (lastAssistant?.id !== revisionTracker.current.id) {
    revisionTracker.current = {
      id: lastAssistant?.id ?? null,
      count: 0,
      prevStage: lastAssistant?.stage || '',
    }
  } else if (lastAssistant?.stage && lastAssistant.stage !== revisionTracker.current.prevStage) {
    if (lastAssistant.stage === 'revising') revisionTracker.current.count += 1
    revisionTracker.current.prevStage = lastAssistant.stage
  }
  const revisionRound = revisionTracker.current.count

  // 16 分钟轮询上限（与后端 sweep_stale_running 同口径，锚点是确认时刻
  // run_started_at；旧数据无锚点则不本地停轮询，由后端 16 分钟 sweep 兜底）。
  const [pollCapReached, setPollCapReached] = useState(false)
  const runningMessageId = isRunning ? (lastAssistant?.id ?? null) : null
  const runStartedAt = isRunning ? (lastAssistant?.run_started_at ?? null) : null
  useEffect(() => {
    setPollCapReached(false)
  }, [runningMessageId])
  // 进入运行态（或轮询带回新锚点）时立即判一次，不必等首个 4s tick。
  useEffect(() => {
    if (isRunning && isPollCapReached(runStartedAt)) setPollCapReached(true)
  }, [isRunning, runStartedAt])
  useEffect(() => {
    if (!isRunning || pollCapReached) return
    const timer = window.setInterval(() => {
      if (isPollCapReached(runStartedAt)) {
        setPollCapReached(true)
        return
      }
      void loadDetail()
    }, 4000)
    return () => window.clearInterval(timer)
  }, [isRunning, pollCapReached, runStartedAt, loadDetail])

  const [cancellingWait, setCancellingWait] = useState(false)
  const cancelWait = useCallback(async () => {
    if (!lastAssistant || lastAssistant.status !== 'running') return
    setCancellingWait(true)
    try {
      await cancelWaitStrategyGeneration(conversationId, lastAssistant.id)
      await loadDetail()
    } catch (e) {
      setError(e instanceof Error ? e.message : '放弃等待失败')
    } finally {
      setCancellingWait(false)
    }
  }, [conversationId, lastAssistant, loadDetail])

  const confirm = useCallback(async () => {
    if (!draftData) return
    setSubmitting(true)
    try {
      await confirmStrategyDraft(conversationId, draftData.assistant_message_id, draft)
      setDraftData((current) => (current ? { ...current, status: 'running' } : current))
      setConfirmedPromptMessageId(draftData.assistant_message_id)
      goRef.current('generation')
      await loadDetail()
    } catch (e) {
      setError(e instanceof Error ? e.message : '确认失败')
    } finally {
      setSubmitting(false)
    }
  }, [conversationId, draftData, draft, loadDetail])

  const regenerate = useCallback(async (requirement?: string) => {
    const text = (requirement ?? '').trim() || detail?.conversation?.title || ''
    if (!text) return
    setSubmitting(true)
    try {
      const result = await createStrategyDraft(conversationId, text, LOOKBACK_DAYS, draftOptions())
      applyDraftResult(result)
      goRef.current('intel')
      await loadDetail()
    } catch (e) {
      setError(e instanceof Error ? e.message : '重新生成失败')
    } finally {
      setSubmitting(false)
    }
  }, [conversationId, detail, draftOptions, applyDraftResult, loadDetail])

  const sendChat = useCallback(async (message: string) => {
    const msg = message.trim()
    if (!msg || !conversationId) return
    setChatInput('')
    setSubmitting(true)
    try {
      const result = await createStrategyDraft(conversationId, msg, LOOKBACK_DAYS, draftOptions())
      applyDraftResult(result)
      goRef.current('intel')
      await loadDetail()
    } catch (e) {
      setError(e instanceof Error ? e.message : '发送失败')
    } finally {
      setSubmitting(false)
    }
  }, [conversationId, draftOptions, applyDraftResult, loadDetail])

  const resetDraft = useCallback(() => setDraft(systemDraft), [systemDraft])
  const patchDraft = useCallback((next: string) => setDraft(next), [])

  const lastVersion: StrategyVersion | null = detail?.versions?.[0] || null
  const isDraftReady = draftData?.status === 'pending_confirmation'
  const isDone = Boolean(lastVersion)
  const hasTextOnlyReply = !isDraftReady && !isRunning && !isDone && Boolean(lastAssistant?.content)
  const failureMessage = lastAssistant?.public_error_message || lastAssistant?.content || '策略生成失败，请重新生成策略。'
  // 最近一轮已在④失败收尾（失败/超时/放弃等待/无版本文本回复）；
  // 默认步骤应停在④让失败面板可见，而不是退回情报步。
  const isTurnFailed =
    Boolean(lastAssistant && FAILED_TURN_STATUSES.has(lastAssistant.status)) || hasTextOnlyReply
  const hasDraft = Boolean(systemDraft || draftData)
  const isPromptConfirmed =
    confirmedPromptMessageId === draftData?.assistant_message_id
    || Boolean(lastAssistant?.final_sent_prompt)
    || (hasDraft && !isDraftReady && !hasTextOnlyReply)
    || isRunning
    || isDone

  const newsReferences = useMemo<StrategyNewsReference[]>(() => {
    const references = lastAssistant?.references_json
    return Array.isArray(references) ? references as StrategyNewsReference[] : []
  }, [lastAssistant])

  const factorPanel = useMemo(() => {
    const snapshot = (lastAssistant?.context_json || {}) as DraftContext
    return snapshot.factor_panel ?? null
  }, [lastAssistant])

  const draftContext = useMemo<DraftContext | null>(() => {
    const snapshot = draftData?.context || (lastAssistant?.context_json as DraftContext | undefined)
    return snapshot && typeof snapshot === 'object' ? snapshot : null
  }, [draftData, lastAssistant])

  const validation = useMemo<StrategyValidation | null>(() => {
    const raw = lastAssistant?.validation_json
    return raw && typeof raw === 'object' ? raw : null
  }, [lastAssistant])

  return {
    // 数据
    detail,
    loading,
    submitting,
    error,
    setError,
    draft,
    systemDraft,
    draftData,
    instruments,
    instrumentCode,
    backtestMode,
    candleInterval,
    setInstrumentCode,
    setBacktestMode,
    setCandleInterval,
    chatInput,
    setChatInput,
    // 派生
    conversationId,
    lastAssistant,
    lastVersion,
    isDraftReady,
    isRunning,
    isDone,
    hasDraft,
    isPromptConfirmed,
    hasTextOnlyReply,
    isTurnFailed,
    failureMessage,
    newsReferences,
    factorPanel,
    draftContext,
    validation,
    // ④ 生成中：阶段/计时/轮询上限/放弃等待
    revisionRound,
    pollCapReached,
    cancelWait,
    cancellingWait,
    refreshNow: loadDetail,
    // 动作
    confirm,
    regenerate,
    sendChat,
    resetDraft,
    patchDraft,
  }
}

export type StrategyWizardApi = ReturnType<typeof useStrategyWizard>
