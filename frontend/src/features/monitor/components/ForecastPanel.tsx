/**
 * 模块F：每日预测报告
 */
import React from 'react'
import ReactECharts from 'echarts-for-react'
import type { ForecastModuleData } from '@/types'
import { PanelTitle, MetricCard } from './Widgets'
import { ALERT } from './constants'

interface Props {
  data: ForecastModuleData
}

export const ForecastPanel: React.FC<Props> = ({ data }) => {
  // F2 状态判断
  const latestDateStatus = (() => {
    if (!data.latest_date) return 'danger'
    const latest = new Date(data.latest_date)
    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 1)
    return latest >= new Date(yesterday.toDateString()) ? 'normal' : 'danger'
  })()

  // F4: 日历热力图
  const calendarOption = (() => {
    const calData = data.coverage_30d
    if (!calData || calData.length === 0) return {}

    const heatData = calData.filter((d) => d.has_report).map((d) => [d.date, 1])

    const today = new Date()
    const startDate = new Date()
    startDate.setDate(startDate.getDate() - 29)

    return {
      tooltip: {
        backgroundColor: 'rgba(17,24,39,0.95)',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb', fontSize: 12 },
        formatter: (params: any) => {
          return `${params.value[0]}${params.value[1] === 1 ? ' ✅ 有报告' : ' ❌ 无报告'}`
        },
      },
      visualMap: {
        min: 0,
        max: 1,
        show: false,
        inRange: { color: ['#374151', '#10b981'] },
      },
      calendar: {
        range: [startDate.toISOString().slice(0, 10), today.toISOString().slice(0, 10)],
        cellSize: ['auto', 14],
        dayLabel: { color: '#9ca3af', fontSize: 9 },
        monthLabel: { color: '#9ca3af', fontSize: 10 },
        itemStyle: { borderColor: '#1f2937', borderWidth: 2, borderRadius: 2 },
        yearLabel: { show: false },
      },
      series: [
        {
          type: 'heatmap',
          coordinateSystem: 'calendar',
          data: heatData,
          label: { show: false },
          emphasis: { itemStyle: { borderColor: '#fff', borderWidth: 1 } },
        },
      ],
    }
  })()

  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
      <PanelTitle title="每日预测报告" icon="📋" />

      <div className="grid grid-cols-2 gap-2 mb-3">
        <MetricCard label="报告总数" value={data.total_reports.toLocaleString()} />
        <div
          className={`rounded-lg border px-4 py-3 ${
            latestDateStatus === 'danger' ? 'border-red-700/30 bg-red-900/20' : 'border-gray-700/50 bg-gray-800/40'
          }`}
        >
          <div className="text-[11px] text-gray-400">最新报告</div>
          <div
            className={`text-sm font-bold mt-0.5 ${latestDateStatus === 'danger' ? 'text-red-400' : 'text-gray-200'}`}
          >
            {data.latest_date || 'N/A'}
          </div>
        </div>
      </div>

      {/* F4: 30日覆盖日历热力图 */}
      <div>
        <div className="text-[11px] text-gray-400 mb-1">30日报告覆盖</div>
        {data.coverage_30d?.length > 0 ? (
          <ReactECharts option={calendarOption} style={{ height: 160 }} opts={{ renderer: 'svg' }} />
        ) : (
          <div className="text-gray-500 text-xs py-3 text-center">暂无报告数据</div>
        )}
      </div>
    </div>
  )
}
