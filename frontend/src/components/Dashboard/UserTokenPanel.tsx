/**
 * 用户 Token 消耗面板（管理员）— 全局概览 + 趋势 + 模型分布 + 用户排行
 */
import React, { useEffect, useState, useCallback } from 'react';
import { fetchUserTokenList, fetchTokenOverview, fetchTokenTrend, fetchTokenByModel } from '@/api';
import { getModelLabel, CALL_SOURCE_MAP } from '@/config/labels';
import type { UserTokenItem, TokenOverview, TokenTrendItem, TokenModelDist } from '@/types';

const ROLE_LABELS: Record<string, string> = {
  admin: '管理员', manager: '经理', user: '普通用户',
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

const UserTokenPanel: React.FC = () => {
  const [items, setItems] = useState<UserTokenItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('month_tokens');
  const [order, setOrder] = useState('desc');
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const pageSize = 50;

  // Token 概览 + 趋势 + 模型分布
  const [overview, setOverview] = useState<TokenOverview | null>(null);
  const [trend, setTrend] = useState<TokenTrendItem[]>([]);
  const [models, setModels] = useState<TokenModelDist[]>([]);
  const [trendDays, setTrendDays] = useState(7);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [data, ov, tr, md] = await Promise.all([
        fetchUserTokenList({ sort_by: sortBy, order, limit: pageSize, offset: page * pageSize, search }),
        fetchTokenOverview(),
        fetchTokenTrend(trendDays),
        fetchTokenByModel(trendDays),
      ]);
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setOverview(ov);
      setTrend(tr.trend);
      setModels(md.models);
    } catch (e) {
      console.error('Token数据加载失败:', e);
    } finally {
      setLoading(false);
    }
  }, [sortBy, order, page, search, trendDays]);

  useEffect(() => { load(); }, [load]);

  const handleSort = (col: string) => {
    if (sortBy === col) { setOrder(o => o === 'desc' ? 'asc' : 'desc'); }
    else { setSortBy(col); setOrder('desc'); }
    setPage(0);
  };

  const handleSearch = () => { setSearch(searchInput); setPage(0); };

  const sortCols = [
    { key: 'username', label: '用户名' }, { key: 'month_tokens', label: '本月Token' },
    { key: 'today_tokens', label: '今日Token' }, { key: 'total_tokens', label: '累计Token' },
    { key: 'total_calls', label: '调用次数' }, { key: 'active_days', label: '活跃天数' },
  ];

  return (
    <div className="space-y-4">
      {/* Token 概览卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">今日Token</div>
          <div className="text-xl font-bold text-blue-400">{formatTokens(overview?.today_tokens ?? 0)}</div>
          <div className="text-[10px] text-gray-500 mt-0.5">调用 {overview?.today_calls ?? 0} 次</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">本月Token</div>
          <div className="text-xl font-bold text-green-400">{formatTokens(overview?.month_tokens ?? 0)}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">累计Token</div>
          <div className="text-xl font-bold text-purple-400">{formatTokens(overview?.all_tokens ?? 0)}</div>
        </div>
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">活跃用户(今日)</div>
          <div className="text-xl font-bold text-white">{overview?.today_users ?? '-'}</div>
          <div className="text-[10px] text-gray-500 mt-0.5">失败 {overview?.today_failed ?? 0} 次</div>
        </div>
      </div>

      {/* Token来源分布 */}
      {overview?.by_source && overview.by_source.length > 0 && (
        <div className="bg-gray-800/80 border border-gray-700/50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">今日Token分布（按来源）</h3>
          <div className="flex flex-wrap gap-3">
            {overview.by_source.map(s => (
              <div key={s.source} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-700/50">
                <span className="text-xs text-gray-300">{CALL_SOURCE_MAP[s.source] || s.source}</span>
                <span className="text-sm font-bold text-blue-400">{formatTokens(s.tokens)}</span>
                <span className="text-[10px] text-gray-500">({s.calls}次)</span>
              </div>
            ))}
          </div>
        </div>
      )}

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
                    <div className="w-full bg-yellow-500/60 hover:bg-yellow-400 rounded-t" style={{ height: `${h}%`, minHeight: '2px' }} />
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
                    <span className="text-gray-300">{getModelLabel(m.model)}</span>
                    <span className="text-gray-400">{formatTokens(m.tokens)} ({m.percentage}%)</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2.5">
                    <div className="bg-gradient-to-r from-yellow-500 to-red-500 h-2.5 rounded-full" style={{ width: `${Math.max(m.percentage, 2)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 搜索 + 用户列表 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <input type="text" className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-3 py-1.5 w-48"
            placeholder="搜索用户名..." value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleSearch(); }} />
          <button className="px-3 py-1.5 rounded bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 text-xs border border-blue-700/30"
            onClick={handleSearch}>搜索</button>
        </div>
        <div className="text-xs text-gray-400">共 <span className="text-gray-200">{total}</span> 个用户</div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr className="border-b border-gray-700/50">
            {sortCols.map(col => (
              <th key={col.key} className="text-left py-2 px-2 text-gray-400 font-medium cursor-pointer hover:text-gray-200 select-none"
                onClick={() => handleSort(col.key)}>
                {col.label}{sortBy === col.key && <span className="ml-1">{order === 'desc' ? '↓' : '↑'}</span>}
              </th>
            ))}
            <th className="text-left py-2 px-2 text-gray-400 font-medium">角色</th>
            <th className="text-left py-2 px-2 text-gray-400 font-medium">部门</th>
            <th className="text-left py-2 px-2 text-gray-400 font-medium">最后活跃</th>
          </tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={10} className="text-center py-8 text-gray-400">加载中...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={10} className="text-center py-8 text-gray-400">暂无数据</td></tr>
            ) : items.map(item => (
              <tr key={item.user_id} className="border-b border-gray-800 hover:bg-gray-800/40">
                <td className="py-2 px-2 text-gray-200">{item.display_name || item.username}</td>
                <td className="py-2 px-2 text-blue-400 font-mono">{formatTokens(item.month_tokens)}</td>
                <td className="py-2 px-2 text-green-400 font-mono">{formatTokens(item.today_tokens)}</td>
                <td className="py-2 px-2 text-gray-300 font-mono">{formatTokens(item.total_tokens)}</td>
                <td className="py-2 px-2 text-gray-300">{item.total_calls}</td>
                <td className="py-2 px-2 text-gray-300">{item.active_days_30d}天</td>
                <td className="py-2 px-2">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                    item.role === 'admin' ? 'bg-red-900/40 text-red-300' :
                    item.role === 'manager' ? 'bg-yellow-900/40 text-yellow-300' : 'bg-gray-700/50 text-gray-300'
                  }`}>{ROLE_LABELS[item.role] || item.role}</span>
                </td>
                <td className="py-2 px-2 text-gray-400">{item.department || '-'}</td>
                <td className="py-2 px-2 text-gray-400">
                  {item.last_active ? new Date(item.last_active).toLocaleDateString('zh-CN') : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button className="px-2 py-1 rounded bg-gray-700 text-gray-300 text-xs hover:bg-gray-600 disabled:opacity-40"
            disabled={page === 0} onClick={() => setPage(p => p - 1)}>上一页</button>
          <span className="text-xs text-gray-400">{page + 1} / {totalPages}</span>
          <button className="px-2 py-1 rounded bg-gray-700 text-gray-300 text-xs hover:bg-gray-600 disabled:opacity-40"
            disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>下一页</button>
        </div>
      )}
    </div>
  );
};

export default UserTokenPanel;
