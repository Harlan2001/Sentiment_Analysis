import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ResearchListItem, getResearchList } from '@/api/reportGeneration'
import { ComputerDateRangePicker } from './components/ComputerDateRangePicker'
import { ReportSourceDetailPanel } from './ReportSourceDetailPanel'

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
  const [filters, setFilters] = useState({ institution: '', industry: '', market_view: '', keyword: '', dateStart: '', dateEnd: '' })
  const [options, setOptions] = useState<{ institutions: string[]; industries: string[] }>({ institutions: [], industries: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  useEffect(() => {
    const reportId = Number(searchParams.get('reportId'))
    setSelectedId(Number.isInteger(reportId) && reportId > 0 ? reportId : null)
  }, [searchParams])
  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getResearchList({ page, page_size: PAGE_SIZE, institution: filters.institution || undefined, industry: filters.industry || undefined, market_view: filters.market_view || undefined, keyword: filters.keyword || undefined, status: 'analyzed' })
      setItems(data.items); setTotal(data.total); setOptions(data.filters); setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : '读取研报库失败') }
    finally { setLoading(false) }
  }, [filters, page])
  useEffect(() => { void load() }, [load])
  function update(key: keyof typeof filters, value: string) { setFilters((current) => ({ ...current, [key]: value })); setPage(1) }
  const pages = Math.ceil(total / PAGE_SIZE)
  return <section className="computer-page report-library-page">
    <div className="computer-tabs"><button onClick={() => navigate('/computer/reports')}>← 返回研报分析</button><span className="computer-spacer" /><button className="computer-button" onClick={() => void load()}>刷新</button></div>
    <section className="computer-table-wrap report-library-page-wrap" style={{ overflow: 'visible' }}><div style={{ padding: 13 }}>
    <div className="computer-list-head" style={{ margin: '0 0 10px', padding: 0 }}><div><strong>研报库</strong><span>· {total} 份已完成 AI 分析的研报</span></div></div>
    <div className="report-library-filters">
      <ComputerDateRangePicker start={filters.dateStart} end={filters.dateEnd} label="发布日期" onChange={(dateStart, dateEnd) => { setFilters((current) => ({ ...current, dateStart, dateEnd })); setPage(1) }} />
      <input value={filters.keyword} onChange={(event) => update('keyword', event.target.value)} placeholder="搜索标题或摘要" />
      <select value={filters.institution} onChange={(event) => update('institution', event.target.value)}><option value="">全部机构</option>{options.institutions.map((item) => <option key={item}>{item}</option>)}</select>
      <select value={filters.industry} onChange={(event) => update('industry', event.target.value)}><option value="">全部行业</option>{options.industries.map((item) => <option key={item}>{item}</option>)}</select>
      <select value={filters.market_view} onChange={(event) => update('market_view', event.target.value)}><option value="">全部观点</option><option value="bullish">看多</option><option value="bearish">看空</option><option value="neutral">中性</option></select>
    </div>
    <div className="report-source-list report-library-results">
      {loading ? <div className="report-empty">正在读取研报库…</div> : error ? <div className="report-empty error">{error}<button onClick={() => void load()}>重试</button></div> : items.length === 0 ? <div className="report-empty">暂无已上传的研报。</div> : items.map((item) => {
        const status = STATUS[item.status] || { label: item.status, tone: 'waiting' }
        return <button type="button" className="report-source-card" key={item.id} onClick={() => setSelectedId(item.id)}><span><strong>{item.title}</strong><small>{item.institution || '未知机构'} · {item.publish_date || '日期未知'} · {item.industry || item.report_type || '未分类'}</small></span><div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span className={`computer-badge ${status.tone}`}>{status.label}</span>{item.ai_market_view && <em className="report-source-view-em" data-view={item.ai_market_view}>{VIEW[item.ai_market_view] || item.ai_market_view}{item.ai_view_strength != null && ` ${Math.round(item.ai_view_strength * 100)}%`}</em>}</div></button>
      })}
    </div>
    {pages > 1 && <div className="report-library-pagination"><button className="computer-button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>上一页</button><span>{page} / {pages}</span><button className="computer-button" disabled={page >= pages} onClick={() => setPage((current) => current + 1)}>下一页</button></div>}
    </div></section>
    {selectedId && <ReportSourceDetailPanel reportId={selectedId} onClose={() => setSelectedId(null)} />}
  </section>
}
