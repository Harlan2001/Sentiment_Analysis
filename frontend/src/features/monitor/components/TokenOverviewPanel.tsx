/**
 * Token 消耗概览面板 — 系统监控 Tab 内展示
 * 显示今日/本月 Token 总量、调用次数、按来源分布、趋势图、模型分布
 */
import React, { useEffect, useState, useCallback } from 'react'
import { fetchTokenOverview, fetchTokenTrend, fetchTokenByModel } from '@/api/monitor'
import type { TokenOverview, TokenTrendItem, TokenModelDist } from '@/types'
import { CALL_SOURCE_MAP, getModelLabel } from '@/config/labels'

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

const TokenOverviewPanel: React.FC = () => {
  const [overview, setOverview] = useState<TokenOverview | null>(null)
  const [trend, setTrend] = useState<TokenTrendItem[]>([])
  const [models, setModels] = useState<TokenModelDist[]>([])
  const [trendDays, setTrendDays] = useState(7)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, tr, md] = await Promise.all([
        fetchTokenOverview(),
        fetchTokenTrend(trendDays),
        fetchTokenByModel(trendDays),
      ])
      setOverview(ov)
      setTrend(tr.trend)
      setModels(md.models)
    } catch (e) {
      console.error('Token数据加载失败:', e)
    } finally {
      setLoading(false)
    }
  }, [trendDays])

  useEffect(() => {
    load()
  }, [load])

  if (loading && !overview) {
    return (
      <div className="text-center py-8 text-gray-400">
        <div className="animate-spin w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full mx-auto mb-2" />
        加载Token数据...
      </div>
    )
  }

  if (!overview) return null

  const modelColors: Record<string, string> = {
    glm: '#8b5cf6',
    doubao: '#8b5cf6',
    deepseek: '#10b981',
    qwen: '#f59e0b',
  }

  return (
    <div className="space-y-4">
      {/* Top Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">今日Token</div>
          <div className="text-xl font-bold text-blue-400">{formatTokens(overview.today_tokens)}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">本月Token</div>
          <div className="text-xl font-bold text-green-400">{formatTokens(overview.month_tokens)}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">今日调用次数</div>
          <div className="text-xl font-bold text-yellow-400">{overview.today_calls}</div>
          {overview.today_failed > 0 && (
            <div className="text-xs text-red-400 mt-1">失败 {overview.today_failed} 次</div>
          )}
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">今日活跃用户</div>
          <div className="text-xl font-bold text-purple-400">{overview.today_users}</div>
        </div>
      </div>

      {/* 按来源分布 + 模型分布 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 按调用来源 */}
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">今日Token分布（按来源）</h3>
          {overview.by_source.length === 0 ? (
            <div className="text-gray-500 text-sm text-center py-4">暂无数据</div>
          ) : (
            <div className="space-y-2">
              {overview.by_source.map((s) => {
                const maxTokens = overview.by_source[0]?.tokens || 1
                const pct = Math.round((s.tokens / maxTokens) * 100)
                return (
                  <div key={s.source}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-300">{CALL_SOURCE_MAP[s.source] || s.source}</span>
                      <span className="text-gray-400">
                        {formatTokens(s.tokens)} ({s.calls}次)
                      </span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* 按模型分布 */}
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">模型用量分布（{trendDays}天）</h3>
          {models.length === 0 ? (
            <div className="text-gray-500 text-sm text-center py-4">暂无数据</div>
          ) : (
            <div className="space-y-2">
              {models.map((m) => (
                <div key={m.model}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-300">
                      <span
                        className="inline-block w-2 h-2 rounded-full mr-1.5"
                        style={{ backgroundColor: modelColors[m.model] || '#6b7280' }}
                      />
                      {getModelLabel(m.model)}
                    </span>
                    <span className="text-gray-400">
                      {formatTokens(m.tokens)} ({m.percentage}%)
                    </span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div
                      className="h-2 rounded-full"
                      style={{ width: `${m.percentage}%`, backgroundColor: modelColors[m.model] || '#6b7280' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Token 消耗趋势（简易柱状图） */}
      <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-300">Token消耗趋势</h3>
          <select
            className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1"
            value={trendDays}
            onChange={(e) => setTrendDays(Number(e.target.value))}
          >
            <option value={7}>近7天</option>
            <option value={30}>近30天</option>
          </select>
        </div>
        {trend.length === 0 ? (
          <div className="text-gray-500 text-sm text-center py-4">暂无数据</div>
        ) : (
          <div className="flex items-end gap-1 h-32">
            {trend.map((item) => {
              const maxTotal = Math.max(...trend.map((t) => t.total as number), 1)
              const heightPct = Math.max(2, Math.round(((item.total as number) / maxTotal) * 100))
              return (
                <div
                  key={item.date}
                  className="flex-1 flex flex-col items-center justify-end h-full"
                  title={`${item.date}: ${formatTokens(item.total as number)}`}
                >
                  <span className="text-[10px] text-gray-400 mb-1">{formatTokens(item.total as number)}</span>
                  <div
                    className="w-full bg-blue-500/70 hover:bg-blue-400 rounded-t"
                    style={{ height: `${heightPct}%`, minHeight: '2px' }}
                  />
                  <span className="text-[10px] text-gray-500 mt-1">{item.date.slice(5)}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default TokenOverviewPanel
