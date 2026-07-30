/**
 * 个人使用 Dashboard — 所有登录用户可见
 * 显示个人 Token 汇总、趋势、功能使用分布、时段分布、模型偏好
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { getModelLabel, getPageTitle } from '@/config/labels';

const API_PREFIX = '/sapi';

interface MyUsagePageProps {
  embedded?: boolean;
}

interface MyUsageOverview {
  today_tokens: number;
  month_tokens: number;
  total_tokens: number;
  total_calls: number;
  today_calls: number;
}

interface TrendItem {
  date: string;
  total: number;
  [model: string]: number | string;
}

interface PageDistItem {
  route: string;
  title: string;
  count: number;
  percentage: number;
}

interface ModelPref {
  model: string;
  tokens: number;
  percentage: number;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token');
  if (token) {
    try { const p = JSON.parse(token); if (p) return { Authorization: `Bearer ${p}` }; }
    catch { return { Authorization: `Bearer ${token}` }; }
  }
  return {};
}

const MyUsagePage: React.FC<MyUsagePageProps> = ({ embedded = false }) => {
  const { username, displayName } = useAuth();
  const [overview, setOverview] = useState<MyUsageOverview | null>(null);
  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [pages, setPages] = useState<PageDistItem[]>([]);
  const [hourDist, setHourDist] = useState<Record<string, number>>({});
  const [modelPrefs, setModelPrefs] = useState<ModelPref[]>([]);
  const [trendDays, setTrendDays] = useState(7);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const h = authHeaders();
    try {
      const [ov, tr, bh] = await Promise.all([
        fetch(`${API_PREFIX}/dashboard/my-usage/overview`, { headers: h }).then(r => r.json()),
        fetch(`${API_PREFIX}/dashboard/my-usage/trend?days=${trendDays}`, { headers: h }).then(r => r.json()),
        fetch(`${API_PREFIX}/dashboard/my-usage/behavior`, { headers: h }).then(r => r.json()),
      ]);
      setOverview(ov);
      setTrend(tr.trend || []);
      setPages(bh.page_distribution || []);
      setHourDist(bh.hour_distribution || {});
      setModelPrefs(bh.model_preferences || []);
    } catch (e) {
      console.error('个人使用数据加载失败:', e);
    } finally {
      setLoading(false);
    }
  }, [trendDays]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="text-center py-16 text-gray-400">
        <div className="animate-spin w-8 h-8 border-2 border-green-400 border-t-transparent rounded-full mx-auto mb-3" />
        加载个人使用数据...
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${embedded ? '' : 'max-w-5xl mx-auto'}`}>
      {!embedded && <h1 className="text-xl font-bold text-white">📊 我的使用</h1>}

      {/* 个人汇总卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">今日Token</div>
          <div className="text-lg font-bold text-blue-400">{formatTokens(overview?.today_tokens ?? 0)}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">本月Token</div>
          <div className="text-lg font-bold text-green-400">{formatTokens(overview?.month_tokens ?? 0)}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">累计Token</div>
          <div className="text-lg font-bold text-purple-400">{formatTokens(overview?.total_tokens ?? 0)}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">今日调用</div>
          <div className="text-lg font-bold text-yellow-400">{overview?.today_calls ?? 0}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">累计调用</div>
          <div className="text-lg font-bold text-gray-200">{overview?.total_calls ?? 0}</div>
        </div>
      </div>

      {/* Token趋势图 */}
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
                  <div className="w-full bg-green-500/60 hover:bg-green-400 rounded-t" style={{ height: `${h}%`, minHeight: '2px' }} />
                  <span className="text-[10px] text-gray-500 mt-1">{item.date.slice(5)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 使用行为 + 模型偏好 + 时段分布 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* 功能使用分布 */}
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">功能使用分布（30天）</h3>
          {pages.length === 0 ? (
            <div className="text-gray-500 text-sm text-center py-4">暂无数据</div>
          ) : (
            <div className="space-y-2">
              {pages.map(p => (
                <div key={p.route}>
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="text-gray-300">{p.title}</span>
                    <span className="text-gray-400">{p.count}次 ({p.percentage}%)</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-1.5">
                    <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${Math.max(p.percentage, 2)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 模型偏好 */}
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">模型使用偏好（30天）</h3>
          {modelPrefs.length === 0 ? (
            <div className="text-gray-500 text-sm text-center py-4">暂无数据</div>
          ) : (
            <div className="space-y-2">
              {modelPrefs.map(m => (
                <div key={m.model}>
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="text-gray-300">{getModelLabel(m.model)}</span>
                    <span className="text-gray-400">{formatTokens(m.tokens)} ({m.percentage}%)</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-1.5">
                    <div className="bg-purple-500 h-1.5 rounded-full" style={{ width: `${Math.max(m.percentage, 2)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 活跃时段分布 */}
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">活跃时段分布（30天）</h3>
          {Object.keys(hourDist).length === 0 ? (
            <div className="text-gray-500 text-sm text-center py-4">暂无数据</div>
          ) : (
            <div className="flex items-end gap-0.5 h-24">
              {Array.from({ length: 24 }, (_, h) => {
                const count = hourDist[String(h)] || 0;
                const maxCount = Math.max(...Object.values(hourDist), 1);
                const heightPct = Math.max(2, Math.round((count / maxCount) * 100));
                return (
                  <div key={h} className="flex-1 flex flex-col items-center justify-end h-full"
                    title={`${h}:00 - ${count}次`}>
                    <div className="w-full bg-green-500/50 hover:bg-green-400 rounded-t" style={{ height: `${heightPct}%`, minHeight: count > 0 ? '2px' : '0' }} />
                    {(h % 6 === 0) && <span className="text-[9px] text-gray-500 mt-1">{h}h</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MyUsagePage;
