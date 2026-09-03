import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  createDailyNewsSummary, DailyNewsSummaryTask, deleteDailyNewsSummary, getDailyNewsSummaries, getDailyNewsSummary,
  getLatestNewsDate, getNewsSources, NewsSourceOption, retryDailyNewsSummary,
} from '@/api/workbench'
import { NewsCalendarPicker } from '../components/NewsCalendarPicker'

const STATUS: Record<DailyNewsSummaryTask['status'], string> = {
  pending: '等待生成', running: '正在生成', succeeded: '生成成功', failed: '生成失败', empty: '范围内无新闻',
}
const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const range = (task: DailyNewsSummaryTask) => task.start_date === task.end_date ? task.start_date : `${task.start_date} 至 ${task.end_date}`
const time = (value: string | null) => value ? new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value)) : '-'

export function NewsSummaryPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const [tasks, setTasks] = useState<DailyNewsSummaryTask[]>([])
  const [sources, setSources] = useState<NewsSourceOption[]>([])
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [startDate, setStartDate] = useState(today())
  const [endDate, setEndDate] = useState(today())
  const [focus, setFocus] = useState('')
  const [filter, setFilter] = useState<'all' | DailyNewsSummaryTask['status']>('all')
  const [historySource, setHistorySource] = useState('all')
  const [retrying, setRetrying] = useState<number | null>(null)
  const [detail, setDetail] = useState<DailyNewsSummaryTask | null>(null)
  const [historyDate, setHistoryDate] = useState('')
  const [showAll, setShowAll] = useState(false)
  const [showAllActive, setShowAllActive] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [newsStatusOpen, setNewsStatusOpen] = useState(false)
  const [newsSourceOpen, setNewsSourceOpen] = useState(false)
  const newsStatusRef = useRef<HTMLDivElement>(null)
  const newsSourceRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function outside(e: MouseEvent) {
      if (newsStatusRef.current && !newsStatusRef.current.contains(e.target as Node)) setNewsStatusOpen(false)
      if (newsSourceRef.current && !newsSourceRef.current.contains(e.target as Node)) setNewsSourceOpen(false)
    }
    if (newsStatusOpen || newsSourceOpen) document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [newsStatusOpen, newsSourceOpen])

  const load = useCallback(async (withLoading = false) => {
    if (withLoading) setLoading(true)
    try {
      const data = await getDailyNewsSummaries(50)
      setTasks(data.items)
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : '读取新闻总结历史失败')
    } finally {
      if (withLoading) setLoading(false)
    }
  }, [])

  useEffect(() => {
    Promise.allSettled([load(true), getNewsSources(), getLatestNewsDate()]).then(([, sourceResult, dateResult]) => {
      if (sourceResult.status === 'fulfilled') setSources(sourceResult.value.sources)
      if (dateResult.status === 'fulfilled' && dateResult.value.latest_date) {
        setStartDate(dateResult.value.latest_date)
        setEndDate(dateResult.value.latest_date)
      }
    })
  }, [load])

  useEffect(() => {
    const taskId = Number(searchParams.get('task'))
    if (Number.isInteger(taskId) && taskId > 0) void open(taskId)
  }, [searchParams])

  const toolbarTasks = useMemo(() => tasks.filter((task) => {
    if (historySource !== 'all' && task.sources_json.length && !task.sources_json.includes(historySource)) return false
    return !historyDate || (task.start_date <= historyDate && task.end_date >= historyDate)
  }), [historyDate, historySource, tasks])
  const active = toolbarTasks.filter((task) => ['pending', 'running'].includes(task.status))
  useEffect(() => {
    if (!active.length) return
    const timer = window.setInterval(() => void load(), 2500)
    return () => window.clearInterval(timer)
  }, [active.length, load])

  const history = useMemo(() => toolbarTasks.filter((task) =>
    !['pending', 'running'].includes(task.status) && (filter === 'all' || task.status === filter)
  ), [filter, toolbarTasks])
  const visible = showAll ? history : history.slice(0, 4)
  const displayActive = showAllActive ? active : active.slice(0, 2)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (!startDate || !endDate || endDate < startDate) return setError('请选择有效的起止日期。')
    if ((new Date(endDate).getTime() - new Date(startDate).getTime()) / 86400000 > 30) return setError('单次最多总结 31 天新闻。')
    setBusy(true)
    try {
      const task = await createDailyNewsSummary({ start_date: startDate, end_date: endDate, sources: selectedSources, focus: focus.trim() })
      setTasks((current) => [task, ...current]); setFocus(''); await load()
    } catch (e) { setError(e instanceof Error ? e.message : '创建新闻总结失败') }
    finally { setBusy(false) }
  }

  async function open(taskId: number) {
    navigate(`/computer/news/${taskId}`)
  }

  async function retry(taskId: number) {
    setRetrying(taskId)
    try {
      const task = await retryDailyNewsSummary(taskId)
      setTasks((current) => [task, ...current]); setDetail(task); await load()
    } catch (e) { setError(e instanceof Error ? e.message : '重试失败') }
    finally { setRetrying(null) }
  }

  async function deleteTask(task: DailyNewsSummaryTask) {
    if (!window.confirm(`将「${range(task)} 新闻总结」移入最近删除？`)) return
    try {
      await deleteDailyNewsSummary(task.id)
      setTasks((current) => current.filter((item) => item.id !== task.id))
      setDetail((current) => current?.id === task.id ? null : current)
    } catch (e) { setError(e instanceof Error ? e.message : '删除新闻总结失败') }
  }

  return <section className="computer-page daily-news-page">
    <div className="computer-toolbar daily-news-history-toolbar">
      <div className="computer-dropdown" ref={newsStatusRef}>
        <button className={'computer-chip dropdown-chip ' + (filter !== 'all' ? 'selected' : '')} onClick={() => { setNewsStatusOpen((v) => !v); setNewsSourceOpen(false) }}>
          状态：{filter === 'all' ? '全部' : filter === 'succeeded' ? '生成成功' : filter === 'failed' ? '生成失败' : '范围内无新闻'}<i className="inline-caret" aria-hidden="true" />
        </button>
        {newsStatusOpen && (
          <div className="computer-dropdown-menu">
            {[{value:'all',label:'全部'},{value:'succeeded',label:'生成成功'},{value:'failed',label:'生成失败'},{value:'empty',label:'范围内无新闻'}].map((opt) => (
              <button key={opt.value} className={filter === opt.value ? 'active' : ''} onClick={() => { setFilter(opt.value as typeof filter); setNewsStatusOpen(false) }}>{opt.label}</button>
            ))}
          </div>
        )}
      </div>
      <div className="computer-dropdown" ref={newsSourceRef}>
        <button className={'computer-chip dropdown-chip ' + (historySource !== 'all' ? 'selected' : '')} onClick={() => { setNewsSourceOpen((v) => !v); setNewsStatusOpen(false) }}>
          来源：{historySource === 'all' ? '全部' : sources.find(s => s.key === historySource)?.name || historySource}<i className="inline-caret" aria-hidden="true" />
        </button>
        {newsSourceOpen && (
          <div className="computer-dropdown-menu">
            {[{key:'all',name:'全部'},...sources].map((source) => (
              <button key={source.key} className={historySource === source.key ? 'active' : ''} onClick={() => { setHistorySource(source.key); setNewsSourceOpen(false) }}>{source.name}</button>
            ))}
          </div>
        )}
      </div>
      <NewsCalendarPicker label="日期" value={historyDate} onChange={setHistoryDate} emptyLabel="全部日期" />
      {historyDate && <button type="button" className="computer-chip" onClick={() => setHistoryDate('')}>清除日期</button>}
      <span className="computer-spacer" /><button className="computer-button" onClick={() => void load(true)}>刷新</button><button className="computer-button primary" onClick={() => composerRef.current?.focus()}>＋ 立即生成</button><span className="computer-count">{loading ? '读取中…' : `${history.length} 段新闻总结`}</span>
    </div>
    {error && <div className="daily-news-error" role="alert">{error}</div>}
    <section className="computer-attention">
      <div className="computer-attention-head"><strong>需要处理 · {active.length}</strong><span aria-hidden="true">⌃</span></div>
      {!active.length ? <div className="computer-attention-row daily-news-empty-row"><span className="attention-dot" /><div><strong>当前没有需要处理的新闻总结</strong><small>新任务创建后会立即持久化并显示在这里。</small></div></div>
        : <>
          {displayActive.map((task) => <div className="computer-attention-row" key={task.id}><span className="attention-dot running daily-news-pulse" /><div><strong>{range(task)} 新闻总结</strong><small>{task.focus || '全部主题'} · {task.sources_json.length ? `${task.sources_json.length} 个指定来源` : '全部来源'}</small><span className="computer-progress"><i /></span></div><span className="computer-badge running">{STATUS[task.status]}</span><button className="computer-button" onClick={() => void open(task.id)}>查看状态</button><time>{time(task.updated_at)}</time></div>)}
          {active.length > 2 && (
            <div style={{textAlign:'center',padding:'6px 0 2px'}}>
              <button className="expand-toggle" onClick={() => setShowAllActive((v) => !v)} aria-label={showAllActive ? '收起' : '展开'}>
                <i className={'expand-arrow ' + (showAllActive ? 'up' : 'down')} />
              </button>
            </div>
          )}
        </>}
    </section>
    <div className="computer-list-head">
      <div><strong>{historyDate || '历史新闻总结'}</strong><span>· {history.length} 段总结会话</span></div>
      <div className="computer-view-switch"><button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>全部</button><button className={filter === 'succeeded' ? 'active' : ''} onClick={() => setFilter('succeeded')}>仅成功</button><button className={filter === 'failed' ? 'active' : ''} onClick={() => setFilter('failed')}>仅失败</button></div>
    </div>
    <div className="computer-table-wrap">
      <table className="computer-table"><thead><tr><th /><th>总结任务</th><th>新闻来源</th><th>状态或结果</th><th>更新时间</th><th>操作</th></tr></thead><tbody>
        {loading ? <tr><td colSpan={6} className="daily-news-table-state">正在读取持久化历史…</td></tr> : !visible.length ? <tr><td colSpan={6} className="daily-news-table-state">暂无历史生成记录</td></tr> : visible.map((task) => <tr key={task.id} onClick={() => void open(task.id)} className="daily-news-history-row"><td><span className={'computer-status ' + (task.status === 'succeeded' ? 'done' : task.status === 'failed' ? 'failed' : 'waiting')}>{task.status === 'succeeded' ? '✓' : task.status === 'failed' ? '!' : '○'}</span></td><td><strong>{range(task)} 新闻总结</strong><small>{task.news_count} 条新闻 · {task.focus || '全部主题'}</small></td><td>{task.sources_json.length ? `${task.sources_json.length} 个指定来源` : '全部来源'}</td><td><span className={'computer-badge ' + (task.status === 'failed' ? 'failure' : 'file')}>{STATUS[task.status]}</span></td><td><time>{time(task.updated_at)}</time></td><td><button className="computer-delete-button" onClick={(event) => { event.stopPropagation(); void deleteTask(task) }} aria-label={`删除新闻总结 ${range(task)}`}>🗑</button></td></tr>)}
      </tbody></table>
      {history.length > 4 && <div className="daily-news-expand"><button className="expand-toggle" onClick={() => setShowAll((current) => !current)}><i className={'expand-arrow ' + (showAll ? 'up' : 'down')} /></button></div>}
    </div>
    <form className="report-composer daily-news-composer" onSubmit={submit}>
      <textarea ref={composerRef} value={focus} maxLength={1000} onChange={(event) => setFocus(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} placeholder="输入本次新闻总结的关注重点，例如信用风险、资金面或政策影响…" rows={2} />
      <div className="daily-news-composer-controls">
        <NewsCalendarPicker label="开始" value={startDate} max={endDate} onChange={setStartDate} /><NewsCalendarPicker label="结束" value={endDate} min={startDate} onChange={setEndDate} />
        <button type="button" className={'computer-chip ' + (!selectedSources.length ? 'selected' : '')} onClick={() => setSelectedSources([])}>全部来源</button>
        {sources.map((source) => <button type="button" key={source.key} className={'computer-chip ' + (selectedSources.includes(source.key) ? 'selected' : '')} onClick={() => setSelectedSources((current) => current.includes(source.key) ? current.filter((key) => key !== source.key) : [...current, source.key])}>{source.name}</button>)}
        <span className="computer-badge">{selectedSources.length ? `已选 ${selectedSources.length} 个来源` : '全部来源'} · 真实新闻</span>
        <button className="report-send" disabled={busy} aria-label="生成新闻总结">{busy ? '…' : '↑'}</button>
      </div>
    </form>  </section>
}
