/** AI 策略两阶段工作台：草稿、确认、版本与回测展示。 */
import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import {
  createAiStrategyConversation,
  createAiStrategyPromptDraft,
  confirmAiStrategyPromptDraft,
  fetchAiStrategyConversation,
} from '../../api'
import type { AiStrategyBacktestMetric, AiStrategyConversationMessage, AiStrategyPromptContext } from '../../types'
import { Button, Card, CardContent, CardHeader, CardTitle, Error as ErrorState, Loading, Select, Textarea } from '../UI'
import { formatBeijingDateTime } from '../../utils/helpers'

type ConversationTurn = {
  id: number
  requirement: string
  reply: string
  status: 'pending' | 'complete' | 'error'
}
type PromptDraft = {
  assistantMessageId: number
  prompt: string
  context: AiStrategyPromptContext
}


type VersionFilter = 'all' | 'passed' | 'failed'

const directionLabel: Record<string, string> = {
  positive: '\u5229\u591a\u503a\u5238',
  negative: '\u5229\u7a7a\u503a\u5238',
  neutral: '\u4e2d\u6027\u80cc\u666f',
}

const backtestMetricLabels: Record<string, string> = {
  total_orders: '\u603b\u8ba2\u5355\u6570',
  average_win: '\u5e73\u5747\u76c8\u5229',
  average_loss: '\u5e73\u5747\u4e8f\u635f',
  compounding_annual_return: '\u5e74\u5316\u590d\u5408\u6536\u76ca',
  drawdown: '\u6700\u5927\u56de\u64a4',
  start_equity: '\u8d77\u59cb\u8d44\u91d1',
  end_equity: '\u7ed3\u675f\u8d44\u91d1',
  net_profit: '\u51c0\u5229\u6da6',
  sharpe_ratio: 'Sharpe \u6bd4\u7387',
  sortino_ratio: 'Sortino \u6bd4\u7387',
  probabilistic_sharpe_ratio: '\u6982\u7387 Sharpe \u6bd4\u7387',
  win_rate: '\u80dc\u7387',
  loss_rate: '\u4e8f\u635f\u7387',
  profit_loss_ratio: '\u76c8\u4e8f\u6bd4',
  total_fees: '\u603b\u624b\u7eed\u8d39',
  portfolio_turnover: '\u7ec4\u5408\u6362\u624b\u7387',
  annual_standard_deviation: '\u5e74\u5316\u6807\u51c6\u5dee',
  annual_variance: '\u5e74\u5316\u65b9\u5dee',
  information_ratio: '\u4fe1\u606f\u6bd4\u7387',
  tracking_error: '\u8ddf\u8e2a\u8bef\u5dee',
  treynor_ratio: 'Treynor \u6bd4\u7387',
  alpha: 'Alpha',
  beta: 'Beta',
  expectancy: '\u671f\u671b\u503c',
  estimated_strategy_capacity: '\u9884\u4f30\u7b56\u7565\u5bb9\u91cf',
  lowest_capacity_asset: '\u6700\u4f4e\u5bb9\u91cf\u6807\u7684',
  drawdown_recovery: '\u56de\u64a4\u6062\u590d\u65f6\u95f4',
}
// The database stores user and assistant messages separately; render them as one conversational turn.
const toTurns = (messages: AiStrategyConversationMessage[]): ConversationTurn[] => {
  const turns: ConversationTurn[] = []
  for (const message of messages) {
    if (message.role === 'user') {
      turns.push({ id: message.id, requirement: message.content, reply: '', status: 'pending' })
      continue
    }
    const previous = turns[turns.length - 1]
    const status = message.status === 'succeeded' || message.status === 'pending_confirmation' ? 'complete' : message.status === 'running' ? 'pending' : 'error'
    if (previous && !previous.reply) {
      previous.reply = message.content || message.public_error_message || 'DreamStrategy \u6b63\u5728\u751f\u6210\u7b56\u7565...'
      previous.status = status
    } else {
      turns.push({ id: message.id, requirement: '', reply: message.content || message.public_error_message || '', status })
    }
  }
  return turns
}

const AiStrategyGenerationPreviewPage: React.FC = () => {
  const navigate = useNavigate()
  const { conversationId } = useParams()
  const queryClient = useQueryClient()
  const numericConversationId = conversationId ? Number(conversationId) : null
  const [requirement, setRequirement] = useState('')
  const [turns, setTurns] = useState<ConversationTurn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [versionFilter, setVersionFilter] = useState<VersionFilter>('all')
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null)
  const [draft, setDraft] = useState<PromptDraft | null>(null)
  const [editedPrompt, setEditedPrompt] = useState('')
  // A ref closes the short gap before React Query exposes its pending state.
  const draftRequestInFlight = useRef(false)

  const detailQuery = useQuery({
    queryKey: ['ai-strategy-conversation', numericConversationId],
    queryFn: () => fetchAiStrategyConversation(numericConversationId as number),
    enabled: Boolean(numericConversationId),
  })

  const versions = detailQuery.data?.data.versions ?? []
  const filteredVersions = useMemo(() => versions.filter((version) => {
    if (versionFilter === 'passed') return version.backtest_passed === true
    if (versionFilter === 'failed') return version.backtest_passed === false
    return true
  }), [versionFilter, versions])
  const selectedVersion = versions.find((version) => version.id === selectedVersionId) || filteredVersions[0] || null
  const sourceMessage = selectedVersion
    ? detailQuery.data?.data.messages.find((message) => message.id === selectedVersion.source_message_id)
    : undefined
  const messages = detailQuery.data?.data.messages ?? []
  // The persisted assistant status is the shared per-conversation lock across reloads and tabs.
  const activeStrategyMessage = [...messages].reverse().find((message) => (
    message.role === 'assistant' && (message.status === 'pending_confirmation' || message.status === 'running')
  ))
  const activePrompt = draft?.prompt
    ?? activeStrategyMessage?.final_sent_prompt
    ?? activeStrategyMessage?.system_draft_prompt
    ?? ''
  const activeContext = draft?.context ?? activeStrategyMessage?.context_json ?? null

  useEffect(() => {
    if (detailQuery.data) {
      setTurns(toTurns(detailQuery.data.data.messages))
      const latestPendingDraft = [...detailQuery.data.data.messages].reverse().find((message) => (
        message.role === 'assistant'
        && message.status === 'pending_confirmation'
        && message.system_draft_prompt
        && message.context_json
      ))
      if (latestPendingDraft?.system_draft_prompt && latestPendingDraft.context_json) {
        setDraft({
          assistantMessageId: latestPendingDraft.id,
          prompt: latestPendingDraft.system_draft_prompt,
          context: latestPendingDraft.context_json,
        })
        setEditedPrompt(latestPendingDraft.user_edited_prompt ?? latestPendingDraft.system_draft_prompt)
      } else {
        setDraft(null)
      }
    }

  }, [detailQuery.data])
  useEffect(() => {
    if (filteredVersions.length && !filteredVersions.some((version) => version.id === selectedVersionId)) {
      setSelectedVersionId(filteredVersions[0].id)
    }
  }, [filteredVersions, selectedVersionId])
  const draftMutation = useMutation({
    mutationFn: async (content: string) => {
      let targetId = numericConversationId
      if (!targetId) {
        const created = await createAiStrategyConversation(content.slice(0, 80))
        targetId = created.data.id
      }
      const response = await createAiStrategyPromptDraft(targetId, content)
      return { targetId, response }
    },
    onSuccess: async ({ targetId, response }) => {
      setDraft({ assistantMessageId: response.data.assistant_message_id, prompt: response.data.system_draft_prompt, context: response.data.context })
      setEditedPrompt(response.data.system_draft_prompt)
      await queryClient.invalidateQueries({ queryKey: ['ai-strategy-conversations'] })
      await queryClient.invalidateQueries({ queryKey: ['ai-strategy-conversation', targetId] })
      if (!numericConversationId) navigate(`/ai-strategy-generation-preview/${targetId}`, { replace: true })
    },
    onError: async (reason) => {
      const message = reason instanceof Error ? reason.message : '\u63d0\u793a\u8bcd\u8349\u7a3f\u751f\u6210\u5931\u8d25\u3002'
      if (message.includes('Confirm or wait for the current strategy turn first') && numericConversationId) {
        await detailQuery.refetch()
        setError(null)
        return
      }
      setError(message)
    },
    onSettled: () => {
      draftRequestInFlight.current = false
    },
  })

  const confirmMutation = useMutation({
    mutationFn: () => confirmAiStrategyPromptDraft(numericConversationId as number, draft!.assistantMessageId, editedPrompt),
    onSuccess: async () => {
      setDraft(null)
      const refreshed = await detailQuery.refetch()
      const latestVersion = refreshed.data?.data.versions[0]
      setSelectedVersionId(latestVersion?.id ?? null)
      await queryClient.invalidateQueries({ queryKey: ['ai-strategy-conversations'] })
    },
    onError: async (reason) => {
      setDraft(null)
      await queryClient.invalidateQueries({ queryKey: ['ai-strategy-conversation', numericConversationId] })
      setError(reason instanceof Error ? reason.message : 'DreamStrategy generation failed.')
    },
  })

  const generate = () => {
    const submittedRequirement = requirement.trim()
    if (!submittedRequirement || draftRequestInFlight.current || draftMutation.isPending || confirmMutation.isPending || activeStrategyMessage) return
    const turnId = Date.now()
    setTurns((current) => [...current, {
      id: turnId,
      requirement: submittedRequirement,
      reply: '\u5df2\u751f\u6210\u7b56\u7565\u63d0\u793a\u8bcd\u8349\u7a3f\uff0c\u8bf7\u5728\u53f3\u4fa7\u68c0\u67e5\u6216\u4fee\u6539\u540e\u518d\u786e\u8ba4\u53d1\u9001\u3002',
      status: 'complete',
    }])
    setRequirement('')
    setError(null)
    draftRequestInFlight.current = true
    draftMutation.mutate(submittedRequirement)
  }

  const handleComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      generate()
    }
  }

  const clear = () => {
    setRequirement('')
    setTurns([])
    setError(null)
    setSelectedVersionId(null)
    navigate('/ai-strategy-generation-preview')
  }

  const referencedNews = sourceMessage?.references_json ?? []
  const strategy = selectedVersion ? {
    name: selectedVersion.name,
    description: selectedVersion.description,
    code: selectedVersion.code,
  } : null
  const backtestPassed = selectedVersion?.backtest_passed ?? null
  const backtestMetrics: AiStrategyBacktestMetric[] = selectedVersion?.backtest_metrics_json ?? []
  const backtestLogPreview = selectedVersion?.backtest_summary?.split('\n').filter(Boolean).slice(-8).join('\n') ?? ''
  const activeIsRunning = confirmMutation.isPending || activeStrategyMessage?.status === 'running'
  return <div className="mx-auto max-w-[1480px] space-y-5">
    <div className="border-b border-gray-800 pb-5">
      <h1 className="text-3xl font-bold text-blue-400">{'AI\u7b56\u7565\u751f\u6210'}</h1>
    </div>

    {detailQuery.isLoading && <Loading text="\u6b63\u5728\u52a0\u8f7d\u5386\u53f2\u4f1a\u8bdd..." />}
    {detailQuery.error && <ErrorState message={detailQuery.error instanceof Error ? detailQuery.error.message : '\u52a0\u8f7d\u5386\u53f2\u4f1a\u8bdd\u5931\u8d25\u3002'} />}

    <div className="grid gap-5 lg:grid-cols-2">
    <Card>
      <CardHeader className="flex items-center justify-between border-b border-gray-800 pb-4">
        <CardTitle className="mb-0">{'\u7b56\u7565\u5bf9\u8bdd'}</CardTitle>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={clear}>{'\u65b0\u5efa\u5bf9\u8bdd'}</Button>
          <Button variant="secondary" size="sm" onClick={() => navigate('/ai-strategy-generation-history')}>{'\u5386\u53f2\u4f1a\u8bdd'}</Button>
        </div>
      </CardHeader>
      <CardContent className="flex h-[28rem] flex-col gap-4">
        <div className="flex-1 space-y-5 overflow-y-auto pr-2">
          {turns.length === 0 && <div className="rounded-xl border border-dashed border-gray-700 bg-gray-950/40 p-5 text-sm leading-7 text-gray-400">{'\u8bf7\u5728\u4e0b\u65b9\u8f93\u5165\u7b56\u7565\u9700\u6c42\u3002\u540e\u7aef\u4f1a\u81ea\u52a8\u52a0\u5165\u8fd1\u671f\u5e02\u573a\u60c5\u62a5\u5e76\u4fdd\u5b58\u5b8c\u6574\u5386\u53f2\u3002'}</div>}
          {turns.map((turn) => <div key={turn.id} className="space-y-3">
            {turn.requirement && <div className="ml-auto max-w-[82%] rounded-2xl rounded-tr-sm bg-gradient-to-r from-blue-600/70 to-purple-600/70 px-4 py-3 text-sm leading-7 text-white shadow-lg shadow-purple-950/20">{turn.requirement}</div>}
            {turn.reply && <div className={`mr-auto max-w-[92%] whitespace-pre-wrap rounded-2xl rounded-tl-sm border px-4 py-3 text-sm leading-7 ${turn.status === 'error' ? 'border-red-500/40 bg-red-950/20 text-red-100' : turn.status === 'pending' ? 'border-purple-500/40 bg-purple-950/30 text-purple-100' : 'border-gray-700 bg-gray-950/70 text-gray-200'}`}>{turn.reply}</div>}
          </div>)}
          {activeIsRunning && <div className="mr-auto flex max-w-[92%] items-start gap-3 rounded-2xl rounded-tl-sm border border-blue-500/40 bg-blue-950/30 px-4 py-3 text-sm text-blue-100" role="status">
            <svg className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-blue-300" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
            <p className="leading-6 text-blue-100">{'\u6b63\u5728\u751f\u6210\u7b56\u7565\u4e0e\u56de\u6d4b\u7ed3\u679c\uff0c\u8bf7\u7a0d\u5019\u3002'}</p>
          </div>}
        </div>
        <div className="space-y-3 border-t border-gray-800 pt-4">
          <Textarea value={requirement} onChange={(event) => setRequirement(event.target.value)} onKeyDown={handleComposerKeyDown} disabled={Boolean(activeStrategyMessage)} rows={4} placeholder={'\u4f8b\uff1a\u5728\u5f53\u524d\u7b56\u7565\u57fa\u7840\u4e0a\u63d0\u9ad8\u5f00\u4ed3\u9608\u503c\uff0c\u5e76\u52a0\u5165\u66f4\u4e25\u683c\u7684\u6b62\u635f\u6761\u4ef6\u3002'} />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-5 text-amber-300">{'Enter \u53d1\u9001\uff0cShift + Enter \u6362\u884c\u3002\u6bcf\u6b21\u771f\u5b9e\u751f\u6210\u90fd\u4f1a\u4fdd\u5b58\u5230\u72ec\u7acb\u5386\u53f2\u5e93\u3002'}</p>
            <Button loading={draftMutation.isPending} disabled={!requirement.trim() || Boolean(activeStrategyMessage) || confirmMutation.isPending} onClick={generate} className="shrink-0">{draftMutation.isPending ? '\u6b63\u5728\u751f\u6210\u63d0\u793a\u8bcd...' : '\u53d1\u9001\u5e76\u751f\u6210\u63d0\u793a\u8bcd'}</Button>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>
      </CardContent>
    </Card>

      <Card>
        <CardHeader className="flex items-center justify-between border-b border-gray-800 pb-4">
          <CardTitle className="mb-0">{'\u751f\u6210\u63d0\u793a\u8bcd'}</CardTitle>
          <span className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-200">{activeIsRunning ? 'AI \u6b63\u5728\u751f\u6210\u7b56\u7565' : draft ? editedPrompt !== draft.prompt ? '\u5df2\u4fee\u6539\uff0c\u5f85\u786e\u8ba4' : '\u5f85\u786e\u8ba4' : selectedVersion ? '\u5df2\u5b8c\u6210' : '\u5f85\u786e\u8ba4'}</span>
        </CardHeader>
        <CardContent className="flex h-[28rem] flex-col gap-4">
          <Textarea value={draft ? editedPrompt : activePrompt} onChange={(event) => setEditedPrompt(event.target.value)} disabled={!draft || activeIsRunning} rows={12} placeholder={'\u53d1\u9001\u9700\u6c42\u540e\uff0c\u5b8c\u6574\u63d0\u793a\u8bcd\u5c06\u5728\u6b64\u5904\u5f85\u786e\u8ba4\u3002'} containerClassName="min-h-0 flex-1" className="h-full min-h-0 resize-none font-mono text-xs leading-6" />
          {activeContext ? <div className="rounded-lg border border-gray-700 bg-gray-950/70 p-3 text-xs leading-6 text-gray-400"><p>{'\u65b0\u95fb\u5f15\u7528\uff1a'}{activeContext.references.length}{' \u6761  \u6807\u7684\uff1a'}{activeContext.instrument || '-'}</p><p>{'\u68c0\u7d22\u7a97\u53e3\uff1a'}{activeContext.window_start || '-'} {' ~ '} {activeContext.reference_time || '-'}</p></div> : <p className="text-sm text-gray-500">{'\u8bf7\u5148\u5728\u5de6\u4fa7\u53d1\u9001\u9700\u6c42\u3002\u751f\u6210\u8349\u7a3f\u4e0d\u4f1a\u8c03\u7528 DreamStrategy\u3002'}</p>}
          <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
            <Button variant="secondary" disabled={!draft || activeIsRunning} onClick={() => draft && setEditedPrompt(draft.prompt)}>{'\u8fd8\u539f\u7cfb\u7edf\u8349\u7a3f'}</Button>
            <Button loading={activeIsRunning} disabled={!draft || activeIsRunning} onClick={() => confirmMutation.mutate()}>{activeIsRunning ? '\u5df2\u53d1\u9001\uff0cAI \u6b63\u5728\u751f\u6210\u7b56\u7565' : '\u786e\u8ba4\u53d1\u9001\u5e76\u751f\u6210\u7b56\u7565'}</Button>
          </div>
        </CardContent>
      </Card>
    </div>

    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="mb-0">{'\u7b56\u7565\u7248\u672c'}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2 pt-0 sm:grid-cols-2">
        <Select value={versionFilter} onChange={(event) => setVersionFilter(event.target.value as VersionFilter)}>
          <option value="all">{'\u5168\u90e8\u7248\u672c'}</option>
          <option value="passed">{'\u4ec5\u56de\u6d4b\u901a\u8fc7'}</option>
          <option value="failed">{'\u4ec5\u56de\u6d4b\u672a\u901a\u8fc7'}</option>
        </Select>
        <Select value={selectedVersion?.id ?? ''} onChange={(event) => setSelectedVersionId(Number(event.target.value))} disabled={!filteredVersions.length}>
          {!filteredVersions.length && <option value="">{'\u6682\u65e0\u7b56\u7565\u7248\u672c'}</option>}
          {filteredVersions.map((version) => <option key={version.id} value={version.id}>v{version.local_version_no} - {formatBeijingDateTime(version.created_at)}</option>)}
        </Select>
      </CardContent>
    </Card>

    <Card>
      <CardHeader className="border-b border-gray-800 pb-4">
        <CardTitle>{'\u903b\u8f91\u6982\u8981'}</CardTitle>
      </CardHeader>
      <CardContent className="max-h-80 overflow-y-auto pr-2"><p className="min-h-28 whitespace-pre-wrap text-sm leading-7 text-gray-200">{strategy?.description || '\u6682\u65e0\u7b56\u7565\u8bf4\u660e\u3002'}</p></CardContent>
    </Card>

    <Card>
      <CardHeader className="border-b border-gray-800 pb-4">
        <CardTitle>{'\u76f8\u5173\u65b0\u95fb'}</CardTitle>
      </CardHeader>
      <CardContent>
        {referencedNews.length ? <div className="grid gap-4 lg:grid-cols-3">{referencedNews.map((news, index) => <div key={`${news.title}-${index}`} className={`rounded-xl border p-4 ${news.direction === 'positive' ? 'border-emerald-500/30 bg-emerald-950/20' : news.direction === 'negative' ? 'border-rose-500/30 bg-rose-950/20' : 'border-slate-600/50 bg-slate-900/30'}`}>
          <div className="flex items-center justify-between gap-3 text-xs text-gray-400"><span>{formatBeijingDateTime(news.pub_time)}</span><span className={news.direction === 'positive' ? 'rounded-full bg-emerald-500/15 px-2 py-1 text-emerald-300' : news.direction === 'negative' ? 'rounded-full bg-rose-500/15 px-2 py-1 text-rose-300' : 'rounded-full bg-slate-700/70 px-2 py-1 text-slate-300'}>{news.direction_label || directionLabel[news.direction] || news.direction}</span></div>
          {news.news_id ? <a href={`/news?newsId=${news.news_id}`} target="_blank" rel="noreferrer" className="mt-3 block text-sm font-semibold leading-6 text-blue-300 hover:text-blue-200 hover:underline">{news.title}<span className="ml-2 text-xs font-normal text-gray-400">{'\u67e5\u770b\u539f\u59cb\u65b0\u95fb'}</span></a> : <p className="mt-3 text-sm font-semibold leading-6 text-gray-100">{news.title}</p>}
          <div className="mt-3 flex items-center gap-2 text-xs text-gray-400"><span className="rounded bg-gray-800 px-2 py-1">{news.horizon}</span><span>{news.usage || '\u7528\u4e8e\u65b9\u5411\u786e\u8ba4\u4e0e\u8fc7\u6ee4'}</span></div>
          <p className="mt-3 border-t border-gray-700/70 pt-3 text-xs leading-5 text-gray-400">{news.reason}</p>
        </div>)}</div> : <p className="text-sm text-gray-500">{'\u6682\u65e0\u5f15\u7528\u65b0\u95fb\u3002'}</p>}
      </CardContent>
    </Card>


    <Card>
      <CardHeader className="border-b border-gray-800 pb-4">
        <CardTitle>{'\u7b56\u7565\u4ee3\u7801'}</CardTitle>
      </CardHeader>
      {strategy ? <CardContent className="max-h-[42rem] overflow-auto pr-2"><pre className="whitespace-pre rounded-lg border border-gray-700 bg-gray-950 p-4 text-xs leading-6 text-gray-200">{strategy.code}</pre></CardContent> : <CardContent><p className="text-sm text-gray-500">{'\u6682\u65e0\u4ee3\u7801\u3002'}</p></CardContent>}
    </Card>

    <Card>
      <CardHeader className="flex items-center justify-between border-b border-gray-800 pb-4">
        <CardTitle className="mb-0">{'\u4ee3\u7801\u56de\u6d4b\u7ed3\u679c'}</CardTitle>
        {backtestPassed === true ? <span className="rounded-full bg-emerald-500/15 px-3 py-1 text-sm font-medium text-emerald-300">{'\u901a\u8fc7'}</span> : backtestPassed === false ? <span className="rounded-full bg-rose-500/15 px-3 py-1 text-sm font-medium text-rose-300">{'\u672a\u901a\u8fc7'}</span> : <span className="rounded-full bg-gray-800 px-3 py-1 text-sm text-gray-400">{'\u7b49\u5f85\u7ed3\u679c'}</span>}
      </CardHeader>
      <CardContent className="space-y-4">
        {backtestMetrics.length > 0 && <section className="rounded-lg border border-gray-700 bg-gray-950/50 p-3">
          <h3 className="mb-3 text-sm font-semibold text-gray-200">{'回测指标统计'}</h3>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-center sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            {backtestMetrics.map((metric) => <div key={metric.key} className="min-w-0">
              <p className="truncate text-xs text-gray-400" title={backtestMetricLabels[metric.key] || metric.label}>{backtestMetricLabels[metric.key] || metric.label}</p>
              <p className="mt-1 truncate text-sm font-semibold text-gray-100" title={metric.value}>{metric.value || '-'}</p>
            </div>)}
          </div>
        </section>}
        <details className="rounded-lg border border-gray-700 bg-gray-950/50 p-3">
          <summary className="cursor-pointer text-sm font-medium text-gray-300">{'\u56de\u6d4b\u65e5\u5fd7\u6458\u8981'}</summary>
          <p className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap text-sm text-gray-400">{backtestLogPreview || (backtestPassed === true ? '\u672c\u6b21\u7b56\u7565\u56de\u6d4b\u5df2\u901a\u8fc7\u3002' : backtestPassed === false ? '\u672c\u6b21\u7b56\u7565\u56de\u6d4b\u672a\u901a\u8fc7\u3002' : '\u6682\u65e0\u56de\u6d4b\u7ed3\u679c\u3002')}</p>
        </details>
      </CardContent>
    </Card>
  </div>
}

export default AiStrategyGenerationPreviewPage
