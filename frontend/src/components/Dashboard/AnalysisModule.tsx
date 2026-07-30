/**
 * 模块B：分析引擎
 */
import React from 'react';
import ReactECharts from 'echarts-for-react';
import type { AnalysisModuleData } from '@/types';
import { PanelTitle, MetricCard, ProgressBar, TimelinessLabel } from './Widgets';
import { ALERT } from './constants';

interface Props { data: AnalysisModuleData; }

const modelColors: Record<string, string> = {
  doubao: '#3b82f6', deepseek: '#10b981', qwen: '#f59e0b', default: '#6b7280',
};

const directionColors: Record<string, string> = {
  '看涨': '#ef4444', '看跌': '#10b981', '中性': '#9ca3af',
};

export const AnalysisModule: React.FC<Props> = ({ data }) => {
  const pendingStatus = data.pending > 500 ? 'danger' : data.pending > 100 ? 'warning' : 'normal';
  const coverageStatus = data.coverage_pct < 50 ? 'danger' : data.coverage_pct < 80 ? 'warning' : 'normal';
  const validStatus = data.valid_analysis_pct < 90 ? 'warning' : 'normal';

  // B4: 模型分布饼图
  const pieOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
    },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['50%', '55%'],
      label: { color: '#9ca3af', fontSize: 10 },
      data: data.model_distribution?.map(d => ({
        name: d.model, value: d.count,
        itemStyle: { color: modelColors[d.model] || '#6b7280' },
      })) || [],
    }],
  };

  // B5: 7日方向堆叠柱状图
  const directionBarOption = (() => {
    const trend = data.direction_7d;
    if (!trend || trend.length === 0) return {};
    const directions = ['看涨', '看跌', '中性'];
    const dates = trend.map(t => t.date);
    return {
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 } },
      legend: { data: directions, textStyle: { color: '#9ca3af', fontSize: 10 }, top: 0 },
      grid: { left: 40, right: 10, top: 30, bottom: 25 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 9, rotate: 45 } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#1f2937' } } },
      series: directions.map(dir => ({
        name: dir, type: 'bar', stack: 'total',
        data: trend.map(t => (typeof t[dir] === 'number' ? t[dir] : 0) as number),
        itemStyle: { color: directionColors[dir] || '#6b7280' },
      })),
    };
  })();

  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
      <PanelTitle title="分析引擎" icon="🧩" />

      <div className="grid grid-cols-2 gap-2 mb-3">
        <MetricCard label="已分析" value={data.analyzed.toLocaleString()} />
        <MetricCard label="待分析" value={data.pending.toLocaleString()} status={pendingStatus} />
      </div>

      {/* B3: 分析覆盖率 */}
      <div className="mb-3">
        <ProgressBar label="分析覆盖率" value={data.coverage_pct} status={coverageStatus} />
      </div>

      {/* B4: 模型分布饼图 */}
      <div className="mb-3">
        <div className="text-[11px] text-gray-400 mb-1">模型分布</div>
        {data.model_distribution?.length > 0 ? (
          <ReactECharts option={pieOption} style={{ height: 160 }} opts={{ renderer: 'svg' }} />
        ) : <div className="text-gray-500 text-xs py-3 text-center">暂无数据</div>}
      </div>

      {/* B5: 7日方向分布 */}
      <div className="mb-3">
        <div className="text-[11px] text-gray-400 mb-1">7日分析方向分布</div>
        {data.direction_7d?.length > 0 ? (
          <ReactECharts option={directionBarOption} style={{ height: 150 }} opts={{ renderer: 'svg' }} />
        ) : <div className="text-gray-500 text-xs py-3 text-center">暂无数据</div>}
      </div>

      {/* B6: 有效分析占比 */}
      <div className="mb-2">
        <ProgressBar label="有效分析占比" value={data.valid_analysis_pct} status={validStatus} />
      </div>

      {/* B7: 分析时效性 */}
      <TimelinessLabel label="分析时效" diffHours={data.timeliness_diff_hours} threshold={2} />
    </div>
  );
};
