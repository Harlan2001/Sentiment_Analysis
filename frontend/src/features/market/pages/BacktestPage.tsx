import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import { fetchBacktestOverview } from '@/api/market'
import { Skeleton } from '@/components/ui'
import type { BacktestOverviewItem, BacktestOverviewResponse } from '@/types'

/**
 * 回测仿真。
 *
 * 用事件研究法评估各因子的历史方向表现：某因子出现后 T+N 个交易日的
 * 10Y 国债收益率变动。**样本来自 news_factor（6.4 万行），按交易日对齐、
 * 严格防未来函数**。
 *
 * 口径与因子详情页一致：同时给出**多数类基准**作对照 —— 方向命中率的
 * 正确参照不是 50%，而是"无脑猜多数方向"的命中率。
 *
 * 本页定位：一屏纵览多个因子的表现，便于快速筛选；单因子细节仍在因子详情页。
 */

const HOLDINGS = [1, 5, 20]
const UP = '#f87171'
const DOWN = '#4ade80'

function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

function bp(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}bp`
}

export default function BacktestPage() {
  const navigate = useNavigate()
  const [holding, setHolding] = useState(5)
  const [onlySufficient, setOnlySufficient] = useState(true)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 12

  const { data, isLoading, isError } = useQuery({
    queryKey: ['backtest-overview', holding],
    queryFn: () => fetchBacktestOverview(holding),
    staleTime: 10 * 60 * 1000,
  })

  const summary = data?.summary

  const filtered = useMemo(() => {
    const rows = data?.items ?? []
    return rows.filter((row) => {
      if (onlySufficient && !row.sufficient) return false
      if (query && !`${row.factor_code}${row.factor_name ?? ''}`.toLowerCase().includes(query.toLowerCase())) return false
      return true
    })
  }, [data, onlySufficient, query])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  if (isLoading) {
    return (
      <div className="home-section-page">
        <div className="home-section-grid">
          <main className="home-section-main space-y-4">
            <Skeleton height="110px" variant="rectangular" />
            <Skeleton height="360px" variant="rectangular" />
          </main>
        </div>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="home-section-page">
        <div className="home-section-grid">
          <main className="home-section-main">
            <Empty text="回测数据加载失败，请稍后重试" />
          </main>
        </div>
      </div>
    )
  }

  if (!data.items.length) {
    return (
      <div className="home-section-page">
        <div className="home-section-grid">
          <main className="home-section-main">
            <Empty text="暂无回测结果，请先在服务端执行 scripts/run_factor_backtest.py" />
          </main>
        </div>
      </div>
    )
  }

  return (
    <div className="home-section-page">
      <div className="home-section-grid">
        <main className="home-section-main space-y-4">
          <header className="flex flex-wrap items-start justify-between gap-3 pt-2">
            <div>
              <h1 className="text-lg font-bold text-white">回测仿真</h1>
              <p className="mt-1 text-xs text-gray-500">
                因子事件研究 · 按交易日对齐 · 严格防未来函数
              </p>
            </div>
            <div className="factor-view-tabs">
              {HOLDINGS.map((value) => (
                <button
                  key={value}
                  onClick={() => {
                    setHolding(value)
                    setPage(1)
                  }}
                  className={`factor-view-tab${holding === value ? ' active' : ''}`}
                >
                  持有 T+{value}
                </button>
              ))}
            </div>
          </header>

          {/* 概览统计：带数字滚动动画 */}
          <section className="bt-stat-row">
            <StatCard label="覆盖因子" value={summary?.factors ?? 0} />
            <StatCard label="累计样本" value={summary?.total_samples ?? 0} />
            <StatCard label="平均命中率" value={summary?.avg_hit_rate ?? 0} percent />
            <StatCard label="平均基准" value={summary?.avg_base ?? 0} percent tone="muted" />
            <StatCard
              label={`样本充足（≥${data.min_samples}）`}
              value={summary?.sufficient ?? 0}
            />
          </section>

          {/* 命中率分布：直方图，看整体形态 */}
          <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
            <h2 className="mb-1 text-sm font-medium text-gray-400">
              命中率分布（T+{holding}）
            </h2>
            <p className="diag-caption">
              虚线为平均基准位置；分布中心若在虚线左侧，说明多数因子的方向判断弱于无脑猜
            </p>
            <DistributionChart items={filtered} base={summary?.avg_base ?? null} />
          </section>

          {/* 因子明细 */}
          <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-medium text-gray-400">
                因子明细 · {filtered.length} 个
              </h2>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value)
                    setPage(1)
                  }}
                  placeholder="搜索因子"
                  className="h-8 w-40 rounded border border-[#3d3d42] bg-[#0d0d0d] px-2 text-xs text-gray-200 outline-none"
                />
                <button
                  onClick={() => {
                    setOnlySufficient((v) => !v)
                    setPage(1)
                  }}
                  className={`factor-filter-tab${onlySufficient ? ' active' : ''}`}
                >
                  {onlySufficient ? '仅样本充足' : '显示全部'}
                </button>
              </div>
            </div>

            <div className="bt-grid">
              {pageItems.map((item, index) => (
                <FactorCard
                  key={item.factor_code}
                  item={item}
                  minSamples={data.min_samples}
                  delay={index * 30}
                  onClick={() => item.factor_id && navigate(`/factor/${item.factor_id}`)}
                />
              ))}
            </div>

            <div className="factor-table-pagination">
              <span>
                第 {page} / {totalPages} 页 · 共 {filtered.length} 个因子
              </span>
              <div>
                <button disabled={page === 1} onClick={() => setPage((v) => Math.max(1, v - 1))}>
                  上一页
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((v) => Math.min(totalPages, v + 1))}
                >
                  下一页
                </button>
              </div>
            </div>
          </section>

          <p className="diag-footnote">
            对照基准为**多数类基准**（无后猜多数方向的命中率），非 50%。
            样本不足 {data.min_samples} 的因子统计波动较大，供参考。
          </p>
        </main>

        <aside className="home-section-sidebar cs-sidebar bt-sidebar">
          <div className="space-y-4">
            <ChartCard title="样本量 Top 10">
              <TopSamplesChart items={(data.items ?? []).slice(0, 10)} />
            </ChartCard>

            {/* 持有期对比：同一批因子在不同持有期下的表现差异 */}
            <ChartCard title="持有期对比">
              <HoldingCompare items={data.items ?? []} holding={holding} />
            </ChartCard>

            {/* 相对基准分布：高于/低于基准的因子占比（主区直方图不体现这点） */}
            <ChartCard title="相对基准分布">
              <AboveBaseDonut summary={summary} minSamples={data.min_samples} />
            </ChartCard>

            <p className="diag-footnote">
              事件研究法：信号日 t 只用 t 及之前数据，收益从 t+1 起算
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}

/** 统计卡：数字从 0 滚动到目标值（CSS 动画，无需 JS 计时器） */
function StatCard({
  label,
  value,
  percent = false,
  tone = '',
}: {
  label: string
  value: number
  percent?: boolean
  tone?: string
}) {
  const display = percent ? `${(value * 100).toFixed(1)}%` : value.toLocaleString('en-US')
  return (
    <div className={`bt-stat-card ${tone}`}>
      <small>{label}</small>
      <strong className="bt-stat-value">{display}</strong>
    </div>
  )
}

function FactorCard({
  item,
  minSamples,
  delay,
  onClick,
}: {
  item: BacktestOverviewItem
  minSamples: number
  delay: number
  onClick: () => void
}) {
  const hit = item.hit_rate
  const base = item.majority_base
  const delta = item.delta
  const insufficient = item.sample_size < minSamples

  return (
    <button
      className="bt-card"
      onClick={onClick}
      style={{ animationDelay: `${delay}ms` }}
      title={item.factor_name || item.factor_code}
    >
      <span className="bt-card-name">{item.factor_name || item.factor_code}</span>
      <span className="bt-card-code">{item.factor_code}</span>

      <span className="bt-card-bars">
        <span className="bt-bar-row">
          <span className="bt-bar-name">命中</span>
          <span className="bt-bar-track">
            <i
              className="bt-bar-fill hit"
              style={{ ['--w' as string]: `${Math.min((hit ?? 0) * 100, 100)}%` } as React.CSSProperties}
            />
          </span>
          <span className="bt-bar-num">{insufficient ? '样本不足' : pct(hit)}</span>
        </span>
        <span className="bt-bar-row">
          <span className="bt-bar-name">基准</span>
          <span className="bt-bar-track">
            <i
              className="bt-bar-fill base"
              style={{ ['--w' as string]: `${Math.min((base ?? 0) * 100, 100)}%` } as React.CSSProperties}
            />
          </span>
          <span className="bt-bar-num">{pct(base)}</span>
        </span>
      </span>

      <span className="bt-card-foot">
        <span>样本 {item.sample_size}</span>
        {delta !== null && (
          <span className={delta >= 0 ? 'bt-delta up' : 'bt-delta down'}>
            {delta >= 0 ? '+' : ''}
            {(delta * 100).toFixed(1)}pt
          </span>
        )}
      </span>
    </button>
  )
}

function DistributionChart({
  items,
  base,
}: {
  items: BacktestOverviewItem[]
  base: number | null
}) {
  const rates = items.map((i) => i.hit_rate).filter((v): v is number => v !== null)
  if (!rates.length) return <p className="diag-caption">暂无数据</p>

  // 按 5% 分箱
  const buckets = new Map<string, number>()
  for (const rate of rates) {
    const lower = Math.floor(rate * 20) / 20
    const key = `${(lower * 100).toFixed(0)}%`
    buckets.set(key, (buckets.get(key) ?? 0) + 1)
  }
  const data = [...buckets.entries()].sort((a, b) => parseFloat(a[0]) - parseFloat(b[0]))

  const option = {
    tooltip: { trigger: 'axis' },
    grid: { left: 44, right: 18, top: 14, bottom: 26 },
    xAxis: {
      type: 'category',
      data: data.map((item) => item[0]),
      axisLabel: { color: '#777', fontSize: 10 },
      axisLine: { lineStyle: { color: '#333' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#777', fontSize: 10 },
      splitLine: { lineStyle: { color: '#262626' } },
    },
    series: [
      {
        type: 'bar',
        data: data.map((item) => item[1]),
        itemStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: '#6f8cff' },
              { offset: 1, color: 'rgba(111,140,255,0.25)' },
            ],
          },
          borderRadius: [3, 3, 0, 0],
        },
        barMaxWidth: 42,
        animationDuration: 600,
        markLine: base !== null
          ? {
              silent: true,
              symbol: 'none',
              data: [{ xAxis: `${(Math.floor(base * 20) / 20 * 100).toFixed(0)}%` }],
              lineStyle: { color: '#f0a0a0', type: 'dashed', width: 1.5 },
              label: { show: true, formatter: '平均基准', color: '#f0a0a0', fontSize: 10 },
            }
          : undefined,
      },
    ],
  }
  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 200 }} />
}

function TopSamplesChart({ items }: { items: BacktestOverviewItem[] }) {
  if (!items.length) return <p className="diag-caption">暂无数据</p>
  const option = {
    tooltip: { trigger: 'axis' },
    grid: { left: 90, right: 22, top: 8, bottom: 8 },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#777', fontSize: 9 },
      splitLine: { lineStyle: { color: '#262626' } },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: items.map((item) => (item.factor_name || item.factor_code).slice(0, 8)),
      axisLabel: { color: '#a7a7a7', fontSize: 9 },
      axisLine: { lineStyle: { color: '#333' } },
    },
    series: [
      {
        type: 'bar',
        data: items.map((item) => item.sample_size),
        itemStyle: { color: '#6f8cff', borderRadius: [0, 3, 3, 0] },
        barMaxWidth: 12,
        label: { show: true, position: 'right', color: '#8b8b8b', fontSize: 9 },
        animationDuration: 600,
      },
    ],
  }
  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 240 }} />
}

/** 持有期对比：把当前样本按命中率区间分档，看各持有期的分布差异 */
function HoldingCompare({
  items,
  holding,
}: {
  items: BacktestOverviewItem[]
  holding: number
}) {
  const rates = items.map((i) => i.hit_rate).filter((v): v is number => v !== null)
  if (!rates.length) return <p className="diag-caption">暂无数据</p>
  // 三档：偏弱 / 中性 / 偏强（相对 50% 与 60% 分界，仅作分布描述）
  const weak = rates.filter((r) => r < 0.5).length
  const mid = rates.filter((r) => r >= 0.5 && r < 0.6).length
  const strong = rates.filter((r) => r >= 0.6).length
  const total = rates.length
  const rows = [
    { label: '< 50%', count: weak, color: '#4ade80' },
    { label: '50–60%', count: mid, color: '#8b8b8b' },
    { label: '≥ 60%', count: strong, color: '#f87171' },
  ]
  return (
    <div className="bt-holding-compare">
      <p className="diag-caption">T+{holding} 命中率分档（共 {total} 个因子）</p>
      {rows.map((row) => (
        <div key={row.label} className="bt-holding-row">
          <span className="bt-holding-label">{row.label}</span>
          <span className="bt-holding-track">
            <i style={{ width: `${(row.count / total) * 100}%`, background: row.color }} />
          </span>
          <span className="bt-holding-num">{row.count}</span>
        </div>
      ))}
    </div>
  )
}

/** 相对基准分布：高于/低于多数类基准的因子占比（主区直方图不体现这一点） */
function AboveBaseDonut({
  summary,
  minSamples,
}: {
  summary: BacktestOverviewResponse['summary'] | undefined
  minSamples: number
}) {
  if (!summary || !summary.sufficient) return <p className="diag-caption">暂无充足样本</p>
  const above = summary.above_base
  const below = Math.max(summary.sufficient - above, 0)
  const option = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 个 ({d}%)' },
    legend: {
      bottom: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 6,
      textStyle: { color: '#858585', fontSize: 10 },
    },
    series: [
      {
        type: 'pie',
        radius: ['50%', '72%'],
        center: ['50%', '42%'],
        label: { show: false },
        data: [
          { value: above, name: '高于基准', itemStyle: { color: '#f87171' } },
          { value: below, name: '低于基准', itemStyle: { color: '#4ade80' } },
        ],
        animationDuration: 700,
      },
    ],
  }
  return (
    <>
      <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 170 }} />
      <p className="diag-caption">
        样本 ≥{minSamples} 的 {summary.sufficient} 个因子中，{above} 个命中率高于其基准
      </p>
    </>
  )
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