/**
 * 模块E：收益率数据
 */
import React from 'react';
import ReactECharts from 'echarts-for-react';
import type { YieldModuleData } from '../../types';
import { PanelTitle, MetricCard } from './Widgets';
import { PERIOD_COLORS } from './constants';

interface Props { data: YieldModuleData; }

export const YieldModule: React.FC<Props> = ({ data }) => {
  // E4: 各期限完整性横向柱状图
  const barOption = {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 } },
    grid: { left: 60, right: 50, top: 5, bottom: 5 },
    xAxis: { type: 'value', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#1f2937' } } },
    yAxis: {
      type: 'category',
      data: data.period_completeness?.map(p => p.display_name).reverse() || [],
      axisLabel: { color: '#9ca3af', fontSize: 10 },
    },
    series: [{
      type: 'bar',
      data: data.period_completeness?.map((p, i) => ({
        value: p.count,
        itemStyle: { color: PERIOD_COLORS[i] || '#6b7280', borderRadius: [0, 4, 4, 0] },
      })).reverse() || [],
      label: { show: true, position: 'right', color: '#9ca3af', fontSize: 10 },
    }],
  };

  // E6: 各期限sparkline行
  const sparklineOption = (values: number[], color: string) => ({
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: 'category', show: false, data: values.map((_, i) => i) },
    yAxis: { type: 'value', show: false, min: (v: number) => Math.min(...values) * 0.99, max: (v: number) => Math.max(...values) * 1.01 },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      showSymbol: false,
      lineStyle: { color, width: 1.5 },
      areaStyle: { color: `${color}20` },
    }],
  });

  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
      <PanelTitle title="收益率数据" icon="📈" />

      {/* E2 + E3 */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="rounded-lg border border-gray-700/50 bg-gray-800/40 px-3 py-2">
          <div className="text-[11px] text-gray-400">日期范围</div>
          <div className="text-sm text-gray-200 mt-0.5">
            {data.date_min && data.date_max ? `${data.date_min} ~ ${data.date_max}` : 'N/A'}
          </div>
        </div>
        <MetricCard label="覆盖天数" value={data.coverage_days.toLocaleString()} />
      </div>

      {/* E4: 各期限完整性 */}
      <div className="mb-3">
        <div className="text-[11px] text-gray-400 mb-1">各期限数据条数</div>
        {data.period_completeness?.length > 0 ? (
          <ReactECharts option={barOption} style={{ height: 200 }} opts={{ renderer: 'svg' }} />
        ) : <div className="text-gray-500 text-xs py-3 text-center">暂无数据</div>}
      </div>

      {/* E6: 最新各期限sparkline */}
      <div>
        <div className="text-[11px] text-gray-400 mb-2">最新收益率 (Sparkline)</div>
        <div className="space-y-2">
          {data.latest_yields?.map((y, i) => (
            <div key={y.period} className="flex items-center space-x-3">
              <span className="text-xs text-gray-400 w-10 flex-shrink-0">{y.display_name}</span>
              <span className="text-xs font-medium text-gray-200 w-14 text-right flex-shrink-0">
                {y.latest_value !== null ? `${y.latest_value}%` : '—'}
              </span>
              {y.sparkline?.length > 1 ? (
                <div className="flex-1 h-8">
                  <ReactECharts
                    option={sparklineOption(y.sparkline, PERIOD_COLORS[i] || '#6b7280')}
                    style={{ height: 32 }}
                    opts={{ renderer: 'svg' }}
                  />
                </div>
              ) : (
                <div className="flex-1 text-xs text-gray-600">数据不足</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
