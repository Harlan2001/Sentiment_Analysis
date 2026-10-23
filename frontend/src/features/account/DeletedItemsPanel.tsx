import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  DeletedItemsData,
  emptyDeletedItems,
  getDeletedItems,
  permanentlyDeleteConversation,
  permanentlyDeleteProject,
  restoreConversation,
  restoreProject,
} from '@/api/projects'
import { permanentlyDeleteDailyNewsSummary, restoreDailyNewsSummary } from '@/api/newsSummary'
import { permanentlyDeleteStrategyConversation, restoreStrategyConversation } from '@/api/strategy'
import { permanentlyDeleteReportGenerationTask, restoreReportGenerationTask } from '@/api/reportGeneration'
import { WorkflowDatePicker } from '@/features/workflow/components/WorkflowDatePicker'

type SourceFilter = '全部' | '项目' | '会话' | '策略' | '研报' | '新闻总结'
type EntryKind = Exclude<SourceFilter, '全部'>
type DeletedEntry = { id: string; kind: EntryKind; title: string; deletedAt: string; detail: string }

const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function asEntries(data: DeletedItemsData): DeletedEntry[] {
  return [
    ...(data.deleted_projects ?? []).map((item) => ({ id: item.id, kind: '项目' as const, title: item.name, deletedAt: item.deleted_at, detail: '项目及其会话' })),
    ...(data.deleted_conversations ?? []).map((item) => ({ id: item.id, kind: '会话' as const, title: item.title || '新建对话', deletedAt: item.deleted_at, detail: '普通会话' })),
    ...(data.deleted_strategies ?? []).map((item) => ({ id: String(item.id), kind: '策略' as const, title: item.title || '新策略对话', deletedAt: item.deleted_at, detail: '策略生成' })),
    ...(data.deleted_reports ?? []).map((item) => ({ id: item.id, kind: '研报' as const, title: item.title || '未命名研报', deletedAt: item.deleted_at, detail: '生成研报' })),
    ...(data.deleted_news_summaries ?? []).map((item) => ({ id: String(item.id), kind: '新闻总结' as const, title: item.start_date === item.end_date ? `${item.start_date} 新闻总结` : `${item.start_date} 至 ${item.end_date} 新闻总结`, deletedAt: item.deleted_at, detail: '每日新闻总结' })),
  ].sort((a, b) => b.deletedAt.localeCompare(a.deletedAt))
}

export function DeletedItemsPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [data, setData] = useState<DeletedItemsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('全部')
  const [search, setSearch] = useState('')
  const [selectedDate, setSelectedDate] = useState('')
  const [busyKey, setBusyKey] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try { setData(await getDeletedItems()) }
    catch (e) { setError(e instanceof Error ? e.message : '读取最近删除失败') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    if (!open) return
    void load()
    setSearch('')
    setSourceFilter('全部')
    setSelectedDate('')
  }, [open, load])

  useEffect(() => {
    if (!open) return
    const handleKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  const entries = useMemo(() => data ? asEntries(data) : [], [data])
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    return entries.filter((item) =>
      (sourceFilter === '全部' || item.kind === sourceFilter) &&
      (!selectedDate || item.deletedAt.slice(0, 10) === selectedDate) &&
      (!query || `${item.title} ${item.detail}`.toLowerCase().includes(query)),
    )
  }, [entries, search, selectedDate, sourceFilter])

  async function restore(item: DeletedEntry) {
    setBusyKey(`restore:${item.kind}:${item.id}`)
    setError('')
    try {
      if (item.kind === '项目') await restoreProject(item.id)
      else if (item.kind === '会话') await restoreConversation(item.id)
      else if (item.kind === '策略') await restoreStrategyConversation(Number(item.id))
      else if (item.kind === '研报') await restoreReportGenerationTask(item.id)
      else await restoreDailyNewsSummary(Number(item.id))
      await load()
      window.dispatchEvent(new CustomEvent('bondsense-sidebar-refresh'))
    } catch (e) { setError(e instanceof Error ? e.message : '恢复失败') }
    finally { setBusyKey(null) }
  }

  async function permanentlyDelete(item: DeletedEntry) {
    if (!window.confirm(`永久删除「${item.title}」？此操作无法恢复。`)) return
    setBusyKey(`delete:${item.kind}:${item.id}`)
    setError('')
    try {
      if (item.kind === '项目') await permanentlyDeleteProject(item.id)
      else if (item.kind === '会话') await permanentlyDeleteConversation(item.id)
      else if (item.kind === '策略') await permanentlyDeleteStrategyConversation(Number(item.id))
      else if (item.kind === '研报') await permanentlyDeleteReportGenerationTask(item.id)
      else await permanentlyDeleteDailyNewsSummary(Number(item.id))
      await load()
      window.dispatchEvent(new CustomEvent('bondsense-sidebar-refresh'))
    } catch (e) { setError(e instanceof Error ? e.message : '永久删除失败') }
    finally { setBusyKey(null) }
  }

  async function emptyAll() {
    if (!entries.length || !window.confirm(`永久删除最近删除中的全部 ${entries.length} 项？此操作无法恢复。`)) return
    setBusyKey('empty')
    setError('')
    try {
      await emptyDeletedItems()
      await load()
      window.dispatchEvent(new CustomEvent('bondsense-sidebar-refresh'))
    } catch (e) { setError(e instanceof Error ? e.message : '清空最近删除失败') }
    finally { setBusyKey(null) }
  }

  if (!open) return null
  return <div className="modal-layer" role="presentation">
    <button className="modal-backdrop" onClick={onClose} aria-label="关闭最近删除" />
    <section className="recycle-modal" role="dialog" aria-modal="true" aria-label="最近删除">
      <header className="modal-head"><div><h2>最近删除</h2><p>恢复项目、会话和工作流记录；永久删除后无法找回。</p></div><button className="modal-close" onClick={onClose} aria-label="关闭">✕</button></header>
      <div className="recycle-toolbar">
        <div className="recycle-filters">{(['全部', '项目', '会话', '策略', '研报', '新闻总结'] as SourceFilter[]).map((tab) => <button key={tab} className={sourceFilter === tab ? 'active' : ''} onClick={() => setSourceFilter(tab)}>{tab}</button>)}</div>
        <div className="recycle-actions"><WorkflowDatePicker value={selectedDate} onChange={setSelectedDate} label={today()} /><label className="recycle-search"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索名称…" /></label><button className="recycle-empty" disabled={!entries.length || busyKey === 'empty'} onClick={() => void emptyAll()}>{busyKey === 'empty' ? '清空中…' : '全部删除'}</button></div>
      </div>
      {error && <div className="recycle-error">{error}<button onClick={() => void load()}>重试</button></div>}
      <div className="recycle-count">{loading ? '正在读取…' : `显示 ${filtered.length} / ${entries.length} 项`}</div>
      <div className="recycle-list">
        {loading ? <div className="recycle-empty-state">正在读取…</div> : !filtered.length ? <div className="recycle-empty-state">最近删除中没有匹配的记录</div> : filtered.map((item) => {
          const restoring = busyKey === `restore:${item.kind}:${item.id}`
          const deleting = busyKey === `delete:${item.kind}:${item.id}`
          return <article className="recycle-row" key={`${item.kind}:${item.id}`}><div className="recycle-row-copy"><span className="recycle-kind">{item.kind}</span><strong title={item.title}>{item.title}</strong><small>{item.detail} · 删除于 {new Date(item.deletedAt).toLocaleString('zh-CN')}</small></div><div className="recycle-row-actions"><button disabled={!!busyKey} onClick={() => void restore(item)}>{restoring ? '恢复中…' : '恢复'}</button><button className="recycle-permanent" disabled={!!busyKey} onClick={() => void permanentlyDelete(item)} aria-label={`永久删除${item.title}`}>{deleting ? '…' : '🗑'}</button></div></article>
        })}
      </div>
    </section>
  </div>
}
