import React from 'react'
import ReactECharts from 'echarts-for-react'
import { useYieldChart, useMultiYieldChart, type YieldSeries } from '@/hooks/useChart'
import type { YieldPoint } from '@/types'

interface YieldChartProps {
  data: YieldPoint[]
  type?: string
  onClickDate?: (date: string) => void
  height?: number
  className?: string
  /** 多系列模式：提供后将并行展示多条收益率曲线（如 1年/5年/10年/30年） */
  series?: YieldSeries[]
}

const YieldChart: React.FC<YieldChartProps> = ({
  data,
  type = '10年',
  onClickDate,
  height = 400,
  className = '',
  series,
}) => {
  const multi = series && series.length > 0
  const { chartOption, chartEvents } = multi
    ? useMultiYieldChart(series, { onClickDate })
    : useYieldChart(data, type, { onClickDate })

  return (
    <div className={`chart-container ${className}`} style={{ height }}>
      <div className="h-full w-full overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-slate-950/95 via-slate-900/90 to-slate-800/70 p-3 shadow-[0_20px_60px_rgba(15,23,42,0.35)] backdrop-blur-sm">
        <ReactECharts
          option={chartOption}
          onEvents={chartEvents}
          style={{ height: '100%', width: '100%' }}
          notMerge={true}
          lazyUpdate={true}
          opts={{ renderer: 'canvas' }}
        />
      </div>
    </div>
  )
}

export default YieldChart
