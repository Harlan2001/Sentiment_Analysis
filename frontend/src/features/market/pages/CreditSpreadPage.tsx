import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { fetchCreditSpreadOverview, syncCreditSpread } from '@/api/creditSpread'
import { Skeleton } from '@/components/ui'

/**
 * 信用利差。
 *
 * 数据源：中债中短期票据收益率曲线（与国债曲线同一接口，参数不同）。
 * 利差 = 信用债收益率 − 同期限国债收益率。
 *
 * **主指标是历史分位**，不是利差绝对值 —— 利差 5bp 是高是低，
 * 取决于它相对自身历史的位置，单看数字无法判断。
 *
 * 限制：该数据源只提供**整体曲线**，不能按 AAA/AA 分档（接口不支持）。
 */

const TERM_LABELS: Record<string, string> = {
  '1Y': '1年', '2Y': '2年', '3Y': '3年', '5Y': '5年', '7Y': '7年', '10Y': '10年',
}

const SPREAD_COLOR = '#6f8cff'
const CREDIT_COLOR = '#f0a0a0'
const GOV_COLOR = '#7fd4c1'

function formatBp(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(digits)}bp`
}

/** 分位对应的解读：低分位=利差窄=信用风险偏好高 */
function percentileHint(percentile: number | undefined): { text: string; tone: string } {
  if (percentile === undefined) return { text: '', tone: '' }
  if (percentile <= 20) return { text: '处于历史低位，信用利差偏窄', tone: 'low' }
  if (percentile >= 80) return { text: '处于历史高位，信用利差偏宽', tone: 'high' }
  return { text: '处于历史中位区间', tone: 'mid' }
}

/**
 * 位置条宽度：按 [min, max] 区间归一，但**保证最小可见宽度**。
 * 否则当某值恰为区间最小值时宽度为 0，条形完全消失（当前利差常处于极小值）。
 */
function barWidth(value: number | null | undefined, min?: number, max?: number): number {
  if (value === null || value === undefined) return 0
  const lower = min ?? 0
  const upper = max ?? 1
  if (upper <= lower) return 100
  const ratio = ((value - lower) / (upper - lower)) * 100
  return Math.max(Math.min(ratio, 100), 6)
}

export default function CreditSpreadPage() {
  const queryClient = useQueryClient()
  const [term, setTerm] = useState('10Y')
  const [notice, setNotice] = useState('')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['credit-spread', term],
    queryFn: () => fetchCreditSpreadOverview(term),
    staleTime: 5 * 60 * 1000,
  })

  const sync = useMutation({
    mutationFn: () => syncCreditSpread(365),
    onSuccess: (result) => {
      setNotice(
        `同步完成：获取 ${result.fetched} 条，新增 ${result.inserted}，更新 ${result.updated}`,
      )
      queryClient.invalidateQueries({ queryKey: ['credit-spread'] })
    },
    onError: (error: Error) => setNotice(`同步失败：${error.message}`),
  })

  const latest = data?.latest
  const hint = percentileHint(data?.percentile)
  const terms = data?.available_terms ?? []

  return (
    <div className="home-section-page">
      <div className="home-section-grid">
        <main className="home-section-main space-y-4">
          <header className="flex flex-wrap items-start justify-between gap-3 pt-2">
            <div>
              <h1 className="text-lg font-bold text-white">信用利差</h1>
              <p className="mt-1 text-xs text-gray-500">
                中债中短期票据收益率 − 同期限国债收益率
                {latest ? ` · 数据日期 ${latest.date}` : ''}
              </p>
            </div>
            <button
              onClick={() => sync.mutate()}
              disabled={sync.isPending}
              className="rounded-lg border border-[#3d3d42] px-3 py-2 text-xs text-gray-200 hover:bg-[#1b1b1d] disabled:opacity-50"
            >
              {sync.isPending ? '同步中…' : '同步数据'}
            </button>
          </header>

          {notice && <p className="diag-caption">{notice}</p>}

          {/* 期限切换 */}
          <div className="factor-view-tabs">
            {terms.map((item) => (
              <button
                key={item}
                onClick={() => setTerm(item)}
                className={`factor-view-tab${item === term ? ' active' : ''}`}
              >
                {TERM_LABELS[item] ?? item}
              </button>
            ))}
          </div>

          {isLoading ? (
            <Skeleton height="360px" variant="rectangular" />
          ) : isError || !data ? (
            <Empty text="信用利差数据加载失败，请稍后重试" />
          ) : !latest ? (
            <Empty text="暂无信用债曲线数据，点击右上角「同步数据」拉取" />
          ) : (
            <>
              {/* 概览：当前利差 + 历史分位 */}
              <section className="cs-hero">
                <div className="cs-hero-main">
                  <span className="cs-hero-label">当前{TERM_LABELS[term] ?? term}利差</span>
                  <b className="cs-hero-value">{formatBp(latest.spread_bp)}</b>
                  {data.percentile !== undefined && (
                    <span className={`cs-percentile ${hint.tone}`}>
                      历史分位 {data.percentile}%
                    </span>
                  )}
                </div>
                <div className="cs-hero-sub">
                  信用债 {latest.credit.toFixed(2)}% − 国债 {latest.gov.toFixed(2)}%
                </div>
                <div className="cs-hero-bars">
                  <div className="cs-bar-row">
                    <span className="cs-bar-name">当前</span>
                    <span className="cs-bar-track">
                      <i
                        className="cs-bar-fill current"
                        style={{
                          width: `${barWidth(latest.spread_bp, data.min_bp, data.max_bp)}%`,
                        }}
                      />
                    </span>
                    <span className="cs-bar-num">{formatBp(latest.spread_bp)}</span>
                  </div>
                  <div className="cs-bar-row">
                    <span className="cs-bar-name">均值</span>
                    <span className="cs-bar-track">
                      <i
                        className="cs-bar-fill avg"
                        style={{ width: `${barWidth(data.avg_bp, data.min_bp, data.max_bp)}%` }}
                      />
                    </span>
                    <span className="cs-bar-num">{formatBp(data.avg_bp)}</span>
                  </div>
                </div>
                <div className="cs-hero-facts">
                  <span>
                    近 {data.sample_size} 个交易日 · 区间 {formatBp(data.min_bp, 0)} –{' '}
                    {formatBp(data.max_bp, 0)}
                  </span>
                  {hint.text && <span className="cs-hint">{hint.text}</span>}
                </div>
              </section>

              {/* 利差走势（主图） */}
              <Card title={`${TERM_LABELS[term] ?? term}信用利差走势（bp）`}>
                <SpreadChart series={data.series} />
              </Card>

              {/* 双曲线对照 */}
              <Card title="信用债 vs 国债收益率">
                <DualCurveChart series={data.series} />
              </Card>

              {/* 期限结构对比见右栏（主区不重复展示同一组数据） */}

              <p className="diag-footnote">
                数据来源：中债中短期票据收益率曲线（官方公开接口）· 利差 = 信用债 − 同期限国债。
                <br />
                该曲线为**整体口径**，不含 AAA/AA 评级细分（数据源不提供分评级曲线）。
              </p>
            </>
          )}
        </main>

        <aside className="home-section-sidebar cs-sidebar">
          <div className="space-y-4">
            <ChartCard title="各期限利差对比">
              <TermSpreadChart items={data?.term_structure ?? []} />
            </ChartCard>
            <ChartCard title="期限利差占比">
              <TermSharePie items={data?.term_structure ?? []} />
            </ChartCard>
            <p className="diag-footnote">
              {data?.sample_size ? `样本 ${data.sample_size} 个交易日 · ` : ''}
              整体曲线口径，不区分评级
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}

function SpreadChart({ series }: { series: { date: string; spread_bp: number }[] }) {
  if (series.length < 2) return <p className="diag-caption">样本不足，无法绘制走势</p>
  const option = {
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number) => `${v}bp`,
      formatter: (params: any[]) =>
        `${params[0]?.axisValue ?? ''}<br/>${params[0]?.marker ?? ''}利差 ${params[0]?.value}bp`,
    },
    grid: { left: 50, right: 18, top: 14, bottom: 26 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: series.map((item) => item.date.slice(5)),
      axisLabel: { color: '#777', fontSize: 9, interval: Math.ceil(series.length / 8) },
      axisLine: { lineStyle: { color: '#333' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: '#777', fontSize: 10, formatter: '{value}bp' },
      splitLine: { lineStyle: { color: '#262626' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: series.map((item) => item.spread_bp),
        lineStyle: { color: SPREAD_COLOR, width: 2 },
        itemStyle: { color: SPREAD_COLOR },
        areaStyle: { color: 'rgba(111,140,255,0.12)' },
      },
    ],
  }
  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 240 }} />
}

function DualCurveChart({
  series,
}: {
  series: { date: string; credit: number; gov: number }[]
}) {
  if (series.length < 2) return <p className="diag-caption">样本不足</p>
  const option = {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v}%` },
    legend: {
      top: 0,
      right: 0,
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 6,
      textStyle: { color: '#858585', fontSize: 11 },
    },
    grid: { left: 50, right: 18, top: 30, bottom: 26 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: series.map((item) => item.date.slice(5)),
      axisLabel: { color: '#777', fontSize: 9, interval: Math.ceil(series.length / 8) },
      axisLine: { lineStyle: { color: '#333' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: '#777', fontSize: 10, formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#262626' } },
    },
    series: [
      {
        name: '信用债',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: series.map((item) => item.credit),
        lineStyle: { color: CREDIT_COLOR, width: 2 },
        itemStyle: { color: CREDIT_COLOR },
      },
      {
        name: '国债',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: series.map((item) => item.gov),
        lineStyle: { color: GOV_COLOR, width: 2 },
        itemStyle: { color: GOV_COLOR },
      },
    ],
  }
  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 200 }} />
}

/** 期限利差占比饼图：各期限对总利差的贡献占比。
 *
 * 说明：这是"结构占比"而非"绝对值"——回答的是"当前利差主要由哪些期限贡献"，
 * 与右侧的横向对比图（看各期限高低）互补而非重复。
 */
function TermSharePie({
  items,
}: {
  items: { term: string; spread_bp: number }[]
}) {
  if (!items.length) return <p className="diag-caption">暂无数据</p>
  const total = items.reduce((sum, item) => sum + Math.max(item.spread_bp, 0), 0)
  if (total <= 0) return <p className="diag-caption">各期限利差均为非正值，无法计算占比</p>

  const palette = ['#6f8cff', '#66cabb', '#d6a85f', '#a79bd0', '#f0a0a0', '#7fd4c1', '#8b9ae0']
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => `${params.name}<br/>${params.value}bp · ${params.percent}%`,
    },
    legend: {
      bottom: 0,
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 6,
      textStyle: { color: '#858585', fontSize: 10 },
    },
    series: [
      {
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['50%', '42%'],
        avoidLabelOverlap: true,
        label: { show: false },
        data: items.map((item, index) => ({
          name: TERM_LABELS[item.term] ?? item.term,
          value: Math.max(item.spread_bp, 0),
          itemStyle: { color: palette[index % palette.length] },
        })),
      },
    ],
  }
  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 190 }} />
}

/** 右栏：各期限利差对比（横条，看期限结构高低）。 */
function TermSpreadChart({ items }: { items: { term: string; spread_bp: number }[] }) {
  if (!items.length) return <p className="diag-caption">暂无数据</p>
  const option = {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v}bp` },
    grid: { left: 46, right: 26, top: 8, bottom: 22 },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#777', fontSize: 9, formatter: '{value}bp' },
      splitLine: { lineStyle: { color: '#262626' } },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: items.map((item) => TERM_LABELS[item.term] ?? item.term),
      axisLabel: { color: '#a7a7a7', fontSize: 10 },
      axisLine: { lineStyle: { color: '#333' } },
    },
    series: [
      {
        type: 'bar',
        data: items.map((item) => item.spread_bp),
        itemStyle: { color: SPREAD_COLOR, borderRadius: [0, 3, 3, 0] },
        barMaxWidth: 14,
        label: { show: true, position: 'right', color: '#8b8b8b', fontSize: 10 },
      },
    ],
  }
  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 180 }} />
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
      <h2 className="mb-2 text-sm font-medium text-gray-400">{title}</h2>
      {children}
    </section>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
      <h2 className="mb-3 text-sm font-medium text-gray-400">{title}</h2>
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