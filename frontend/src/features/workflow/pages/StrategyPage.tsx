import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { StrategyConversation, createStrategyConversation, deleteStrategyConversation, getStrategyConversations } from '@/api/strategy'

function timeLabel(value: string | null) {
  if (!value) return ''
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
}

function todayLabel() {
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()).replace(/\//g, '-')
}

function todayDate() {
  return new Date()
}

function matchesDate(iso: string, dateStr: string): boolean {
  const d = new Date(iso)
  const t = new Date(dateStr + 'T00:00:00')
  return d.getFullYear() === t.getFullYear() && d.getMonth() === t.getMonth() && d.getDate() === t.getDate()
}

const DAY_HEADERS = ['一','二','三','四','五','六','日']
const MONTH_NAMES = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']

function getMonthDays(year: number, month: number): (number | null)[] {
  const firstDay = new Date(year, month, 1).getDay() || 7 // 周一=1 周日=7
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const days: (number | null)[] = []
  for (let i = 1; i < firstDay; i++) days.push(null)
  for (let d = 1; d <= daysInMonth; d++) days.push(d)
  return days
}

export function StrategyPage() {
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<StrategyConversation[]>([])
  const [request, setRequest] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [archivedOnly, setArchivedOnly] = useState(false)
  const [selectedDate, setSelectedDate] = useState('')
  const [calOpen, setCalOpen] = useState(false)
  const [calYear, setCalYear] = useState(todayDate().getFullYear())
  const [calMonth, setCalMonth] = useState(todayDate().getMonth())
  const [showAllPending, setShowAllPending] = useState(false)
  const [showAllHistory, setShowAllHistory] = useState(false)
  const calRef = useRef<HTMLDivElement>(null)

  /* dropdown 状态 */
  const [statusFilter, setStatusFilter] = useState<string>('全部')
  const [sourceFilter, setSourceFilter] = useState<string>('全部')
  const [statusOpen, setStatusOpen] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(false)
  const statusRef = useRef<HTMLDivElement>(null)
  const sourceRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function outside(e: MouseEvent) {
      if (statusRef.current && !statusRef.current.contains(e.target as Node)) setStatusOpen(false)
      if (sourceRef.current && !sourceRef.current.contains(e.target as Node)) setSourceOpen(false)
    }
    if (statusOpen || sourceOpen) document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [statusOpen, sourceOpen])

  useEffect(() => {
    function outside(e: MouseEvent) { if (calRef.current && !calRef.current.contains(e.target as Node)) setCalOpen(false) }
    if (calOpen) document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [calOpen])

  const loadConversations = useCallback(() => {
    setLoading(true)
    getStrategyConversations(50)
      .then((data) => { setConversations(data.items); setError('') })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadConversations() }, [loadConversations])

  async function createStrategy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const req = request.trim()
    if (!req) return
    setRequest('')
    setError('')
    try {
      const created = await createStrategyConversation(req || '新策略对话')
      navigate(`/computer/strategies/prompt?id=${created.id}`)
    } catch (e) { setError(e instanceof Error ? e.message : '创建策略失败') }
  }

  async function deleteStrategy(conversation: StrategyConversation) {
    if (!window.confirm(`将策略「${conversation.title || '新策略对话'}」移入最近删除？`)) return
    try {
      await deleteStrategyConversation(conversation.id)
      setConversations((current) => current.filter((item) => item.id !== conversation.id))
    } catch (e) { setError(e instanceof Error ? e.message : '删除策略失败') }
  }

  const activeItems = conversations.filter((c) => c.status !== 'archived')
  const archivedItems = conversations.filter((c) => c.status === 'archived')
  const visibleItems = useMemo(() => {
    let items = archivedOnly ? archivedItems : activeItems
    if (selectedDate) items = items.filter((c) => matchesDate(c.updated_at, selectedDate))
    if (statusFilter === '待确认') items = items.filter((c) => c.current_local_version_no === 0)
    if (statusFilter === '已完成') items = items.filter((c) => c.current_local_version_no > 0)
    if (sourceFilter === '用户生成') items = items.filter((c) => !c.instrument)
    return items
  }, [activeItems, archivedItems, archivedOnly, selectedDate, statusFilter, sourceFilter])
  const pendingItems = visibleItems.filter((c) => c.current_local_version_no === 0)
  const historyItems = visibleItems.filter((c) => c.current_local_version_no > 0)

  const displayPending = showAllPending ? pendingItems : pendingItems.slice(0, 2)
  const displayHistory = showAllHistory ? historyItems : historyItems.slice(0, 4)
  const totalCount = visibleItems.length

  return (
    <section className="computer-page">
      <div className="computer-toolbar">
        <div className="computer-dropdown" ref={statusRef}>
          <button className={'computer-chip dropdown-chip ' + (statusFilter !== '全部' ? 'selected' : '')} onClick={() => { setStatusOpen((v) => !v); setSourceOpen(false) }}>
            状态：{statusFilter}<i className="inline-caret" aria-hidden="true" />
          </button>
          {statusOpen && (
            <div className="computer-dropdown-menu">
              {['全部', '待确认', '已完成'].map((opt) => (
                <button key={opt} className={statusFilter === opt ? 'active' : ''} onClick={() => { setStatusFilter(opt); setStatusOpen(false) }}>{opt}</button>
              ))}
            </div>
          )}
        </div>
        <div className="computer-dropdown" ref={sourceRef}>
          <button className={'computer-chip dropdown-chip ' + (sourceFilter !== '全部' ? 'selected' : '')} onClick={() => { setSourceOpen((v) => !v); setStatusOpen(false) }}>
            来源：{sourceFilter}<i className="inline-caret" aria-hidden="true" />
          </button>
          {sourceOpen && (
            <div className="computer-dropdown-menu">
              {['全部', '用户生成'].map((opt) => (
                <button key={opt} className={sourceFilter === opt ? 'active' : ''} onClick={() => { setSourceFilter(opt); setSourceOpen(false) }}>{opt}</button>
              ))}
            </div>
          )}
        </div>
        <button className={'computer-chip ' + (unreadOnly ? 'selected' : '')} onClick={() => setUnreadOnly((v) => !v)}>仅未读</button>
        <div style={{position:'relative',display:'inline-flex'}} ref={calRef}>
          <button className={'computer-chip ' + (selectedDate ? 'selected' : '')} onClick={() => { const t = selectedDate ? new Date(selectedDate + 'T00:00:00') : todayDate(); setCalYear(t.getFullYear()); setCalMonth(t.getMonth()); setCalOpen((v) => !v) }}>
            <span style={{marginRight:4}}>▣</span>{selectedDate || todayLabel()}
          </button>
          {selectedDate && <button className="computer-chip" onClick={() => setSelectedDate('')} style={{marginLeft:4}}>✕</button>}
          {calOpen && (
            <div className="calendar-popup">
              <div className="calendar-head">
                <button onClick={() => { if (calMonth === 0) { setCalMonth(11); setCalYear((y) => y - 1) } else setCalMonth((m) => m - 1) }}>‹</button>
                <strong>{calYear}年 {MONTH_NAMES[calMonth]}</strong>
                <button onClick={() => { if (calMonth === 11) { setCalMonth(0); setCalYear((y) => y + 1) } else setCalMonth((m) => m + 1) }}>›</button>
              </div>
              <div className="calendar-grid">
                {DAY_HEADERS.map((d) => <span key={d} className="calendar-day-header">{d}</span>)}
                {getMonthDays(calYear, calMonth).map((d, i) => {
                  if (d === null) return <span key={`e${i}`} />
                  const ds = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
                  return <button key={ds} className={'calendar-day ' + (ds === selectedDate ? 'selected' : '')} onClick={() => { setSelectedDate(ds); setCalOpen(false) }}>{d}</button>
                })}
              </div>
            </div>
          )}
        </div>
        <button className={'computer-chip ' + (archivedOnly ? 'selected' : '')} onClick={() => setArchivedOnly((v) => !v)}>已归档</button>
        <span className="computer-spacer" />
        <button className="computer-button primary" onClick={() => { const ta = document.querySelector<HTMLTextAreaElement>('.report-composer textarea'); ta?.focus() }}>＋ 新建策略</button>
        <span className="computer-count">{loading ? '读取中…' : `${totalCount} 段策略会话`}</span>
      </div>

      {/* 需要处理 */}
      <section className="computer-attention">
        <div className="computer-attention-head"><strong>需要处理 · {pendingItems.length}</strong><span>⌃</span></div>
        {pendingItems.length === 0 ? (
          <div className="computer-attention-row">
            <span className="attention-dot" />
            <div><strong>当前无待处理的策略开发</strong><small>新建策略后将在此展示待确认项</small></div>
            <span className="computer-spacer" />
          </div>
        ) : (
          <>
            {displayPending.map((item) => (
              <div className="computer-attention-row" key={item.id}>
                <span className="attention-dot running" />
                <div><strong>{item.title || '新策略对话'}</strong><small>{timeLabel(item.last_message_at)}</small></div>
                <span className="computer-badge warning">等待确认</span>
                <button className="computer-button primary" onClick={() => navigate(`/computer/strategies/prompt?id=${item.id}`)}>查看并确认</button>
                <time>{timeLabel(item.updated_at)}</time>
              </div>
            ))}
            {pendingItems.length > 2 && (
              <div style={{textAlign:'center',padding:'6px 0 2px'}}>
                <button className="expand-toggle" onClick={() => setShowAllPending((v) => !v)} aria-label={showAllPending ? '收起' : '展开'}>
                  <i className={'expand-arrow ' + (showAllPending ? 'up' : 'down')} />
                </button>
              </div>
            )}
          </>
        )}
      </section>

      {/* 历史策略 */}
      <div className="computer-list-head">
        <div><strong>{archivedOnly ? '已归档' : todayLabel()}</strong><span>· {historyItems.length} 段会话</span></div>
        <div className="computer-view-switch"><button className="active">会话与文档</button><button>仅会话</button><button>仅文档</button></div>
      </div>

      <div className="computer-table-wrap">
        <table className="computer-table">
          <thead><tr><th /><th>任务会话</th><th>来源/类型</th><th>状态或结果</th><th>更新时间</th><th>操作</th></tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={6} style={{textAlign:'center',padding:'24px',color:'#809188'}}>正在读取策略会话…</td></tr>
            : historyItems.length === 0 ? <tr><td colSpan={6} style={{textAlign:'center',padding:'24px',color:'#809188'}}>暂无策略会话</td></tr>
            : displayHistory.map((conv) => {
                return (
                  <tr key={conv.id} onClick={() => navigate(`/computer/strategies/prompt?id=${conv.id}`)} style={{cursor:'pointer'}}>
                    <td><span className={'computer-status ' + (conv.current_local_version_no > 0 ? 'done' : 'waiting')}>{conv.current_local_version_no > 0 ? '✓' : '●'}</span></td>
                    <td><strong>{conv.title || '新策略对话'}</strong><small>{timeLabel(conv.last_message_at)}</small></td>
                    <td>用户生成</td>
                    <td><span className={'computer-badge ' + (conv.current_local_version_no > 0 ? 'file' : 'warning')}>{conv.current_local_version_no > 0 ? '已完成' : '待确认'}</span></td>
                    <td><time>{timeLabel(conv.updated_at)}</time></td>
                    <td><button className="computer-delete-button" onClick={(event) => { event.stopPropagation(); void deleteStrategy(conv) }} aria-label={`删除策略 ${conv.title || ''}`}>🗑</button></td>
                  </tr>
                )
              })}
          </tbody>
        </table>
        {historyItems.length > 4 && (
          <div style={{textAlign:'center',padding:'6px 0 10px'}}>
            <button className="expand-toggle" onClick={() => setShowAllHistory((v) => !v)} aria-label={showAllHistory ? '收起' : '展开'}>
              <i className={'expand-arrow ' + (showAllHistory ? 'up' : 'down')} />
            </button>
          </div>
        )}
      </div>

      <form className="report-composer" onSubmit={createStrategy}>
        <textarea value={request} onChange={(event) => setRequest(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} placeholder="描述策略目标、市场范围和回测要求…" rows={2} />
        <div><button type="button" className="computer-button">＋ 添加文件</button><span className="computer-badge">⌁ 策略开发</span><button className="report-send" type="submit" disabled={!request.trim()} aria-label="创建策略">↑</button></div>
        {error && <p className="chat-error">{error}</p>}
      </form>
    </section>
  )
}
