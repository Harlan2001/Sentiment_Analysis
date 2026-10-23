import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ResearchListItem,
  batchReanalyzeReports,
  getResearchList,
  reanalyzeReport,
} from '@/api/reportGeneration'
import { WorkflowDateRangePicker } from '../components/WorkflowDateRangePicker'
import { ReportSourceDetailPanel } from '../components/ReportSourceDetailPanel'

const STATUS: Record<string, { label: string; tone: string }> = {
  parsed: { label: '已解析', tone: 'waiting' }, processing: { label: '分析中', tone: 'running' },
  analyzed: { label: '已分析', tone: 'file' }, failed: { label: '失败', tone: 'failed' },
}
const VIEW: Record<string, string> = { bullish: '看多', bearish: '看空', neutral: '中性' }
const PAGE_SIZE = 6

export function ReportLibraryPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [items, setItems] = useState<ResearchListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ institution: '', industry: '', market_view: '', status: '', keyword: '', dateStart: '', dateEnd: '' })
  // P2-12：关键词输入防抖，避免每次击键都打接口
  const [debouncedKeyword, setDebouncedKeyword] = useState('')
  const [options, setOptions] = useState<{ institutions: string[]; industries: string[] }>({ institutions: [], industries: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryingId, setRetryingId] = useState<number | null>(null)
  const [batchMessage, setBatchMessage] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  useEffect(() => {
    const reportId = Number(searchParams.get('reportId'))
    setSelectedId(Number.isInteger(reportId) && reportId > 0 ? reportId : null)
  }, [searchParams])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedKeyword(filters.keyword.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [filters.keyword])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getResearchList({
        page,
        page_size: PAGE_SIZE,
        institution: filters.institution || undefined,
        industry: filters.industry || undefined,
        market_view: filters.market_view || undefined,
        status: filters.status || undefined,
        keyword: debouncedKeyword || undefined,
        date_start: filters.dateStart || undefined,
        date_end: filters.dateEnd || undefined,
      })
      setItems(data.items); setTotal(data.total); setOptions(data.filters); setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : '读取研报库失败') }
    finally { setLoading(false) }
    // 仅在防抖后的关键词变化时请求
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.institution, filters.industry, filters.market_view, filters.status, filters.dateStart, filters.dateEnd, debouncedKeyword, page])
  useEffect(() => { void load() }, [load])

  function update(key: keyof typeof filters, value: string) { setFilters((current) => ({ ...current, [key]: value })); setPage(1) }

  async function handleReanalyze(reportId: number) {
    setRetryingId(reportId)
    try {
      await reanalyzeReport(reportId)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '重新分析触发失败')
    } finally {
      setRetryingId(null)
    }
  }

  async function handleBatchReanalyze() {
    setBatchMessage('')
    try {
      const result = await batchReanalyzeReports({
        institution: filters.institution || undefined,
        industry: filters.industry || undefined,
        market_view: filters.market_view || undefined,
        keyword: debouncedKeyword || undefined,
        date_start: filters.dateStart || undefined,
        date_end: filters.dateEnd || undefined,
      })
      setBatchMessage(`已提交 ${result.triggered} 份重新分析${result.skipped ? `，跳过 ${result.skipped} 份` : ''}`)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '批量重跑失败')
    }
  }

  const pages = Math.ceil(total / PAGE_SIZE)
  return <section className="computer-page report-library-page">
    <div className="computer-tabs"><button onClick={() => navigate('/computer/reports')}>← 返回研报分析</button><span className="computer-spacer" /><button className="computer-button" onClick={() => void load()}>刷新</button></div>
    <section className="computer-table-wrap report-library-page-wrap" style={{ overflow: 'visible' }}><div style={{ padding: 13 }}>
    <div className="computer-list-head" style={{ margin: '0 0 10px', padding: 0 }}><div><strong>研报库</strong><span>· {total} 份研报</span></div><button className="computer-button" title="按当前筛选条件批量重新分析已分析研报" onClick={() => void handleBatchReanalyze()}>按筛选批量重跑</button></div>
    {batchMessage && <div className="report-library-batch-message">{batchMessage}</div>}
    <div className="report-library-filters">
      <WorkflowDateRangePicker start={filters.dateStart} end={filters.dateEnd} label="发布日期" onChange={(dateStart, dateEnd) => { setFilters((current) => ({ ...current, dateStart, dateEnd })); setPage(1) }} />
      <input value={filters.keyword} onChange={(event) => update('keyword', event.target.value)} placeholder="搜索标题、机构、正文或 AI 观点" />
      <select value={filters.status} onChange={(event) => update('status', event.target.value)}><option value="">全部状态</option><option value="analyzed">已分析</option><option value="parsed">已解析待分析</option><option value="processing">分析中</option><option value="failed">分析失败</option></select>
      <select value={filters.institution} onChange={(event) => update('institution', event.target.value)}><option value="">全部机构</option>{options.institutions.map((item) => <option key={item}>{item}</option>)}</select>
      <select value={filters.industry} onChange={(event) => update('industry', event.target.value)}><option value="">全部行业</option>{options.industries.map((item) => <option key={item}>{item}</option>)}</select>
      <select value={filters.market_view} onChange={(event) => update('market_view', event.target.value)}><option value="">全部观点</option><option value="bullish">看多</option><option value="bearish">看空</option><option value="neutral">中性</option></select>
    </div>
    <div className="report-source-list report-library-results">
      {loading ? <div className="report-empty">正在读取研报库…</div> : error ? <div className="report-empty error">{error}<button onClick={() => void load()}>重试</button></div> : items.length === 0 ? <div className="report-empty">暂无符合条件的研报。</div> : items.map((item) => {
        const status = STATUS[item.status] || { label: item.status, tone: 'waiting' }
        return <div role="button" tabIndex={0} aria-label={`查看研报：${item.title}`} className="report-source-card" key={item.id} onClick={() => setSelectedId(item.id)} onKeyDown={(event) => { if (event.key === 'Enter') setSelectedId(item.id) }}><span><strong>{item.title}</strong><small>{item.institution || '未知机构'} · {item.publish_date || '日期未知'} · {item.industry || item.report_type || '未分类'}</small></span><div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span className={`computer-badge ${status.tone}`}>{status.label}</span>{item.ai_market_view && <em className="report-source-view-em" data-view={item.ai_market_view}>{VIEW[item.ai_market_view] || item.ai_market_view}{item.ai_view_strength != null && ` ${Math.round(item.ai_view_strength * 100)}%`}</em>}
          {item.status === 'failed' && (
            <button
              type="button"
              className="computer-button report-card-retry"
              disabled={retryingId === item.id}
              onClick={(event) => { event.stopPropagation(); void handleReanalyze(item.id) }}
            >{retryingId === item.id ? '提交中…' : '重新分析'}</button>
          )}
        </div></div>
      })}
    </div>
    {pages > 1 && <div className="report-library-pagination"><button className="computer-button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>上一页</button><span>{page} / {pages}</span><button className="computer-button" disabled={page >= pages} onClick={() => setPage((current) => current + 1)}>下一页</button></div>}
    </div></section>
    {selectedId && <ReportSourceDetailPanel reportId={selectedId} onClose={() => setSelectedId(null)} />}
  </section>
}
