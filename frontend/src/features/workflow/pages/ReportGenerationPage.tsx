import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ReportGenerationTask,
  ResearchListItem,
  ResearchSummary,
  deleteReportGenerationTask,
  getReportGenerationTasks,
  getResearchList,
  getResearchSummary,
  retryReportGenerationTask,
} from '@/api/reportGeneration'
import { WorkflowDateRangePicker } from '../components/WorkflowDateRangePicker'
import { WorkflowDatePicker } from '../components/WorkflowDatePicker'
import { ReportCreateModal } from '../components/ReportCreateModal'
import ResearchUploadModal from '@/features/workflow/components/ResearchUploadModal'

function formatDateTime(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value))
}

const STATUS_LABEL: Record<ReportGenerationTask['status'], string> = {
  queued: '排队中', running: '正在生成', completed: '已完成', failed: '生成失败',
}
const VIEW_LABEL: Record<string, string> = { bullish: '看多', bearish: '看空', neutral: '中性' }
const STATUS_ICON: Record<string, { label: string; css: string }> = {
  parsed: { label: '已解析', css: 'waiting' }, processing: { label: '分析中', css: 'running' },
  analyzed: { label: '已分析', css: 'done' }, failed: { label: '失败', css: 'failed' },
}
const PAGE_SIZE = 6

export function ReportGenerationPage() {
  const navigate = useNavigate()

  // ── 我的报告（合成任务） ──
  const [tasks, setTasks] = useState<ReportGenerationTask[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [historyDateStart, setHistoryDateStart] = useState('')
  const [historyDateEnd, setHistoryDateEnd] = useState('')
  const [loadingTasks, setLoadingTasks] = useState(true)
  const [taskError, setTaskError] = useState('')
  const [showAllHistory, setShowAllHistory] = useState(false)

  // ── 研报库（选源 / 浏览） ──
  const [library, setLibrary] = useState<ResearchListItem[]>([])
  const [libraryTotal, setLibraryTotal] = useState(0)
  const [libraryPage, setLibraryPage] = useState(1)
  const [libraryFilters, setLibraryFilters] = useState({ institution: '', industry: '', market_view: '', keyword: '', dateStart: '', dateEnd: '' })
  const [debouncedKeyword, setDebouncedKeyword] = useState('')
  const [libraryOptions, setLibraryOptions] = useState<{ institutions: string[]; industries: string[] }>({ institutions: [], industries: [] })
  const [summary, setSummary] = useState<ResearchSummary | null>(null)
  const [pendingCount, setPendingCount] = useState(0)
  const [failedCount, setFailedCount] = useState(0)
  const [loadingLibrary, setLoadingLibrary] = useState(true)
  const [sourceError, setSourceError] = useState('')

  // ── 弹窗 / 下拉 ──
  const [createOpen, setCreateOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false)
  const statusDropdownRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    function outside(e: MouseEvent) {
      if (statusDropdownRef.current && !statusDropdownRef.current.contains(e.target as Node)) setStatusDropdownOpen(false)
    }
    if (statusDropdownOpen) document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [statusDropdownOpen])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedKeyword(libraryFilters.keyword.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [libraryFilters.keyword])

  // ── 数据加载 ──
  const loadTasks = useCallback(async (quiet = false) => {
    if (!quiet) setLoadingTasks(true)
    try {
      const data = await getReportGenerationTasks({
        status: statusFilter || undefined,
        date_start: historyDateStart || undefined,
        date_end: historyDateEnd || undefined,
      })
      setTasks(data.items)
      setTaskError('')
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : '读取我的报告失败')
    } finally {
      if (!quiet) setLoadingTasks(false)
    }
  }, [historyDateEnd, historyDateStart, statusFilter])

  const loadLibrary = useCallback(async () => {
    setLoadingLibrary(true)
    try {
      const data = await getResearchList({
        page: libraryPage,
        page_size: PAGE_SIZE,
        institution: libraryFilters.institution || undefined,
        industry: libraryFilters.industry || undefined,
        market_view: libraryFilters.market_view || undefined,
        keyword: debouncedKeyword || undefined,
        date_start: libraryFilters.dateStart || undefined,
        date_end: libraryFilters.dateEnd || undefined,
      })
      setLibrary(data.items); setLibraryTotal(data.total); setLibraryOptions(data.filters); setSourceError('')
    } catch (error) {
      setSourceError(error instanceof Error ? error.message : '读取研报库失败')
    } finally { setLoadingLibrary(false) }
  }, [libraryFilters.institution, libraryFilters.industry, libraryFilters.market_view,
      libraryFilters.dateStart, libraryFilters.dateEnd, debouncedKeyword, libraryPage])

  const loadStats = useCallback(async () => {
    try { setSummary(await getResearchSummary()) } catch { /* 统计失败不阻塞页面 */ }
    try {
      const [pending, failed] = await Promise.all([
        getResearchList({ status: 'parsed', page: 1, page_size: 1 }),
        getResearchList({ status: 'failed', page: 1, page_size: 1 }),
      ])
      setPendingCount(pending.total)
      setFailedCount(failed.total)
    } catch { /* 待办计数失败静默 */ }
  }, [])

  useEffect(() => { void loadTasks() }, [loadTasks])
  useEffect(() => { void loadLibrary() }, [loadLibrary])
  useEffect(() => { void loadStats() }, [loadStats])

  const activeTasks = tasks.filter((task) => task.status === 'queued' || task.status === 'running')
  const hasActiveTask = activeTasks.length > 0
  useEffect(() => {
    if (!hasActiveTask) return
    const timer = window.setInterval(() => void loadTasks(true), 4000)
    return () => window.clearInterval(timer)
  }, [hasActiveTask, loadTasks])

  // ── 操作 ──
  async function retry(taskId: string) {
    setTaskError('')
    try {
      const task = await retryReportGenerationTask(taskId)
      setTasks((current) => current.map((item) => item.id === task.id ? task : item))
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : '重试失败')
    }
  }

  async function deleteTask(task: ReportGenerationTask) {
    if (!window.confirm(`将研报「${task.title}」移入最近删除？`)) return
    try {
      await deleteReportGenerationTask(task.id)
      setTasks((current) => current.filter((item) => item.id !== task.id))
    } catch (error) { setTaskError(error instanceof Error ? error.message : '删除研报失败') }
  }

  function handleLibraryFilter(key: string, value: string) {
    setLibraryFilters((prev) => ({ ...prev, [key]: value })); setLibraryPage(1)
  }

  function handlePublishDateChange(dateStart: string, dateEnd: string) {
    setLibraryFilters((prev) => ({ ...prev, dateStart, dateEnd }))
    setLibraryPage(1)
  }

  const historyTasks = tasks.filter((task) => task.status === 'completed' || task.status === 'failed')
  const visibleHistory = showAllHistory ? historyTasks : historyTasks.slice(0, 6)
  const totalPages = Math.ceil(libraryTotal / PAGE_SIZE)

  return (
    <section className="computer-page report-generation-page">
      {/* ── Toolbar ── */}
      <div className="computer-toolbar">
        <button className="computer-button primary" onClick={() => setCreateOpen(true)}>＋ 新建综合研报</button>
        <button className="computer-button" onClick={() => setUploadOpen(true)}>＋ 上传 PDF</button>
        <span className="computer-spacer" />
        <button className="computer-button" onClick={() => { void loadTasks(); void loadLibrary(); void loadStats() }}>刷新状态</button>
        <button className="computer-button" onClick={() => navigate('/computer/reports/library')}>研报库</button>
      </div>

      {/* ── 待办型统计（板块三：数字必须可行动） ── */}
      <div className="report-stat-row">
        <button type="button" className="report-stat-chip waiting" onClick={() => navigate('/computer/reports/library')}>
          <small>待分析</small><strong>{pendingCount}</strong>
        </button>
        <button type="button" className="report-stat-chip failed" onClick={() => navigate('/computer/reports/library')}>
          <small>分析失败</small><strong>{failedCount}</strong>
        </button>
        <div className="report-stat-chip done"><small>已分析</small><strong>{summary?.analyzed ?? '—'}</strong></div>
        <div className="report-stat-chip"><small>研报总数</small><strong>{summary?.total ?? '—'}</strong></div>
        <div className="report-stat-chip bullish"><small>看多</small><strong>{summary?.bullish ?? '—'}</strong></div>
        <div className="report-stat-chip bearish"><small>看空</small><strong>{summary?.bearish ?? '—'}</strong></div>
        <div className="report-stat-chip neutral"><small>中性</small><strong>{summary?.neutral ?? '—'}</strong></div>
      </div>

      {/* ── 我的报告（首屏主区） ── */}
      <div className="computer-list-head" style={{ marginTop: 4 }}>
        <div><strong>我的报告</strong><span>· 综合研报生成任务</span></div>
        <div className="computer-dropdown" ref={statusDropdownRef}>
          <button className={'computer-chip dropdown-chip ' + (statusFilter ? 'selected' : '')} onClick={() => setStatusDropdownOpen((v) => !v)}>
            状态：{statusFilter ? { queued: '排队中', running: '正在生成', completed: '已完成', failed: '失败' }[statusFilter] : '全部'}<i className="inline-caret" aria-hidden="true" />
          </button>
          {statusDropdownOpen && (
            <div className="computer-dropdown-menu">
              {[{ value: '', label: '全部' }, { value: 'queued', label: '排队中' }, { value: 'running', label: '正在生成' }, { value: 'completed', label: '已完成' }, { value: 'failed', label: '失败' }].map((opt) => (
                <button key={opt.value} className={statusFilter === opt.value ? 'active' : ''} onClick={() => { setStatusFilter(opt.value); setStatusDropdownOpen(false) }}>{opt.label}</button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 生成中 */}
      {activeTasks.length > 0 && (
        <section className="computer-attention">
          <div className="computer-attention-head"><strong>生成中 · {activeTasks.length}</strong><span>每 4 秒自动刷新</span></div>
          {activeTasks.map((task) => (
            <div className="computer-attention-row" key={task.id}>
              <span className="attention-dot running" />
              <div><strong>{task.title}</strong><small>{task.source_snapshot_json.length} 份来源 · 第 {task.version_no} 版 · {task.status === 'queued' ? '等待生成资源' : '模型正在综合'}</small></div>
              <span className="computer-spacer" /><span className="computer-badge running">{STATUS_LABEL[task.status]}</span>
              <span className="attention-action-cell"><button className="computer-button" onClick={() => navigate(`/computer/reports/${task.id}`)}>查看详情</button><time>{formatDateTime(task.updated_at)}</time></span>
            </div>
          ))}
        </section>
      )}

      {/* 任务表 */}
      <div className="computer-table-wrap">
        <table className="computer-table"><thead><tr><th /><th>报告</th><th>来源范围</th><th>状态</th><th>更新时间</th><th>操作</th></tr></thead>
          <tbody>{loadingTasks ? <tr><td colSpan={6}><div className="report-empty">正在读取我的报告…</div></td></tr>
            : taskError ? <tr><td colSpan={6}><div className="report-empty error">{taskError}<button onClick={() => void loadTasks()}>重试</button></div></td></tr>
            : visibleHistory.length === 0 ? <tr><td colSpan={6}><div className="report-empty">还没有综合研报，点击「新建综合研报」选择来源开始。</div></td></tr>
            : visibleHistory.map((task) => <tr key={task.id} onClick={() => navigate(`/computer/reports/${task.id}`)} className="clickable-row">
                <td><span className={`computer-status ${task.status === 'completed' ? 'done' : 'failed'}`}>{task.status === 'completed' ? '✓' : '!'}</span></td>
                <td><strong>{task.title}</strong><small>{task.requirement}{task.version_no > 1 ? ` · 第 ${task.version_no} 版` : ''}</small></td>
                <td>{task.source_snapshot_json.length} 份研报{task.date_start ? ` · ${task.date_start}${task.date_end ? ` 至 ${task.date_end}` : ''}` : ''}</td>
                <td><span className={`computer-badge ${task.status === 'completed' ? 'file' : 'failed'}`}>{STATUS_LABEL[task.status]}</span>{task.status === 'failed' && <button className="inline-retry" onClick={(event) => { event.stopPropagation(); void retry(task.id) }}>重试</button>}</td>
                <td><time>{formatDateTime(task.updated_at)}</time></td>
                <td><button className="computer-delete-button" onClick={(event) => { event.stopPropagation(); void deleteTask(task) }} aria-label={`删除研报 ${task.title}`}>🗑</button></td>
              </tr>)}
          </tbody>
        </table>
        {historyTasks.length > 6 && <div className="report-history-toggle"><button className="expand-toggle" onClick={() => setShowAllHistory((value) => !value)} aria-label={showAllHistory ? '收起' : '展开更多'}><i className={'expand-arrow ' + (showAllHistory ? 'up' : 'down')} /></button></div>}
      </div>

      {/* ── 研报库（来源选择 / 浏览） ── */}
      <section className="computer-table-wrap" style={{ marginTop: 14, overflow: 'visible' }}>
        <div style={{ padding: 13 }}>
          <div className="computer-list-head" style={{ margin: '0 0 10px', padding: 0 }}>
            <div><strong>研报库</strong><span>· {libraryTotal} 份研报</span></div>
            <button type="button" className="computer-button" onClick={() => navigate('/computer/reports/library')}>查看全部</button>
          </div>

          <div className="report-library-filters">
            <WorkflowDateRangePicker start={libraryFilters.dateStart} end={libraryFilters.dateEnd} label="发布日期" onChange={handlePublishDateChange} />
            <input value={libraryFilters.keyword} onChange={(e) => handleLibraryFilter('keyword', e.target.value)} placeholder="搜索研报、机构、正文或 AI 观点" />
            <select value={libraryFilters.institution} onChange={(e) => handleLibraryFilter('institution', e.target.value)}><option value="">全部机构</option>{libraryOptions.institutions.map((item) => <option key={item}>{item}</option>)}</select>
            <select value={libraryFilters.industry} onChange={(e) => handleLibraryFilter('industry', e.target.value)}><option value="">全部行业</option>{libraryOptions.industries.map((item) => <option key={item}>{item}</option>)}</select>
            <select value={libraryFilters.market_view} onChange={(e) => handleLibraryFilter('market_view', e.target.value)}><option value="">全部观点</option><option value="bullish">看多</option><option value="bearish">看空</option><option value="neutral">中性</option></select>
          </div>

          <div className="report-source-list">
            {loadingLibrary ? (
              <div className="report-empty">正在读取研报库…</div>
            ) : sourceError ? (
              <div className="report-empty error">{sourceError}<button type="button" onClick={() => void loadLibrary()}>重试</button></div>
            ) : library.length === 0 ? (
              <div className="report-empty">当前条件下没有研报，请调整筛选或上传 PDF。</div>
            ) : (
              library.map((item) => {
                const status = STATUS_ICON[item.status] || { label: item.status, css: 'waiting' }
                return (
                  <button
                    type="button"
                    className="report-source-card"
                    key={item.id}
                    onClick={() => navigate(`/computer/reports/library?reportId=${item.id}`)}
                  >
                    <span>
                      <strong>{item.title}</strong>
                      <small>{item.institution || '未知机构'} · {item.publish_date || '日期未知'} · {item.industry || item.report_type || '未分类'}</small>
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span className={`computer-badge ${status.css === 'done' ? 'file' : status.css === 'running' ? 'running' : status.css === 'failed' ? 'failed' : ''}`} style={{ fontSize: 10 }}>
                        {status.label}
                      </span>
                      {item.ai_market_view && (
                        <em className="report-source-view-em" data-view={item.ai_market_view}>
                          {VIEW_LABEL[item.ai_market_view] || item.ai_market_view}
                          {item.ai_view_strength != null && <>{Math.round(item.ai_view_strength * 100)}%</>}
                        </em>
                      )}
                    </div>
                  </button>
                )
              })
            )}
          </div>

          {totalPages > 1 && (
            <div className="report-library-pagination">
              <button className="computer-button" disabled={libraryPage <= 1} onClick={() => setLibraryPage((p) => p - 1)}>上一页</button>
              <span>{libraryPage} / {totalPages}</span>
              <button className="computer-button" disabled={libraryPage >= totalPages} onClick={() => setLibraryPage((p) => p + 1)}>下一页</button>
            </div>
          )}
        </div>
      </section>

      {/* ── 新建综合研报（唯一创建入口，替代旧底部 composer） ── */}
      <ReportCreateModal
        open={createOpen}
        items={library}
        loading={loadingLibrary}
        dateStart={libraryFilters.dateStart}
        dateEnd={libraryFilters.dateEnd}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false)
          void loadTasks(true)
        }}
      />

      <ResearchUploadModal
        variant="computer"
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSubmitted={() => {
          setUploadOpen(false)
          void loadLibrary()
          void loadStats()
        }}
      />
    </section>
  )
}
