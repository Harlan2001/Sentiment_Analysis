/**
 * 部门概览 — 经理专属面板
 * 全局汇总卡片 + 部门行为图表 + Token趋势 + 模型分布 + 用户排行
 */
import React, { useEffect, useState, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import { fetchTokenTrend, fetchTokenByModel, fetchUserTokenList } from '@/api';
import { getPageTitle } from '@/config/labels';
import type { TokenTrendItem, TokenModelDist, UserTokenItem } from '@/types';

const API_PREFIX = '/sapi';

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

const DOW_LABELS = ['日', '一', '二', '三', '四', '五', '六'];

interface LeaderOverview {
  total_users: number; active_today: number; active_30d: number;
  today_tokens: number; month_tokens: number;
  power_users: number; churn_risk_users: number;
}

interface DeptBehavior {
  department: string; dept_size: number;
  active_users_today: number; sessions_today: number;
  avg_duration_7d: number;
  power_users: number; churn_risk_users: number;
  activity_trend: { date: string; dau: number; sessions: number }[];
  hourly_heatmap: { hour: number; day_of_week: number; count: number }[];
  page_distribution: { page_route: string; page_title: string; count: number }[];
  page_avg_duration: { page_route: string; avg_sec: number }[];
}

function fetchAuthHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  const t = localStorage.getItem('auth_token');
  if (t) {
    try { const p = JSON.parse(t); if (p) h['Authorization'] = `Bearer ${p}`; }
    catch { h['Authorization'] = `Bearer ${t}`; }
  }
  return h;
}

const DeptOverviewPanel: React.FC = () => {
  const [overview, setOverview] = useState<LeaderOverview | null>(null);
  const [behavior, setBehavior] = useState<DeptBehavior | null>(null);
  const [trend, setTrend] = useState<TokenTrendItem[]>([]);
  const [models, setModels] = useState<TokenModelDist[]>([]);
  const [users, setUsers] = useState<UserTokenItem[]>([]);
  const [trendDays, setTrendDays] = useState(7);
  const [behavDays, setBehavDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [userSort, setUserSort] = useState('month_tokens');
  const [userOrder, setUserOrder] = useState('desc');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const h = fetchAuthHeaders();
      const [ov, bh, tr, md, us] = await Promise.all([
        fetch(`${API_PREFIX}/dashboard/usage/overview`, { headers: h }).then(r => r.json()),
        fetch(`${API_PREFIX}/dashboard/usage/behavior?days=${behavDays}`, { headers: h }).then(r => r.json()),
        fetchTokenTrend(trendDays),
        fetchTokenByModel(trendDays),
        fetchUserTokenList({ sort_by: userSort, order: userOrder, limit: 20 }),
      ]);
      setOverview(ov);
      setBehavior(bh);
      setTrend(tr.trend);
      setModels(md.models);
      setUsers(us.items);
    } catch (e) {
      console.error('部门概览加载失败:', e);
    } finally {
      setLoading(false);
    }
  }, [trendDays, behavDays, userSort, userOrder]);

  useEffect(() => { load(); }, [load]);

  // ---- 图表配置 ----
  const trendOption = useCallback(() => {
    const t = behavior?.activity_trend || [];
    return {
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 } },
      legend: { data: ['日活', '会话数'], textStyle: { color: '#9ca3af', fontSize: 10 }, top: 0 },
      grid: { left: 50, right: 50, top: 30, bottom: 25 },
      xAxis: { type: 'category', data: t.map(d => d.date.slice(5)), axisLabel: { color: '#9ca3af', fontSize: 10 } },
      yAxis: [
        { type: 'value', name: '日活', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#1f2937' } } },
        { type: 'value', name: '会话数', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { show: false } },
      ],
      series: [
        { name: '日活', type: 'line', data: t.map(d => d.dau), smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { color: '#3b82f6', width: 2 }, itemStyle: { color: '#60a5fa' }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(59,130,246,0.3)' }, { offset: 1, color: 'rgba(59,130,246,0)' }] } } },
        { name: '会话数', type: 'bar', yAxisIndex: 1, data: t.map(d => d.sessions), barMaxWidth: 24, itemStyle: { color: 'rgba(16,185,129,0.5)', borderRadius: [4, 4, 0, 0] } },
      ],
    };
  }, [behavior?.activity_trend]);

  const heatmapOption = useCallback(() => {
    const data = behavior?.hourly_heatmap || [];
    if (!data.length) return null;
    const matrix: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0));
    data.forEach(d => { matrix[d.day_of_week - 1][d.hour] = d.count; });
    const maxVal = Math.max(...data.map(d => d.count), 1);
    return {
      tooltip: { backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 }, formatter: (p: { value: number[] }) => `周${DOW_LABELS[p.value[1]]} ${p.value[0]}:00-${p.value[0] + 1}:00<br/>访问量: <b>${p.value[2]}</b>` },
      grid: { left: 60, right: 80, top: 10, bottom: 10 },
      xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, i) => `${i}:00`), axisLabel: { color: '#9ca3af', fontSize: 9, interval: 2 } },
      yAxis: { type: 'category', data: DOW_LABELS.map(d => `周${d}`), axisLabel: { color: '#9ca3af', fontSize: 10 } },
      visualMap: { min: 0, max: maxVal, calculable: true, orient: 'vertical', right: 0, top: 'center', itemWidth: 12, itemHeight: 120, textStyle: { color: '#9ca3af', fontSize: 9 }, inRange: { color: ['#111827', '#1e3a5f', '#2563eb', '#60a5fa', '#93c5fd'] } },
      series: [{ type: 'heatmap', data: matrix.flatMap((row, dow) => row.map((val, hour) => [hour, dow, val])), label: { show: false } }],
    };
  }, [behavior?.hourly_heatmap]);

  const ringOption = useCallback(() => ({
    tooltip: { trigger: 'item', backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 } },
    legend: { orient: 'vertical', right: 5, top: 'center', textStyle: { color: '#9ca3af', fontSize: 9 } },
    series: [{ type: 'pie', radius: ['45%', '70%'], center: ['35%', '50%'], label: { show: false }, data: (behavior?.page_distribution || []).map((d, i) => ({ name: getPageTitle(d.page_title) || d.page_title, value: d.count, itemStyle: { color: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316'][i % 7] } })) }],
  }), [behavior?.page_distribution]);

  const barOption = useCallback(() => ({
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(17,24,39,0.95)', borderColor: '#374151', textStyle: { color: '#e5e7eb', fontSize: 12 } },
    grid: { left: 100, right: 50, top: 5, bottom: 5 },
    xAxis: { type: 'value', name: '秒', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#1f2937' } } },
    yAxis: { type: 'category', data: (behavior?.page_avg_duration || []).map(d => getPageTitle(d.page_route)).reverse(), axisLabel: { color: '#9ca3af', fontSize: 9 } },
    series: [{ type: 'bar', data: (behavior?.page_avg_duration || []).map(d => ({ value: d.avg_sec, itemStyle: { color: '#3b82f6', borderRadius: [0, 4, 4, 0] } })).reverse(), label: { show: true, position: 'right', color: '#9ca3af', fontSize: 10, formatter: '{c}秒' } }],
  }), [behavior?.page_avg_duration]);

  if (loading && !overview) {
    return (
      <div className="text-center py-16 text-gray-400">
        <div className="animate-spin w-8 h-8 border-2 border-green-400 border-t-transparent rounded-full mx-auto mb-3" />
        加载部门概览...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 部门标识 */}
      <div className="flex items-center gap-2 text-xs">
        <span className="text-gray-500">部门:</span>
        <span className="px-2 py-0.5 rounded bg-green-900/40 text-green-300">{behavior?.department || '—'}</span>
        <span className="text-gray-600">|</span>
        <span className="text-gray-500">人数:</span>
        <span className="text-gray-200">{behavior?.dept_size ?? '—'}</span>
      </div>

      {/* Top Cards — 全局汇总 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">总用户数</div>
          <div className="text-xl font-bold text-white">{overview?.total_users ?? '-'}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">今日活跃</div>
          <div className="text-xl font-bold text-green-400">{overview?.active_today ?? '-'}</div>
          <div className="text-[10px] text-gray-500 mt-0.5">30日: {overview?.active_30d ?? '-'}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">今日Token</div>
          <div className="text-xl font-bold text-blue-400">{overview ? formatTokens(overview.today_tokens) : '-'}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">本月Token</div>
          <div className="text-xl font-bold text-purple-400">{overview ? formatTokens(overview.month_tokens) : '-'}</div>
        </div>
      </div>

      {/* 部门行为概览卡片：今日会话 / 平均停留 / 重度用户 / 流失风险 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-[11px] text-gray-400">今日会话</div>
          <div className="text-lg font-bold text-blue-400 mt-0.5">{behavior?.sessions_today ?? '-'}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-[11px] text-gray-400">7日平均停留</div>
          <div className="text-lg font-bold text-white mt-0.5">
            {behavior?.avg_duration_7d ? `${Math.round(behavior.avg_duration_7d / 60)}min` : '—'}
          </div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3 flex items-center justify-between">
          <span className="text-[11px] text-gray-400">重度用户</span>
          <span className="text-lg font-bold text-green-400">{behavior?.power_users ?? '-'}</span>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3 flex items-center justify-between">
          <span className="text-[11px] text-gray-400">流失风险</span>
          <span className="text-lg font-bold text-red-400">{behavior?.churn_risk_users ?? '-'}</span>
        </div>
      </div>

      {/* 行为图表：活跃趋势 + 时段热力 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs text-gray-400 font-medium">📈 用户活跃趋势</div>
            <select className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1" value={behavDays} onChange={e => setBehavDays(Number(e.target.value))}>
              <option value={7}>7天</option><option value={30}>30天</option>
            </select>
          </div>
          {(behavior?.activity_trend || []).length > 0 ? (
            <ReactECharts option={trendOption()} style={{ height: 220 }} opts={{ renderer: 'svg' }} />
          ) : <div className="text-gray-500 text-sm py-10 text-center">暂无数据</div>}
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <div className="text-xs text-gray-400 font-medium mb-2">🕐 时段热力分布</div>
          {heatmapOption() ? (
            <ReactECharts option={heatmapOption()!} style={{ height: 220 }} opts={{ renderer: 'svg' }} />
          ) : <div className="text-gray-500 text-sm py-10 text-center">暂无数据</div>}
        </div>
      </div>

      {/* 页面分布 + 停留排行 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <div className="text-xs text-gray-400 font-medium mb-2">📊 页面访问分布</div>
          {(behavior?.page_distribution || []).length > 0 ? (
            <ReactECharts option={ringOption()} style={{ height: 220 }} opts={{ renderer: 'svg' }} />
          ) : <div className="text-gray-500 text-sm py-10 text-center">暂无数据</div>}
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <div className="text-xs text-gray-400 font-medium mb-2">⏱️ 平均停留时长排行</div>
          {(behavior?.page_avg_duration || []).length > 0 ? (
            <ReactECharts option={barOption()} style={{ height: 220 }} opts={{ renderer: 'svg' }} />
          ) : <div className="text-gray-500 text-sm py-10 text-center">暂无数据</div>}
        </div>
      </div>

      {/* Token趋势 + 模型分布 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-300">Token消耗趋势</h3>
            <select className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1" value={trendDays} onChange={e => setTrendDays(Number(e.target.value))}>
              <option value={7}>近7天</option><option value={30}>近30天</option>
            </select>
          </div>
          {trend.length === 0 ? (
            <div className="text-gray-500 text-sm text-center py-6">暂无数据</div>
          ) : (
            <div className="flex items-end gap-1 h-32">
              {trend.map(item => {
                const maxTotal = Math.max(...trend.map(t => t.total as number), 1);
                const h = Math.max(2, Math.round(((item.total as number) / maxTotal) * 100));
                return (
                  <div key={item.date} className="flex-1 flex flex-col items-center justify-end h-full" title={`${item.date}: ${formatTokens(item.total as number)}`}>
                    <span className="text-[10px] text-gray-400 mb-1">{formatTokens(item.total as number)}</span>
                    <div className="w-full bg-green-500/60 hover:bg-green-400 rounded-t" style={{ height: `${h}%`, minHeight: '2px' }} />
                    <span className="text-[10px] text-gray-500 mt-1">{item.date.slice(5)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">模型用量分布（{trendDays}天）</h3>
          {models.length === 0 ? (
            <div className="text-gray-500 text-sm text-center py-6">暂无数据</div>
          ) : (
            <div className="space-y-3">
              {models.map(m => (
                <div key={m.model}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-300">{m.model}</span>
                    <span className="text-gray-400">{formatTokens(m.tokens)} ({m.percentage}%)</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2.5">
                    <div className="bg-gradient-to-r from-green-500 to-blue-500 h-2.5 rounded-full" style={{ width: `${Math.max(m.percentage, 2)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 用户排行 Top20 */}
      <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-300">部门用户Token排行（Top 20）</h3>
          <div className="flex items-center gap-2 text-xs">
            <select className="rounded bg-gray-700 border border-gray-600 text-gray-200 px-2 py-1" value={userSort} onChange={e => { setUserSort(e.target.value); }}>
              <option value="month_tokens">本月Token</option>
              <option value="today_tokens">今日Token</option>
              <option value="total_tokens">累计Token</option>
              <option value="total_calls">调用次数</option>
            </select>
            <button className="px-2 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600" onClick={() => setUserOrder(o => o === 'desc' ? 'asc' : 'desc')}>{userOrder === 'desc' ? '↓降序' : '↑升序'}</button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-gray-700/50 text-gray-400">
              <th className="text-left py-2 px-2">#</th><th className="text-left py-2 px-2">用户</th>
              <th className="text-right py-2 px-2">今日Token</th><th className="text-right py-2 px-2">本月Token</th>
              <th className="text-right py-2 px-2">累计Token</th><th className="text-right py-2 px-2">调用次数</th>
              <th className="text-right py-2 px-2">活跃天数</th>
            </tr></thead>
            <tbody>
              {users.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-6 text-gray-400">暂无数据</td></tr>
              ) : users.map((u, i) => (
                <tr key={u.user_id} className="border-b border-gray-800 hover:bg-gray-800/40">
                  <td className="py-1.5 px-2 text-gray-500">{i + 1}</td>
                  <td className="py-1.5 px-2 text-gray-200">{u.display_name || u.username}</td>
                  <td className="py-1.5 px-2 text-right text-green-400 font-mono">{formatTokens(u.today_tokens)}</td>
                  <td className="py-1.5 px-2 text-right text-blue-400 font-mono">{formatTokens(u.month_tokens)}</td>
                  <td className="py-1.5 px-2 text-right text-gray-300 font-mono">{formatTokens(u.total_tokens)}</td>
                  <td className="py-1.5 px-2 text-right text-gray-300">{u.total_calls}</td>
                  <td className="py-1.5 px-2 text-right text-gray-300">{u.active_days_30d}天</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DeptOverviewPanel;
