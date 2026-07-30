import React from 'react';
import ReactECharts from 'echarts-for-react';
import type { ResearchModuleData } from '@/types';
import { PanelTitle, MetricCard } from './Widgets';

interface Props { data: ResearchModuleData | undefined }

export const ResearchModule: React.FC<Props> = ({ data }) => {
  if (!data) return null;

  const analyzedPct = data.total > 0 ? ((data.analyzed / data.total) * 100).toFixed(0) : '0';

  const pieOption = {
    tooltip: {
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: '{b}: {c} 份 ({d}%)',
    },
    series: [{
      type: 'pie',
      radius: ['55%', '80%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderColor: '#1f2937', borderWidth: 2 },
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
      },
      data: [
        { value: data.bullish, name: '看多', itemStyle: { color: '#ef4444' } },
        { value: data.bearish, name: '看空', itemStyle: { color: '#22c55e' } },
        { value: data.neutral, name: '中性', itemStyle: { color: '#6b7280' } },
      ],
    }],
  };

  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
      <PanelTitle title="研报分析" icon="📊" />

      <div className="grid grid-cols-2 gap-2 mb-3">
        <MetricCard label="研报总数" value={data.total.toLocaleString()} />
        <MetricCard label="已分析" value={`${data.analyzed} (${analyzedPct}%)`} />
      </div>

      {/* 观点分布饼图 */}
      {(data.bullish > 0 || data.bearish > 0 || data.neutral > 0) && (
        <ReactECharts option={pieOption} style={{ height: 140 }} opts={{ renderer: 'svg' }} />
      )}
    </div>
  );
};
