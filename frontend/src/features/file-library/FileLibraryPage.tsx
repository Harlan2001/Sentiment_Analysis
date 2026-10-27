import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authHeaders } from '@/api/client'
import { fetchFileLibrary } from '@/api/fileLibrary'
import type { FileLibraryItem, FileLibraryResponse } from '@/api/fileLibrary'
import './file-library.css'

const PAGE_SIZE = 50
const FORMAT_COLORS = ['#ff9f43', '#f15b63', '#7c8dff', '#4bc9b2', '#bd86ff', '#f2d45c']

function formatDate(value: string | null): string {
  if (!value) return '时间未知'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value.slice(0, 10)
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(parsed)
}

function formatSize(size: number | null): string {
  if (size == null || size <= 0) return '—'
  if (size < 1024) return String(size) + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
  return (size / (1024 * 1024)).toFixed(1) + ' MB'
}

function fileGlyph(format: string): string {
  if (format === 'PDF') return 'PDF'
  if (format === 'DOC' || format === 'DOCX') return 'W'
  if (format === 'XLS' || format === 'XLSX' || format === 'CSV') return 'X'
  if (['PNG', 'JPG', 'JPEG', 'WEBP', 'SVG'].includes(format)) return '图'
  if (format === 'MD' || format === 'TXT') return '文'
  return format.slice(0, 3) || '文'
}

async function downloadFile(item: FileLibraryItem): Promise<void> {
  if (!item.download_url) return
  const response = await fetch(item.download_url, { headers: authHeaders() })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(payload?.detail || '文件下载失败')
  }
  const blobUrl = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = blobUrl
  anchor.download = item.name
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
}

export function FileLibraryPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<FileLibraryResponse | null>(null)
  const [filters, setFilters] = useState({ source: '', format: '', date_start: '', date_end: '' })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await fetchFileLibrary({ ...filters, page, page_size: PAGE_SIZE })
      setData(result)
      setError('')
    } catch (reason) {
      setData(null)
      const message = reason instanceof Error ? reason.message : '读取文件库失败'
      setError(message === 'Not Found'
        ? '当前后端服务尚未加载文件库接口，请重启后端服务后重试。'
        : message)
    } finally {
      setLoading(false)
    }
  }, [filters, page])

  useEffect(() => { void load() }, [load])

  function updateFilter(key: keyof typeof filters, value: string) {
    setFilters((current) => ({ ...current, [key]: value }))
    setPage(1)
  }

  function clearFilters() {
    setFilters({ source: '', format: '', date_start: '', date_end: '' })
    setPage(1)
  }

  async function handleDownload(item: FileLibraryItem) {
    setDownloading(item.id)
    setError('')
    try {
      await downloadFile(item)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '文件下载失败')
    } finally {
      setDownloading(null)
    }
  }

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const hasFilters = Boolean(filters.source || filters.format || filters.date_start || filters.date_end)
  const summary = data?.summary ?? { total: 0, uploaded: 0, generated: 0, formats: [] }
  const visibleFormats = summary.formats.slice(0, 5)
  const otherCount = summary.formats.slice(5).reduce((count, item) => count + item.count, 0)
  const chartFormats = otherCount > 0
    ? [...visibleFormats, { format: '其他', count: otherCount }]
    : visibleFormats
  let chartOffset = 0
  const chartStops = chartFormats.map((item, index) => {
    const start = chartOffset
    chartOffset += summary.total > 0 ? item.count / summary.total * 100 : 0
    return `${FORMAT_COLORS[index % FORMAT_COLORS.length]} ${start}% ${chartOffset}%`
  })
  const chartStyle = {
    background: summary.total > 0
      ? `conic-gradient(${chartStops.join(', ')})`
      : 'conic-gradient(#303036 0% 100%)',
  }

  return (
    <section className="file-library-page">
      <header className="file-library-heading">
        <button className="file-library-refresh" type="button" onClick={() => void load()} disabled={loading}>
          {loading ? '读取中…' : '刷新'}
        </button>
      </header>

      <section className="file-library-overview" aria-label="文件总览">
        <div className="file-library-overview-total">
          <span>文件总览</span>
          <strong>{data ? summary.total : '—'}</strong>
          <small>当前账号的全部文件</small>
        </div>
        <div className="file-library-overview-stats">
          <div className="file-library-stat-upload"><i /> <span>用户上传</span><strong>{data ? summary.uploaded : '—'}</strong></div>
          <div className="file-library-stat-generated"><i /> <span>产品生成</span><strong>{data ? summary.generated : '—'}</strong></div>
        </div>
        <div className="file-library-overview-chart" aria-label="按格式统计文件数量">
          <div className="file-library-donut" style={chartStyle}>
            <div><strong>{data ? summary.formats.length : '—'}</strong><span>{data ? '种格式' : '待读取'}</span></div>
          </div>
          <div className="file-library-format-legend">
            {chartFormats.length > 0 ? chartFormats.map((item, index) => (
              <div key={item.format}>
                <i style={{ backgroundColor: FORMAT_COLORS[index % FORMAT_COLORS.length] }} />
                <span style={{ color: FORMAT_COLORS[index % FORMAT_COLORS.length] }}>{item.format}</span>
                <strong style={{ color: FORMAT_COLORS[index % FORMAT_COLORS.length] }}>{item.count}</strong>
              </div>
            )) : <span className="file-library-chart-empty">{data ? '暂无格式数据' : '统计数据暂不可用'}</span>}
          </div>
        </div>
      </section>

      <section className="file-library-filter-panel" aria-label="文件筛选">
        <label>
          <span>来源</span>
          <select value={filters.source} onChange={(event) => updateFilter('source', event.target.value)}>
            <option value="">全部来源</option>
            {(data?.sources ?? []).map((source) => <option key={source} value={source}>{source}</option>)}
          </select>
        </label>
        <label>
          <span>格式</span>
          <select value={filters.format} onChange={(event) => updateFilter('format', event.target.value)}>
            <option value="">全部格式</option>
            {(data?.formats ?? []).map((format) => <option key={format} value={format}>{format}</option>)}
          </select>
        </label>
        <label>
          <span>开始日期</span>
          <input type="date" value={filters.date_start} onChange={(event) => updateFilter('date_start', event.target.value)} />
        </label>
        <label>
          <span>结束日期</span>
          <input type="date" value={filters.date_end} onChange={(event) => updateFilter('date_end', event.target.value)} />
        </label>
        <button type="button" className="file-library-clear" onClick={clearFilters} disabled={!hasFilters}>
          清除筛选
        </button>
      </section>

      <div className="file-library-list-heading">
        <strong>全部文件</strong>
        <span>{loading ? '正在读取…' : String(total) + ' 个文件 · 按时间倒序'}</span>
      </div>

      {error && data && <div className="file-library-error" role="alert">{error}<button type="button" onClick={() => void load()}>重新读取</button></div>}
      <section className="file-library-list" aria-label="文件列表">
        {loading ? (
          <div className="file-library-state">正在读取文件库…</div>
        ) : error && !data ? (
          <div className="file-library-state">
            <strong>文件库暂时无法读取</strong>
            <p>{error}</p>
            <button type="button" onClick={() => void load()}>重试</button>
          </div>
        ) : items.length === 0 ? (
          <div className="file-library-state">
            <span className="file-library-empty-icon">▤</span>
            <strong>{hasFilters ? '没有符合条件的文件' : '还没有文件'}</strong>
            <p>{hasFilters ? '试试调整筛选条件。' : '你上传或生成的文件会汇总显示在这里。'}</p>
            {hasFilters && <button type="button" onClick={clearFilters}>清除筛选</button>}
          </div>
        ) : items.map((item: FileLibraryItem) => (
          <article className="file-library-row" key={item.id}>
            <span className={'file-library-glyph file-library-glyph-' + item.format.toLowerCase()}>{fileGlyph(item.format)}</span>
            <div className="file-library-main">
              <strong title={item.name}>{item.name}</strong>
              <div className="file-library-meta">
                <span>{item.source}</span><i>·</i><span>{item.kind === 'upload' ? '上传' : '生成'}</span>
                <i>·</i><time dateTime={item.created_at ?? undefined}>{formatDate(item.created_at)}</time>
                <i>·</i><span>{formatSize(item.size_bytes)}</span>
              </div>
            </div>
            <span className="file-library-format">{item.format}</span>
            <div className="file-library-actions">
              {item.open_url
                ? <button type="button" onClick={() => navigate(item.open_url!)}>查看来源</button>
                : <span aria-hidden="true" />}
              {item.download_url
                ? (
                  <button type="button" className="primary" onClick={() => void handleDownload(item)} disabled={downloading === item.id}>
                    {downloading === item.id ? '下载中…' : '下载'}
                  </button>
                )
                : <span aria-hidden="true" />}
            </div>
          </article>
        ))}
      </section>

      {pages > 1 && !loading && (
        <nav className="file-library-pagination" aria-label="文件列表分页">
          <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1}>上一页</button>
          <span>{page} / {pages}</span>
          <button type="button" onClick={() => setPage((current) => Math.min(pages, current + 1))} disabled={page >= pages}>下一页</button>
        </nav>
      )}
    </section>
  )
}
