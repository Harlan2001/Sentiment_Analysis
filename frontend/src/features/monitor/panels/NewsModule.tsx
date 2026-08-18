/**
 * 模块A：新闻数据流
 * A1 卡片 + A2 7日趋势堆叠柱状图 + A3 各源占比环形图 + A4 数据表格
 */
import React from 'react'
import ReactECharts from 'echarts-for-react'
import type { NewsModuleData } from '@/types'
import { PanelTitle, MetricCard } from './Widgets'
import { NEWS_SOURCES } from './constants'

interface Props {
  data: NewsModuleData
}

const sourceColors: Record<string, string> = {
  数据源1: '#f59e0b',
  数据源2: '#8b5cf6',
  wallstreetcn: '#f59e0b',
  yicai: '#8b5cf6',
}

function getSourceColor(name: string): string {
  return sourceColors[name] || '#6b7280'
}

function buildTrendOption(data: NewsModuleData) {
  const trend = data.trend_7d
  if (!trend || trend.length === 0) return {}

  // 收集所有 source name
  const sourceSet = new Set<string>()
  trend.forEach((item) => {
    Object.keys(item).forEach((k) => {
      if (k !== 'date') sourceSet.add(k)
    })
  })
  const sources = Array.from(sourceSet)

  const dates = trend.map((item) => item.date)

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
    },
    legend: {
      data: sources,
      textStyle: { color: '#9ca3af', fontSize: 10 },
      top: 0,
    },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#9ca3af', fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'value',
      name: '条',
      nameTextStyle: { color: '#9ca3af', fontSize: 10 },
      axisLabel: { color: '#9ca3af', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series: sources.map((s) => ({
      name: s,
      type: 'bar',
      stack: 'total',
      data: trend.map((item) => {
        const v = item[s]
        if (typeof v === 'number') return v
        if (typeof v === 'object' && v !== null) return (v as any).count || 0
        return 0
      }),
      itemStyle: { color: getSourceColor(s), borderRadius: [0, 0, 0, 0] },
      emphasis: { itemStyle: { color: getSourceColor(s) } },
    })),
  }
}

function buildDonutOption(data: NewsModuleData) {
  const dist = data.source_distribution
  if (!dist || dist.length === 0) return {}

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: '{b}: {c} 条 ({d}%)',
    },
    legend: {
      orient: 'vertical',
      right: 5,
      top: 'center',
      textStyle: { color: '#9ca3af', fontSize: 10 },
    },
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        label: { show: false },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
            color: '#e5e7eb',
          },
        },
        data: dist.map((d) => ({
          name: d.name,
          value: d.count,
          itemStyle: { color: getSourceColor(d.name) },
        })),
      },
    ],
  }
}

export const NewsModule: React.FC<Props> = ({ data }) => (
  <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
    <PanelTitle title="新闻数据流" icon="📰" />

    {/* A1: 新闻总量卡片 */}
    <div className="mb-3">
      <MetricCard label="新闻总量" value={data.total.toLocaleString()} />
    </div>

    {/* A2: 7日抓取趋势 */}
    <div className="mb-3">
      <div className="text-[11px] text-gray-400 mb-1">7日抓取趋势（按源堆叠）</div>
      {data.trend_7d?.length > 0 ? (
        <ReactECharts option={buildTrendOption(data)} style={{ height: 180 }} opts={{ renderer: 'svg' }} />
      ) : (
        <div className="text-gray-500 text-xs py-4 text-center">暂无7日趋势数据</div>
      )}
    </div>

    {/* A3: 各源占比环形图 */}
    <div className="mb-3">
      <div className="text-[11px] text-gray-400 mb-1">新闻源占比</div>
      {data.source_distribution?.length > 0 ? (
        <ReactECharts option={buildDonutOption(data)} style={{ height: 180 }} opts={{ renderer: 'svg' }} />
      ) : (
        <div className="text-gray-500 text-xs py-4 text-center">暂无数据</div>
      )}
    </div>

    {/* A4: 各源最新抓取时间表格 */}
    <div>
      <div className="text-[11px] text-gray-400 mb-2">最新抓取时间</div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-500 border-b border-gray-700">
            <th className="text-left py-1">源</th>
            <th className="text-right py-1">最新时间</th>
            <th className="text-center py-1">状态</th>
          </tr>
        </thead>
        <tbody>
          {data.latest_per_source?.map((s) => (
            <tr key={s.source} className="border-b border-gray-700/30">
              <td className="text-gray-300 py-1">{s.name}</td>
              <td className="text-right text-gray-400 py-1">{s.latest_time || '—'}</td>
              <td className="text-center py-1">
                <span
                  className={`inline-block w-2 h-2 rounded-full mr-1 ${
                    s.status === 'ok' ? 'bg-green-400' : s.status === 'yellow' ? 'bg-yellow-400' : 'bg-red-400'
                  }`}
                />
                <span
                  className={`text-[10px] ${
                    s.status === 'ok' ? 'text-green-400' : s.status === 'yellow' ? 'text-yellow-400' : 'text-red-400'
                  }`}
                >
                  {s.status === 'ok' ? '正常' : s.status === 'yellow' ? '超24h未更新' : '从未采集'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
)
