/**
 * AI 策略详情 — 新闻信号/市场判断/标的选择/策略匹配 分块展示
 */
import React, { useEffect, useState } from 'react'
import { Loading } from '@/components/UI'
import { API_PREFIX, authHeaders } from '@/api/client'

interface Props { onClose: () => void }
function clean(s: any): string { if (!s) return ''; return String(s).replace(/[\ud800-\udfff]/g, '?') }

const SECTION_LABELS = ['新闻信号', '市场判断', '标的选择', '策略匹配']
const SECTION_KEYS = ['新闻信号', '市场判断', '标的选择', '策略匹配']
const SECTION_COLORS = ['#f59e0b', '#d97706', '#22c55e', '#e5e7eb'] as const

function parseReason(text: string): string[] {
  const parts: string[] = ['', '', '', '']
  if (!text) return parts
  const src = String(text)
  for (let i = 0; i < SECTION_KEYS.length; i++) {
    const kw = SECTION_KEYS[i]
    const idx = src.indexOf(kw)
    if (idx >= 0) {
      let end = src.length
      for (let j = i + 1; j < SECTION_KEYS.length; j++) {
        const nextIdx = src.indexOf(SECTION_KEYS[j], idx + kw.length)
        if (nextIdx >= 0 && nextIdx < end) end = nextIdx
      }
      parts[i] = clean(src.substring(idx + kw.length, end).replace(/^[：:\s]+/, '').replace(/[；;]\s*$/, '').trim())
    }
  }
  if (parts.every(p => !p)) parts[0] = clean(text)
  return parts
}

const StrategyDetailPanel: React.FC<Props> = ({ onClose }) => {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(false)

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', h); return () => document.removeEventListener('keydown', h)
  }, [onClose])

  useEffect(() => {
    let c = false
    fetch(`${API_PREFIX}/ai-strategy-recommendation/latest`, { headers: authHeaders() })
      .then(r => { if (!r.ok) throw Error(); return r.json() })
      .then(raw => { if (!c) { setData((raw?.data) || raw || {}); setLoading(false) } })
      .catch(() => { if (!c) { setErr(true); setLoading(false) } })
    return () => { c = true }
  }, [])

  const close = () => { try { onClose() } catch(e) {} }

  if (loading) return <div className="absolute inset-0 z-30 bg-[#0d0d0d] flex items-center justify-center"><Loading text="加载中..." /></div>
  if (err || !data) return <div className="absolute inset-0 z-30 bg-[#0d0d0d] flex flex-col items-center justify-center gap-3"><span className="text-[#6b7280] text-base">策略数据不可用</span><button onClick={close} className="px-4 py-2 rounded-lg border border-[#2a2a2a] text-[#6b7280] text-sm hover:text-white hover:bg-[#1a1a1a]">关闭</button></div>

  const outcome = data.outcome || {}
  const rawRecs: any[] = Array.isArray(outcome.recommendations) ? outcome.recommendations : []
  const notRec: string[] = []
  for (const item of (Array.isArray(outcome.not_recommended) ? outcome.not_recommended : [])) {
    notRec.push(clean(typeof item === 'object' ? (item.target_name || item.target_code || item.reason || '') : String(item)))
  }

  const recs = rawRecs.map((rec: any) => {
    const s = rec.strategy || {}, t = rec.target || {}
    const name = clean((typeof s === 'object' ? s.name : '') || (typeof t === 'object' ? t.name : '') || clean(rec.reason || '').slice(0, 40) || '推荐策略')
    const p = rec.priority || 1
    const conf = Math.max(0.3, Math.round((1.0 - (p - 1) * 0.2) * 100) / 100)
    const reasonParts = parseReason(clean(rec.reason || ''))
    return { name, confidence: conf, reasonParts, alloc: rec.allocation_ratio || '', hold: clean(rec.expected_holding_period || ''), risk: clean(rec.risk_level || '') }
  })

  const cc = (v: number) => v >= 0.7 ? 'text-[#22c55e]' : v >= 0.5 ? 'text-[#f59e0b]' : 'text-[#ef4444]'
  const hasContent = (o: any) => o && String(o).length > 2

  return (
    <div className="absolute inset-0 z-30 bg-[#0d0d0d] overflow-y-auto">
      <div className="sticky top-0 z-10 flex items-center px-4 py-2 bg-[#0d0d0d]/95 backdrop-blur-sm border-b border-[#1f1f1f]">
        <button onClick={close} className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm text-[#6b7280] hover:text-white hover:bg-[#1a1a1a]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 12H5m0 0l7 7m-7-7l7-7"/></svg>返回</button>
      </div>
      <div className="mx-auto w-full px-4 md:px-6 pb-16" style={{ maxWidth: '1060px' }}>
        <div className="space-y-5 pt-5">
          <div>
            <span className="text-sm text-[#6b7280]">{clean(data.analysis_date)} · AI 每日策略</span>
            <h1 className="text-2xl font-bold text-white mt-1">AI 策略推荐</h1>
          </div>

          {/* 推荐策略 */}
          <div>
            <h2 className="text-base font-bold text-white mb-3 flex items-center gap-2">
              <span className="w-1.5 h-5 rounded-full bg-[#d97706] inline-block" />推荐策略
            </h2>
            {recs.length > 0 ? (
              <div className="space-y-3">
                {recs.map((rec, i) => (
                  <div key={i} className="rounded-xl bg-[#111111] border border-[#2a2a2a] overflow-hidden">
                    <div className="p-5 flex items-start gap-3">
                      <span className="text-sm text-[#6b7280] font-mono mt-0.5">#{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 flex-wrap">
                          <span className="text-lg font-bold text-white">{rec.name}</span>
                          <span className={`text-sm font-mono font-semibold ${cc(rec.confidence)}`}>
                            置信度 {(rec.confidence * 100).toFixed(0)}%
                          </span>
                          {rec.alloc ? <span className="text-sm text-[#6b7280]">配置 {rec.alloc}</span> : null}
                          {rec.hold ? <span className="text-sm text-[#6b7280]">持有 {rec.hold}</span> : null}
                        </div>
                      </div>
                    </div>
                    {rec.reasonParts.some((p: string) => p) && (
                      <div className="px-5 pb-5 grid grid-cols-1 md:grid-cols-2 gap-2">
                        {rec.reasonParts.map((part: string, pi: number) => part ? (
                          <div key={pi} className="rounded-lg bg-[#0a0a0a] border border-[#1f1f1f] p-4">
                            <div className="flex items-center gap-1.5 mb-2">
                              <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: SECTION_COLORS[pi] }} />
                              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: SECTION_COLORS[pi] }}>{SECTION_LABELS[pi]}</span>
                            </div>
                            <p className="text-sm text-[#b0b8c1] leading-relaxed">{part}</p>
                          </div>
                        ) : null)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : <div className="detail-card text-center text-[#6b7280] text-sm">暂无推荐策略</div>}
          </div>

          {/* 新闻驱动 */}
          {data.news_summary && (
            <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-5">
              <h2 className="text-base font-bold text-white mb-3 flex items-center gap-2">
                <span className="w-1.5 h-5 rounded-full bg-[#ec4899] inline-block" />新闻驱动分析
              </h2>
              <p className="text-sm text-[#b0b8c1] leading-relaxed whitespace-pre-line">{clean(data.news_summary)}</p>
            </div>
          )}

          {/* 市场概览 + 情绪摘要 双列 */}
          <div className="grid grid-cols-2 gap-4">
            {hasContent(outcome.market_overview) && (
              <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-5">
                <h2 className="text-base font-bold text-white mb-3 flex items-center gap-2">
                  <span className="w-1.5 h-5 rounded-full bg-[#f59e0b] inline-block" />市场概览
                </h2>
                <p className="text-sm text-[#b0b8c1] leading-relaxed whitespace-pre-line">{clean(outcome.market_overview)}</p>
              </div>
            )}
            {hasContent(outcome.sentiment_summary) && (
              <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-5">
                <h2 className="text-base font-bold text-white mb-3 flex items-center gap-2">
                  <span className="w-1.5 h-5 rounded-full bg-[#f59e0b] inline-block" />情绪摘要
                </h2>
                <p className="text-sm text-[#b0b8c1] leading-relaxed whitespace-pre-line">{clean(outcome.sentiment_summary)}</p>
              </div>
            )}
          </div>

          {/* 风险告警 */}
          {hasContent(outcome.risk_alert) && (
            <div className="rounded-xl p-5" style={{ borderColor: 'rgba(239,68,68,0.15)', background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.15)' }}>
              <h2 className="text-base font-bold text-[#ef4444] mb-3 flex items-center gap-2">
                <span className="w-1.5 h-5 rounded-full bg-[#ef4444] inline-block" />风险告警
              </h2>
              <p className="text-sm text-[#b0b8c1] leading-relaxed whitespace-pre-line">{clean(outcome.risk_alert)}</p>
            </div>
          )}

          {/* 不推荐 */}
          {notRec.length > 0 && (
            <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] p-5">
              <h2 className="text-base font-bold text-white mb-3 flex items-center gap-2">
                <span className="w-1.5 h-5 rounded-full bg-[#6b7280] inline-block" />不推荐标的
              </h2>
              <div className="flex flex-wrap gap-2">
                {notRec.map((item, i) => <span key={i} className="px-3 py-1.5 rounded-lg text-sm bg-[#0a0a0a] text-[#b0b8c1] border border-[#1f1f1f]">{item}</span>)}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StrategyDetailPanel
