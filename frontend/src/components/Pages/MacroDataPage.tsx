/**
 * 宏观数据页面 — 展示宏观经济指标的时间序列
 *
 * 交互流程：
 *   1. 分类筛选 + 搜索 → 定位指标
 *   2. 点击指标（可多选）→ 下方展示大尺寸详情面板
 *   3. 详情面板三种视图模式：表格 / 直方图+折线图 / 饼图
 *   4. 直方图支持横/纵切换，鼠标悬停显示日期+数值
 */

import React, { useState, useMemo, useCallback } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { Card, CardContent, CardHeader, CardTitle, Button, Loading, Empty, Error } from '@/components/UI'
import { useMacroIndicators, useMacroData } from '@/hooks/useMacroDataApi'
import { cn } from '@/utils/helpers'
import type { MacroIndicator, MacroDataSeries, MacroDataPoint } from '@/types'

// ═══════════════════════════════════════════════════════════════════════════
// 常量
// ═══════════════════════════════════════════════════════════════════════════

const CATEGORY_TABS: { key: string; label: string; icon: string }[] = [
  { key: 'all', label: '全部', icon: '📊' },
  { key: 'strong', label: '双向强相关', icon: '🔥' },
  { key: 'medium', label: '双向中等相关', icon: '📈' },
  { key: 'weak', label: '双向弱相关', icon: '📉' },
  { key: 'precious', label: '贵金属', icon: '🥇' },
  { key: 'bond', label: '国债侧重', icon: '🏦' },
  { key: 'general', label: '通用', icon: '📋' },
]

type ViewMode = 'table' | 'chart' | 'pie'
type BarOrientation = 'vertical' | 'horizontal'

const DEFAULT_START = '202201'
const DEFAULT_END = '202606'

const CHART_COLORS = {
  bar: '#a78bfa',
  barHover: '#c4b5fd',
  line: '#34d399',
  pieColors: [
    '#a78bfa', '#60a5fa', '#34d399', '#fbbf24', '#f472b6',
    '#fb923c', '#94a3b8', '#f87171', '#4ade80', '#a3e635',
    '#38bdf8', '#c084fc', '#e879f9', '#2dd4bf', '#facc15',
  ],
}

// ═══════════════════════════════════════════════════════════════════════════
// 月份工具
// ═══════════════════════════════════════════════════════════════════════════

function formatMonth(datestr: string): string {
  if (datestr.length === 6) {
    return `${datestr.slice(0, 4)}-${datestr.slice(4, 6)}`
  }
  return datestr
}

/** 格式化数值，保留合理小数位 */
function fmtVal(v: number | null): string {
  if (v == null) return '—'
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万'
  if (Number.isInteger(v)) return v.toLocaleString()
  return v.toFixed(2)
}

// ═══════════════════════════════════════════════════════════════════════════
// 通用 tooltip 样式
// ═══════════════════════════════════════════════════════════════════════════

const TOOLTIP_BG = 'rgba(15, 23, 42, 0.95)'
const TOOLTIP_BORDER = 'rgba(148, 163, 184, 0.3)'

// ═══════════════════════════════════════════════════════════════════════════
// 视图模式 1：数据表格
// ═══════════════════════════════════════════════════════════════════════════

const TableView: React.FC<{ series: MacroDataSeries }> = ({ series }) => {
  // 按日期降序排列
  const sorted = useMemo(
    () => [...series.data].sort((a, b) => b.datestr.localeCompare(a.datestr)),
    [series.data],
  )

  return (
    <div className="overflow-auto max-h-[500px] rounded-lg border border-gray-700">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-gray-800">
          <tr>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-300 border-b border-gray-700">
              序号
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-300 border-b border-gray-700">
              月份
            </th>
            <th className="px-4 py-2.5 text-right text-xs font-medium text-gray-300 border-b border-gray-700">
              数值
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/50">
          {sorted.map((d, i) => (
            <tr
              key={d.datestr}
              className="hover:bg-gray-700/30 transition-colors"
            >
              <td className="px-4 py-2 text-gray-500 text-xs">{i + 1}</td>
              <td className="px-4 py-2 text-gray-200 font-mono">
                {formatMonth(d.datestr)}
              </td>
              <td className="px-4 py-2 text-right text-gray-100 font-mono tabular-nums">
                {fmtVal(d.value)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="px-4 py-2 bg-gray-800/50 border-t border-gray-700 text-xs text-gray-500">
        共 {sorted.length} 条记录
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// 视图模式 2：直方图 + 折线图（可切换横/纵）
// ═══════════════════════════════════════════════════════════════════════════

const BarLineChartView: React.FC<{
  series: MacroDataSeries
  barOrientation: BarOrientation
  onToggleOrientation: () => void
}> = ({ series, barOrientation, onToggleOrientation }) => {
  const data = series.data
  const isHorizontal = barOrientation === 'horizontal'

  const option: EChartsOption = useMemo(() => {
    const dates = data.map((d) => formatMonth(d.datestr))
    const values = data.map((d) => d.value)

    const xCategory = isHorizontal ? undefined : dates
    const yCategory = isHorizontal ? dates : undefined

    return {
      grid: { top: 50, right: 50, bottom: 60, left: 90 },
      // 直方图
      ...(isHorizontal
        ? {
            yAxis: {
              type: 'category' as const,
              data: dates,
              axisLabel: { color: '#94a3b8', fontSize: 11 },
              axisLine: { lineStyle: { color: '#475569' } },
              inverse: true,
            },
            xAxis: {
              type: 'value' as const,
              axisLabel: { color: '#94a3b8', fontSize: 10 },
              splitLine: { lineStyle: { color: '#334155', type: 'dashed' } },
            },
          }
        : {
            xAxis: {
              type: 'category' as const,
              data: dates,
              axisLabel: {
                color: '#94a3b8',
                fontSize: 10,
                rotate: dates.length > 24 ? 45 : 0,
              },
              axisLine: { lineStyle: { color: '#475569' } },
            },
            yAxis: {
              type: 'value' as const,
              axisLabel: { color: '#94a3b8', fontSize: 10 },
              splitLine: { lineStyle: { color: '#334155', type: 'dashed' } },
            },
          }),
      series: [
        {
          name: series.name,
          type: 'bar',
          data: values,
          barWidth: isHorizontal ? '60%' : Math.max(6, Math.min(20, 400 / data.length)),
          itemStyle: {
            color: CHART_COLORS.bar,
            borderRadius: isHorizontal ? [0, 4, 4, 0] : [4, 4, 0, 0],
          },
          emphasis: {
            itemStyle: { color: CHART_COLORS.barHover },
          },
        },
      ],
      tooltip: {
        trigger: isHorizontal ? 'axis' : 'item',
        backgroundColor: TOOLTIP_BG,
        borderColor: TOOLTIP_BORDER,
        textStyle: { color: '#e2e8f0', fontSize: 12 },
        formatter: (params: any) => {
          const p = Array.isArray(params) ? params[0] : params
          if (!p) return ''
          const label = isHorizontal ? p.name : p.axisValue
          return `<div style="font-size:12px;font-weight:600;margin-bottom:4px">${series.name}</div>
            <div><span style="color:#94a3b8">日期：</span>${label}</div>
            <div><span style="color:#94a3b8">数值：</span><span style="color:#a78bfa;font-weight:600">${fmtVal(p.value)}</span></div>`
        },
      },
    }
  }, [data, isHorizontal, series.name])

  // 折线图 option（独立的双轴图表）
  const lineOption: EChartsOption = useMemo(() => {
    const dates = data.map((d) => formatMonth(d.datestr))
    const values = data.map((d) => d.value)

    return {
      grid: { top: 40, right: 40, bottom: 60, left: 90 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          rotate: dates.length > 24 ? 45 : 0,
        },
        axisLine: { lineStyle: { color: '#475569' } },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        splitLine: { lineStyle: { color: '#334155', type: 'dashed' } },
      },
      series: [
        {
          type: 'line',
          data: values,
          smooth: true,
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: { color: CHART_COLORS.line, width: 2 },
          itemStyle: { color: CHART_COLORS.line },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(52, 211, 153, 0.2)' },
                { offset: 1, color: 'rgba(52, 211, 153, 0.02)' },
              ],
            },
          },
        },
      ],
      tooltip: {
        trigger: 'axis',
        backgroundColor: TOOLTIP_BG,
        borderColor: TOOLTIP_BORDER,
        textStyle: { color: '#e2e8f0', fontSize: 12 },
        formatter: (params: any) => {
          const p = Array.isArray(params) ? params[0] : params
          if (!p) return ''
          return `<div style="font-size:12px;font-weight:600;margin-bottom:4px">${series.name}</div>
            <div><span style="color:#94a3b8">日期：</span>${p.axisValue}</div>
            <div><span style="color:#94a3b8">数值：</span><span style="color:#34d399;font-weight:600">${fmtVal(p.value)}</span></div>`
        },
      },
    }
  }, [data, series.name])

  return (
    <div className="space-y-6">
      {/* 直方图 + 切换按钮 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-medium text-gray-300">直方图</h4>
          <Button variant="outline" size="sm" onClick={onToggleOrientation}>
            {isHorizontal ? '⬌ 横向' : '⬍ 纵向'} → 切换
          </Button>
        </div>
        <div className="bg-gray-800/40 rounded-lg border border-gray-700/60 p-2">
          <ReactECharts
            option={option}
            style={{ height: '380px', width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
        </div>
      </div>

      {/* 折线图 */}
      <div>
        <h4 className="text-sm font-medium text-gray-300 mb-3">折线图</h4>
        <div className="bg-gray-800/40 rounded-lg border border-gray-700/60 p-2">
          <ReactECharts
            option={lineOption}
            style={{ height: '380px', width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// 视图模式 3：饼图
// ═══════════════════════════════════════════════════════════════════════════

const PieChartView: React.FC<{ series: MacroDataSeries }> = ({ series }) => {
  const data = series.data

  const option: EChartsOption = useMemo(() => {
    // 取最近 N 个数据点做饼图（太多会挤）
    const MAX_SLICES = 14
    const slice = data.length <= MAX_SLICES ? data : data.slice(-MAX_SLICES)

    const pieData = slice.map((d, i) => ({
      name: formatMonth(d.datestr),
      value: d.value ?? 0,
      itemStyle: {
        color: CHART_COLORS.pieColors[i % CHART_COLORS.pieColors.length],
      },
    }))

    return {
      tooltip: {
        trigger: 'item',
        backgroundColor: TOOLTIP_BG,
        borderColor: TOOLTIP_BORDER,
        textStyle: { color: '#e2e8f0', fontSize: 12 },
        formatter: (params: any) => {
          return `<div style="font-size:12px;font-weight:600;margin-bottom:4px">${series.name}</div>
            <div><span style="color:#94a3b8">日期：</span>${params.name}</div>
            <div><span style="color:#94a3b8">数值：</span><span style="color:#c4b5fd;font-weight:600">${fmtVal(params.value)}</span></div>
            <div><span style="color:#94a3b8">占比：</span>${params.percent}%</div>`
        },
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center',
        textStyle: { color: '#94a3b8', fontSize: 11 },
        itemWidth: 10,
        itemHeight: 10,
      },
      series: [
        {
          name: series.name,
          type: 'pie',
          radius: ['35%', '68%'],
          center: ['42%', '50%'],
          data: pieData,
          label: {
            color: '#cbd5e1',
            fontSize: 10,
            formatter: '{b}: {d}%',
          },
          labelLine: { lineStyle: { color: '#475569' } },
          emphasis: {
            itemStyle: {
              shadowBlur: 20,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
              scaleSize: 8,
            },
            label: { fontSize: 13, fontWeight: 'bold' },
          },
        },
      ],
    }
  }, [data, series.name])

  if (data.length === 0) {
    return <div className="text-center text-gray-500 py-12">暂无数据</div>
  }

  return (
    <div>
      <h4 className="text-sm font-medium text-gray-300 mb-3">
        饼图{data.length > 14 ? `（最近 ${14} 个月）` : ''}
      </h4>
      <div className="bg-gray-800/40 rounded-lg border border-gray-700/60 p-2">
        <ReactECharts
          option={option}
          style={{ height: '440px', width: '100%' }}
          opts={{ renderer: 'svg' }}
        />
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// 指标详情面板（选择指标后展示）
// ═══════════════════════════════════════════════════════════════════════════

const IndicatorDetailPanel: React.FC<{
  activeCode: string
  activeName: string
  allCodes: string[]
  onSelectCode: (code: string) => void
  seriesMap: Record<string, MacroDataSeries>
  dataLoading: boolean
  onClose: () => void
}> = ({ activeCode, activeName, allCodes, onSelectCode, seriesMap, dataLoading, onClose }) => {
  const [viewMode, setViewMode] = useState<ViewMode>('chart')
  const [barOrientation, setBarOrientation] = useState<BarOrientation>('vertical')

  const series = seriesMap[activeCode]

  return (
    <Card className="border-purple-500/30">
      {/* 头部：指标名 + 切换器 + 关闭 */}
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-3 min-w-0">
            <CardTitle className="text-lg truncate max-w-[400px]">
              <span title={activeName}>{activeName}</span>
            </CardTitle>
            <span className="text-xs text-gray-500 font-mono flex-shrink-0">{activeCode}</span>
            {/* 多指标时显示下拉 */}
            {allCodes.length > 1 && (
              <select
                value={activeCode}
                onChange={(e) => onSelectCode(e.target.value)}
                className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-300 focus:border-purple-500 focus:outline-none"
              >
                {allCodes.map((c) => (
                  <option key={c} value={c}>
                    {seriesMap[c]?.name ?? c}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* 视图模式切换 */}
            <div className="flex bg-gray-800 rounded-lg border border-gray-600 p-0.5">
              {([
                { key: 'table' as ViewMode, label: '📋 表格' },
                { key: 'chart' as ViewMode, label: '📊 直方图+折线图' },
                { key: 'pie' as ViewMode, label: '🥧 饼图' },
              ]).map((m) => (
                <button
                  key={m.key}
                  onClick={() => setViewMode(m.key)}
                  className={cn(
                    'px-3 py-1.5 rounded-md text-xs font-medium transition-all',
                    viewMode === m.key
                      ? 'bg-purple-500/20 text-purple-400'
                      : 'text-gray-400 hover:text-gray-300',
                  )}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <Button variant="outline" size="sm" onClick={onClose}>
              ✕ 关闭
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {dataLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-pulse text-gray-400 text-sm">加载数据中...</div>
          </div>
        ) : !series ? (
          <div className="text-center py-20 text-gray-500">未找到该指标的数据</div>
        ) : viewMode === 'table' ? (
          <TableView series={series} />
        ) : viewMode === 'chart' ? (
          <BarLineChartView
            series={series}
            barOrientation={barOrientation}
            onToggleOrientation={() =>
              setBarOrientation((prev) => (prev === 'vertical' ? 'horizontal' : 'vertical'))
            }
          />
        ) : (
          <PieChartView series={series} />
        )}
      </CardContent>
    </Card>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// 主页面
// ═══════════════════════════════════════════════════════════════════════════

const MacroDataPage: React.FC = () => {
  // ── 状态 ─────────────────────────────────────────────────
  const [activeCategory, setActiveCategory] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [startMonth, setStartMonth] = useState(DEFAULT_START)
  const [endMonth, setEndMonth] = useState(DEFAULT_END)
  const [selectedCodes, setSelectedCodes] = useState<string[]>([])
  const [showAllCharts, setShowAllCharts] = useState(false)
  const [activeDetailCode, setActiveDetailCode] = useState<string | null>(null) // 当前详情的指标

  // ── 数据 ─────────────────────────────────────────────────
  const { data: indicatorsData, isLoading: indicatorsLoading, error: indicatorsError } = useMacroIndicators()

  const allIndicators: MacroIndicator[] = useMemo(
    () => indicatorsData?.indicators ?? [],
    [indicatorsData],
  )

  const filteredIndicators = useMemo(() => {
    return allIndicators.filter((ind) => {
      if (activeCategory !== 'all' && ind.category !== activeCategory) return false
      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        return ind.name.toLowerCase().includes(q) || ind.code.toLowerCase().includes(q)
      }
      return true
    })
  }, [allIndicators, activeCategory, searchQuery])

  // 所有选中指标（用于 API 查询 & 详情面板下拉）
  const queryCodes = useMemo(() => {
    if (showAllCharts) return filteredIndicators.map((i) => i.code)
    return selectedCodes
  }, [showAllCharts, filteredIndicators, selectedCodes])

  const { data: macroData, isLoading: dataLoading, error: dataError } = useMacroData(
    queryCodes,
    startMonth,
    endMonth,
  )

  const seriesMap = useMemo(() => {
    const map: Record<string, MacroDataSeries> = {}
    if (macroData?.indicators) {
      for (const s of macroData.indicators) {
        map[s.zbcode] = s
      }
    }
    return map
  }, [macroData])

  // 代码 → 指标名 映射
  const codeNameMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const ind of allIndicators) {
      map[ind.code] = ind.name
    }
    return map
  }, [allIndicators])

  // ── 操作 ─────────────────────────────────────────────────
  const handleIndicatorClick = useCallback(
    (code: string) => {
      setShowAllCharts(false)
      setSelectedCodes((prev) => {
        const next = prev.includes(code)
          ? prev.filter((c) => c !== code)
          : [...prev, code]
        // 自动打开刚点击的指标详情（如果是新增的）
        if (!prev.includes(code)) {
          setActiveDetailCode(code)
        } else if (next.length === 0) {
          setActiveDetailCode(null)
        } else if (activeDetailCode === code) {
          setActiveDetailCode(next[0] ?? null)
        }
        return next
      })
    },
    [activeDetailCode],
  )

  const handleShowAllClick = useCallback(() => {
    setShowAllCharts(true)
    setSelectedCodes([])
    const first = filteredIndicators[0]
    if (first) setActiveDetailCode(first.code)
  }, [filteredIndicators])

  const handleClearSelection = useCallback(() => {
    setSelectedCodes([])
    setShowAllCharts(false)
    setActiveDetailCode(null)
  }, [])

  // ── 统计 ─────────────────────────────────────────────────
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: allIndicators.length }
    for (const ind of allIndicators) {
      counts[ind.category] = (counts[ind.category] || 0) + 1
    }
    return counts
  }, [allIndicators])

  // ── 加载 / 错误状态 ──────────────────────────────────────
  if (indicatorsLoading) {
    return <Loading text="加载指标列表..." />
  }
  if (indicatorsError) {
    return <Error title="加载失败" message={indicatorsError.message} />
  }

  const hasSelection = queryCodes.length > 0
  // 默认 auto-open 第一个已选指标
  const activeCode = activeDetailCode && queryCodes.includes(activeDetailCode)
    ? activeDetailCode
    : queryCodes[0] ?? null
  const activeName = activeCode ? (seriesMap[activeCode]?.name ?? codeNameMap[activeCode] ?? activeCode) : ''

  return (
    <div className="space-y-6">
      {/* ═════════════ 页面头部 ═════════════ */}
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
          📊 宏观数据
        </h1>
        <p className="text-gray-400 text-sm">
          基于国家统计局数据的宏观经济指标查询与可视化，涵盖 CPI、PPI、PMI、货币供应、房地产、进出口等 {allIndicators.length} 个核心指标
        </p>
      </div>

      {/* ═════════════ 分类筛选 ═════════════ */}
      <Card>
        <CardContent className="p-3">
          <div className="flex flex-wrap gap-2">
            {CATEGORY_TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveCategory(tab.key)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border',
                  activeCategory === tab.key
                    ? 'bg-purple-500/20 border-purple-500 text-purple-400'
                    : 'bg-gray-800 border-gray-600 text-gray-400 hover:border-gray-500 hover:bg-gray-700',
                )}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
                <span className={cn(
                  'text-[10px] ml-0.5',
                  activeCategory === tab.key ? 'text-purple-500' : 'text-gray-500',
                )}>
                  ({categoryCounts[tab.key] ?? 0})
                </span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ═════════════ 搜索 + 日期范围 ═════════════ */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索指标名称或代码..."
              className="flex-1 min-w-[200px] px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-400 focus:border-purple-500 focus:outline-none"
            />
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">日期范围:</span>
              <input
                type="text"
                value={startMonth}
                onChange={(e) => setStartMonth(e.target.value)}
                placeholder="202201"
                className="w-20 px-2 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-xs text-center focus:border-purple-500 focus:outline-none"
              />
              <span className="text-gray-500">-</span>
              <input
                type="text"
                value={endMonth}
                onChange={(e) => setEndMonth(e.target.value)}
                placeholder="202606"
                className="w-20 px-2 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-xs text-center focus:border-purple-500 focus:outline-none"
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleShowAllClick}
                disabled={filteredIndicators.length === 0}
              >
                查看全部
              </Button>
              {hasSelection && (
                <Button variant="outline" size="sm" onClick={handleClearSelection}>
                  清空
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ═════════════ 指标选择区 ═════════════ */}
      <Card>
        <CardHeader>
          <CardTitle>
            指标列表
            <span className="ml-2 text-sm font-normal text-gray-400">
              ({filteredIndicators.length} 个，已选 {queryCodes.length} 个)
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
            {filteredIndicators.slice(0, showAllCharts ? undefined : 50).map((ind) => (
              <button
                key={ind.code}
                onClick={() => handleIndicatorClick(ind.code)}
                className={cn(
                  'text-left px-3 py-2 rounded-lg text-xs transition-all border truncate',
                  queryCodes.includes(ind.code)
                    ? 'border-purple-500 bg-purple-500/15 text-purple-300'
                    : 'border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-500 hover:bg-gray-700',
                )}
                title={`${ind.name} (${ind.code})`}
              >
                <div className="truncate font-medium">{ind.name}</div>
                <div className="text-[10px] text-gray-500 mt-0.5">{ind.code}</div>
              </button>
            ))}
          </div>
          {filteredIndicators.length > 50 && !showAllCharts && (
            <div className="mt-3 text-center">
              <span className="text-xs text-gray-500">{'显示前50个指标，使用搜索或"查看全部"查看更多'}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ═════════════ 详情面板 ═════════════ */}
      {dataError && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-sm text-red-400">数据加载失败: {dataError.message}</p>
        </div>
      )}

      {hasSelection && activeCode ? (
        <IndicatorDetailPanel
          activeCode={activeCode}
          activeName={activeName}
          allCodes={queryCodes}
          onSelectCode={setActiveDetailCode}
          seriesMap={seriesMap}
          dataLoading={dataLoading}
          onClose={handleClearSelection}
        />
      ) : (
        !hasSelection && (
          <Card>
            <CardContent className="py-12 text-center">
              <Empty
                title="选择指标以显示图表"
                message={'在指标列表中点击指标名称，或点击"查看全部"展示当前筛选的所有指标'}
              />
            </CardContent>
          </Card>
        )
      )}

      {/* 分页提示 */}
      {hasSelection && queryCodes.length > 1 && activeCode && (
        <div className="text-center">
          <span className="text-xs text-gray-500">
            当前查看: {activeName}（{queryCodes.indexOf(activeCode) + 1}/{queryCodes.length}）
          </span>
        </div>
      )}
    </div>
  )
}

export default MacroDataPage
