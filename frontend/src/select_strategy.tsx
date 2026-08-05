import React, { useEffect, useMemo, useState } from 'react'
import { Button, Card, CardContent, CardHeader, CardTitle, Empty, Error as ErrorUI, Input, Loading } from '@/components/UI'
import { storage } from '@/utils/helpers'
import { API_PREFIX } from '@/constants'

function authHeaders(): Record<string, string> {
  const token = storage.get<string>("auth_token");
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

const BASE = `${API_PREFIX}/ai-strategy-recommendation`

interface RecommendationTarget {
  code?: string
  name?: string
  type?: string
}

interface RecommendationStrategy {
  id?: string
  name?: string
}

interface RecommendationItem {
  priority?: number
  target?: RecommendationTarget
  stock?: RecommendationTarget
  strategy?: RecommendationStrategy
  allocation_ratio?: string
  reason?: string
  expected_holding_period?: string
  risk_level?: string
}

interface RecommendationOutcome {
  market_overview?: string
  sentiment_summary?: string
  risk_alert?: string
  recommendations?: RecommendationItem[]
  not_recommended?: Array<{
    target_code?: string
    target_name?: string
    stock_code?: string
    stock_name?: string
    reason?: string
  }>
  error?: string
}

interface RecommendationRecord {
  id: number
  analysis_date: string
  news_summary?: string
  outcome: RecommendationOutcome
  model_name?: string
  news_count?: number
  created_at?: string
  updated_at?: string
}

interface LatestResponse {
  success: boolean
  data: RecommendationRecord | null
}

interface AnalyzeResponse {
  success: boolean
  from_cache: boolean
  data: RecommendationRecord | null
}

interface HistoryResponse {
  success: boolean
  items: RecommendationRecord[]
}

function getYesterday() {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

async function fetchLatestRecommendation(): Promise<LatestResponse> {
  const res = await fetch(`${BASE}/latest`, { headers: authHeaders() })
  if (!res.ok) throw new Error('最新推荐读取失败')
  return res.json()
}

async function fetchRecommendationHistory(): Promise<HistoryResponse> {
  const res = await fetch(`${BASE}/history?limit=100`, { headers: authHeaders() })
  if (!res.ok) throw new Error('历史推荐读取失败')
  return res.json()
}

async function requestRecommendation(analysisDate: string, forceRefresh: boolean = false): Promise<AnalyzeResponse> {
  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      analysis_date: analysisDate,
      force_refresh: forceRefresh,
    }),
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.detail || '推荐生成失败')
  }
  return res.json()
}

const Field: React.FC<{ label: string; value?: React.ReactNode }> = ({ label, value }) => (
  <div>
    <div className="text-xs text-gray-500 mb-1">{label}</div>
    <div className="text-sm text-gray-200 break-words">{value || '-'}</div>
  </div>
)

const RecommendationDetail: React.FC<{ record: RecommendationRecord | null }> = ({ record }) => {
  const outcome = record?.outcome
  const recommendations = outcome?.recommendations || []

  if (!record) {
    return <Empty message="暂无推荐结果，请选择日期后点击开始推荐" />
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Field label="分析日期" value={record.analysis_date} />
        <Field label="新闻条数" value={record.news_count} />
        <Field label="模型" value={record.model_name} />
        <Field label="更新时间" value={record.updated_at || record.created_at} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2 bg-gray-950/40 border border-gray-700 rounded-lg p-4">
          <div className="text-sm font-semibold text-gray-200 mb-2">市场判断</div>
          <p className="text-sm text-gray-300 leading-6 whitespace-pre-wrap">{outcome?.market_overview || '-'}</p>
        </div>
        <div className="bg-gray-950/40 border border-gray-700 rounded-lg p-4">
          <div className="text-sm font-semibold text-gray-200 mb-2">舆情与风险</div>
          <p className="text-sm text-blue-300 mb-3">{outcome?.sentiment_summary || '-'}</p>
          <p className="text-sm text-amber-300 whitespace-pre-wrap">{outcome?.risk_alert || '-'}</p>
        </div>
      </div>

      {outcome?.error && (
        <div className="text-sm text-red-300 bg-red-950/30 border border-red-800 rounded-lg p-3">
          {outcome.error}
        </div>
      )}

      <div className="space-y-3">
        {recommendations.length === 0 ? (
          <Empty message="暂无推荐组合" />
        ) : (
          recommendations.map((item, index) => {
            const target = item.target || item.stock || {}
            return (
              <div key={`${target.code || index}-${item.strategy?.id || index}`} className="bg-gray-950/40 border border-gray-700 rounded-lg p-4">
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3 mb-3">
                  <div>
                    <div className="text-xs text-purple-300 mb-1">优先级 {item.priority || index + 1}</div>
                    <div className="text-lg font-semibold text-white">{target.name || target.code || '未命名标的'}</div>
                    <div className="text-xs text-gray-500 mt-1">{target.code || '-'} · {target.type || '-'}</div>
                  </div>
                  <div className="text-left md:text-right">
                    <div className="text-sm text-gray-200">{item.strategy?.name || item.strategy?.id || '未命名策略'}</div>
                    <div className="text-xs text-gray-500 mt-1">{item.strategy?.id || '-'}</div>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                  <Field label="配置比例" value={item.allocation_ratio} />
                  <Field label="持有周期" value={item.expected_holding_period} />
                  <Field label="风险等级" value={item.risk_level} />
                </div>
                <p className="text-sm text-gray-300 leading-6 whitespace-pre-wrap">{item.reason || '-'}</p>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

const SelectStrategyPage: React.FC = () => {
  const [analysisDate, setAnalysisDate] = useState(getYesterday())
  const [latest, setLatest] = useState<RecommendationRecord | null>(null)
  const [history, setHistory] = useState<RecommendationRecord[]>([])
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cacheHint, setCacheHint] = useState<string>('')

  const expandedRecord = useMemo(
    () => history.find(item => item.id === expandedId) || null,
    [expandedId, history]
  )

  const loadPageData = async () => {
    const [latestRes, historyRes] = await Promise.all([
      fetchLatestRecommendation(),
      fetchRecommendationHistory(),
    ])
    setLatest(latestRes.data)
    setHistory(historyRes.items || [])
  }

  useEffect(() => {
    setInitialLoading(true)
    loadPageData()
      .catch(err => setError((err as Error)?.message || '页面数据加载失败'))
      .finally(() => setInitialLoading(false))
  }, [])

  const handleAnalyze = async (forceRefresh: boolean = false) => {
    setLoading(true)
    setError(null)
    setCacheHint('')
    try {
      const result = await requestRecommendation(analysisDate, forceRefresh)
      setLatest(result.data)
      if (forceRefresh) {
        setCacheHint('已强制刷新，覆盖了历史缓存记录')
      } else {
        setCacheHint(result.from_cache ? '已命中当日缓存，直接展示历史推荐结果' : '已生成新的推荐结果并写入缓存')
      }
      const historyRes = await fetchRecommendationHistory()
      setHistory(historyRes.items || [])
    } catch (err) {
      setError((err as Error)?.message || '推荐生成失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-white">
          AI智能推荐标的与策略
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          基于所选日期的新闻舆情分析结果生成推荐；同一日期优先读取缓存。
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>推荐任务</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
            <div className="w-full sm:w-64">
              <label className="block text-xs text-gray-400 mb-1">新闻分析日期</label>
              <Input type="date" value={analysisDate} onChange={event => setAnalysisDate(event.target.value)} />
            </div>
            <Button onClick={() => handleAnalyze(false)} loading={loading}>
              开始推荐
            </Button>
            <Button onClick={() => handleAnalyze(true)} loading={loading} variant="secondary">
              强制刷新
            </Button>
          </div>
          {cacheHint && <div className="mt-3 text-sm text-green-300">{cacheHint}</div>}
        </CardContent>
      </Card>

      {error && <ErrorUI message={error} />}

      {initialLoading ? (
        <Loading text="正在加载推荐缓存" />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>最新推荐结果</CardTitle>
            </CardHeader>
            <CardContent>
              <RecommendationDetail record={latest} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>历史记录</CardTitle>
            </CardHeader>
            <CardContent>
              {history.length === 0 ? (
                <Empty message="暂无历史推荐信息" />
              ) : (
                <div className="space-y-2">
                  {history.map(item => (
                    <div key={item.id} className="border border-gray-700 rounded-lg bg-gray-950/30">
                      <button
                        type="button"
                        className="w-full p-4 text-left flex flex-col md:flex-row md:items-center md:justify-between gap-2"
                        onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                      >
                        <div>
                          <div className="text-sm font-semibold text-gray-100">{item.analysis_date}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            {item.news_count || 0} 条新闻 · {item.model_name || '-'} · {item.updated_at || item.created_at || '-'}
                          </div>
                        </div>
                        <div className="text-sm text-blue-300">
                          {expandedId === item.id ? '收起' : '查看详情'}
                        </div>
                      </button>
                      {expandedRecord?.id === item.id && (
                        <div className="px-4 pb-4">
                          <RecommendationDetail record={item} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

export default SelectStrategyPage
