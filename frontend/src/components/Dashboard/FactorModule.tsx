/**
 * 模块C：因子体系
 */
import React from 'react';
import ReactECharts from 'echarts-for-react';
import type { FactorModuleData } from '../../types';
import { PanelTitle, MetricCard, ProgressBar, TimelinessLabel } from './Widgets';
import { CATEGORY_COLORS, CATEGORY_NAME_MAP, ALERT } from './constants';

interface Props { data: FactorModuleData; }

export const FactorModule: React.FC<Props> = ({ data }) => {
  const assocStatus = data.association_coverage_pct < ALERT.FACTOR_ASSOC_COVERAGE_YELLOW ? 'warning' : 'normal';

  // C2: 南丁格尔玫瑰图（去除图例，避免遮挡）
  const roseOption = {
    tooltip: { trigger: 'item', backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 } },
    series: [{
      type: 'pie',
      roseType: 'radius',
      radius: ['25%', '72%'],
      center: ['50%', '50%'],
      label: {
        color: '#9ca3af',
        fontSize: 9,
        formatter: '{b}\n{d}%',
        lineHeight: 12,
      },
      labelLine: { lineStyle: { color: '#4b5563' } },
      data: data.category_distribution?.map(d => ({
        name: d.display_name || CATEGORY_NAME_MAP[d.category] || d.category,
        value: d.count,
        itemStyle: { color: CATEGORY_COLORS[d.category] || '#6b7280' },
      })) || [],
    }],
  };

  // C3: 因子类型饼图
  const typePieOption = {
    tooltip: { trigger: 'item', backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['40%', '65%'],
      center: ['50%', '50%'],
      label: { color: '#9ca3af', fontSize: 10 },
      data: data.type_distribution?.map(d => ({
        name: d.factor_type === 'quantitative' ? '量化' : '概念',
        value: d.count,
        itemStyle: { color: d.factor_type === 'quantitative' ? '#3b82f6' : '#f59e0b' },
      })) || [],
    }],
  };

  // C4: 新因子7日趋势折线图
  const lineOption = {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 } },
    grid: { left: 40, right: 10, top: 10, bottom: 25 },
    xAxis: {
      type: 'category',
      data: data.new_factors_trend_7d?.map(t => t.date) || [],
      axisLabel: { color: '#9ca3af', fontSize: 9, rotate: 45 },
    },
    yAxis: { type: 'value', axisLabel: { color: '#9ca3af', fontSize: 10 }, minInterval: 1, splitLine: { lineStyle: { color: '#1f2937' } } },
    series: [{
      type: 'line',
      data: data.new_factors_trend_7d?.map(t => t.count) || [],
      smooth: true,
      lineStyle: { color: '#8b5cf6', width: 2 },
      itemStyle: { color: '#8b5cf6' },
      areaStyle: { color: 'rgba(139,92,246,0.15)' },
    }],
  };

  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
      <PanelTitle title="因子体系" icon="📊" />

      <div className="grid grid-cols-2 gap-2 mb-3">
        <MetricCard label="因子总数" value={data.total.toLocaleString()} />
        <MetricCard label="新因子(7日)" value={data.new_factors_7d.toLocaleString()} />
      </div>

      {/* C2: 南丁格尔玫瑰图 */}
      <div className="mb-3">
        <div className="text-[11px] text-gray-400 mb-1">因子分类分布</div>
        {data.category_distribution?.length > 0 ? (
          <ReactECharts option={roseOption} style={{ height: 180 }} opts={{ renderer: 'svg' }} />
        ) : <div className="text-gray-500 text-xs py-3 text-center">暂无数据</div>}
      </div>

      {/* C3: 因子类型饼图 */}
      <div className="mb-3">
        <div className="text-[11px] text-gray-400 mb-1">因子类型分布</div>
        {data.type_distribution?.length > 0 ? (
          <ReactECharts option={typePieOption} style={{ height: 120 }} opts={{ renderer: 'svg' }} />
        ) : <div className="text-gray-500 text-xs py-3 text-center">暂无数据</div>}
      </div>

      {/* C4: 新因子7日趋势 */}
      <div className="mb-3">
        <div className="text-[11px] text-gray-400 mb-1">新因子7日趋势</div>
        {data.new_factors_trend_7d?.length > 0 ? (
          <ReactECharts option={lineOption} style={{ height: 120 }} opts={{ renderer: 'svg' }} />
        ) : <div className="text-gray-500 text-xs py-3 text-center">暂无新因子</div>}
      </div>

      {/* C5: 关联覆盖率 */}
      <div className="mb-2">
        <ProgressBar label="因子关联覆盖率" value={data.association_coverage_pct} status={assocStatus} />
      </div>

      {/* C6: 更新时效 */}
      <TimelinessLabel label="因子更新时效" diffMinutes={data.update_timeliness_diff_minutes} diffHours={null} threshold={2} />
    </div>
  );
};
