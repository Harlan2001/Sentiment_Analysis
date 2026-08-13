import { useEffect, useState } from 'react'
import { API_PREFIX } from '../../constants'
import { storage } from '../../utils/helpers'

interface Evidence {
  text: string
  inference: string
}

interface SymbolItem {
  symbol: string
  direction?: string
}

interface ResearchDetail {
  id: number
  title: string
  institution: string | null
  analyst: string | null
  publish_date: string | null
  industry: string | null
  report_type: string | null
  page_count: number | null
  file_size_kb: number | null
  source: string | null
  ai_summary: string | null
  ai_key_points: unknown
  ai_symbols: unknown
  ai_market_view: string | null
  ai_view_strength: number | null
  ai_time_horizon: string | null
  ai_evidence: unknown
  ai_model: string | null
  ai_analyzed_at: string | null
  full_text: string
  status: string
}

const VIEW_LABEL: Record<string, string> = { bullish: '看多', bearish: '看空', neutral: '中性' }
const HORIZON_LABELS: Record<string, string> = { short: '短期(<1月)', medium: '中期(1-6月)', long: '长期(>6月)' }

function authHeaders(): Record<string, string> {
  const token = storage.get<string>('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function parseList(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string')
  if (typeof value !== 'string') return []
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : []
  } catch { return [] }
}

function parseSymbols(value: unknown): SymbolItem[] {
  if (Array.isArray(value)) return value.filter((item): item is SymbolItem => typeof item === 'object' && item !== null && 'symbol' in item)
  if (typeof value !== 'string') return []
  try { const parsed = JSON.parse(value); return Array.isArray(parsed) ? parsed : [] } catch { return [] }
}

function parseEvidence(value: unknown): Evidence[] {
  if (Array.isArray(value)) return value.filter((item): item is Evidence => typeof item === 'object' && item !== null && 'text' in item && 'inference' in item)
  if (typeof value !== 'string') return []
  try { const parsed = JSON.parse(value); return Array.isArray(parsed) ? parsed : [] } catch { return [] }
}

export function ReportSourceDetailPanel({ reportId, onClose }: { reportId: number; onClose: () => void }) {
  const [detail, setDetail] = useState<ResearchDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setDetail(null)
    setError('')
    fetch(`${API_PREFIX}/research/${reportId}`, { headers: authHeaders(), signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => null)
          throw new Error(body?.detail || `读取来源研报失败 (${response.status})`)
        }
        return response.json() as Promise<ResearchDetail>
      })
      .then(setDetail)
      .catch((reason) => { if (reason.name !== 'AbortError') setError(reason instanceof Error ? reason.message : '读取来源研报失败') })
    return () => controller.abort()
  }, [reportId])

  const keyPoints = detail ? parseList(detail.ai_key_points) : []
  const symbols = detail ? parseSymbols(detail.ai_symbols) : []
  const evidence = detail ? parseEvidence(detail.ai_evidence) : []
  const excerpt = detail?.full_text?.split(/\n\n+/).filter((item) => item.trim().length > 20).slice(0, 5) ?? []

  const dirIcon = (d?: string) => d === 'bullish' ? '↑' : d === 'bearish' ? '↓' : '－'

  return <section className="report-source-detail" aria-live="polite">
    <div className="report-source-detail-head">
      <div>
        <span>来源研报详情</span>
        {detail && (
          <h3>{detail.title}</h3>
        )}
      </div>
      <button className="computer-button" onClick={onClose}>收起</button>
    </div>

    {!detail && !error && <div className="report-source-detail-state"><span className="report-spinner" />正在加载研报内容…</div>}
    {error && <div className="report-source-detail-state error">{error}</div>}

    {detail && <>
      {/* 元数据行 */}
      <div className="report-source-detail-meta">
        <span>{detail.institution || '未知机构'}</span>
        {detail.analyst && <span>{detail.analyst}</span>}
        <span>{detail.publish_date || '日期未知'}</span>
        <span>{detail.industry || detail.report_type || '未分类'}</span>
        {detail.page_count ? <span>{detail.page_count} 页</span> : null}
        {detail.file_size_kb ? <span>{Math.round(detail.file_size_kb)} KB</span> : null}
        {detail.source && <span>{detail.source}</span>}
        {detail.ai_model && <span>模型 {detail.ai_model}</span>}
        {detail.ai_analyzed_at && <span>分析于 {String(detail.ai_analyzed_at).slice(0, 10)}</span>}
      </div>

      {/* 市场观点 + 置信度 + 时间周期 */}
      {detail.ai_market_view && (
        <div className="report-source-detail-view">
          <span className={`report-source-view-badge ${detail.ai_market_view}`}>
            {VIEW_LABEL[detail.ai_market_view] || detail.ai_market_view}
            {detail.ai_view_strength != null && <em>{Math.round(detail.ai_view_strength * 100)}%</em>}
          </span>
          {detail.ai_time_horizon && (
            <span className="report-source-horizon">{HORIZON_LABELS[detail.ai_time_horizon] || detail.ai_time_horizon}</span>
          )}
        </div>
      )}

      {/* AI 摘要 */}
      {detail.ai_summary && (
        <div className="report-source-summary"><strong>AI 摘要</strong><p>{detail.ai_summary}</p></div>
      )}

      {/* 关键要点 */}
      {keyPoints.length > 0 && (
        <div className="report-source-points"><strong>关键要点</strong><ul>{keyPoints.map((point, index) => <li key={`${index}-${point}`}>{point}</li>)}</ul></div>
      )}

      {/* 标的 */}
      {symbols.length > 0 && (
        <div className="report-source-points">
          <strong>关联标的</strong>
          <div className="report-source-symbols">
            {symbols.map((item, i) => (
              <span key={i} className={`report-source-symbol ${item.direction || ''}`}>{dirIcon(item.direction)} {item.symbol}</span>
            ))}
          </div>
        </div>
      )}

      {/* AI 分析追溯 */}
      {evidence.length > 0 && (
        <div className="report-source-points">
          <strong>AI 分析追溯</strong>
          {evidence.map((ev, i) => (
            <div key={i} className="report-source-evidence-item">
              <p className="report-source-evidence-text">"{ev.text}"</p>
              <p className="report-source-evidence-inference">→ {ev.inference}</p>
            </div>
          ))}
        </div>
      )}

      {/* 原文摘录 */}
      {excerpt.length > 0 && (
        <div className="report-source-excerpt"><strong>原文摘录</strong>{excerpt.map((paragraph, index) => <p key={index}>{paragraph.trim()}</p>)}</div>
      )}

      {!detail.ai_summary && keyPoints.length === 0 && excerpt.length === 0 && (
        <div className="report-source-detail-state">该研报暂无可展示的分析内容。</div>
      )}
    </>}
  </section>
}