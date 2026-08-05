/**
 * 领导看板 — 管理员/经理可见
 * 全局汇总卡片 + Token趋势 + 模型分布 + 用户排行
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { fetchTokenTrend, fetchTokenByModel, fetchUserTokenList } from '@/api';
import type { TokenTrendItem, TokenModelDist, UserTokenItem } from '@/types';

const API_PREFIX = '/sapi';

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

interface LeaderOverview {
  total_users: number;
  active_today: number;
  active_30d: number;
  today_tokens: number;
  month_tokens: number;
  power_users: number;
  churn_risk_users: number;
}

const LeaderDashboardPanel: React.FC = () => {
  const { isAdmin, role } = useAuth();
  const [overview, setOverview] = useState<LeaderOverview | null>(null);
  const [trend, setTrend] = useState<TokenTrendItem[]>([]);
  const [models, setModels] = useState<TokenModelDist[]>([]);
  const [users, setUsers] = useState<UserTokenItem[]>([]);
  const [trendDays, setTrendDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [userSort, setUserSort] = useState('month_tokens');
  const [userOrder, setUserOrder] = useState('desc');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const headers: Record<string, string> = {};
      const token = (window as any).__auth_token;
      if (token) headers['Authorization'] = `Bearer ${token}`;
      else {
        const stored = localStorage.getItem('auth_token');
        if (stored) {
          try { const t = JSON.parse(stored); if (t) headers['Authorization'] = `Bearer ${t}`; }
          catch { headers['Authorization'] = `Bearer ${stored}`; }
        }
      }

      const fetchHeaders = () => {
        const h: Record<string, string> = {};
        const t = localStorage.getItem('auth_token');
        if (t) {
          try { const p = JSON.parse(t); if (p) h['Authorization'] = `Bearer ${p}`; }
          catch { h['Authorization'] = `Bearer ${t}`; }
        }
        return h;
      };

      const h = fetchHeaders();

      const [ov, tr, md, us] = await Promise.all([
        fetch(`${API_PREFIX}/dashboard/usage/overview`, { headers: h }).then(r => r.json()),
        fetchTokenTrend(trendDays),
        fetchTokenByModel(trendDays),
        fetchUserTokenList({ sort_by: userSort, order: userOrder, limit: 20 }),
      ]);
      setOverview(ov);
      setTrend(tr.trend);
      setModels(md.models);
      setUsers(us.items);
    } catch (e) {
      console.error('领导看板加载失败:', e);
    } finally {
      setLoading(false);
    }
  }, [trendDays, userSort, userOrder]);

  useEffect(() => { load(); }, [load]);

  const roleLabel = isAdmin ? '管理员' : role === 'manager' ? '经理' : '';

  if (loading && !overview) {
    return (
      <div className="text-center py-16 text-gray-400">
        <div className="animate-spin w-8 h-8 border-2 border-purple-400 border-t-transparent rounded-full mx-auto mb-3" />
        加载领导看板...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 角色标识 */}
      <div className="flex items-center gap-2 text-xs">
        <span className="text-gray-500">视角:</span>
        <span className={`px-2 py-0.5 rounded ${isAdmin ? 'bg-red-900/40 text-red-300' : 'bg-yellow-900/40 text-yellow-300'}`}>
          {roleLabel}
        </span>
      </div>

      {/* Top Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">总用户数</div>
          <div className="text-xl font-bold text-white">{overview?.total_users ?? '-'}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">今日活跃</div>
          <div className="text-xl font-bold text-green-400">{overview?.active_today ?? '-'}</div>
          <div className="text-[10px] text-gray-500 mt-0.5">30日活跃: {overview?.active_30d ?? '-'}</div>
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

      {/* 第二行：重度用户 + 流失风险 */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3 flex items-center justify-between">
          <span className="text-xs text-gray-400">重度用户</span>
          <span className="text-lg font-bold text-green-400">{overview?.power_users ?? '-'}</span>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3 flex items-center justify-between">
          <span className="text-xs text-gray-400">流失风险</span>
          <span className="text-lg font-bold text-red-400">{overview?.churn_risk_users ?? '-'}</span>
        </div>
      </div>

      {/* Token趋势 + 模型分布 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-300">Token消耗趋势</h3>
            <select
              className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1"
              value={trendDays}
              onChange={e => setTrendDays(Number(e.target.value))}
            >
              <option value={7}>近7天</option>
              <option value={30}>近30天</option>
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
                  <div key={item.date} className="flex-1 flex flex-col items-center justify-end h-full"
                    title={`${item.date}: ${formatTokens(item.total as number)}`}>
                    <span className="text-[10px] text-gray-400 mb-1">{formatTokens(item.total as number)}</span>
                    <div className="w-full bg-purple-500/60 hover:bg-purple-400 rounded-t" style={{ height: `${h}%`, minHeight: '2px' }} />
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
                    <div className="bg-gradient-to-r from-white to-gray-400 h-2.5 rounded-full"
                      style={{ width: `${Math.max(m.percentage, 2)}%` }} />
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
          <h3 className="text-sm font-medium text-gray-300">用户Token排行（Top 20）</h3>
          <div className="flex items-center gap-2 text-xs">
            <select
              className="rounded bg-gray-700 border border-gray-600 text-gray-200 px-2 py-1"
              value={userSort}
              onChange={e => { setUserSort(e.target.value); }}
            >
              <option value="month_tokens">本月Token</option>
              <option value="today_tokens">今日Token</option>
              <option value="total_tokens">累计Token</option>
              <option value="total_calls">调用次数</option>
            </select>
            <button
              className="px-2 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600"
              onClick={() => setUserOrder(o => o === 'desc' ? 'asc' : 'desc')}
            >{userOrder === 'desc' ? '↓降序' : '↑升序'}</button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-700/50 text-gray-400">
                <th className="text-left py-2 px-2">#</th>
                <th className="text-left py-2 px-2">用户</th>
                <th className="text-right py-2 px-2">今日Token</th>
                <th className="text-right py-2 px-2">本月Token</th>
                <th className="text-right py-2 px-2">累计Token</th>
                <th className="text-right py-2 px-2">调用次数</th>
                <th className="text-right py-2 px-2">活跃天数</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-6 text-gray-400">暂无数据</td></tr>
              ) : (
                users.map((u, i) => (
                  <tr key={u.user_id} className="border-b border-gray-800 hover:bg-gray-800/40">
                    <td className="py-1.5 px-2 text-gray-500">{i + 1}</td>
                    <td className="py-1.5 px-2 text-gray-200">{u.display_name || u.username}</td>
                    <td className="py-1.5 px-2 text-right text-green-400 font-mono">{formatTokens(u.today_tokens)}</td>
                    <td className="py-1.5 px-2 text-right text-blue-400 font-mono">{formatTokens(u.month_tokens)}</td>
                    <td className="py-1.5 px-2 text-right text-gray-300 font-mono">{formatTokens(u.total_tokens)}</td>
                    <td className="py-1.5 px-2 text-right text-gray-300">{u.total_calls}</td>
                    <td className="py-1.5 px-2 text-right text-gray-300">{u.active_days_30d}天</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default LeaderDashboardPanel;
