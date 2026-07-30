import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle, Loading } from '../UI'
import { API_PREFIX } from '../../constants'
import { storage } from '../../utils/helpers'

function authHeaders(): Record<string, string> {
  const token = storage.get<string>('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const VIEW_COLORS: Record<string, string> = {
  bullish: 'text-red-400', bearish: 'text-green-400', neutral: 'text-gray-400',
}
const VIEW_BG: Record<string, string> = {
  bullish: 'bg-red-500/10 border-red-500/30', bearish: 'bg-green-500/10 border-green-500/30',
  neutral: 'bg-gray-500/10 border-gray-500/30',
}
const VIEW_LABEL: Record<string, string> = {
  bullish: '看多', bearish: '看空', neutral: '中性',
}
const HORIZON_LABELS: Record<string, string> = {
  short: '短期(<1月)', medium: '中期(1-6月)', long: '长期(>6月)',
}

interface Evidence {
  text: string
  inference: string
}

interface ResearchDetail {
  id: number; title: string; institution: string | null; analyst: string | null
  publish_date: string | null; industry: string | null; report_type: string | null
  page_count: number; file_size_kb: number; source: string | null; file_hash: string
  ai_summary: string | null; ai_key_points: any; ai_symbols: any; ai_industries: any
  ai_market_view: string | null; ai_view_strength: number | null
  ai_time_horizon: string | null; ai_evidence: any
  ai_model: string | null; ai_analyzed_at: string | null
  full_text: string; status: string
}

function parseJSON(v: any): any {
  if (!v) return null
  if (typeof v === 'object') return v
  try { return JSON.parse(v) } catch { return null }
}

export default function ResearchDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<ResearchDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`${API_PREFIX}/research/${id}`, { headers: authHeaders() })
      .then(r => r.json())
      .then(d => setDetail(d))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <Loading text="加载研报详情..." />
  if (!detail) return <div className="text-gray-400 text-center py-20">研报不存在</div>

  const symbols: any[] = parseJSON(detail.ai_symbols) || []
  const keyPoints: string[] = parseJSON(detail.ai_key_points) || []
  const industries: string[] = parseJSON(detail.ai_industries) || []
  const evidence: Evidence[] = parseJSON(detail.ai_evidence) || []

  // 原文摘要：API 返回的 display_text 已清洗，按段落展示
  const textExcerpt = detail.full_text || ''
  const paragraphs = textExcerpt
    .split(/\n\n+/)
    .filter((p: string) => p.trim().length > 10)

  return (
    <div className="space-y-5">
      <button
        onClick={() => navigate('/research')}
        className="text-sm text-gray-400 hover:text-white transition-colors inline-flex items-center gap-1"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        返回列表
      </button>

      {/* 标题栏 */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-white mb-2">{detail.title}</h1>
          <div className="flex flex-wrap items-center gap-2 text-xs text-gray-400">
            {detail.institution && (
              <span className="px-2 py-0.5 rounded bg-gray-700/60">{detail.institution}</span>
            )}
            {detail.analyst && <span>分析师: {detail.analyst}</span>}
            {detail.publish_date && <span>{detail.publish_date}</span>}
            {detail.page_count && <span>{detail.page_count}页</span>}
            {detail.report_type && (
              <span className="text-gray-500">{detail.report_type}</span>
            )}
          </div>
        </div>
        {detail.status !== 'analyzed' && (
          <span className="text-[10px] px-2 py-0.5 rounded bg-yellow-500/10 text-yellow-400 border border-yellow-500/30">
            {detail.status}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* 左侧主体 */}
        <div className="lg:col-span-2 space-y-5">

          {/* AI 分析主卡 */}
          <Card>
            <CardHeader>
              <CardTitle>AI 分析结果</CardTitle>
            </CardHeader>
            <CardContent>
              {/* 情感徽章 */}
              <div className="flex items-center gap-3 mb-5">
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border
                  ${VIEW_BG[detail.ai_market_view || 'neutral']}
                  ${VIEW_COLORS[detail.ai_market_view || 'neutral']}`}>
                  {VIEW_LABEL[detail.ai_market_view || 'neutral']}
                  {detail.ai_view_strength != null && (
                    <span className="ml-1.5 opacity-70">
                      {Math.round(detail.ai_view_strength * 100)}%
                    </span>
                  )}
                </span>
                {detail.ai_time_horizon && (
                  <span className="text-xs text-gray-500">
                    {HORIZON_LABELS[detail.ai_time_horizon] || detail.ai_time_horizon}
                  </span>
                )}
                {detail.ai_model && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-gray-700/50 text-gray-500 ml-auto">
                    {detail.ai_model}
                  </span>
                )}
              </div>

              {/* 核心摘要 */}
              {detail.ai_summary && (
                <div className="mb-5 p-4 rounded-lg bg-blue-500/5 border border-blue-500/10">
                  <h4 className="text-[11px] font-medium text-blue-400 uppercase tracking-wide mb-2">
                    核心摘要
                  </h4>
                  <p className="text-sm text-gray-300 leading-relaxed">{detail.ai_summary}</p>
                </div>
              )}

              {/* 关键要点 */}
              {keyPoints.length > 0 && (
                <div className="mb-5">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">
                    关键要点
                  </h4>
                  <div className="space-y-2">
                    {keyPoints.map((kp, i) => (
                      <div key={i} className="flex items-start gap-2.5 p-2.5 rounded-lg bg-gray-800/50">
                        <span className="flex-shrink-0 w-5 h-5 rounded bg-blue-500/20 text-blue-400 text-[10px] flex items-center justify-center font-medium">
                          {i + 1}
                        </span>
                        <span className="text-sm text-gray-300">{kp}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 行业 + 标的 */}
              <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs border-t border-gray-700/50 pt-4">
                {industries.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-gray-500">行业</span>
                    {industries.map((ind, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">
                        {ind}
                      </span>
                    ))}
                  </div>
                )}
                {symbols.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-gray-500">标的</span>
                    {symbols.map((s: any, i: number) => {
                      const icon = s.polarity === 'bullish' ? '↑' : s.polarity === 'bearish' ? '↓' : '—'
                      return (
                        <span key={i} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 text-xs">
                          <span className="text-[10px]">{icon}</span>
                          {s.name || s.code}
                        </span>
                      )
                    })}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* AI 溯源 */}
          {evidence.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>AI 分析溯源</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {evidence.map((ev, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="flex-shrink-0 w-1 rounded-full bg-blue-500/50" />
                    <div className="flex-1 space-y-2">
                      <div className="p-3 rounded-lg bg-gray-800/50 border border-gray-700/50">
                        <p className="text-xs text-gray-400 leading-relaxed">
                          <span className="text-[10px] text-gray-600 uppercase tracking-wider mr-1">原文</span>
                          {ev.text}
                        </p>
                      </div>
                      <div className="flex items-start gap-2 pl-1">
                        <span className="text-blue-400 text-[10px] mt-0.5">→</span>
                        <p className="text-xs text-blue-300">{ev.inference}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* 原文摘要 */}
          {paragraphs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>原文摘要</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="prose prose-invert max-w-none">
                  <div className="space-y-3">
                    {paragraphs.map((p: string, i: number) => (
                      <p key={i} className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                        {p.trim()}
                      </p>
                    ))}
                  </div>
                </div>
                <div className="mt-4 pt-3 border-t border-gray-700/50 text-[10px] text-gray-600">
                  以上为研报正文摘要，完整内容共 {detail.page_count} 页
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* 右侧信息栏 */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">基本信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5 text-xs">
              <InfoRow label="机构" value={detail.institution} />
              <InfoRow label="分析师" value={detail.analyst} />
              <InfoRow label="发布日期" value={detail.publish_date} />
              <InfoRow label="行业分类" value={detail.industry} />
              <InfoRow label="报告类型" value={detail.report_type} />
              <InfoRow label="页数" value={detail.page_count ? `${detail.page_count}页` : null} />
              <InfoRow label="文件大小" value={detail.file_size_kb ? `${detail.file_size_kb}KB` : null} />
              <InfoRow label="来源" value={detail.source} />
              {detail.ai_model && <InfoRow label="分析模型" value={detail.ai_model} />}
              {detail.ai_analyzed_at && (
                <InfoRow label="分析时间" value={detail.ai_analyzed_at?.replace('T', ' ').slice(0, 19)} />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <div className="flex justify-between gap-2">
      <span className="text-gray-500 flex-shrink-0">{label}</span>
      <span className="text-gray-300 text-right truncate">{value}</span>
    </div>
  )
}
