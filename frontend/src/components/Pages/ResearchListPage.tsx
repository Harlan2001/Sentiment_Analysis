import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle, Loading } from '../UI'
import { API_PREFIX } from '../../constants'
import { storage } from '../../utils/helpers'
import UploadArea from './UploadArea'
import ResearchUploadModal from './ResearchUploadModal'

function authHeaders(): Record<string, string> {
  const token = storage.get<string>('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const VIEW_COLORS: Record<string, string> = {
  bullish: 'text-red-400',
  bearish: 'text-green-400',
  neutral: 'text-gray-400',
}
const VIEW_BG: Record<string, string> = {
  bullish: 'bg-red-500/10 border-red-500/30',
  bearish: 'bg-green-500/10 border-green-500/30',
  neutral: 'bg-gray-500/10 border-gray-500/30',
}
const VIEW_LABEL: Record<string, string> = {
  bullish: '看多',
  bearish: '看空',
  neutral: '中性',
}
const STATUS_COLORS: Record<string, string> = {
  parsed: 'text-blue-400',
  processing: 'text-yellow-400',
  failed: 'text-red-400',
  analyzed: 'text-gray-400',
}
const STATUS_BG: Record<string, string> = {
  parsed: 'bg-blue-500/10 border-blue-500/30',
  processing: 'bg-yellow-500/10 border-yellow-500/30 animate-pulse',
  failed: 'bg-red-500/10 border-red-500/30',
  analyzed: 'bg-green-500/10 border-green-500/30',
}
const STATUS_LABEL: Record<string, string> = {
  parsed: '已解析',
  processing: '分析中...',
  failed: '失败',
}

interface ResearchItem {
  id: number
  title: string
  institution: string | null
  publish_date: string | null
  industry: string | null
  report_type: string | null
  ai_summary: string | null
  ai_market_view: string | null
  ai_view_strength: number | null
  ai_symbols: any
  ai_key_points: any
  page_count: number
  status: string
  source: string | null
  created_at: string | null
}

interface SummaryData {
  total: number
  analyzed: number
  bullish: number
  bearish: number
  neutral: number
  institutions: number
  date_start: string | null
  date_end: string | null
}

export default function ResearchListPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<ResearchItem[]>([])
  const [summary, setSummary] = useState<SummaryData | null>(null)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ institution: '', industry: '', market_view: '' })
  const [filterOptions, setFilterOptions] = useState<{
    institutions: string[]
    industries: string[]
  }>({ institutions: [], industries: [] })
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const fetchData = () => {
    setLoading(true)
    const params = new URLSearchParams({ page: String(page), page_size: '20' })
    if (filters.institution) params.set('institution', filters.institution)
    if (filters.industry) params.set('industry', filters.industry)
    if (filters.market_view) params.set('market_view', filters.market_view)

    fetch(`${API_PREFIX}/research/list?${params}`, { headers: authHeaders() })
      .then(r => r.json())
      .then(d => {
        setData(d.items || [])
        setTotal(d.total || 0)
        setFilterOptions(d.filters || { institutions: [], industries: [] })
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetch(`${API_PREFIX}/research/summary`, { headers: authHeaders() })
      .then(r => r.json())
      .then(setSummary)
  }, [])

  useEffect(() => { fetchData() }, [page, filters, refreshTrigger])

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setPage(1)
  }

  if (loading && data.length === 0) return <Loading text="加载研报数据..." />

  return (
    <div className="space-y-5">
      {/* 概览卡片 */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <StatCard label="研报总数" value={summary.total} />
          <StatCard label="已分析" value={summary.analyzed} color="blue" />
          <StatCard label="看多" value={summary.bullish} color="red" />
          <StatCard label="看空" value={summary.bearish} color="green" />
          <StatCard label="中性" value={summary.neutral} color="gray" />
          <StatCard label="机构数" value={summary.institutions} color="purple" />
        </div>
      )}

      {/* 上传区域 */}
      <UploadArea onClick={() => setUploadModalOpen(true)} />

      {/* 筛选栏 */}
      <Card>
        <CardContent className="flex flex-wrap items-center gap-3">
          <select
            value={filters.institution}
            onChange={e => handleFilterChange('institution', e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-gray-300
                       focus:outline-none focus:border-blue-500"
          >
            <option value="">全部机构</option>
            {filterOptions.institutions.map(inst => (
              <option key={inst} value={inst}>{inst}</option>
            ))}
          </select>

          <select
            value={filters.industry}
            onChange={e => handleFilterChange('industry', e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-gray-300
                       focus:outline-none focus:border-blue-500"
          >
            <option value="">全部行业</option>
            {filterOptions.industries.map(ind => (
              <option key={ind} value={ind}>{ind}</option>
            ))}
          </select>

          <select
            value={filters.market_view}
            onChange={e => handleFilterChange('market_view', e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-gray-300
                       focus:outline-none focus:border-blue-500"
          >
            <option value="">全部观点</option>
            <option value="bullish">看多</option>
            <option value="bearish">看空</option>
            <option value="neutral">中性</option>
          </select>

          <span className="text-xs text-gray-500 ml-auto">
            共 {total} 份
          </span>
        </CardContent>
      </Card>

      {/* 列表 */}
      <div className="space-y-3">
        {data.map(item => (
          <Card
            key={item.id}
            hover
            onClick={() => navigate(`/research/${item.id}`)}
            className="cursor-pointer"
          >
            <CardContent className="flex items-start gap-4">
              {/* 情感徽章 */}
              <div className="flex-shrink-0 mt-0.5">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border
                  ${VIEW_BG[item.ai_market_view || 'neutral']}
                  ${VIEW_COLORS[item.ai_market_view || 'neutral']}`}>
                  {VIEW_LABEL[item.ai_market_view || 'neutral']}
                  {item.ai_view_strength && (
                    <span className="ml-1 opacity-70">
                      {Math.round(item.ai_view_strength * 100)}%
                    </span>
                  )}
                </span>
              </div>

              {/* 主体内容 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-white text-sm font-medium truncate">
                    {item.title}
                  </h3>
                  {item.status !== 'analyzed' && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium
                      ${STATUS_BG[item.status] || 'bg-gray-500/10 border-gray-500/30'}
                      ${STATUS_COLORS[item.status] || 'text-gray-400'}`}>
                      {STATUS_LABEL[item.status] || item.status}
                    </span>
                  )}
                </div>

                {item.ai_summary && (
                  <p className="text-gray-400 text-xs line-clamp-2 mb-2">
                    {item.ai_summary}
                  </p>
                )}

                {/* 标签行 */}
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
                  {item.institution && (
                    <span className="px-1.5 py-0.5 rounded bg-gray-700/50">{item.institution}</span>
                  )}
                  {item.publish_date && (
                    <span>{item.publish_date}</span>
                  )}
                  {item.industry && item.industry.split(',').slice(0, 3).map((ind: string) => (
                    <span key={ind} className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">
                      {ind.trim()}
                    </span>
                  ))}
                  <span className="text-gray-600">{item.page_count}页</span>
                  {item.source && (
                    <span className="text-gray-600">{item.source}</span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 分页 */}
      {total > 20 && (
        <div className="flex justify-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
            className="px-3 py-1.5 rounded-lg text-xs bg-gray-800 text-gray-400
                       disabled:opacity-30 hover:bg-gray-700 transition-colors"
          >
            上一页
          </button>
          <span className="px-3 py-1.5 text-xs text-gray-400">
            {page} / {Math.ceil(total / 20)}
          </span>
          <button
            disabled={page >= Math.ceil(total / 20)}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1.5 rounded-lg text-xs bg-gray-800 text-gray-400
                       disabled:opacity-30 hover:bg-gray-700 transition-colors"
          >
            下一页
          </button>
        </div>
      )}

      {/* 上传模态框 */}
      <ResearchUploadModal
        isOpen={uploadModalOpen}
        onClose={() => {
          setUploadModalOpen(false)
          setRefreshTrigger(t => t + 1)
        }}
        onSubmitted={() => {
          setUploadModalOpen(false)
          setRefreshTrigger(t => t + 1)
        }}
      />
    </div>
  )
}

function StatCard({ label, value, color = 'gray' }: {
  label: string
  value: number
  color?: string
}) {
  const colors: Record<string, string> = {
    blue: 'from-blue-500/20 to-blue-600/10 border-blue-500/30 text-blue-400',
    red: 'from-red-500/20 to-red-600/10 border-red-500/30 text-red-400',
    green: 'from-green-500/20 to-green-600/10 border-green-500/30 text-green-400',
    gray: 'from-gray-500/20 to-gray-600/10 border-gray-500/30 text-gray-400',
    purple: 'from-purple-500/20 to-purple-600/10 border-purple-500/30 text-purple-400',
  }

  return (
    <Card className={`bg-gradient-to-br ${colors[color]} border text-center`} padding="sm">
      <div className="text-lg font-bold">{value}</div>
      <div className="text-[11px] opacity-70">{label}</div>
    </Card>
  )
}
