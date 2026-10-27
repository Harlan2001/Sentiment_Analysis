import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { fetchFactorPerformance } from '@/api/market'
import type { FactorPerformanceHolding, FactorPerformanceYear } from '@/types'

/**
 * 因子历史表现（事件研究）。
 *
 * 口径说明：
 * - 用 news_factor 做事件研究：某因子出现后 T+N 个交易日的 10Y 收益率变动
 * - 按交易日对齐；信号日 t 只用 t 及之前数据，收益从 t+1 起算（防未来函数）
 * - **同时给出多数类基准** —— 方向命中率的正确对照不是 50%，
 *   而是"无脑猜多数方向"的命中率，两者同屏供对照
 *
 * 展示取向：**呈现数据，不对因子下"有效/无效"的结论**，由读者自行判断。
 */

const HOLDING_ORDER = [1, 5, 20]

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function formatBp(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}bp`
}

export default function FactorPerformance({ factorCode }: { factorCode: string }) {
  const [holding, setHolding] = useState(5)
  const { data, isLoading, isError } = useQuery({
    queryKey: ['factor-performance', factorCode],
    queryFn: () => fetchFactorPerformance(factorCode),
    staleTime: 10 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <article className="factor-detail-card factor-performance-panel">
        <header><div><h2>历史表现</h2><p>加载中…</p></div></header>
      </article>
    )
  }

  const rows = data?.holding ?? []
  // 未计算过的因子：不报错，提示需先跑回测
  if (isError || !rows.length) {
    return (
      <article className="factor-detail-card factor-performance-panel">
        <header>
          <div>
            <h2>历史表现</h2>
            <p>该因子尚未计算历史表现</p>
          </div>
        </header>
        <div className="factor-detail-empty">
          历史表现由批量任务计算，可在服务端执行 <code>scripts/run_factor_backtest.py</code> 生成
        </div>
      </article>
    )
  }

  const active = rows.find((row) => row.holding_days === holding) ?? rows[0]
  const insufficient = active.sample_size < (data?.min_samples ?? 20)
  // 分年度数据按当前持有期筛选，保证切换器对图表同样生效
  const yearlyForHolding = (data?.yearly ?? []).filter(
    (row) => row.holding_days === active.holding_days,
  )

  return (
    <article className="factor-detail-card factor-performance-panel">
      <header>
        <div>
          <h2>历史表现</h2>
          <p>
            基于 {active.sample_size} 次历史事件
            {active.period_start && active.period_end
              ? ` · ${active.period_start} ~ ${active.period_end}`
              : ''}
          </p>
        </div>
        <div className="factor-detail-periods">
          {HOLDING_ORDER.map((value) => (
            <button
              type="button"
              key={value}
              className={holding === value ? 'active' : ''}
              onClick={() => setHolding(value)}
            >
              T+{value}
            </button>
          ))}
        </div>
      </header>

      {/* 各持有期明细表 */}
      <table className="factor-performance-table">
        <thead>
          <tr>
            <th>持有期</th>
            <th>样本</th>
            <th>方向命中率</th>
            <th>多数类基准</th>
            <th>平均变动</th>
            <th>中位数</th>
          </tr>
        </thead>
        <tbody>
          {/* 只显示当前持有期：切换器 + 图表 + 表格三者联动 */}
          <PerformanceRow row={active} minSamples={data?.min_samples ?? 20} />
        </tbody>
      </table>

      {insufficient && (
        <p className="factor-performance-note">
          当前持有期样本不足 {data?.min_samples ?? 20} 条，统计结果波动较大，仅供参考。
        </p>
      )}

      {/* 分年度稳定性：跟随当前持有期 */}
      {yearlyForHolding.length ? (
        <>
          <header className="factor-performance-subhead">
            <div>
              <h2>分年度表现（T+{active.holding_days}）</h2>
              <p>观察该因子在不同年份的表现是否稳定</p>
            </div>
          </header>
          <YearlyChart rows={yearlyForHolding} />
        </>
      ) : null}

      {data?.computed_at && (
        <p className="factor-performance-foot">
          计算于 {String(data.computed_at).slice(0, 16)} · 按交易日对齐 · 对照基准为多数类基准（非 50%）
        </p>
      )}
    </article>
  )
}

function PerformanceRow({
  row,
  minSamples,
}: {
  row: FactorPerformanceHolding
  minSamples: number
}) {
  const insufficient = row.sample_size < minSamples
  return (
    <tr>
      <td>T+{row.holding_days}</td>
      <td className="num">{row.sample_size}</td>
      <td className="num strong">
        {insufficient ? '样本不足' : formatPercent(row.hit_rate)}
      </td>
      <td className="num">{formatPercent(row.majority_base)}</td>
      <td className="num">{formatBp(row.avg_move_bp)}</td>
      <td className="num">{formatBp(row.median_move_bp)}</td>
    </tr>
  )
}

/** 分年度折线：命中率 vs 基准，看两者是否长期贴合（贴近即无明显优势） */
function YearlyChart({ rows }: { rows: FactorPerformanceYear[] }) {
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) =>
        [
          `${params[0]?.axisValue ?? ''} 年`,
          ...params.map((p) => `${p.marker}${p.seriesName} ${(Number(p.value) * 100).toFixed(1)}%`),
        ].join('<br/>'),
    },
    legend: {
      top: 0,
      right: 0,
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 6,
      textStyle: { color: '#858585', fontSize: 11 },
    },
    grid: { left: 48, right: 16, top: 30, bottom: 24 },
    xAxis: {
      type: 'category',
      data: rows.map((row) => row.period_label),
      axisLabel: { color: '#777', fontSize: 10 },
      axisLine: { lineStyle: { color: '#333' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#777', fontSize: 10, formatter: (v: number) => `${v * 100}%` },
      splitLine: { lineStyle: { color: '#262626' } },
    },
    series: [
      {
        name: '命中率',
        type: 'line',
        smooth: true,
        symbolSize: 5,
        data: rows.map((row) => row.hit_rate),
        lineStyle: { color: '#6f8cff', width: 2 },
        itemStyle: { color: '#6f8cff' },
      },
      {
        name: '多数类基准',
        type: 'line',
        smooth: true,
        symbolSize: 4,
        data: rows.map((row) => row.majority_base),
        lineStyle: { color: '#8b8b8b', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#8b8b8b' },
      },
    ],
  }
  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height: 180 }} />
}