import React, { useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { useForecastDiagnosis } from '@/features/market/hooks/useForecastApi'
import { Skeleton } from '@/components/ui'
import type { ForecastHorizonDiagnosis, ForecastQuality } from '@/types'

/**
 * 准确度诊断：把历史预测与事后实际收益率对账。
 *
 * 定位是**诊断工具，不是成绩单**。三条展示原则：
 * 1. 命中率旁**必须**同时显示多数类基准 —— 方向预测的正确对照线不是 50%，
 *    只看命中率会被误读成"接近随机"，而真实问题常是系统性方向偏置。
 * 2. 三档标签（有效/噪音/风险）直接回答"能不能用"。
 * 3. 校准度是主图：预测看涨占比 vs 实际上涨占比，长期背离即说明偏置。
 *
 * 周期采用**切换**而非并列：三个周期的问题程度差别大（−19.5 / −30.1 / −54.0pt），
 * 单屏看完一个周期比滚动三个更清楚；底部保留另两周期的横向参照，避免丢失对比。
 */

const QUALITY_META: Record<ForecastQuality, { label: string; className: string }> = {
  effective: { label: '有效', className: 'diag-badge effective' },
  noise: { label: '噪音', className: 'diag-badge noise' },
  risk: { label: '风险', className: 'diag-badge risk' },
}

const UP = '#f87171'
const DOWN = '#4ade80'
const HORIZON_ORDER = ['日', '周', '月']

function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

function formatBp(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(2)}bp`
}

function formatDelta(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const points = (value * 100).toFixed(1)
  return `${value >= 0 ? '+' : ''}${points}pt`
}

export default function ForecastDiagnosis() {
  const { data, isLoading, isError } = useForecastDiagnosis()
  const [horizon, setHorizon] = useState('日')

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton height="90px" variant="rectangular" />
        <Skeleton height="300px" variant="rectangular" />
      </div>
    )
  }

  if (isError || !data) {
    return <Empty text="诊断数据加载失败，请稍后重试" />
  }

  const evaluable = data.horizons.filter((item) => item.sample_size > 0)
  if (!evaluable.length) {
    return <Empty text="暂无可评估的历史预测（需报告已到期且当日有行情数据）" />
  }

  // 按固定周期顺序排列，保证切换项顺序稳定
  const horizons = HORIZON_ORDER.map((key) =>
    data.horizons.find((item) => item.horizon === key),
  ).filter((item): item is ForecastHorizonDiagnosis => Boolean(item))
  const active = horizons.find((item) => item.horizon === horizon) ?? horizons[0]
  const others = horizons.filter((item) => item.horizon !== active.horizon)
  const activeMeta = QUALITY_META[active.quality] ?? QUALITY_META.noise

  return (
    <>
      <div className="diag-toolbar">
        <div className="factor-view-tabs diag-horizon-tabs">
          {horizons.map((item) => (
            <button
              key={item.horizon}
              onClick={() => setHorizon(item.horizon)}
              className={`factor-view-tab${item.horizon === active.horizon ? ' active' : ''}`}
            >
              {item.horizon}度
            </button>
          ))}
        </div>
        <span className={activeMeta.className}>{activeMeta.label}</span>
      </div>

      {/* 核心指标：命中率 vs 基准，用对照条直观呈现差距 */}
      <section className="diag-hero">
        <div className="diag-hero-head">
          <span className="diag-hero-title">
            命中率 <b>{formatPercent(active.hit_rate)}</b>
            <i className={(active.delta ?? 0) >= 0 ? 'up' : 'down'}>
              {formatDelta(active.delta)}
            </i>
          </span>
          <span className="diag-hero-facts">
            <span>
              基准 <b>{formatPercent(active.majority_base)}</b>
            </span>
            <span>
              误差 <b>{formatBp(active.avg_abs_error_bp)}</b>
            </span>
            <span>
              样本 <b>{active.sample_size}</b>
            </span>
            <span>
              T+{active.holding_days}
            </span>
            {active.confidence_interval && (
              <span>
                95% <b>{formatPercent(active.confidence_interval[0])}–{formatPercent(active.confidence_interval[1])}</b>
              </span>
            )}
          </span>
        </div>
        <div className="diag-hero-bars">
          <div className="diag-bar-row">
            <span className="diag-bar-name">模型</span>
            <span className="diag-bar-track">
              <i
                className="diag-bar-fill model"
                style={{ width: `${Math.min((active.hit_rate ?? 0) * 100, 100)}%` }}
              />
            </span>
            <span className="diag-bar-num">{formatPercent(active.hit_rate)}</span>
          </div>
          <div className="diag-bar-row">
            <span className="diag-bar-name">基准</span>
            <span className="diag-bar-track">
              <i
                className="diag-bar-fill bench"
                style={{ width: `${Math.min((active.majority_base ?? 0) * 100, 100)}%` }}
              />
            </span>
            <span className="diag-bar-num">{formatPercent(active.majority_base)}</span>
          </div>
        </div>
      </section>

      {/* 校准度（主图） */}
      <Card title={`校准度 · ${active.horizon}度预测`}>
        <p className="diag-caption">
          两条线长期背离，说明模型存在系统性方向偏置（而非随机误差）。
        </p>
        <CalibrationChart item={active} height={240} />
      </Card>

      {/* 置信度分档 */}
      <Card title="置信度分档 · 模型说有把握时是否真的更准">
        <ConfidenceTable horizons={[active]} />
      </Card>

      {/* 其余周期横向参照 */}
      {others.length > 0 && (
        <section className="diag-others">
          <span className="diag-others-label">其它周期</span>
          {others.map((item) => {
            const meta = QUALITY_META[item.quality] ?? QUALITY_META.noise
            return (
              <button
                key={item.horizon}
                className="diag-other-item"
                onClick={() => setHorizon(item.horizon)}
              >
                <span className="diag-other-name">{item.horizon}度</span>
                <span className="diag-other-rate">{formatPercent(item.hit_rate)}</span>
                <span className="diag-other-delta">
                  基准 {formatPercent(item.majority_base)}
                </span>
                <span className={meta.className}>{meta.label}</span>
              </button>
            )
          })}
        </section>
      )}

      <p className="diag-footnote">
        共 {data.report_count} 份报告 · 口径 {data.period} 国债收益率 · 按交易日对齐 ·
        生成于 {data.generated_at} · 对照基准为多数类基准（事后无脑猜多数方向），非 50%
      </p>
    </>
  )
}

/** 右侧功能栏（诊断视图）：把主区放不下的"结论/对比/口径"信息收进来。
 *
 * 为什么是这三块：
 * - 结论：把"能不能用"一句话讲完，不必让用户自己从数字里推
 * - 其它周期：三个周期的问题程度差别很大，此处保留横向对比
 * - 口径：命中率高低的判定标准（基准、样本量、区间），防止误读
 */
export function ForecastDiagnosisAside() {
  const { data, isLoading, isError } = useForecastDiagnosis()
  const [horizon, setHorizon] = useState('日')

  if (isLoading) {
    return (
      <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
        <Skeleton height="160px" variant="rectangular" />
      </section>
    )
  }
  if (isError || !data) {
    return (
      <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
        <p className="diag-caption">诊断数据加载失败</p>
      </section>
    )
  }

  const horizons = HORIZON_ORDER.map((key) =>
    data.horizons.find((item) => item.horizon === key),
  ).filter((item): item is ForecastHorizonDiagnosis => Boolean(item))
  if (!horizons.length) return null

  const active = horizons.find((item) => item.horizon === horizon) ?? horizons[0]
  const meta = QUALITY_META[active.quality] ?? QUALITY_META.noise

  return (
    <>
      {/* 结论 */}
      <section className="diag-aside-card">
        <div className="diag-aside-head">
          <h2>当前结论</h2>
          <span className={meta.className}>{meta.label}</span>
        </div>
        <p className="diag-aside-lead">{VERDICT_TEXT[active.quality]}</p>
        {active.delta !== null && (
          <p className="diag-aside-sub">
            {active.horizon}度命中率 {formatPercent(active.hit_rate)}，较无脑基准
            {active.delta >= 0 ? '高' : '低'} {Math.abs(active.delta * 100).toFixed(1)} 个点
          </p>
        )}
        {(active.horizon === '周' || active.horizon === '月') &&
          active.predicted_up_share !== null &&
          active.predicted_up_share >= 0.85 && (
            <p className="diag-aside-warn">
              该周期 {(active.predicted_up_share * 100).toFixed(0)}% 的预测都看涨，
              而实际仅 {formatPercent(active.actual_up_share)} 上涨 —— 存在明显方向偏置。
            </p>
          )}
      </section>

      {/* 其它周期横向对比 */}
      <section className="diag-aside-card">
        <h2>周期对比</h2>
        <ul className="diag-aside-list">
          {horizons.map((item) => {
            const itemMeta = QUALITY_META[item.quality] ?? QUALITY_META.noise
            return (
              <li key={item.horizon}>
                <button
                  className={item.horizon === active.horizon ? 'active' : ''}
                  onClick={() => setHorizon(item.horizon)}
                >
                  <span className="diag-aside-name">{item.horizon}度</span>
                  <span className="diag-aside-rate">{formatPercent(item.hit_rate)}</span>
                  <span className={itemMeta.className}>{itemMeta.label}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </section>

      {/* 判定口径 */}
      <section className="diag-aside-card">
        <h2>判定口径</h2>
        <ul className="diag-aside-notes">
          <li>
            基准取<b>多数类基准</b>（事后无脑猜多数方向），不是 50%。
          </li>
          <li>
            区间整体高于基准记<b>有效</b>，低于基准记<b>风险</b>，无显著差异记<b>噪音</b>。
          </li>
          <li>样本少于 20 的分档不展示，避免小样本得出误导性结论。</li>
          <li>按交易日对齐，不按自然日。</li>
        </ul>
        <p className="diag-aside-meta">
          {data.report_count} 份报告 · {data.period} · {data.generated_at}
        </p>
      </section>
    </>
  )
}

const VERDICT_TEXT: Record<ForecastQuality, string> = {
  effective: '显著优于无脑基准，该周期的方向判断具备参考价值。',
  noise: '与无脑基准无显著差异，方向判断未提供额外信息。',
  risk: '显著弱于无脑基准，方向判断目前不建议直接采信。',
}

function CalibrationChart({
  item,
  height = 200,
}: {
  item: ForecastHorizonDiagnosis
  height?: number
}) {
  const points = item.calibration
  if (!points.length) {
    return <p className="diag-caption">该周期暂无足够的月度样本可绘制趋势。</p>
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) =>
        [
          `${params[0]?.axisValue ?? ''}　样本 ${points[params[0]?.dataIndex]?.sample_size ?? '—'}`,
          ...params.map(
            (p) => `${p.marker}${p.seriesName} ${(Number(p.value) * 100).toFixed(1)}%`,
          ),
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
    grid: { left: 52, right: 20, top: 34, bottom: 26 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: points.map((p) => p.month),
      axisLabel: { color: '#777', fontSize: 10 },
      axisLine: { lineStyle: { color: '#333' } },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1,
      axisLabel: { color: '#777', fontSize: 10, formatter: (v: number) => `${v * 100}%` },
      splitLine: { lineStyle: { color: '#262626' } },
    },
    series: [
      {
        name: '预测看涨占比',
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbolSize: 5,
        data: points.map((p) => p.predicted_up_share),
        lineStyle: { color: UP, width: 2 },
        itemStyle: { color: UP },
      },
      {
        name: '实际上涨占比',
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbolSize: 5,
        data: points.map((p) => p.actual_up_share),
        lineStyle: { color: DOWN, width: 2 },
        itemStyle: { color: DOWN },
      },
    ],
  }

  return <ReactECharts opts={{ renderer: 'svg' }} option={option} style={{ height }} />
}

function ConfidenceTable({ horizons }: { horizons: ForecastHorizonDiagnosis[] }) {
  const rows = horizons.flatMap((item) =>
    item.confidence_buckets
      // 样本不足的分档直接隐藏，避免小样本误导
      .filter((bucket) => bucket.sufficient)
      .map((bucket) => ({ horizon: item.horizon, ...bucket })),
  )

  if (!rows.length) {
    return <p className="diag-caption">该周期各置信度分档样本均不足 20，暂不展示分档统计。</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[460px] text-left text-xs">
        <thead className="text-[11px] text-gray-500">
          <tr className="border-b border-[#2a2a2e]">
            {['置信度区间', '样本', '命中率', '多数类基准', '平均误差'].map((label) => (
              <th key={label} className="px-3 py-2.5 font-medium">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[#1e1e1e]">
          {rows.map((row) => (
            <tr key={`${row.horizon}-${row.label}`}>
              <td className="px-3 py-2.5 text-gray-400">{row.label}</td>
              <td className="px-3 py-2.5 font-mono text-gray-400">{row.sample_size}</td>
              <td className="px-3 py-2.5 font-mono text-gray-200">
                {formatPercent(row.hit_rate)}
              </td>
              <td className="px-3 py-2.5 font-mono text-gray-400">
                {formatPercent(row.majority_base)}
              </td>
              <td className="px-3 py-2.5 font-mono text-gray-400">
                {formatBp(row.avg_abs_error_bp)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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