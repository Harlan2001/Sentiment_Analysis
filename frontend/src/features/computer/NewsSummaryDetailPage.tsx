import { useCallback, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useNavigate, useParams } from 'react-router-dom'
import { DailyNewsSummaryTask, getDailyNewsSummary, retryDailyNewsSummary } from '@/api/workbench'

const STATUS: Record<DailyNewsSummaryTask['status'], string> = { pending: '等待生成', running: '正在生成', succeeded: '生成成功', failed: '生成失败', empty: '范围内无新闻' }
const range = (task: DailyNewsSummaryTask) => task.start_date === task.end_date ? task.start_date : `${task.start_date} 至 ${task.end_date}`
const DIRECTION_META: Record<'positive' | 'negative' | 'neutral', { label: string; color: string }> = {
  positive: { label: '利多', color: '#ef4444' },
  negative: { label: '利空', color: '#22c55e' },
  neutral: { label: '中性', color: '#8b8b8b' },
}
const normalizeDirection = (direction?: string): 'positive' | 'negative' | 'neutral' =>
  direction === 'positive' ? 'positive' : direction === 'negative' ? 'negative' : 'neutral'

export function NewsSummaryDetailPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const [task, setTask] = useState<DailyNewsSummaryTask | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(false)
  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    try { setTask(await getDailyNewsSummary(Number(taskId))); setError('') }
    catch (reason) { setError(reason instanceof Error ? reason.message : '读取新闻总结详情失败') }
    finally { if (!quiet) setLoading(false) }
  }, [taskId])
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (!task || !['pending', 'running'].includes(task.status)) return
    const timer = window.setInterval(() => void load(true), 4000)
    return () => window.clearInterval(timer)
  }, [load, task])
  async function retry() {
    if (!task) return
    setRetrying(true)
    try { setTask(await retryDailyNewsSummary(task.id)); setError('') }
    catch (reason) { setError(reason instanceof Error ? reason.message : '重试失败') }
    finally { setRetrying(false) }
  }
  return <section className="computer-page daily-news-page">
    <div className="computer-tabs"><button onClick={() => navigate('/computer/news')}>← 返回每日新闻总结</button><span className="computer-spacer" /><button className="computer-button" onClick={() => void load()}>刷新状态</button></div>
    {loading ? <div className="report-detail-state">正在读取新闻总结详情…</div> : !task ? <div className="report-detail-state error">{error || '未找到新闻总结记录'}</div> : <article className="daily-news-detail daily-news-detail-page" aria-live="polite">
      <div className="daily-news-detail-head"><div><span className="computer-badge">{STATUS[task.status]}</span><h1>{range(task)} 新闻总结</h1><p>覆盖 {task.news_count} 条新闻 · {task.source_stats_json ? Object.entries(task.source_stats_json).map(([name, count]) => `${name} ${count} 条`).join(' · ') : '暂无来源统计'}</p></div></div>
      {!!task.references_json?.length && (() => {
        const counts: Record<'positive' | 'negative' | 'neutral', number> = { positive: 0, negative: 0, neutral: 0 }
        task.references_json!.forEach((item) => { counts[normalizeDirection(item.direction)] += 1 })
        const total = task.references_json!.length || 1
        return <div className="daily-news-direction-stats">{(['positive', 'negative', 'neutral'] as const).map((dir) => {
          const meta = DIRECTION_META[dir]
          const count = counts[dir]
          const pct = Math.round((count / total) * 100)
          return <div key={dir} className="daily-news-direction-stat"><span className="daily-news-direction-stat-label"><i style={{ background: meta.color }} />{meta.label}</span><strong>{count}<small> 条 · {pct}%</small></strong><span className="daily-news-direction-bar"><i style={{ width: `${pct}%`, background: meta.color }} /></span></div>
        })}
        </div>
      })()}
      {error && <div className="daily-news-error">{error}</div>}
      {['pending', 'running'].includes(task.status) && <div className="daily-news-detail-state"><span className="daily-news-spinner" />AI 正在基于真实新闻生成总结，页面会自动刷新。</div>}
      {task.error_message && <div className="daily-news-error">{task.error_message}<button className="computer-button primary" disabled={retrying} onClick={() => void retry()}>{retrying ? '正在重试…' : '重试'}</button></div>}
      {task.status === 'empty' && <div className="daily-news-detail-state">{task.summary}<button className="computer-button" disabled={retrying} onClick={() => void retry()}>重新检索</button></div>}
      {task.summary && task.status === 'succeeded' && <div className="daily-news-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{task.summary}</ReactMarkdown></div>}
      {!!task.references_json?.length && <details className="daily-news-references"><summary>引用新闻（{task.references_json.length}）</summary><div>{task.references_json.map((item) => { const dir = normalizeDirection(item.direction); const meta = DIRECTION_META[dir]; return <a key={item.news_id} href={`/news/${item.news_id}`} target="_blank" rel="noreferrer"><span className="daily-news-ref-meta">{item.source} · {String(item.publish_time).slice(0, 10)}<em className="daily-news-dir-tag" style={{ color: meta.color, borderColor: meta.color }}>{meta.label}</em>{item.horizon && <em className="daily-news-horizon-tag">{item.horizon}</em>}</span><strong>{item.title}</strong></a> })}</div></details>}
    </article>}
  </section>
}
