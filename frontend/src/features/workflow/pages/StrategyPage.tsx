import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  StrategyConversation,
  StrategyConversationSummary,
  createStrategyConversation,
  deleteStrategyConversation,
  getStrategyConversations,
} from '@/api/strategy'
import './strategy-workbench.css'

type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral'

type Badge = { text: string; tone: Tone }

const MODE_LABELS: Record<string, string> = {
  bar: 'K线',
  tick: 'Tick',
  factor: '因子',
}

function timeLabel(value: string | null) {
  if (!value) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
    .format(new Date(value))
    .replace(/\//g, '-')
}

function turnBadge(summary: StrategyConversationSummary): Badge {
  switch (summary.turn_status) {
    case 'pending_confirmation':
      return { text: '待确认', tone: 'warning' }
    case 'running':
      return { text: '生成中', tone: 'info' }
    case 'cancelled':
      return { text: '已放弃', tone: 'neutral' }
    case 'failed':
      return { text: '失败', tone: 'danger' }
    case 'timed_out':
      return { text: '已超时', tone: 'danger' }
    case 'succeeded':
      switch (summary.verdict) {
        case 'passed':
          return { text: '验收通过', tone: 'success' }
        case 'no_trade':
          return { text: '无成交 · 不合格', tone: 'warning' }
        case 'backtest_failed':
          return { text: '回测失败', tone: 'danger' }
        case 'backtest_error':
          return { text: '回测异常', tone: 'danger' }
        default:
          return { text: '已生成', tone: 'neutral' }
      }
    default:
      return { text: '新会话', tone: 'neutral' }
  }
}

const STATUS_OPTIONS = [
  { value: '全部', match: () => true },
  { value: '待确认', match: (s: StrategyConversationSummary) => s.turn_status === 'pending_confirmation' },
  { value: '生成中', match: (s: StrategyConversationSummary) => s.turn_status === 'running' },
  { value: '已完成', match: (s: StrategyConversationSummary) => s.turn_status === 'succeeded' },
  { value: '失败', match: (s: StrategyConversationSummary) => s.turn_status === 'failed' || s.turn_status === 'timed_out' },
]

const VERDICT_OPTIONS = [
  { value: '全部', match: () => true },
  { value: '验收通过', match: (s: StrategyConversationSummary) => s.verdict === 'passed' },
  { value: '无成交', match: (s: StrategyConversationSummary) => s.verdict === 'no_trade' },
  { value: '回测失败', match: (s: StrategyConversationSummary) => s.verdict === 'backtest_failed' },
  { value: '回测异常', match: (s: StrategyConversationSummary) => s.verdict === 'backtest_error' },
]

function FilterDropdown({
  label,
  value,
  options,
  onSelect,
}: {
  label: string
  value: string
  options: { value: string }[]
  onSelect: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function outside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [open])

  return (
    <div className="sw-filter" ref={ref}>
      <button
        type="button"
        className={'sw-filter-chip' + (value !== '全部' ? ' is-active' : '')}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {label}：{value}
        <i className="sw-caret" aria-hidden="true" />
      </button>
      {open && (
        <div className="sw-filter-menu">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              className={option.value === value ? 'is-active' : ''}
              onClick={() => {
                onSelect(option.value)
                setOpen(false)
              }}
            >
              {option.value}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function StrategyPage() {
  const navigate = useNavigate()
  const promptBase = '/strategy/prompt'
  const [conversations, setConversations] = useState<StrategyConversation[]>([])
  const [request, setRequest] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('全部')
  const [verdictFilter, setVerdictFilter] = useState('全部')

  const loadConversations = useCallback(() => {
    setLoading(true)
    getStrategyConversations(50)
      .then((data) => {
        setConversations(data.items)
        setError('')
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  async function createStrategy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const req = request.trim()
    if (!req) return
    setRequest('')
    setError('')
    try {
      const created = await createStrategyConversation(req)
      navigate(`${promptBase}?id=${created.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建策略失败')
    }
  }

  async function deleteStrategy(conversation: StrategyConversation) {
    if (!window.confirm(`将策略「${conversation.title || '新策略对话'}」移入最近删除？`)) return
    try {
      await deleteStrategyConversation(conversation.id)
      setConversations((current) => current.filter((item) => item.id !== conversation.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除策略失败')
    }
  }

  const visibleItems = useMemo(() => {
    const word = keyword.trim().toLowerCase()
    const statusMatcher = STATUS_OPTIONS.find((option) => option.value === statusFilter) ?? STATUS_OPTIONS[0]
    const verdictMatcher = VERDICT_OPTIONS.find((option) => option.value === verdictFilter) ?? VERDICT_OPTIONS[0]
    return conversations.filter((conversation) => {
      const summary = conversation.summary
      if (word && !(conversation.title || '').toLowerCase().includes(word)) return false
      if (!statusMatcher.match(summary)) return false
      if (!verdictMatcher.match(summary)) return false
      return true
    })
  }, [conversations, keyword, statusFilter, verdictFilter])

  return (
    <section className="sw-list-page">
      <header className="sw-list-header">
        <div>
          <h1 className="sw-list-title">策略生成</h1>
          <p className="sw-list-subtitle">AI 生成的研究草案，回测结果不代表实盘</p>
        </div>
        <div className="sw-list-controls">
          <div className="sw-search">
            <span aria-hidden="true">⌕</span>
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索策略名称"
              aria-label="搜索策略"
            />
          </div>
          <FilterDropdown label="状态" value={statusFilter} options={STATUS_OPTIONS} onSelect={setStatusFilter} />
          <FilterDropdown label="结论" value={verdictFilter} options={VERDICT_OPTIONS} onSelect={setVerdictFilter} />
        </div>
      </header>

      {error && <p className="sw-list-error" role="alert">{error}</p>}

      <div className="sw-card-list">
        {loading ? (
          <div className="sw-list-state">正在读取策略会话…</div>
        ) : visibleItems.length === 0 ? (
          <div className="sw-list-state">
            {conversations.length === 0 ? '还没有策略会话，在下方输入一句话想法开始' : '没有符合筛选条件的策略'}
          </div>
        ) : (
          visibleItems.map((conversation) => {
            const summary = conversation.summary
            const badge = turnBadge(summary)
            const modeText = [
              MODE_LABELS[summary.backtest_mode ?? ''] ?? summary.backtest_mode,
              summary.candle_interval,
            ]
              .filter(Boolean)
              .join(' / ')
            return (
              <article
                key={conversation.id}
                className="sw-card"
                onClick={() => navigate(`${promptBase}?id=${conversation.id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    navigate(`${promptBase}?id=${conversation.id}`)
                  }
                }}
              >
                <div className="sw-card-main">
                  <h2 className="sw-card-title">{conversation.title || '新策略对话'}</h2>
                  <p className="sw-card-meta">
                    {summary.instrument || summary.instrument_code || '标的待草稿生成后回填'}
                    {modeText ? ` · ${modeText}` : ''}
                  </p>
                  {summary.failure_reason && <p className="sw-card-reason">{summary.failure_reason}</p>}
                </div>
                <div className="sw-card-aside">
                  <div className="sw-card-badges">
                    <span className={`sw-badge sw-badge--${badge.tone}`}>{badge.text}</span>
                    {conversation.current_local_version_no > 0 && (
                      <span className="sw-badge sw-badge--neutral">v{conversation.current_local_version_no}</span>
                    )}
                  </div>
                  <p className="sw-card-metrics">
                    {summary.trade_count != null && <span>成交 {summary.trade_count} 笔</span>}
                    {summary.annual_return && <span>年化 {summary.annual_return}</span>}
                  </p>
                  <div className="sw-card-foot">
                    <time>{timeLabel(conversation.updated_at)}</time>
                    <button
                      type="button"
                      className="sw-card-delete"
                      aria-label={`删除策略 ${conversation.title || ''}`}
                      onClick={(event) => {
                        event.stopPropagation()
                        void deleteStrategy(conversation)
                      }}
                    >
                      删除
                    </button>
                  </div>
                </div>
              </article>
            )
          })
        )}
      </div>

      <form className="sw-composer" onSubmit={createStrategy}>
        <textarea
          value={request}
          onChange={(event) => setRequest(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              event.currentTarget.form?.requestSubmit()
            }
          }}
          placeholder="输入一句话策略想法（标的、方向、规则、回测要求）…"
          rows={2}
        />
        <div className="sw-composer-foot">
          <span className="sw-composer-hint">Enter 发送 · Shift+Enter 换行</span>
          <button type="submit" className="sw-primary-button" disabled={!request.trim()}>
            创建策略
          </button>
        </div>
      </form>
    </section>
  )
}
