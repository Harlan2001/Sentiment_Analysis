import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ReportGenerationTask,
  ReportSource,
  ResearchListItem,
  ResearchSummary,
  createReportGenerationTask,
  getReportGenerationTasks,
  getReportSources,
  getResearchList,
  getResearchSummary,
  retryReportGenerationTask,
} from '../../api/reportGeneration'
import { ComputerDateRangePicker } from './components/ComputerDateRangePicker'
import { ComputerDatePicker } from './components/ComputerDatePicker'
import { ReportSourceDetailPanel } from './ReportSourceDetailPanel'
import ResearchUploadModal from '../../components/Pages/ResearchUploadModal'

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
  parsed: { label: '已解析', css: 'waiting' },
  processing: { label: '分析中', css: 'running' },
  analyzed: { label: '已分析', css: 'done' },
  failed: { label: '失败', css: 'failed' },
}

export function ReportGenerationPage() {
  const navigate = useNavigate()

  // ── 研报库状态 ──
  const [sources, setSources] = useState<ReportSource[]>([])
  const [library, setLibrary] = useState<ResearchListItem[]>([])
  const [libraryTotal, setLibraryTotal] = useState(0)
  const [libraryPage, setLibraryPage] = useState(1)
  const [libraryFilters, setLibraryFilters] = useState({ institution: '', industry: '', market_view: '', keyword: '' })
  const [libraryOptions, setLibraryOptions] = useState<{ institutions: string[]; industries: string[] }>({ institutions: [], industries: [] })
  const [summary, setSummary] = useState<ResearchSummary | null>(null)
  const [loadingLibrary, setLoadingLibrary] = useState(true)
  const [sourceError, setSourceError] = useState('')
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null)
  const PAGE_SIZE = 6

  // ── 合成任务 ──
  const [tasks, setTasks] = useState<ReportGenerationTask[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [historyDateStart, setHistoryDateStart] = useState('')
  const [historyDateEnd, setHistoryDateEnd] = useState('')
  const [loadingTasks, setLoadingTasks] = useState(true)
  const [taskError, setTaskError] = useState('')
  const [showAllHistory, setShowAllHistory] = useState(false)
  const [showAllActive, setShowAllActive] = useState(false)

  // ── Composer ──
  const [composerOpen, setComposerOpen] = useState(true)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [title, setTitle] = useState('')
  const [requirement, setRequirement] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [dateStart, setDateStart] = useState('')
  const [dateEnd, setDateEnd] = useState('')

  // ── Dropdown ──
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false)
  const statusDropdownRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    function outside(e: MouseEvent) {
      if (statusDropdownRef.current && !statusDropdownRef.current.contains(e.target as Node)) setStatusDropdownOpen(false)
    }
    if (statusDropdownOpen) document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [statusDropdownOpen])

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
      setTaskError(error instanceof Error ? error.message : '读取研报生成历史失败')
    } finally {
      if (!quiet) setLoadingTasks(false)
    }
  }, [historyDateEnd, historyDateStart, statusFilter])

  const loadSources = useCallback(async () => {
    try {
      const data = await getReportSources({
        keyword: libraryFilters.keyword || undefined,
        institution: libraryFilters.institution || undefined,
        industry: libraryFilters.industry || undefined,
        date_start: dateStart || undefined,
        date_end: dateEnd || undefined,
      })
      setSources(data.items)
      setSourceError('')
    } catch (error) {
      setSourceError(error instanceof Error ? error.message : '读取可用研报失败')
    }
  }, [dateEnd, dateStart, libraryFilters])

  const loadLibrary = useCallback(async () => {
    setLoadingLibrary(true)
    try {
      const data = await getResearchList({
        page: libraryPage,
        page_size: PAGE_SIZE,
        institution: libraryFilters.institution || undefined,
        industry: libraryFilters.industry || undefined,
        market_view: libraryFilters.market_view || undefined,
        keyword: libraryFilters.keyword || undefined,
      })
      setLibrary(data.items)
      setLibraryTotal(data.total)
      setLibraryOptions(data.filters)
      setSourceError('')
    } catch (error) {
      setSourceError(error instanceof Error ? error.message : '读取研报库失败')
    } finally {
      setLoadingLibrary(false)
    }
  }, [libraryFilters, libraryPage])

  const loadSummary = useCallback(async () => {
    try { setSummary(await getResearchSummary()) } catch { /* ignore */ }
  }, [])

  useEffect(() => { void loadTasks() }, [loadTasks])
  useEffect(() => { void loadSummary() }, [loadSummary])
  useEffect(() => { void loadLibrary() }, [loadLibrary])
  useEffect(() => { void loadSources() }, [loadSources])

  const hasActiveTask = tasks.some((task) => task.status === 'queued' || task.status === 'running')
  useEffect(() => {
    if (!hasActiveTask) return
    const timer = window.setInterval(() => void loadTasks(true), 4000)
    return () => window.clearInterval(timer)
  }, [hasActiveTask, loadTasks])

  // ── 操作 ──
  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!title.trim()) return setFormError('请输入报告标题')
    if (!requirement.trim()) return setFormError('请输入生成要求')
    if (selectedIds.length === 0) return setFormError('请至少选择一份已完成 AI 分析的研报')
    setSubmitting(true)
    setFormError('')
    try {
      const task = await createReportGenerationTask({
        title: title.trim(), requirement: requirement.trim(), report_ids: selectedIds,
        date_start: dateStart || undefined, date_end: dateEnd || undefined,
      })
      setTasks((current) => [task, ...current.filter((item) => item.id !== task.id)])
      setTitle('')
      setRequirement('')
      setSelectedIds([])
      setComposerOpen(false)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : '创建研报生成任务失败')
    } finally {
      setSubmitting(false)
    }
  }

  async function retry(taskId: string) {
    setTaskError('')
    try {
      const task = await retryReportGenerationTask(taskId)
      setTasks((current) => current.map((item) => item.id === task.id ? task : item))
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : '重试失败')
    }
  }

  function handleLibraryFilter(key: string, value: string) {
    setLibraryFilters((prev) => ({ ...prev, [key]: value }))
    setLibraryPage(1)
  }

  function toggleSelect(id: number) {
    setSelectedIds((current) => current.includes(id) ? current.filter((i) => i !== id) : current.length >= 12 ? current : [...current, id])
  }

  // ── 计算变量 ──
  const activeTasks = tasks.filter((task) => task.status === 'queued' || task.status === 'running')
  const historyTasks = tasks.filter((task) => task.status === 'completed' || task.status === 'failed')
  const visibleHistory = showAllHistory ? historyTasks : historyTasks.slice(0, 4)
  const displayActive = showAllActive ? activeTasks : activeTasks.slice(0, 2)
  const totalPages = Math.ceil(libraryTotal / PAGE_SIZE)
  const selectedSources = sources.filter((s) => selectedIds.includes(s.id))

  return (
    <section className="computer-page report-generation-page">
      {/* ── Tabs ── */}
      <div className="computer-tabs">
        <button onClick={() => navigate('/computer')}>全部</button>
        <button className="active">研报生成</button>
        <button onClick={() => navigate('/computer/strategies')}>策略开发</button>
        <button onClick={() => navigate('/computer/news')}>每日新闻总结</button>
        <span className="computer-spacer" />
        <button className="computer-button" onClick={() => { void loadTasks(); void loadLibrary(); void loadSummary() }}>刷新状态</button>
        <button className="computer-button primary" onClick={() => setComposerOpen(true)}>＋ 新建研报</button>
      </div>

      {/* ── Toolbar ── */}
      <div className="computer-toolbar">
        <div className="computer-dropdown" ref={statusDropdownRef}>
          <button className={'computer-chip dropdown-chip ' + (statusFilter ? 'selected' : '')} onClick={() => setStatusDropdownOpen((v) => !v)}>
            状态：{statusFilter ? {queued:'排队中',running:'正在生成',completed:'已完成',failed:'失败'}[statusFilter] : '全部'}<i className="inline-caret" aria-hidden="true" />
          </button>
          {statusDropdownOpen && (
            <div className="computer-dropdown-menu">
              {[{value:'',label:'全部'},{value:'queued',label:'排队中'},{value:'running',label:'正在生成'},{value:'completed',label:'已完成'},{value:'failed',label:'失败'}].map((opt) => (
                <button key={opt.value} className={statusFilter === opt.value ? 'active' : ''} onClick={() => { setStatusFilter(opt.value); setStatusDropdownOpen(false) }}>{opt.label}</button>
              ))}
            </div>
          )}
        </div>
        <ComputerDatePicker value={historyDateStart} label="任务日期" onChange={(value) => { setHistoryDateStart(value); setHistoryDateEnd(value) }} />
        <span className="computer-spacer" />
        <span className="computer-count">{loadingTasks ? '读取中…' : `${tasks.length} 个合成任务`}</span>
      </div>

      {/* ── 统计卡片 ── */}
      {summary && (
        <div className="report-stat-row">
          {[
            { label: '研报总数', value: summary.total },
            { label: '已分析', value: summary.analyzed, tone: 'done' },
            { label: '看多', value: summary.bullish, tone: 'bullish' },
            { label: '看空', value: summary.bearish, tone: 'bearish' },
            { label: '中性', value: summary.neutral, tone: 'neutral' },
            { label: '机构数', value: summary.institutions, tone: 'info' },
          ].map((s) => (
            <div key={s.label} className={`report-stat-chip ${s.tone || ''}`}>
              <small>{s.label}</small>
              <strong>{s.value}</strong>
            </div>
          ))}
        </div>
      )}

      {/* ── 研报库 ── */}
      <section className="computer-table-wrap" style={{marginBottom:14,overflow:'visible'}}>
        <div style={{padding:13}}>
        <div className="computer-list-head" style={{margin:'0 0 10px',padding:0}}>
          <div>
            <strong>研报库</strong>
            <span>· {libraryTotal} 份研报</span>
          </div>
          <button type="button" className="computer-button" onClick={() => setUploadOpen(true)}>＋ 上传 PDF</button>
        </div>

        {/* 库筛选 */}
        <div className="report-library-filters">
          <ComputerDateRangePicker start={dateStart} end={dateEnd} label="发布日期" onChange={(s, e) => { setDateStart(s); setDateEnd(e) }} />
          <input value={libraryFilters.keyword} onChange={(e) => handleLibraryFilter('keyword', e.target.value)} placeholder="搜索标题或摘要" />
          <select value={libraryFilters.institution} onChange={(e) => handleLibraryFilter('institution', e.target.value)}><option value="">全部机构</option>{libraryOptions.institutions.map((item) => <option key={item}>{item}</option>)}</select>
          <select value={libraryFilters.industry} onChange={(e) => handleLibraryFilter('industry', e.target.value)}><option value="">全部行业</option>{libraryOptions.industries.map((item) => <option key={item}>{item}</option>)}</select>
          <select value={libraryFilters.market_view} onChange={(e) => handleLibraryFilter('market_view', e.target.value)}><option value="">全部观点</option><option value="bullish">看多</option><option value="bearish">看空</option><option value="neutral">中性</option></select>
        </div>

        {/* 选中 chips (composer 开启时显示) */}
        {composerOpen && selectedSources.length > 0 && (
          <div className="report-source-chips" style={{marginBottom:10}}>
            {selectedSources.map((source) => (
              <button key={source.id} type="button" onClick={() => setSelectedIds((c) => c.filter((id) => id !== source.id))}>{source.title}<span>×</span></button>
            ))}
          </div>
        )}

        {/* 选择工具栏 (composer 开启时显示) */}
        {composerOpen && (
          <div className="report-source-toolbar" style={{marginBottom:8}}>
            <label><input type="checkbox" checked={library.length > 0 && library.every((item) => selectedIds.includes(item.id))} onChange={() => {
              const allSelected = library.every((item) => selectedIds.includes(item.id))
              if (allSelected) setSelectedIds([])
              else {
                const ids = library.slice(0, 12).map((item) => item.id)
                setSelectedIds(ids)
              }
            }} /> 全选当前页</label>
            <span>{selectedIds.length} / 12 已选择</span>
          </div>
        )}

        {/* 研报卡片列表 */}
        <div className="report-source-list">
          {loadingLibrary ? (
            <div className="report-empty">正在读取研报库…</div>
          ) : sourceError ? (
            <div className="report-empty error">{sourceError}<button type="button" onClick={() => void loadLibrary()}>重试</button></div>
          ) : library.length === 0 ? (
            <div className="report-empty">当前条件下没有研报，请调整筛选或上传 PDF 进行 AI 分析。</div>
          ) : (
            library.map((item) => {
              const status = STATUS_ICON[item.status] || { label: item.status, css: 'waiting' }
              const checked = selectedIds.includes(item.id)
              return (
                <label
                  className={`report-source-card ${checked ? 'selected' : ''}`}
                  key={item.id}
                  onClick={() => setSelectedSourceId(item.id)}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleSelect(item.id)}
                    onClick={(e) => e.stopPropagation()}
                    style={{ display: composerOpen ? undefined : 'none' }}
                  />
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.institution || '未知机构'} · {item.publish_date || '日期未知'} · {item.industry || item.report_type || '未分类'}</small>
                  </span>
                  <div style={{display:'flex',alignItems:'center',gap:6}}>
                    <span className={`computer-badge ${status.css === 'done' ? 'file' : status.css === 'running' ? 'running' : status.css === 'failed' ? 'failed' : ''}`} style={{fontSize:10}}>
                      {status.label}
                    </span>
                    {item.ai_market_view && (
                      <em className="report-source-view-em" data-view={item.ai_market_view}>
                        {VIEW_LABEL[item.ai_market_view] || item.ai_market_view}
                        {item.ai_view_strength != null && <>{Math.round(item.ai_view_strength * 100)}%</>}
                      </em>
                    )}
                  </div>
                </label>
              )
            })
          )}
        </div>

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="report-library-pagination">
            <button className="computer-button" disabled={libraryPage <= 1} onClick={() => setLibraryPage((p) => p - 1)}>上一页</button>
            <span>{libraryPage} / {totalPages}</span>
            <button className="computer-button" disabled={libraryPage >= totalPages} onClick={() => setLibraryPage((p) => p + 1)}>下一页</button>
          </div>
        )}
        </div>
      </section>

      {/* ── Attention ── */}
      <section className="computer-attention">
        <div className="computer-attention-head"><strong>需要处理 · {activeTasks.length}</strong><span>实时状态</span></div>
        {activeTasks.length === 0 ? (
          <div className="computer-attention-row"><span className="attention-dot" /><div><strong>当前没有生成中的研报</strong><small>创建任务后会在此显示排队或生成状态</small></div></div>
        ) : (
          <>
            {displayActive.map((task) => (
              <div className="computer-attention-row" key={task.id}>
                <span className="attention-dot running" />
                <div><strong>{task.title}</strong><small>{task.source_snapshot_json.length} 份来源 · {task.status === 'queued' ? '等待生成资源' : '模型正在综合，刷新后状态仍会保留'}</small></div>
                <span className="computer-spacer" /><span className="computer-badge running">{STATUS_LABEL[task.status]}</span>
                <span className="attention-action-cell"><button className="computer-button" onClick={() => navigate(`/computer/reports/${task.id}`)}>查看详情</button><time>{formatDateTime(task.updated_at)}</time></span>
              </div>
            ))}
            {activeTasks.length > 2 && (
              <div style={{textAlign:'center',padding:'4px 0 2px'}}>
                <button className="expand-toggle" onClick={() => setShowAllActive((v) => !v)} aria-label={showAllActive ? '收起' : '展开'}>
                  <i className={'expand-arrow ' + (showAllActive ? 'up' : 'down')} />
                </button>
              </div>
            )}
          </>
        )}
      </section>

      {/* ── History ── */}
      <div className="computer-list-head" style={{marginTop:18}}>
        <div><strong>历史生成</strong><span>· {historyTasks.length} 个任务</span></div>
      </div>
      <div className="computer-table-wrap">
        <table className="computer-table"><thead><tr><th /><th>报告</th><th>来源范围</th><th>状态</th><th>更新时间</th></tr></thead>
          <tbody>{loadingTasks ? <tr><td colSpan={5}><div className="report-empty">正在读取历史…</div></td></tr>
            : taskError ? <tr><td colSpan={5}><div className="report-empty error">{taskError}<button onClick={() => void loadTasks()}>重试</button></div></td></tr>
            : visibleHistory.length === 0 ? <tr><td colSpan={5}><div className="report-empty">暂无历史生成记录</div></td></tr>
            : visibleHistory.map((task) => <tr key={task.id} onClick={() => navigate(`/computer/reports/${task.id}`)} className="clickable-row">
                <td><span className={`computer-status ${task.status === 'completed' ? 'done' : 'failed'}`}>{task.status === 'completed' ? '✓' : '!'}</span></td>
                <td><strong>{task.title}</strong><small>{task.requirement}</small></td>
                <td>{task.source_snapshot_json.length} 份研报{task.date_start ? ` · ${task.date_start}${task.date_end ? ` 至 ${task.date_end}` : ''}` : ''}</td>
                <td><span className={`computer-badge ${task.status === 'completed' ? 'file' : 'failed'}`}>{STATUS_LABEL[task.status]}</span>{task.status === 'failed' && <button className="inline-retry" onClick={(event) => { event.stopPropagation(); void retry(task.id) }}>重试</button>}</td>
                <td><time>{formatDateTime(task.updated_at)}</time></td>
              </tr>)}</tbody>
        </table>
        {historyTasks.length > 4 && <div className="report-history-toggle"><button className="expand-toggle" onClick={() => setShowAllHistory((value) => !value)}><i className={'expand-arrow ' + (showAllHistory ? 'up' : 'down')} /></button></div>}
      </div>

      {/* ── Composer (sticky bottom) ── */}
      {composerOpen && (
        <form className="report-composer" onSubmit={createTask}>
          <textarea className="report-title-input" value={title} onChange={(event) => setTitle(event.target.value.replace(/[\r\n]+/g, ' '))} maxLength={255} rows={1} placeholder="报告标题，例如：8 月利率债市场观点综述" />
          <textarea value={requirement} onChange={(event) => setRequirement(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} maxLength={4000} rows={2} placeholder="描述分析重点、目标读者和希望比较的问题…" />
          <div className="report-task-submit">
            <span className="composer-status">已选 {selectedIds.length} 份来源 · 发送后将创建真实生成任务</span>
            <button className="report-send" disabled={submitting} type="submit" aria-label="开始生成研报" title="开始生成研报">{submitting ? '…' : '↑'}</button>
          </div>
          {formError && <p className="chat-error">{formError}</p>}
        </form>
      )}

      {/* ── Modals & Panels ── */}
      <ResearchUploadModal
        variant="computer"
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSubmitted={() => {
          setUploadOpen(false)
          void loadLibrary()
          void loadSummary()
        }}
      />
      {selectedSourceId && <ReportSourceDetailPanel reportId={selectedSourceId} onClose={() => setSelectedSourceId(null)} />}
    </section>
  )
}