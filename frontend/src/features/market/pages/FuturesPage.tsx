import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import {
  fetchFuturesOverview,
  fetchFuturesRanking,
  fetchFuturesTrend,
  syncFuturesPositions,
} from '@/api/futures'
import { Skeleton } from '@/components/ui'
import type { FuturesRankingRow } from '@/types'

/**
 * 国债期货持仓（中金所成交持仓排名）。
 *
 * 数据源：中金所公开 CSV，每日快照积累。
 * 仅覆盖 T(10年) / TF(5年) / TS(2年) / TL(30年) 四个国债期货品种。
 *
 * 指标口径：
 * - 多空比 = 前 20 名会员**多头持仓合计 ÷ 空头持仓合计**（只算主力合约）
 * - 期货市场套保盘天然偏向空头，故多空比通常略低于 1，并非异常
 */

const VARIETY_COLORS: Record<string, string> = {
  T: '#6f8cff',
  TF: '#66cabb',
  TS: '#d6a85f',
  TL: '#a79bd0',
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('en-US')
}

function formatChange(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toLocaleString('en-US')}`
}

export default function FuturesPage() {
  const queryClient = useQueryClient()
  const [contract, setContract] = useState<string>('')
  const [variety, setVariety] = useState<string>('T')
  const [notice, setNotice] = useState('')

  const { data: overview, isLoading: loadingOverview } = useQuery({
    queryKey: ['futures', 'overview'],
    queryFn: fetchFuturesOverview,
    staleTime: 5 * 60 * 1000,
  })

  // 合约默认取主力（overview 已按品种排序，取第一个 T 系合约）
  const activeContract = contract || overview?.contracts?.[0]?.contract || ''
  const activeVariety =
    overview?.contracts?.find((item) => item.contract === activeContract)?.variety || variety

  const { data: ranking, isLoading: loadingRanking } = useQuery({
    queryKey: ['futures', 'ranking', activeContract],
    queryFn: () => fetchFuturesRanking(activeContract),
    enabled: Boolean(activeContract),
    staleTime: 5 * 60 * 1000,
  })

  const { data: trend, isLoading: loadingTrend } = useQuery({
    queryKey: ['futures', 'trend', activeVariety],
    queryFn: () => fetchFuturesTrend(activeVariety, 60),
    enabled: Boolean(activeVariety),
    staleTime: 5 * 60 * 1000,
  })

  const sync = useMutation({
    mutationFn: () => syncFuturesPositions(),
    onSuccess: (result) => {
      setNotice(
        `同步完成（${result.trade_date}）：抓取 ${result.fetched} 条，新增 ${result.inserted}，更新 ${result.updated}`,
      )
      queryClient.invalidateQueries({ queryKey: ['futures'] })
    },
    onError: (error: Error) => setNotice(`同步失败：${error.message}`),
  })

  const rows = ranking?.rows ?? []
  const summary = ranking?.summary

  // 净持仓排序（多单 − 空单），供右栏 Top10
  // 注意：不同排名口径下会员可能重名（如同时出现在多空榜），故按会员聚合并用索引兜底 key
  const netTop = useMemo(() => {
    const byTrader = new Map<string, { trader: string; long: number; short: number }>()
    for (const row of rows) {
      for (const [trader, position, isLong] of [
        [row.long_trader, row.long_position, true],
        [row.short_trader, row.short_position, false],
      ] as [string | null, number | null, boolean][]) {
        if (!trader) continue
        const current = byTrader.get(trader) ?? { trader, long: 0, short: 0 }
        if (isLong) current.long += position ?? 0
        else current.short += position ?? 0
        byTrader.set(trader, current)
      }
    }
    return [...byTrader.values()]
      .map((item) => ({ ...item, net: item.long - item.short }))
      .sort((a, b) => Math.abs(b.net) - Math.abs(a.net))
      .slice(0, 10)
  }, [rows])

  return (
    <div className="home-section-page">
      <div className="home-section-grid">
        <main className="home-section-main space-y-4">
          <header className="flex flex-wrap items-start justify-between gap-3 pt-2">
            <div>
              <h1 className="text-lg font-bold text-white">国债期货持仓</h1>
              <p className="mt-1 text-xs text-gray-500">
                中金所成交持仓排名（前 20 名会员）
                {overview?.trade_date ? ` · 数据日期 ${overview.trade_date}` : ''}
              </p>
            </div>
            <button
              onClick={() => sync.mutate()}
              disabled={sync.isPending}
              className="rounded-lg border border-[#3d3d42] px-3 py-2 text-xs text-gray-200 hover:bg-[#1b1b1d] disabled:opacity-50"
            >
              {sync.isPending ? '同步中…' : '同步当日数据'}
            </button>
          </header>

          {notice && <p className="diag-caption">{notice}</p>}

          {loadingOverview ? (
            <Skeleton height="120px" variant="rectangular" />
          ) : !overview?.trade_date ? (
            <Empty text="暂无持仓数据，点击右上角「同步当日数据」拉取" />
          ) : (
            <>
              {/* 概览：多空比 + 四品种对比 */}
              <section className="fut-hero">
                <div className="fut-hero-main">
                  <span className="fut-hero-label">多空比</span>
                  <b className="fut-hero-value">
                    {summary?.long_short_ratio?.toFixed(3) ?? '—'}
                  </b>
                  <span className="fut-hero-sub">
                    多头 {formatNumber(summary?.long_total)} · 空头{' '}
                    {formatNumber(summary?.short_total)}
                  </span>
                </div>
                <div className="fut-compare">
                  {overview.comparison.map((item) => (
                    <button
                      key={item.variety}
                      className={`fut-compare-item${item.variety === activeVariety ? ' active' : ''}`}
                      onClick={() => {
                        setVariety(item.variety)
                        setContract('')
                      }}
                    >
                      <span className="fut-compare-name">{item.label}</span>
                      <span
                        className="fut-compare-ratio"
                        style={{ color: VARIETY_COLORS[item.variety] }}
                      >
                        {item.ratio?.toFixed(3) ?? '—'}
                      </span>
                    </button>
                  ))}
                </div>
              </section>

              {/* 合约切换 */}
              <div className="factor-view-tabs">
                {(overview.contracts ?? []).map((item) => (
                  <button
                    key={item.contract}
                    onClick={() => {
                      setContract(item.contract)
                      setVariety(item.variety)
                    }}
                    className={`factor-view-tab${item.contract === activeContract ? ' active' : ''}`}
                  >
                    {item.contract}
                  </button>
                ))}
              </div>

              {/* 持仓排名 */}
              {loadingRanking ? (
                <Skeleton height="400px" variant="rectangular" />
              ) : !rows.length ? (
                <Empty text="该合约暂无持仓数据" />
              ) : (
                <div className="overflow-x-auto rounded-xl border border-[#2a2a2e] bg-[#111111]">
                  <table className="w-full min-w-[760px] text-left text-xs">
                    <thead className="text-[11px] text-gray-500">
                      <tr className="border-b border-[#2a2a2e]">
                        {/* 表头：多空两侧都有"增减"，用唯一 key 而非文案 */}
                        {(
                          [
                            ['rank', '排名'],
                            ['trader', '会员'],
                            ['long', '持买单'],
                            ['long_chg', '增减'],
                            ['short', '持卖单'],
                            ['short_chg', '增减'],
                            ['net', '净持仓'],
                          ] as const
                        ).map(([key, label]) => (
                          <th key={key} className="px-4 py-3 font-medium">
                            {label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => {
                        const net = (row.long_position ?? 0) - (row.short_position ?? 0)
                        return (
                          <tr key={row.rank_no} className="border-b border-[#1e1e1e] hover:bg-[#181818]">
                            <td className="px-4 py-2.5 font-mono text-gray-500">{row.rank_no}</td>
                            <td className="px-4 py-2.5 text-gray-200">
                              {row.long_trader || row.short_trader || '—'}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-gray-300">
                              {formatNumber(row.long_position)}
                            </td>
                            <td
                              className={`px-4 py-2.5 font-mono ${(row.long_change ?? 0) > 0 ? 'text-red-400' : 'text-green-400'}`}
                            >
                              {formatChange(row.long_change)}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-gray-300">
                              {formatNumber(row.short_position)}
                            </td>
                            <td
                              className={`px-4 py-2.5 font-mono ${(row.short_change ?? 0) > 0 ? 'text-red-400' : 'text-green-400'}`}
                            >
                              {formatChange(row.short_change)}
                            </td>
                            <td
                              className={`px-4 py-2.5 font-mono ${net >= 0 ? 'text-red-400' : 'text-green-400'}`}
                            >
                              {net > 0 ? '+' : ''}
                              {formatNumber(net)}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              <p className="diag-footnote">
                多空比为前 20 名会员多头合计 ÷ 空头合计，仅统计主力合约。
                期货市场套保盘天然偏向空头，多空比通常略低于 1，并非异常。
              </p>
            </>
          )}
        </main>

        <aside className="home-section-sidebar fut-sidebar">
          <div className="space-y-4">
            <ChartCard title={`多空比走势 · ${trend?.label ?? '10年期'}`}>
              {loadingTrend ? (
                <Skeleton height="150px" variant="rectangular" />
              ) : (
                <TrendChart series={trend?.series ?? []} color={VARIETY_COLORS[activeVariety]} />
              )}
            </ChartCard>

            <ChartCard title="四品种多空比">
              <ComparisonChart comparison={overview?.comparison ?? []} />
            </ChartCard>

            <ChartCard title="净持仓 Top 10">
              {!netTop.length ? (
                <p className="diag-caption">暂无数据</p>
              ) : (
                <ul className="space-y-2">
                  {netTop.map((item) => {
                    const max = Math.max(...netTop.map((x) => Math.abs(x.net)), 1)
                    return (
                      <li key={item.trader} className="text-xs">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="truncate text-gray-300">{item.trader}</span>
                          <span
                            className={`shrink-0 font-mono ${item.net >= 0 ? 'text-red-400' : 'text-green-400'}`}
                          >
                            {item.net > 0 ? '+' : ''}
                            {formatNumber(item.net)}
                          </span>
                        </div>
                        <div className="mt-1 flex h-1 gap-px">
                          <span className="flex-1">
                            <i
                              className="block h-1 rounded-sm bg-[#6f8cff]"
                              style={{ width: `${(Math.abs(item.net) / max) * 100}%` }}
                            />
                          </span>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </ChartCard>

            <p className="diag-footnote">
              数据来源：中金所成交持仓排名（每日快照）
              <br />
              仅含 T / TF / TS / TL 四个国债期货品种
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}

function TrendChart({
  series,
  color,
}: {
  series: { date: string; ratio: number | null }[]
  color: string
}) {
  if (series.length < 2) {
    return <p className="diag-caption">历史样本不足（需至少 2 个交易日），可先用同步按钮逐日积累</p>
  }
  const option = {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => v?.toFixed(3) },
    grid: { left: 46, right: 14, top: 12, bottom: 24 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: series.map((item) => item.date.slice(5)),
      axisLabel: { color: '#777', fontSize: 9, interval: Math.ceil(series.length / 6) },
      axisLine: { lineStyle: { color: '#333' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: '#777', fontSize: 10 },
      splitLine: { lineStyle: { color: '#262626' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: series.map((item) => item.ratio),
        lineStyle: { color, width: 2 },
        itemStyle: { color },
        areaStyle: { color: 'rgba(111,140,255,0.10)' },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ yAxis: 1 }],
          lineStyle: { color: '#3a3a3e', type: 'dashed' },
          label: { show: true, formatter: '1.0', color: '#666', fontSize: 9 },
        },
      },
    ],
  }
  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 150 }} />
}

function ComparisonChart({
  comparison,
}: {
  comparison: { variety: string; label: string; ratio: number | null }[]
}) {
  if (!comparison.length) return <p className="diag-caption">暂无数据</p>
  const option = {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => v?.toFixed(3) },
    grid: { left: 62, right: 20, top: 8, bottom: 8 },
    xAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: '#777', fontSize: 9 },
      splitLine: { lineStyle: { color: '#262626' } },
    },
    yAxis: {
      type: 'category',
      data: comparison.map((item) => item.label),
      axisLabel: { color: '#a7a7a7', fontSize: 10 },
      axisLine: { lineStyle: { color: '#333' } },
    },
    series: [
      {
        type: 'bar',
        data: comparison.map((item) => ({
          value: item.ratio,
          itemStyle: { color: VARIETY_COLORS[item.variety] ?? '#6f8cff', borderRadius: [0, 3, 3, 0] },
        })),
        barMaxWidth: 14,
        label: {
          show: true,
          position: 'right',
          color: '#8b8b8b',
          fontSize: 10,
          formatter: (p: any) => p.value?.toFixed(3),
        },
      },
    ],
  }
  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 130 }} />
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
      <h2 className="mb-2 text-sm font-medium text-gray-400">{title}</h2>
      {children}
    </section>
  )
}

function Empty({ text }: { text: string }) {
  return (
    <div className="flex min-h-[240px] items-center justify-center rounded-xl border border-[#2a2a2e] bg-[#111111] p-6 text-center text-sm text-gray-500">
      {text}
    </div>
  )
}