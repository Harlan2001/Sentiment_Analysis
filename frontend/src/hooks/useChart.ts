import React from 'react'
import { graphic } from 'echarts'
import type { EChartsOption } from 'echarts'
import type { YieldPoint } from '@/types'

const chartPalette = {
  primary: '#a78bfa',
  primarySoft: 'rgba(167, 139, 250, 0.18)',
  primaryGlow: 'rgba(167, 139, 250, 0.35)',
  line: '#d8b4fe',
  axis: '#94a3b8',
  splitLine: 'rgba(148, 163, 184, 0.16)',
  tooltipBg: 'rgba(15, 23, 42, 0.92)',
  tooltipBorder: 'rgba(148, 163, 184, 0.28)',
  news: '#fb7185',
}

const formatChartDate = (date: string) => {
  const parsedDate = new Date(date)
  return `${parsedDate.getMonth() + 1}/${parsedDate.getDate()}`
}

const formatTooltipValue = (value: unknown) => {
  const numericValue = Number(value)
  return Number.isFinite(numericValue) ? `${numericValue.toFixed(2)}%` : ''
}

// 收益率图表Hook
export const useYieldChart = (
  data: YieldPoint[],
  type: string = '10年',
  options?: {
    onClickDate?: (date: string) => void
    showTooltip?: boolean
  }
) => {
  const chartOption = React.useMemo<EChartsOption>(() => {
    const labels = data.map((point) => formatChartDate(point.date))
    const values = data.map((point) => point.value)

    return {
      backgroundColor: 'transparent',
      animationDuration: 450,
      animationEasing: 'cubicOut',
      grid: {
        left: '2%',
        right: '3%',
        top: 56,
        bottom: 36,
        containLabel: true,
      },
      legend: {
        show: true,
        top: 12,
        textStyle: {
          color: '#e2e8f0',
          fontSize: 12,
          fontWeight: 600,
        },
      },
      tooltip: {
        show: options?.showTooltip !== false,
        trigger: 'axis',
        backgroundColor: chartPalette.tooltipBg,
        borderColor: chartPalette.tooltipBorder,
        borderWidth: 1,
        borderRadius: 12,
        padding: [10, 12],
        textStyle: {
          color: '#f8fafc',
          fontSize: 12,
        },
        axisPointer: {
          type: 'line',
          lineStyle: {
            color: chartPalette.primary,
            width: 1.5,
            opacity: 0.55,
          },
        },
        formatter: (params: any) => {
          const items = Array.isArray(params) ? params : [params]
          const primaryItem = items.find((item) => item.seriesType === 'line') || items[0]
          const index = primaryItem?.dataIndex ?? 0
          const selectedDate = data[index]?.date || primaryItem?.axisValueLabel || ''
          return `<div style="font-weight: 600; margin-bottom: 4px;">${selectedDate}</div><div>收益率：${formatTooltipValue(primaryItem?.value)}</div>`
        },
      },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLine: {
          lineStyle: {
            color: 'rgba(148, 163, 184, 0.45)',
          },
        },
        axisTick: {
          show: false,
        },
        axisLabel: {
          color: chartPalette.axis,
          fontSize: 10,
          margin: 14,
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: chartPalette.splitLine,
            type: 'dashed',
          },
        },
        axisPointer: {
          label: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
          },
        },
      },
      yAxis: {
        type: 'value',
        name: '收益率 (%)',
        nameTextStyle: {
          color: chartPalette.axis,
          fontSize: 11,
          padding: [0, 0, 0, 8],
        },
        axisLine: {
          lineStyle: {
            color: 'rgba(148, 163, 184, 0.45)',
          },
        },
        axisLabel: {
          color: chartPalette.axis,
          fontSize: 10,
          margin: 12,
          formatter: (value: number) => `${value.toFixed(1)}%`,
        },
        splitLine: {
          lineStyle: {
            color: chartPalette.splitLine,
            type: 'dashed',
          },
        },
      },
      series: [
        {
          name: `${type}国债收益率`,
          type: 'line',
          data: values,
          smooth: true,
          showSymbol: true,
          symbol: 'circle',
          symbolSize: 7,
          lineStyle: {
            width: 2.5,
            color: new graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: '#7c3aed' },
              { offset: 0.5, color: chartPalette.primary },
              { offset: 1, color: '#c084fc' },
            ]),
            shadowBlur: 12,
            shadowColor: chartPalette.primaryGlow,
          },
          itemStyle: {
            color: chartPalette.primary,
            borderColor: '#f8fafc',
            borderWidth: 2,
            shadowBlur: 8,
            shadowColor: chartPalette.primaryGlow,
          },
          areaStyle: {
            color: new graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(167, 139, 250, 0.24)' },
              { offset: 0.7, color: 'rgba(167, 139, 250, 0.08)' },
              { offset: 1, color: 'rgba(167, 139, 250, 0.01)' },
            ]),
          },
          emphasis: {
            focus: 'series',
            scale: true,
          },
        },
      ],
    }
  }, [data, options?.showTooltip, type])

  const chartEvents = React.useMemo(
    () => ({
      click: (params: { dataIndex?: number }) => {
        if (options?.onClickDate && typeof params.dataIndex === 'number') {
          const selectedDate = data[params.dataIndex]?.date
          if (selectedDate) {
            options.onClickDate(selectedDate)
          }
        }
      },
    }),
    [data, options?.onClickDate]
  )

  return { chartOption, chartEvents }
}

// 带新闻事件的图表Hook
export const useNewsYieldChart = (data: YieldPoint[], newsEvents: any[], type: string = '10年') => {
  const chartOption = React.useMemo<EChartsOption>(() => {
    const labels = data.map((point) => formatChartDate(point.date))
    const values = data.map((point) => point.value)
    const newsDates = new Set(newsEvents.map((event) => event.date))

    return {
      backgroundColor: 'transparent',
      animationDuration: 450,
      animationEasing: 'cubicOut',
      grid: {
        left: '2%',
        right: '3%',
        top: 56,
        bottom: 36,
        containLabel: true,
      },
      legend: {
        show: true,
        top: 12,
        textStyle: {
          color: '#e2e8f0',
          fontSize: 12,
          fontWeight: 600,
        },
      },
      tooltip: {
        show: true,
        trigger: 'axis',
        backgroundColor: chartPalette.tooltipBg,
        borderColor: chartPalette.tooltipBorder,
        borderWidth: 1,
        borderRadius: 12,
        padding: [10, 12],
        textStyle: {
          color: '#f8fafc',
          fontSize: 12,
        },
        axisPointer: {
          type: 'line',
          lineStyle: {
            color: chartPalette.primary,
            width: 1.5,
            opacity: 0.55,
          },
        },
        formatter: (params: any) => {
          const items = Array.isArray(params) ? params : [params]
          const primaryItem = items.find((item) => item.seriesType === 'line') || items[0]
          const index = primaryItem?.dataIndex ?? 0
          const selectedDate = data[index]?.date || primaryItem?.axisValueLabel || ''
          return `<div style="font-weight: 600; margin-bottom: 4px;">${selectedDate}</div><div>收益率：${formatTooltipValue(primaryItem?.value)}</div>`
        },
      },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLine: {
          lineStyle: {
            color: 'rgba(148, 163, 184, 0.45)',
          },
        },
        axisTick: {
          show: false,
        },
        axisLabel: {
          color: chartPalette.axis,
          fontSize: 10,
          margin: 14,
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: chartPalette.splitLine,
            type: 'dashed',
          },
        },
        axisPointer: {
          label: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
          },
        },
      },
      yAxis: {
        type: 'value',
        name: '收益率 (%)',
        nameTextStyle: {
          color: chartPalette.axis,
          fontSize: 11,
          padding: [0, 0, 0, 8],
        },
        axisLine: {
          lineStyle: {
            color: 'rgba(148, 163, 184, 0.45)',
          },
        },
        axisLabel: {
          color: chartPalette.axis,
          fontSize: 10,
          margin: 12,
          formatter: (value: number) => `${value.toFixed(1)}%`,
        },
        splitLine: {
          lineStyle: {
            color: chartPalette.splitLine,
            type: 'dashed',
          },
        },
      },
      series: [
        {
          name: `${type}国债收益率`,
          type: 'line',
          data: values,
          smooth: true,
          showSymbol: true,
          symbol: 'circle',
          symbolSize: 7,
          lineStyle: {
            width: 2.5,
            color: new graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: '#7c3aed' },
              { offset: 0.5, color: chartPalette.primary },
              { offset: 1, color: '#c084fc' },
            ]),
            shadowBlur: 12,
            shadowColor: chartPalette.primaryGlow,
          },
          itemStyle: {
            color: chartPalette.primary,
            borderColor: '#f8fafc',
            borderWidth: 2,
            shadowBlur: 8,
            shadowColor: chartPalette.primaryGlow,
          },
          areaStyle: {
            color: new graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(167, 139, 250, 0.24)' },
              { offset: 0.7, color: 'rgba(167, 139, 250, 0.08)' },
              { offset: 1, color: 'rgba(167, 139, 250, 0.01)' },
            ]),
          },
          markPoint: {
            symbol: 'pin',
            symbolSize: 42,
            label: {
              show: true,
              color: '#fff1f2',
              fontSize: 10,
              fontWeight: 600,
              formatter: '新闻',
            },
            data: data
              .filter((point) => newsDates.has(point.date))
              .map((point) => ({
                name: '新闻事件',
                coord: [formatChartDate(point.date), point.value],
                value: point.value,
                itemStyle: {
                  color: chartPalette.news,
                  shadowBlur: 10,
                  shadowColor: 'rgba(251, 113, 133, 0.4)',
                },
              })),
          },
          emphasis: {
            focus: 'series',
            scale: true,
          },
        },
      ],
    }
  }, [data, newsEvents, type])

  return { chartOption }
}

export interface YieldSeries {
  label: string
  data: YieldPoint[]
}

const multiSeriesPalette = [
  '#a78bfa', // 紫
  '#34d399', // 绿
  '#60a5fa', // 蓝
  '#fbbf24', // 黄
  '#fb7185', // 粉
]

// 多期限收益率图表Hook：在同一坐标系叠加多条期限曲线（固定展示 1年/5年/10年/30年）
export const useMultiYieldChart = (series: YieldSeries[], options?: { onClickDate?: (date: string) => void }) => {
  const chartOption = React.useMemo<EChartsOption>(() => {
    // 对齐所有期限的日期（取并集排序），缺失补 null
    const dateSet = new Map<string, number>()
    series.forEach((s) =>
      s.data.forEach((p) => {
        if (!dateSet.has(p.date)) dateSet.set(p.date, dateSet.size)
      })
    )
    const dates = Array.from(dateSet.keys()).sort()
    const labels = dates.map(formatChartDate)

    const lineSeries = series.map((s, idx) => {
      const color = multiSeriesPalette[idx % multiSeriesPalette.length]
      const values = dates.map((d) => {
        const match = s.data.find((p) => p.date === d)
        return match ? match.value : null
      })
      return {
        name: `${s.label}收益率`,
        type: 'line' as const,
        data: values,
        smooth: true,
        showSymbol: false,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          width: 2.2,
          color,
          shadowBlur: 8,
          shadowColor: color + '55',
        },
        itemStyle: { color, borderColor: '#f8fafc', borderWidth: 1.5 },
        emphasis: { focus: 'series' as const },
      }
    })

    return {
      backgroundColor: 'transparent',
      animationDuration: 450,
      animationEasing: 'cubicOut',
      grid: { left: '2%', right: '3%', top: 56, bottom: 36, containLabel: true },
      legend: {
        show: true,
        top: 12,
        textStyle: { color: '#e2e8f0', fontSize: 12, fontWeight: 600 },
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: chartPalette.tooltipBg,
        borderColor: chartPalette.tooltipBorder,
        borderWidth: 1,
        borderRadius: 12,
        padding: [10, 12],
        textStyle: { color: '#f8fafc', fontSize: 12 },
        axisPointer: { type: 'line', lineStyle: { color: chartPalette.primary, width: 1.5, opacity: 0.55 } },
      },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.45)' } },
        axisTick: { show: false },
        axisLabel: { color: chartPalette.axis, fontSize: 10, margin: 14 },
        splitLine: { show: true, lineStyle: { color: chartPalette.splitLine, type: 'dashed' } },
        axisPointer: { label: { backgroundColor: 'rgba(15, 23, 42, 0.95)' } },
      },
      yAxis: {
        type: 'value',
        name: '收益率 (%)',
        nameTextStyle: { color: chartPalette.axis, fontSize: 11, padding: [0, 0, 0, 8] },
        axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.45)' } },
        axisLabel: { color: chartPalette.axis, fontSize: 10, margin: 12, formatter: (v: number) => `${v.toFixed(1)}%` },
        splitLine: { lineStyle: { color: chartPalette.splitLine, type: 'dashed' } },
      },
      series: lineSeries,
    }
  }, [series])

  const chartEvents = React.useMemo(
    () => ({
      click: (params: { dataIndex?: number }) => {
        if (options?.onClickDate && typeof params.dataIndex === 'number') {
          const dateSet = new Map<string, number>()
          series.forEach((s) =>
            s.data.forEach((p) => {
              if (!dateSet.has(p.date)) dateSet.set(p.date, dateSet.size)
            })
          )
          const dates = Array.from(dateSet.keys()).sort()
          const selectedDate = dates[params.dataIndex]
          if (selectedDate) options.onClickDate(selectedDate)
        }
      },
    }),
    [series, options?.onClickDate]
  )

  return { chartOption, chartEvents }
}
