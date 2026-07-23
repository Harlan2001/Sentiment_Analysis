/**
 * 模块L：用户行为审计面板（管理员可见）
 * 增强版：7日活跃趋势 + 时段热力图 + 操作/目标列 + 日期范围选择器
 */
import React, { useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { BehaviorStats, AuditLogEntry } from '../../types';
import { useBehaviorLogs } from '../../hooks/useSimpleBehavior';
import { MetricCard } from './Widgets';
import { pageTitle } from '../../utils/pageTitle';
import { getActionLabel, getExitTypeLabel, getActionTargetLabel, ACTION_LABEL_MAP } from '../../config/labels';

interface Props {
  stats: BehaviorStats | undefined;
  statsLoading: boolean;
  days: number;
}

// 星期/小时映射
const DOW_LABELS = ['日', '一', '二', '三', '四', '五', '六'];
const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => `${i}:00`);

function actionLabel(type: string): string {
  return getActionLabel(type);
}

export const BehaviorPanel: React.FC<Props> = ({ stats, statsLoading, days }) => {
  // 默认日期范围：最近10天
  const defaultStart = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - 10);
    return d.toISOString().slice(0, 10);
  }, []);

  // 日期范围选择器状态
  const [dateRangeOpen, setDateRangeOpen] = useState(false);
  const [dateStart, setDateStart] = useState(defaultStart);
  const [dateEnd, setDateEnd] = useState('');

  const [logFilter, setLogFilter] = useState<{
    user_id?: string;
    page_route?: string;
    action_type?: string;
    limit?: number;
    offset?: number;
  }>({ limit: 30, offset: 0 });

  const actualFilter = {
    ...logFilter,
    start: dateStart || undefined,
    end: dateEnd || undefined,
  };

  const { data: logData, isLoading: logLoading } = useBehaviorLogs(actualFilter, true);

  // 应用日期范围
  const applyDateRange = () => {
    setLogFilter(prev => ({ ...prev, offset: 0 }));
    setDateRangeOpen(false);
  };

  // 清除日期范围
  const clearDateRange = () => {
    setDateStart('');
    setDateEnd('');
    setLogFilter(prev => ({ ...prev, offset: 0 }));
  };

  // 已选日期范围的显示文本
  const dateRangeLabel = dateStart && dateEnd
    ? `${dateStart} ~ ${dateEnd}`
    : dateStart ? `${dateStart} 起` : dateEnd ? `至 ${dateEnd}` : '';

  // ========== L9: 页面访问分布环形图 ==========
  const ringOption = {
    tooltip: { trigger: 'item', backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 } },
    legend: { orient: 'vertical', right: 5, top: 'center', textStyle: { color: '#9ca3af', fontSize: 9 } },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['35%', '50%'],
      label: { show: false },
      data: stats?.page_distribution?.map((d, i) => ({
        name: d.page_title,
        value: d.count,
        itemStyle: { color: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316'][i % 7] },
      })) || [],
    }],
  };

  // ========== L12: 页面平均停留排行 ==========
  const durationBarOption = {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 } },
    grid: { left: 100, right: 50, top: 5, bottom: 5 },
    xAxis: { type: 'value', name: '秒', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#1f2937' } } },
    yAxis: {
      type: 'category',
      data: stats?.page_avg_duration?.map(d => pageTitle(d.page_route)).reverse() || [],
      axisLabel: { color: '#9ca3af', fontSize: 9 },
    },
    series: [{
      type: 'bar',
      data: stats?.page_avg_duration?.map(d => ({
        value: d.avg_sec,
        itemStyle: { color: '#3b82f6', borderRadius: [0, 4, 4, 0] },
      })).reverse() || [],
      label: { show: true, position: 'right', color: '#9ca3af', fontSize: 10, formatter: '{c}s' },
    }],
  };

  // ========== L7: 7日活跃趋势 折线+柱状混合图 ==========
  const activityTrendOption = useMemo(() => {
    const trend = stats?.activity_trend || [];
    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(17,24,39,0.95)',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb', fontSize: 12 },
      },
      legend: {
        data: ['日活', '会话数'],
        textStyle: { color: '#9ca3af', fontSize: 10 },
        top: 0,
      },
      grid: { left: 50, right: 50, top: 30, bottom: 25 },
      xAxis: {
        type: 'category',
        data: trend.map(t => t.date.slice(5)),
        axisLabel: { color: '#9ca3af', fontSize: 10 },
        axisLine: { lineStyle: { color: '#374151' } },
      },
      yAxis: [
        {
          type: 'value',
          name: '日活',
          axisLabel: { color: '#9ca3af', fontSize: 10 },
          splitLine: { lineStyle: { color: '#1f2937' } },
        },
        {
          type: 'value',
          name: '会话数',
          axisLabel: { color: '#9ca3af', fontSize: 10 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '日活',
          type: 'line',
          data: trend.map(t => t.dau),
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { color: '#3b82f6', width: 2 },
          itemStyle: { color: '#60a5fa' },
          areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(59,130,246,0.3)' }, { offset: 1, color: 'rgba(59,130,246,0)' }] } },
        },
        {
          name: '会话数',
          type: 'bar',
          yAxisIndex: 1,
          data: trend.map(t => t.sessions),
          barMaxWidth: 24,
          itemStyle: { color: 'rgba(16,185,129,0.5)', borderRadius: [4, 4, 0, 0] },
        },
      ],
    };
  }, [stats?.activity_trend]);

  // ========== L8: 时段热力矩阵 ==========
  const heatmapOption = useMemo(() => {
    const data = stats?.hourly_heatmap || [];
    if (!data.length) return null;

    // 构建 24x7 矩阵 (小时 0-23, 星期 1-7)
    const matrix: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0));
    data.forEach(d => {
      // MySQL DAYOFWEEK: 1=Sun, 2=Mon, ..., 7=Sat
      const dowIdx = d.day_of_week - 1; // 0=Sun, 1=Mon, ...6=Sat
      matrix[dowIdx][d.hour] = d.count;
    });

    const maxVal = Math.max(...data.map(d => d.count), 1);

    return {
      tooltip: {
        backgroundColor: 'rgba(17,24,39,0.95)',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb', fontSize: 12 },
        formatter: (p: { value: number[] }) =>
          `周${DOW_LABELS[p.value[1]]} ${p.value[0]}:00-${p.value[0] + 1}:00<br/>访问量: <b>${p.value[2]}</b>`,
      },
      grid: { left: 60, right: 80, top: 10, bottom: 10 },
      xAxis: {
        type: 'category',
        data: HOUR_LABELS,
        axisLabel: { color: '#9ca3af', fontSize: 9, interval: 2 },
        splitArea: { show: true, areaStyle: { color: ['rgba(0,0,0,0)', 'rgba(0,0,0,0.05)'] } },
      },
      yAxis: {
        type: 'category',
        data: DOW_LABELS.map(d => `周${d}`),
        axisLabel: { color: '#9ca3af', fontSize: 10 },
      },
      visualMap: {
        min: 0,
        max: maxVal,
        calculable: true,
        orient: 'vertical',
        right: 0,
        top: 'center',
        itemWidth: 12,
        itemHeight: 120,
        textStyle: { color: '#9ca3af', fontSize: 9 },
        inRange: { color: ['#111827', '#1e3a5f', '#2563eb', '#60a5fa', '#93c5fd'] },
      },
      series: [{
        type: 'heatmap',
        data: matrix.flatMap((row, dow) =>
          row.map((val, hour) => [hour, dow, val])
        ),
        label: { show: false },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' },
        },
      }],
    };
  }, [stats?.hourly_heatmap]);

  // 日志筛选控件
  const handleFilterChange = (key: string, value: string) => {
    setLogFilter(prev => ({ ...prev, [key]: value || undefined, offset: 0 }));
  };

  const handlePageChange = (direction: 'prev' | 'next') => {
    setLogFilter(prev => ({
      ...prev,
      offset: Math.max(0, (prev.offset || 0) + (direction === 'next' ? (prev.limit || 30) : -(prev.limit || 30))),
    }));
  };

  // 导出CSV
  const handleExportCSV = () => {
    if (!logData?.items?.length) return;
    const headers = ['时间', '用户', '页面', '操作', '目标', '停留时长(秒)', '离开方式'];
    const rows = logData.items.map(item => [
      item.enter_time,
      item.username,
      item.page_title || item.page_route,
      actionLabel(item.action_type || 'page_enter'),
      item.action_target || '',
      String(item.duration_sec || ''),
      item.exit_type || '',
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (statsLoading) {
    return <div className="text-center text-gray-400 py-12">加载中...</div>;
  }

  return (
    <div className="space-y-4">
      {/* L1/L2/L3 卡片 + 重度用户 + 流失风险 */}
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
        <MetricCard label="今日活跃用户" value={stats?.active_users_today || 0} />
        <MetricCard label="今日会话数" value={stats?.sessions_today || 0} />
        <div className="rounded-lg border border-gray-700/50 bg-gray-800/40 px-4 py-3">
          <div className="text-[11px] text-gray-400">7日平均停留</div>
          <div className="text-xl font-bold text-white mt-0.5">
            {stats?.avg_duration_7d ? `${Math.round(stats.avg_duration_7d / 60)}min` : '—'}
          </div>
        </div>
        <MetricCard
          label="重度用户"
          value={stats?.power_users ?? '—'}
          status={stats?.power_users !== undefined && stats.power_users > 0 ? 'normal' : 'normal'}
        />
        <MetricCard
          label="流失风险"
          value={stats?.churn_risk_users ?? '—'}
          status={stats?.churn_risk_users !== undefined && stats.churn_risk_users > 0 ? 'warning' : 'normal'}
        />
      </div>

      {/* L7: 7日活跃趋势 + L8: 时段热力图 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
          <div className="text-xs text-gray-400 font-medium mb-2">📈 用户活跃趋势 (7日)</div>
          {stats?.activity_trend?.length ? (
            <ReactECharts option={activityTrendOption} style={{ height: 240 }} opts={{ renderer: 'svg' }} />
          ) : <div className="text-gray-500 text-sm py-10 text-center">暂无数据</div>}
        </div>

        <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
          <div className="text-xs text-gray-400 font-medium mb-2">🕐 时段热力分布</div>
          {heatmapOption ? (
            <ReactECharts option={heatmapOption} style={{ height: 240 }} opts={{ renderer: 'svg' }} />
          ) : <div className="text-gray-500 text-sm py-10 text-center">暂无数据</div>}
        </div>
      </div>

      {/* L9 页面分布 + L12 停留排行 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
          <div className="text-xs text-gray-400 font-medium mb-2">📊 页面访问分布 ({days}日)</div>
          {stats?.page_distribution?.length ? (
            <ReactECharts option={ringOption} style={{ height: 220 }} opts={{ renderer: 'svg' }} />
          ) : <div className="text-gray-500 text-sm py-6 text-center">暂无数据</div>}
        </div>

        <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
          <div className="text-xs text-gray-400 font-medium mb-2">⏱️ 平均停留时长排行</div>
          {stats?.page_avg_duration?.length ? (
            <ReactECharts option={durationBarOption} style={{ height: 220 }} opts={{ renderer: 'svg' }} />
          ) : <div className="text-gray-500 text-sm py-6 text-center">暂无数据</div>}
        </div>
      </div>

      {/* L11: 审计日志表格 */}
      <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="text-xs text-gray-400 font-medium">📋 行为审计日志</div>
          <button
            onClick={handleExportCSV}
            data-track="export"
            data-target="audit_log"
            className="text-xs text-blue-400 hover:text-blue-300 border border-blue-700/50 px-3 py-1 rounded"
          >
            导出CSV
          </button>
        </div>

        {/* 筛选栏 */}
        <div className="flex flex-wrap gap-2 mb-3 items-center">
          <input
            type="text"
            placeholder="用户ID"
            className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1 w-24"
            onChange={e => handleFilterChange('user_id', e.target.value)}
          />
          <select
            className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1"
            onChange={e => handleFilterChange('page_route', e.target.value)}
            defaultValue=""
          >
            <option value="">全部页面</option>
            {['/news', '/factors', '/data', '/prediction', '/agents', '/strategies', '/change', '/dashboard'].map(r => (
              <option key={r} value={r}>{pageTitle(r)}</option>
            ))}
          </select>
          <select
            className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1"
            onChange={e => handleFilterChange('action_type', e.target.value)}
            defaultValue=""
          >
            <option value="">全部操作</option>
            {Object.entries(ACTION_LABEL_MAP).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>

          {/* 日期范围选择器：一个框，打开两个并排日历 */}
          <div className="relative flex items-center">
            <button
              onClick={() => setDateRangeOpen(!dateRangeOpen)}
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded border transition-colors ${
                dateStart || dateEnd
                  ? 'bg-blue-900/30 border-blue-700/50 text-blue-300'
                  : 'bg-gray-700 border-gray-600 text-gray-400 hover:text-gray-300'
              }`}
            >
              <span>📅</span>
              {dateRangeLabel || '日期范围'}
              {(dateStart || dateEnd) && (
                <span onClick={(e) => { e.stopPropagation(); clearDateRange(); }} className="ml-1 text-gray-500 hover:text-gray-300">&times;</span>
              )}
            </button>

            {/* 弹出并排双日历 */}
            {dateRangeOpen && (
              <div className="absolute top-full left-0 mt-1 z-50 bg-gray-800 border border-gray-600 rounded-lg p-3 shadow-xl">
                <div className="flex gap-3">
                  <div>
                    <div className="text-[11px] text-gray-400 mb-1">开始日期</div>
                    <input
                      type="date"
                      value={dateStart}
                      onChange={e => setDateStart(e.target.value)}
                      className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1.5 w-36"
                    />
                  </div>
                  <div>
                    <div className="text-[11px] text-gray-400 mb-1">结束日期</div>
                    <input
                      type="date"
                      value={dateEnd}
                      onChange={e => setDateEnd(e.target.value)}
                      className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1.5 w-36"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2 mt-3">
                  <button
                    onClick={() => setDateRangeOpen(false)}
                    className="text-xs px-3 py-1 rounded bg-gray-700 text-gray-400 hover:text-gray-300"
                  >
                    取消
                  </button>
                  <button
                    onClick={applyDateRange}
                    className="text-xs px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-500"
                  >
                    应用
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 数据表格 */}
        {logLoading ? (
          <div className="text-center text-gray-500 text-sm py-6">加载中...</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-700">
                    <th className="text-left py-2 px-2">日期</th>
                    <th className="text-left py-2 px-2">时间</th>
                    <th className="text-left py-2 px-2">用户</th>
                    <th className="text-left py-2 px-2">页面</th>
                    <th className="text-left py-2 px-2">操作</th>
                    <th className="text-left py-2 px-2">目标</th>
                    <th className="text-right py-2 px-2">停留</th>
                    <th className="text-left py-2 px-2">离开方式</th>
                  </tr>
                </thead>
                <tbody>
                  {logData?.items?.map((item: AuditLogEntry) => (
                    <tr key={item.id} className="border-b border-gray-700/30 hover:bg-gray-700/20">
                      <td className="text-gray-400 py-1.5 px-2 whitespace-nowrap">
                        {item.enter_time ? new Date(item.enter_time).toLocaleDateString('zh-CN') : '—'}
                      </td>
                      <td className="text-gray-300 py-1.5 px-2 whitespace-nowrap">
                        {item.enter_time ? new Date(item.enter_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'}
                      </td>
                      <td className="text-gray-300 py-1.5 px-2">{item.username}</td>
                      <td className="text-gray-400 py-1.5 px-2">{item.page_title || item.page_route}</td>
                      <td className="text-gray-300 py-1.5 px-2">
                        <span className="text-[11px] px-1.5 py-0.5 rounded bg-gray-700/50">
                          {actionLabel(item.action_type || 'page_enter')}
                        </span>
                      </td>
                      <td className="text-gray-400 py-1.5 px-2 max-w-[120px] truncate" title={item.action_target || ''}>
                        {getActionTargetLabel(item.action_target || '') || '—'}
                      </td>
                      <td className="text-right text-gray-400 py-1.5 px-2">
                        {item.duration_sec ? `${item.duration_sec}秒` : '—'}
                      </td>
                      <td className="text-gray-500 py-1.5 px-2">
                        {getExitTypeLabel(item.exit_type || '') || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(!logData?.items || logData.items.length === 0) && (
                <div className="text-center text-gray-500 text-sm py-6">暂无日志数据</div>
              )}
            </div>

            {/* 分页 */}
            <div className="flex items-center justify-between mt-3 text-xs text-gray-500">
              <div className="flex items-center space-x-2">
                <span>共 {logData?.total || 0} 条，每页 {logFilter.limit || 30} 条</span>
                <span className="text-gray-600">|</span>
                <span>默认最近10天，日志保留 180 天</span>
              </div>
              {logData && logData.total > 0 && (
                <div className="flex items-center space-x-3">
                  <span>第 {(logFilter.offset || 0) / (logFilter.limit || 30) + 1}/{Math.max(1, Math.ceil(logData.total / (logFilter.limit || 30)))} 页</span>
                  <div className="space-x-2">
                    <button
                      className="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-40"
                      disabled={(logFilter.offset || 0) === 0}
                      onClick={() => handlePageChange('prev')}
                    >上一页</button>
                    <button
                      className="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-40"
                      disabled={(logFilter.offset || 0) + (logFilter.limit || 30) >= (logData?.total || 0)}
                      onClick={() => handlePageChange('next')}
                    >下一页</button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
