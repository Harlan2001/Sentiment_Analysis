/**
 * AI 策略详情 — 丰富内容版本：新闻信号/市场判断/标的选择/策略匹配 分块展示
 */
import React, { useEffect, useState } from 'react'
import { Loading } from '@/components/UI'
import { API_PREFIX } from '@/constants'

interface Props { onClose: () => void }
function clean(s: any): string { if (!s) return ''; return String(s).replace(/[\ud800-\udfff]/g, '?') }

const SECTION_LABELS = ['新闻信号', '市场判断', '标的选择', '策略匹配']
const SECTION_KEYS = ['新闻信号', '市场判断', '标的选择', '策略匹配']
const SECTION_COLORS = ['#3b82f6', '#f59e0b', '#22c55e', '#8b5cf6'] as const

// 解析 reason 文本为四个段落
function parseReason(text: string): string[] {
  const parts: string[] = ['', '', '', '']
  if (!text) return parts
  // 分割策略：按"新闻信号"、"市场判断"、"标的选择"、"策略匹配"关键字切分
  const src = String(text)
  for (let i = 0; i < SECTION_KEYS.length; i++) {
    const kw = SECTION_KEYS[i]
    const idx = src.indexOf(kw)
    if (idx >= 0) {
      // 找到下一个关键字的起始位置
      let end = src.length
      for (let j = i + 1; j < SECTION_KEYS.length; j++) {
        const nextIdx = src.indexOf(SECTION_KEYS[j], idx + kw.length)
        if (nextIdx >= 0 && nextIdx < end) end = nextIdx
      }
      parts[i] = clean(src.substring(idx + kw.length, end).replace(/^[：:\s]+/, '').replace(/[；;]\s*$/, '').trim())
    }
  }
  // 如果没有匹配到任何关键字，把全部文本放在第一段
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
    fetch(`${API_PREFIX}/ai-strategy-recommendation/latest`)
      .then(r => { if (!r.ok) throw Error(); return r.json() })
      .then(raw => { if (!c) { setData((raw?.data) || raw || {}); setLoading(false) } })
      .catch(() => { if (!c) { setErr(true); setLoading(false) } })
    return () => { c = true }
  }, [])

  const close = () => { try { onClose() } catch(e) {} }

  if (loading) return <div className="absolute inset-0 z-30 bg-[#0d0d0d] flex items-center justify-center"><Loading text="加载中..." /></div>
  if (err || !data) return <div className="absolute inset-0 z-30 bg-[#0d0d0d] flex flex-col items-center justify-center gap-3"><span className="text-[#6b7280] text-sm">策略数据不可用</span><button onClick={close} className="px-4 py-2 rounded-lg border border-[#2a2a2a] text-[#6b7280] text-[13px] hover:text-white hover:bg-[#1a1a1a]">关闭</button></div>

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
        <button onClick={close} className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[12px] text-[#6b7280] hover:text-white hover:bg-[#1a1a1a]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 12H5m0 0l7 7m-7-7l7-7"/></svg>返回</button>
      </div>
      <div className="mx-auto w-full px-4 md:px-6 pb-16" style={{ maxWidth: '740px' }}>
        <div className="space-y-4 pt-4">
          {/* Header */}
          <div>
            <span className="text-[11px] text-[#6b7280] tracking-wide uppercase">{clean(data.analysis_date)} · AI 每日策略</span>
            <h1 className="text-[1.6rem] font-semibold text-white mt-0.5">AI 策略推荐</h1>
          </div>

          {/* 推荐策略 */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-1 h-3.5 rounded-full bg-[#8b5cf6]" />
              <span className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wider">推荐策略</span>
            </div>
            {recs.length > 0 ? (
              <div className="space-y-3">
                {recs.map((rec, i) => (
                  <div key={i} className="detail-card">
                    <div className="p-4 pb-2 flex items-start gap-3">
                      <span className="text-[11px] text-[#6b7280] font-mono mt-0.5">#{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 flex-wrap">
                          <span className="text-[15px] font-semibold text-white">{rec.name}</span>
                          <span className={`text-[12px] font-mono font-medium ${cc(rec.confidence)}`}>
                            置信度 {(rec.confidence * 100).toFixed(0)}%
                          </span>
                          {rec.alloc ? <span className="text-[11px] text-[#6b7280]">配置 {rec.alloc}</span> : null}
                          {rec.hold ? <span className="text-[11px] text-[#6b7280]">持有 {rec.hold}</span> : null}
                        </div>
                      </div>
                    </div>
                    {/* 四个分块 */}
                    {rec.reasonParts.some((p: string) => p) && (
                      <div className="px-4 pb-4 grid grid-cols-1 md:grid-cols-2 gap-2">
                        {rec.reasonParts.map((part: string, pi: number) => part ? (
                          <div key={pi} className="rounded-md bg-[#0a0a0a] border border-[#1f1f1f] p-3">
                            <div className="flex items-center gap-1.5 mb-1.5">
                              <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: SECTION_COLORS[pi] }} />
                              <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: SECTION_COLORS[pi] }}>{SECTION_LABELS[pi]}</span>
                            </div>
                            <p className="text-[12px] text-[#8b949e] leading-relaxed">{part}</p>
                          </div>
                        ) : null)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : <div className="detail-card text-center text-[#6b7280] text-[12px]">暂无推荐策略</div>}
          </div>

          {/* 新闻驱动 */}
          {data.news_summary && (
            <div className="detail-card">
              <div className="flex items-center gap-2 mb-2"><div className="w-1 h-3.5 rounded-full bg-[#ec4899]" /><span className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wider">新闻驱动分析</span></div>
              <p className="text-[12px] text-[#8b949e] leading-relaxed whitespace-pre-line">{clean(data.news_summary)}</p>
            </div>
          )}

          {/* 市场概览 + 情绪摘要 双列 */}
          <div className="grid grid-cols-2 gap-3">
            {hasContent(outcome.market_overview) && (
              <div className="detail-card">
                <div className="flex items-center gap-2 mb-2"><div className="w-1 h-3.5 rounded-full bg-[#3b82f6]" /><span className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wider">市场概览</span></div>
                <p className="text-[12px] text-[#8b949e] leading-relaxed whitespace-pre-line">{clean(outcome.market_overview)}</p>
              </div>
            )}
            {hasContent(outcome.sentiment_summary) && (
              <div className="detail-card">
                <div className="flex items-center gap-2 mb-2"><div className="w-1 h-3.5 rounded-full bg-[#f59e0b]" /><span className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wider">情绪摘要</span></div>
                <p className="text-[12px] text-[#8b949e] leading-relaxed whitespace-pre-line">{clean(outcome.sentiment_summary)}</p>
              </div>
            )}
          </div>

          {/* 风险告警 */}
          {hasContent(outcome.risk_alert) && (
            <div className="detail-card" style={{ borderColor: 'rgba(239,68,68,0.15)', background: 'rgba(239,68,68,0.04)' }}>
              <div className="flex items-center gap-2 mb-2"><div className="w-1 h-3.5 rounded-full bg-[#ef4444]" /><span className="text-[11px] font-semibold text-[#ef4444] uppercase tracking-wider">风险告警</span></div>
              <p className="text-[12px] text-[#8b949e] leading-relaxed whitespace-pre-line">{clean(outcome.risk_alert)}</p>
            </div>
          )}

          {/* 不推荐 */}
          {notRec.length > 0 && (
            <div className="detail-card">
              <div className="flex items-center gap-2 mb-2"><div className="w-1 h-3.5 rounded-full bg-[#6b7280]" /><span className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wider">不推荐标的</span></div>
              <div className="flex flex-wrap gap-2">
                {notRec.map((item, i) => <span key={i} className="px-2.5 py-1 rounded-md text-[11px] bg-[#0a0a0a] text-[#8b949e] border border-[#1f1f1f]">{item}</span>)}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StrategyDetailPanel
