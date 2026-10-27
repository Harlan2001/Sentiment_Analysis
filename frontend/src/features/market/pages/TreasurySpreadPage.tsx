import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { fetchTreasurySpread, syncTreasury } from '@/api/treasury'
import { Skeleton } from '@/components/ui'

/**
 * 中美利差。
 *
 * 数据源：美国财政部官方 CSV（合规、免密钥）+ 库内中债 10Y。
 * **注意**：中美交易日不同，利差只在双方都有数据的日期计算，不插值。
 *
 * 主指标为**历史分位** —— 利差绝对值因中美利差长期为负（倒挂），
 * 单看数字无法判断"倒挂是加深还是收窄"，必须看相对自身历史的位置。
 */

const TERM_LABELS: Record<string, string> = { '2Y': '2年', '10Y': '10年', '30Y': '30年' }
const CN_COLOR = '#7fd4c1'
const US_COLOR = '#f0a0a0'
const SPREAD_COLOR = '#6f8cff'

function formatBp(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(digits)}bp`
}

/** 分位解读：中美利差为负是常态，故用"倒挂深浅"表述 */
function percentileHint(percentile: number | undefined): { text: string; tone: string } {
  if (percentile === undefined) return { text: '', tone: '' }
  if (percentile <= 20) return { text: '处于历史低位，倒挂相对较深', tone: 'low' }
  if (percentile >= 80) return { text: '处于历史高位，倒挂相对较浅', tone: 'high' }
  return { text: '处于历史中位区间', tone: 'mid' }
}

/** 位置条宽度：按区间归一，保留最小可见宽度（避免恰为最小值时不可见） */
function barWidth(value: number | null | undefined, min?: number, max?: number): number {
  if (value === null || value === undefined) return 0
  const lower = min ?? 0
  const upper = max ?? 1
  if (upper <= lower) return 100
  return Math.max(Math.min(((value - lower) / (upper - lower)) * 100, 100), 6)
}

export default function TreasurySpreadPage() {
  const queryClient = useQueryClient()
  const [term, setTerm] = useState('10Y')
  const [notice, setNotice] = useState('')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['treasury-spread', term],
    queryFn: () => fetchTreasurySpread(term),
    staleTime: 5 * 60 * 1000,
  })

  const sync = useMutation({
    mutationFn: () => syncTreasury(),
    onSuccess: (result) => {
      setNotice(`同步完成（${result.year} 年）：获取 ${result.fetched} 条，新增 ${result.inserted}，更新 ${result.updated}`)
      queryClient.invalidateQueries({ queryKey: ['treasury-spread'] })
    },
    onError: (error: Error) => setNotice(`同步失败：${error.message}`),
  })

  const latest = data?.latest
  const hint = percentileHint(data?.percentile)

  return (
    <div className="home-section-page">
      <div className="home-section-grid">
        <main className="home-section-main space-y-4">
          <header className="flex flex-wrap items-start justify-between gap-3 pt-2">
            <div>
              <h1 className="text-lg font-bold text-white">中美利差</h1>
              <p className="mt-1 text-xs text-gray-500">
                中债收益率 − 美债收益率（美国财政部官方数据）
                {latest ? ` · 数据日期 ${latest.date}` : ''}
              </p>
            </div>
            <button
              onClick={() => sync.mutate()}
              disabled={sync.isPending}
              className="rounded-lg border border-[#3d3d42] px-3 py-2 text-xs text-gray-200 hover:bg-[#1b1b1d] disabled:opacity-50"
            >
              {sync.isPending ? '同步中…' : '同步美债数据'}
            </button>
          </header>

          {notice && <p className="diag-caption">{notice}</p>}

          <div className="factor-view-tabs">
            {(data?.available_terms ?? ['2Y', '10Y', '30Y']).map((item) => (
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
            <Empty text="中美利差数据加载失败，请稍后重试" />
          ) : !latest ? (
            <Empty text="暂无美债数据，点击右上角「同步美债数据」拉取" />
          ) : (
            <>
              <section className="cs-hero">
                <div className="cs-hero-main">
                  <span className="cs-hero-label">当前{TERM_LABELS[term] ?? term}利差</span>
                  <b className="cs-hero-value">{formatBp(latest.spread_bp)}</b>
                  {data.percentile !== undefined && (
                    <span className={`cs-percentile ${hint.tone}`}>历史分位 {data.percentile}%</span>
                  )}
                </div>
                <div className="cs-hero-sub">
                  中债 {latest.cn.toFixed(2)}% − 美债 {latest.us.toFixed(2)}%
                </div>
                <div className="cs-hero-bars">
                  <div className="cs-bar-row">
                    <span className="cs-bar-name">当前</span>
                    <span className="cs-bar-track">
                      <i className="cs-bar-fill current" style={{ width: `${barWidth(latest.spread_bp, data.min_bp, data.max_bp)}%` }} />
                    </span>
                    <span className="cs-bar-num">{formatBp(latest.spread_bp)}</span>
                  </div>
                  <div className="cs-bar-row">
                    <span className="cs-bar-name">均值</span>
                    <span className="cs-bar-track">
                      <i className="cs-bar-fill avg" style={{ width: `${barWidth(data.avg_bp, data.min_bp, data.max_bp)}%` }} />
                    </span>
                    <span className="cs-bar-num">{formatBp(data.avg_bp)}</span>
                  </div>
                </div>
                <div className="cs-hero-facts">
                  <span>
                    近 {data.sample_size} 个交易日 · 区间 {formatBp(data.min_bp)} – {formatBp(data.max_bp)}
                  </span>
                  {hint.text && <span className="cs-hint">{hint.text}</span>}
                </div>
              </section>

              <Card title={`${TERM_LABELS[term] ?? term}中美利差走势（bp）`}>
                <SpreadChart series={data.series} />
              </Card>

              <Card title="中债 vs 美债收益率">
                <DualCurveChart series={data.series} />
              </Card>

              <p className="diag-footnote">
                数据来源：美国财政部官方公开数据（免密钥）· 中债收益率来自库内 yield_data。
                <br />
                中美交易日不同，利差**只在双方都有数据的日期计算，不插值**。
              </p>
            </>
          )}
        </main>

        <aside className="home-section-sidebar cs-sidebar">
          <div className="space-y-4">
            <ChartCard title="美债收益率曲线">
              <TreasuryCurveChart curve={data?.curve ?? []} />
            </ChartCard>

            {/* 利差历史位置：主区看着走势，此处把当前值放到历史区间上看清"高低" */}
            <ChartCard title="利差历史位置">
              <RangeGauge
                current={data?.latest?.spread_bp ?? null}
                min={data?.min_bp ?? null}
                max={data?.max_bp ?? null}
                avg={data?.avg_bp ?? null}
                percentile={data?.percentile ?? null}
              />
            </ChartCard>

            {/* 美债曲线形态：陡峭/平坦判断，主区的曲线图不含形态解读 */}
            <ChartCard title="美债曲线形态">
              <CurveShapeWidget curve={data?.curve ?? []} />
            </ChartCard>

            <p className="diag-footnote">
              {data?.sample_size ? `样本 ${data.sample_size} 个交易日 · ` : ''}
              中美交易日不同，利差只在双方均有数据的日期计算
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
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v}bp` },
    grid: { left: 56, right: 18, top: 14, bottom: 26 },
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

function DualCurveChart({ series }: { series: { date: string; cn: number; us: number }[] }) {
  if (series.length < 2) return <p className="diag-caption">样本不足</p>
  const option = {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v}%` },
    legend: {
      top: 0, right: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 6,
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
      { name: '中债', type: 'line', smooth: true, showSymbol: false, data: series.map((i) => i.cn), lineStyle: { color: CN_COLOR, width: 2 }, itemStyle: { color: CN_COLOR } },
      { name: '美债', type: 'line', smooth: true, showSymbol: false, data: series.map((i) => i.us), lineStyle: { color: US_COLOR, width: 2 }, itemStyle: { color: US_COLOR } },
    ],
  }
  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 200 }} />
}

function TreasuryCurveChart({ curve }: { curve: { term: string; value: number }[] }) {
  if (!curve.length) return <p className="diag-caption">暂无数据</p>
  const option = {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v}%` },
    grid: { left: 44, right: 20, top: 8, bottom: 22 },
    xAxis: {
      type: 'category',
      data: curve.map((item) => TERM_LABELS[item.term] ?? item.term),
      axisLabel: { color: '#777', fontSize: 10 },
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
        type: 'bar',
        data: curve.map((item) => item.value),
        itemStyle: { color: US_COLOR, borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 32,
        label: { show: true, position: 'top', color: '#8b8b8b', fontSize: 10 },
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
/** 利差历史位置：把当前值放到 [min, max] 区间上看清高低，比单看数字直观 */
function RangeGauge({
  current,
  min,
  max,
  avg,
  percentile,
}: {
  current: number | null
  min: number | null
  max: number | null
  avg: number | null
  percentile: number | null
}) {
  if (current === null || min === null || max === null) {
    return <p className="diag-caption">暂无数据</p>
  }
  const span = max - min || 1
  const pos = Math.max(Math.min(((current - min) / span) * 100, 100), 0)
  const avgPos = avg === null ? null : Math.max(Math.min(((avg - min) / span) * 100, 100), 0)
  return (
    <div className="ts-gauge">
      <div className="ts-gauge-track">
        {avgPos !== null && <i className="ts-gauge-avg" style={{ left: `${avgPos}%` }} />}
        <i className="ts-gauge-marker" style={{ left: `${pos}%` }} />
      </div>
      <div className="ts-gauge-labels">
        <span>{min.toFixed(0)}bp</span>
        <span className="ts-gauge-current">
          当前 {current.toFixed(0)}bp{percentile !== null ? ` · 分位 ${percentile}%` : ''}
        </span>
        <span>{max.toFixed(0)}bp</span>
      </div>
    </div>
  )
}

/** 美债曲线形态：用 10Y-2Y 判断陡峭/平坦，这是主区曲线图不提供的解读 */
function CurveShapeWidget({ curve }: { curve: { term: string; value: number }[] }) {
  if (curve.length < 2) return <p className="diag-caption">暂无数据</p>
  const byTerm = Object.fromEntries(curve.map((item) => [item.term, item.value]))
  const short = byTerm['2Y']
  const mid = byTerm['10Y']
  const long = byTerm['30Y']

  const spread10Y2Y = short !== undefined && mid !== undefined ? (mid - short) * 100 : null
  const spread30Y10Y = mid !== undefined && long !== undefined ? (long - mid) * 100 : null

  const shape =
    spread10Y2Y === null
      ? null
      : spread10Y2Y > 0
        ? spread10Y2Y > 80
          ? '陡峭'
          : '正常上倾'
        : '倒挂'

  return (
    <div className="ts-shape">
      {spread10Y2Y !== null && (
        <div className="ts-shape-row">
          <span>10Y − 2Y</span>
          <b className={spread10Y2Y >= 0 ? 'up' : 'down'}>
            {spread10Y2Y > 0 ? '+' : ''}
            {spread10Y2Y.toFixed(0)}bp
          </b>
        </div>
      )}
      {spread30Y10Y !== null && (
        <div className="ts-shape-row">
          <span>30Y − 10Y</span>
          <b className={spread30Y10Y >= 0 ? 'up' : 'down'}>
            {spread30Y10Y > 0 ? '+' : ''}
            {spread30Y10Y.toFixed(0)}bp
          </b>
        </div>
      )}
      {shape && (
        <p className="ts-shape-note">
          曲线形态：<b>{shape}</b>
          {shape === '倒挂' ? '（短端高于长端，通常反映紧缩预期）' : ''}
        </p>
      )}
    </div>
  )
}
