/**
 * 收益率卡片网格 — Perplexity Finance 风格，2 列紧凑排列
 * 展示全部 9 种期限国债：最新值、变动 BP、分段红绿 sparkline
 */
import React, { useMemo, useRef } from 'react'
import type { MarketPanelYields } from '@/types'

interface Props {
  yields: MarketPanelYields
  onYieldClick: (period: string) => void
}

const PERIOD_ORDER = ['3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '30Y']

const UP_COLOR = '#22c55e'
const DOWN_COLOR = '#ef4444'

/**
 * 生成 Perplexity 风格分段 sparkline SVG
 * 每段根据涨跌分别着色（涨=绿，跌=红），带阴影面积 + 垂直渐变透明度遮罩
 */
function miniSparkSvg(values: number[], width: number, height: number): string {
  if (!values.length) return ''
  const n = values.length
  const max = Math.max(...values)
  const min = Math.min(...values)
  const rng = max - min || 1
  const padX = 2
  const padY = 3
  const w = width - padX * 2
  const h = height - padY * 2

  const toX = (i: number) => padX + (i / Math.max(n - 1, 1)) * w
  const toY = (v: number) => padY + h - ((v - min) / rng) * h

  // 构建 polyline 点串
  const ptsStr = values.map((v, i) => `${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ')

  // 构建分段线性渐变（line + area），每个转折点用双 stop 实现锐利切换
  const gradId = `lg-${Math.random().toString(36).slice(2, 8)}`
  const maskId = `mk-${Math.random().toString(36).slice(2, 8)}`

  let lineStops = ''
  let areaStops = ''
  for (let i = 0; i < n - 1; i++) {
    const pct = ((i / (n - 1)) * 100).toFixed(2)
    const segColor = values[i + 1] >= values[i] ? UP_COLOR : DOWN_COLOR
    // 双 stop 同一位置实现锐利切换
    lineStops += `<stop offset="${pct}%" stop-color="${segColor}" stop-opacity="1"/>`
    areaStops += `<stop offset="${pct}%" stop-color="${segColor}" stop-opacity="1"/>`
  }
  // 最后一个 stop
  lineStops += `<stop offset="100%" stop-color="${values[n - 1] >= values[n - 2] ? UP_COLOR : DOWN_COLOR}" stop-opacity="1"/>`
  areaStops += `<stop offset="100%" stop-color="${values[n - 1] >= values[n - 2] ? UP_COLOR : DOWN_COLOR}" stop-opacity="1"/>`

  const firstX = toX(0).toFixed(1)
  const lastX = toX(n - 1).toFixed(1)
  const bottomY = height

  // 面积多边形：曲线 + 底部闭合
  const areaPts =
    `${firstX},${bottomY} ` +
    values.map((v, i) => `${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ') +
    ` ${lastX},${bottomY}`

  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">` +
    `<defs>` +
    `<linearGradient id="${gradId}-line" x1="0" y1="0" x2="1" y2="0">${lineStops}</linearGradient>` +
    `<linearGradient id="${gradId}-area" x1="0" y1="0" x2="1" y2="0">${areaStops}</linearGradient>` +
    `<linearGradient id="${maskId}" x1="0" y1="0" x2="0" y2="1">` +
    `<stop offset="0%" stop-color="white" stop-opacity="0.3"/>` +
    `<stop offset="75%" stop-color="white" stop-opacity="0.05"/>` +
    `<stop offset="100%" stop-color="white" stop-opacity="0.01"/>` +
    `</linearGradient>` +
    `<mask id="${maskId}-m"><rect width="${width}" height="${height}" fill="url(#${maskId})"/></mask>` +
    `</defs>` +
    `<polygon points="${areaPts}" fill="url(#${gradId}-area)" mask="url(#${maskId}-m)" />` +
    `<polyline points="${ptsStr}" fill="none" stroke="url(#${gradId}-line)" stroke-width="1.5" vector-effect="non-scaling-stroke" shape-rendering="geometricPrecision" />` +
    `</svg>`
  )
}

const YieldCardGrid: React.FC<Props> = ({ yields, onYieldClick }) => {
  const { items, spread_10y2y } = yields
  const svgCache = useRef<Record<string, string>>({})

  const sorted = useMemo(
    () =>
      PERIOD_ORDER.map((p) => items.find((it) => it.period === p)).filter(
        Boolean,
      ) as typeof items,
    [items],
  )

  return (
    <div className="rounded-xl bg-[#111111] border border-[#2a2a2a] overflow-hidden">
      <div className="px-3 py-2 border-b border-[#1f1f1f] flex items-center justify-between">
        <span className="text-[11px] font-medium text-[#6b7280] uppercase tracking-wide">
          国债收益率
        </span>
        {spread_10y2y && (
          <span className="text-[10px] text-[#6b7280]">
            10Y-2Y{' '}
            <span
              className={
                spread_10y2y.direction === 'up'
                  ? 'text-[#ef4444]'
                  : spread_10y2y.direction === 'down'
                    ? 'text-[#22c55e]'
                    : ''
              }
            >
              {spread_10y2y.value.toFixed(2)}%
            </span>
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-px bg-[#1f1f1f]">
        {sorted.map((item) => {
          const isUp = item.direction === 'up'
          const isDown = item.direction === 'down'
          const chgColor = isUp ? 'text-[#ef4444]' : isDown ? 'text-[#22c55e]' : 'text-[#6b7280]'

          // 缓存 SVG 避免每次渲染重新生成
          const cacheKey = `${item.period}-${item.sparkline.values.length}`
          if (!svgCache.current[cacheKey]) {
            svgCache.current[cacheKey] = miniSparkSvg(item.sparkline.values, 150, 30)
          }

          return (
            <div
              key={item.period}
              className="bg-[#111111] p-2.5 hover:bg-[#1a1a1a] transition-colors cursor-pointer"
              onClick={() => onYieldClick(item.period)}
            >
              {/* 第一行：期限名 + 变动 */}
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[12px] font-medium text-[#e0e0e0] truncate">
                  {item.label}
                </span>
                <span className={`flex items-center gap-0.5 text-[11px] font-medium ${chgColor}`}>
                  <span className="text-[10px]">
                    {isUp ? '↑' : isDown ? '↓' : '→'}
                  </span>
                  <span className="tabular-nums">
                    {item.diff_bp > 0 ? '+' : ''}
                    {item.diff_bp}BP
                  </span>
                </span>
              </div>

              {/* 第二行：当前值 */}
              <div className="flex items-center justify-between mb-1">
                <span className="text-[15px] font-mono font-semibold text-white tabular-nums">
                  {item.value.toFixed(3)}%
                </span>
              </div>

              {/* 第三行：分段 sparkline */}
              <div
                className="h-[30px] w-full"
                dangerouslySetInnerHTML={{ __html: svgCache.current[cacheKey] }}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default YieldCardGrid
