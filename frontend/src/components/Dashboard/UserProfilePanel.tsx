/**
 * 单用户画像面板：雷达图 + 偏好细节 + 用户对比
 */
import React, { useState, useMemo, useEffect, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import { useUserProfiles, useUserProfile, useUserCompare } from '@/hooks/useSimpleBehavior';
import { triggerProfileCompute, fetchActiveUsers } from '@/api';
import type { UserBehaviorProfile, ActiveUser } from '@/types';
import { MetricCard } from './Widgets';

// 页面路由中文映射
// ========== 雷达图（hover单个维度显示该维度详情）==========
function RadarChart({ profile }: { profile: UserBehaviorProfile }) {
  const radarData = profile.radar || [];
  const option = {
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: (p: { name: string; value: number }) => {
        const dim = radarData.find(d => d.dimension === p.name);
        if (!dim) return `${p.name}: <b>${p.value}分</b>`;
        return `${dim.dimension}<br/>评分: <b>${p.value}分</b><br/>实际值: <b>${dim.value}</b> ${dim.unit}`;
      },
      extraCssText: 'max-width:200px;',
    },
    legend: { show: false },
    radar: {
      center: ['50%', '50%'],
      radius: '65%',
      indicator: radarData.map(d => ({ name: d.dimension, max: 100 })),
      axisName: { color: '#9ca3af', fontSize: 10 },
      splitArea: { areaStyle: { color: ['rgba(59,130,246,0.05)', 'rgba(59,130,246,0.1)'] } },
      splitLine: { lineStyle: { color: '#374151' } },
      axisLine: { lineStyle: { color: '#4b5563' } },
    },
    series: [{
      type: 'radar',
      symbol: 'circle',
      symbolSize: 5,
      data: [{
        value: radarData.map(d => d.score),
        name: profile.username,
        areaStyle: { color: 'rgba(59,130,246,0.2)' },
        lineStyle: { color: '#3b82f6', width: 2 },
        itemStyle: { color: '#60a5fa' },
      }],
      emphasis: {
        focus: 'self',
        areaStyle: { color: 'rgba(59,130,246,0.3)' },
      },
    }],
  };

  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
      <div className="text-xs text-gray-400 font-medium mb-2">🎯 产品使用程度总览</div>
      {radarData.length > 0 ? (
        <ReactECharts option={option} style={{ height: 300 }} opts={{ renderer: 'svg' }} />
      ) : (
        <div className="text-gray-500 text-sm py-10 text-center">暂无雷达图数据</div>
      )}
    </div>
  );
}

// ========== 偏好细节卡片 ==========
function PreferenceDetail({ profile }: { profile: UserBehaviorProfile }) {
  const prefs = profile.preferences;
  if (!prefs) return null;

  const tagClass = (active: boolean) =>
    `text-[11px] px-2 py-0.5 rounded-full ${active ? 'bg-blue-900/50 text-blue-300 border border-blue-700/30' : 'bg-gray-700/50 text-gray-500 border border-gray-600/30'}`;

  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
      <div className="text-xs text-gray-400 font-medium mb-3">📋 偏好细节</div>
      <div className="grid grid-cols-2 gap-4">
        {/* 偏好时段 */}
        <div>
          <div className="text-[11px] text-gray-500 mb-1">偏好时段</div>
          <div className="text-sm text-white">
            {prefs.peak_slot || '未知'}
            {prefs.peak_hour !== null && (
              <span className="text-gray-500 text-xs ml-1">({prefs.peak_hour}:00 前后)</span>
            )}
          </div>
        </div>

        {/* 用户标签 */}
        <div>
          <div className="text-[11px] text-gray-500 mb-1">用户标签</div>
          <div className="flex flex-wrap gap-1.5">
            <span className={tagClass(!!prefs.power_user)}>💪 重度用户</span>
            <span className={tagClass(!!prefs.report_focused)}>📊 报告导向</span>
            <span className={tagClass(!!prefs.strategy_focused)}>🎯 策略导向</span>
          </div>
        </div>

        {/* 最常访问页面 */}
        <div className="col-span-2">
          <div className="text-[11px] text-gray-500 mb-1">最常访问页面 TOP5</div>
          <div className="space-y-1">
            {(prefs.top_pages || []).slice(0, 5).map((p, i) => (
              <div key={p.route} className="flex items-center text-xs">
                <span className="text-gray-500 w-5">{i + 1}.</span>
                <span className="text-gray-200 flex-1">{p.title || p.route}</span>
                <span className="text-gray-500">{Math.round(p.affinity * 100)}%</span>
                <div className="w-20 h-1.5 rounded bg-gray-700 ml-2 overflow-hidden">
                  <div className="h-full rounded bg-blue-500/60" style={{ width: `${p.affinity * 100}%` }} />
                </div>
              </div>
            ))}
            {(!prefs.top_pages || prefs.top_pages.length === 0) && (
              <div className="text-gray-600 text-xs">暂无数据</div>
            )}
          </div>
        </div>

        {/* 流失风险 */}
        <div className="col-span-2">
          <div className="text-[11px] text-gray-500 mb-1">流失风险</div>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 rounded-full bg-gray-700 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${(prefs.churn_risk || 0) > 0.5 ? 'bg-red-500' : (prefs.churn_risk || 0) > 0.3 ? 'bg-yellow-500' : 'bg-green-500'}`}
                style={{ width: `${(prefs.churn_risk || 0) * 100}%` }}
              />
            </div>
            <span className={`text-xs font-medium ${(prefs.churn_risk || 0) > 0.5 ? 'text-red-400' : (prefs.churn_risk || 0) > 0.3 ? 'text-yellow-400' : 'text-green-400'}`}>
              {Math.round((prefs.churn_risk || 0) * 100)}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ========== 用户对比 ==========
function ComparePanel({ userIds, onClose }: { userIds: number[]; onClose: () => void }) {
  const { data, isLoading } = useUserCompare(userIds, userIds.length >= 2);

  const barOption = useMemo(() => {
    if (!data?.comparison?.length) return null;
    const dims = data.comparison.map(d => d.label);
    const series = data.profiles.map((p, i) => ({
      name: p.username,
      type: 'bar' as const,
      data: data.comparison.map(d => d.values[i]?.value || 0),
      itemStyle: {
        color: ['#3b82f6', '#10b981', '#f59e0b'][i],
        borderRadius: [4, 4, 0, 0],
      },
      barMaxWidth: 40,
    }));

    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(17,24,39,0.95)',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb', fontSize: 12 },
      },
      legend: {
        data: data.profiles.map(p => p.username),
        textStyle: { color: '#9ca3af', fontSize: 11 },
        top: 0,
      },
      grid: { left: 100, right: 30, top: 35, bottom: 20 },
      xAxis: {
        type: 'value',
        axisLabel: { color: '#9ca3af', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1f2937' } },
      },
      yAxis: {
        type: 'category',
        data: dims,
        axisLabel: { color: '#9ca3af', fontSize: 10 },
      },
      series,
    };
  }, [data]);

  if (isLoading) return <div className="text-center text-gray-400 py-4">加载对比数据...</div>;
  if (!data?.profiles?.length) return <div className="text-center text-gray-500 py-4">对比数据不可用</div>;

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs text-blue-400 font-medium">📊 用户对比</div>
        <button onClick={onClose} className="text-xs text-gray-500 hover:text-gray-300">✕ 关闭</button>
      </div>
      <div className="flex gap-2 mb-3">
        {data.profiles.map(p => (
          <span key={p.user_id} className="text-[11px] px-2 py-0.5 rounded bg-gray-700/50 text-gray-300">
            {p.username}
          </span>
        ))}
      </div>
      {barOption && (
        <ReactECharts option={barOption} style={{ height: 280 }} opts={{ renderer: 'svg' }} />
      )}
    </div>
  );
}

// ========== 搜索下拉选择器 ==========
function UserSearchSelect({
  users,
  selectedUserId,
  onSelect,
  placeholder = '搜索用户...',
}: {
  users: ActiveUser[];
  selectedUserId: number | null;
  onSelect: (userId: number) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = query
    ? users.filter(u =>
        u.username.toLowerCase().includes(query.toLowerCase()) ||
        u.display_name.toLowerCase().includes(query.toLowerCase()) ||
        (u.department && u.department.toLowerCase().includes(query.toLowerCase()))
      )
    : users;

  const selectedUser = users.find(u => u.id === selectedUserId);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className="relative w-56">
      <div
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between px-3 py-1.5 rounded-lg border border-gray-600/50 bg-gray-700/40 cursor-pointer hover:border-gray-500 transition-colors"
      >
        {selectedUser ? (
          <span className="text-sm text-gray-200">{selectedUser.display_name}</span>
        ) : (
          <span className="text-sm text-gray-500">选择用户...</span>
        )}
        <svg className={`w-4 h-4 text-gray-500 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {open && (
        <div className="absolute z-50 mt-1 w-full bg-gray-800 border border-gray-600/50 rounded-lg shadow-xl overflow-hidden">
          <div className="p-2 border-b border-gray-700">
            <div className="relative">
              <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder={placeholder}
                autoFocus
                className="w-full pl-8 pr-3 py-1.5 text-sm bg-gray-700/50 border border-gray-600/30 rounded text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
                onKeyDown={e => {
                  if (e.key === 'Escape') { setOpen(false); setQuery(''); }
                  if (e.key === 'Enter' && filtered.length > 0) {
                    onSelect(filtered[0].id);
                    setOpen(false);
                    setQuery('');
                  }
                }}
              />
            </div>
          </div>
          <div className="max-h-48 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-3 py-4 text-xs text-gray-500 text-center">无匹配用户</div>
            ) : (
              filtered.map(u => (
                <button
                  key={u.id}
                  onClick={() => { onSelect(u.id); setOpen(false); setQuery(''); }}
                  className={`w-full text-left px-3 py-2 text-sm transition-colors hover:bg-gray-700/50 flex items-center justify-between ${
                    u.id === selectedUserId ? 'bg-blue-600/20 text-blue-300' : 'text-gray-300'
                  }`}
                >
                  <span>{u.display_name}</span>
                  <span className="text-[11px] text-gray-500">{u.department || u.role}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ========== 多选搜索下拉（对比用） ==========
function MultiUserSelect({
  users,
  selectedIds,
  onToggle,
  max = 3,
}: {
  users: ActiveUser[];
  selectedIds: number[];
  onToggle: (userId: number) => void;
  max?: number;
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = query
    ? users.filter(u =>
        u.username.toLowerCase().includes(query.toLowerCase()) ||
        u.display_name.toLowerCase().includes(query.toLowerCase()) ||
        (u.department && u.department.toLowerCase().includes(query.toLowerCase()))
      )
    : users;

  const selectedUsers = users.filter(u => selectedIds.includes(u.id));

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className="relative w-56">
      <div
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between px-3 py-1.5 rounded-lg border border-gray-600/50 bg-gray-700/40 cursor-pointer hover:border-gray-500 transition-colors min-h-[32px]"
      >
        {selectedUsers.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {selectedUsers.map(u => (
              <span key={u.id} className="text-[11px] px-1.5 py-0.5 rounded bg-green-900/30 text-green-300 border border-green-700/30">
                {u.display_name}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-sm text-gray-500">选择对比用户...</span>
        )}
        <svg className={`w-4 h-4 text-gray-500 flex-shrink-0 ml-2 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {open && (
        <div className="absolute z-50 mt-1 w-full bg-gray-800 border border-gray-600/50 rounded-lg shadow-xl overflow-hidden">
          <div className="p-2 border-b border-gray-700">
            <div className="relative">
              <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="搜索用户..."
                autoFocus
                className="w-full pl-8 pr-3 py-1.5 text-sm bg-gray-700/50 border border-gray-600/30 rounded text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
                onKeyDown={e => { if (e.key === 'Escape') { setOpen(false); setQuery(''); } }}
              />
            </div>
          </div>
          <div className="max-h-48 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-3 py-4 text-xs text-gray-500 text-center">无匹配用户</div>
            ) : (
              filtered.map(u => {
                const isSelected = selectedIds.includes(u.id);
                const disabled = !isSelected && selectedIds.length >= max;
                return (
                  <button
                    key={u.id}
                    onClick={() => { if (!disabled) onToggle(u.id); }}
                    disabled={disabled}
                    className={`w-full text-left px-3 py-2 text-sm transition-colors flex items-center gap-2 ${
                      disabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-gray-700/50 cursor-pointer'
                    } ${isSelected ? 'bg-green-600/20 text-green-300' : 'text-gray-300'}`}
                  >
                    <span className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 text-[10px] ${
                      isSelected ? 'bg-green-600/40 border-green-500/50 text-green-300' : 'border-gray-500/50'
                    }`}>
                      {isSelected ? '✓' : ''}
                    </span>
                    <span>{u.display_name}</span>
                    <span className="text-[11px] text-gray-500 ml-auto">{u.department || u.role}</span>
                  </button>
                );
              })
            )}
          </div>
          {selectedIds.length > 0 && (
            <div className="border-t border-gray-700 px-2 py-1.5 flex justify-between items-center">
              <span className="text-[11px] text-gray-500">已选 {selectedIds.length}/{max}</span>
              <button
                onClick={() => selectedIds.forEach(id => onToggle(id))}
                className="text-[11px] text-gray-400 hover:text-gray-200"
              >清除</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ========== 用户画像主面板 ==========
export const UserProfilePanel: React.FC = () => {
  const [activeUsers, setActiveUsers] = useState<ActiveUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [compareUserIds, setCompareUserIds] = useState<number[]>([]);
  const [showCompare, setShowCompare] = useState(false);
  const [computing, setComputing] = useState(false);

  const { data: profileList } = useUserProfiles('last_visit', 'desc', true);
  const { data: profile, isLoading: profileLoading, refetch: refetchProfile } = useUserProfile(
    selectedUserId,
    selectedUserId !== null
  );

  // 加载活跃用户列表（自动跟随 users 表变化）
  useEffect(() => {
    let cancelled = false;
    fetchActiveUsers()
      .then(data => { if (!cancelled) { setActiveUsers(data.users); setUsersLoading(false); } })
      .catch(() => { if (!cancelled) setUsersLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const handleSelectUser = (userId: number) => {
    setSelectedUserId(userId);
    setShowCompare(false);
  };

  const handleToggleCompare = (userId: number) => {
    setCompareUserIds(prev => {
      if (prev.includes(userId)) return prev.filter(id => id !== userId);
      if (prev.length >= 3) return [...prev.slice(1), userId];
      return [...prev, userId];
    });
  };

  const handleCompare = () => {
    if (compareUserIds.length >= 2) setShowCompare(true);
  };

  const handleComputeProfile = async () => {
    if (!selectedUserId) return;
    setComputing(true);
    try {
      await triggerProfileCompute(selectedUserId);
      await refetchProfile();
    } catch (e) {
      console.error('画像计算失败', e);
    } finally {
      setComputing(false);
    }
  };

  // 合并活跃用户和画像数据用于对比选择
  const profileUserIds = new Set((profileList?.profiles || []).map(p => p.user_id));
  const compareCandidates = activeUsers.filter(u => profileUserIds.has(u.id));

  return (
    <div className="space-y-4">
      {/* 用户选择区 — 搜索下拉 + 对比操作 */}
      <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-3">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[11px] text-gray-500 flex-shrink-0">用户</span>
          {usersLoading ? (
            <span className="text-gray-600 text-xs">加载中...</span>
          ) : (
            <UserSearchSelect
              users={activeUsers}
              selectedUserId={selectedUserId}
              onSelect={handleSelectUser}
            />
          )}

          {/* 分隔 + 对比操作 */}
          <span className="text-gray-700 mx-1">|</span>
          <span className="text-[11px] text-gray-500 flex-shrink-0">对比</span>
          <MultiUserSelect
            users={activeUsers}
            selectedIds={compareUserIds}
            onToggle={handleToggleCompare}
            max={3}
          />
          {compareUserIds.length >= 2 && (
            <>
              <button
                onClick={handleCompare}
                className="text-xs px-2 py-1 rounded bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 border border-blue-700/30 transition-colors"
              >📊 对比 ({compareUserIds.length})</button>
              <button
                onClick={() => { setCompareUserIds([]); setShowCompare(false); }}
                className="text-xs text-gray-500 hover:text-gray-300"
              >✕</button>
            </>
          )}
        </div>
      </div>

      {/* 对比面板 */}
      {showCompare && compareUserIds.length >= 2 && (
        <ComparePanel
          userIds={compareUserIds}
          onClose={() => setShowCompare(false)}
        />
      )}

      {/* 单用户画像详情 */}
      {selectedUserId && (
        <>
          {profileLoading ? (
            <div className="text-center text-gray-400 py-12">加载画像数据...</div>
          ) : profile ? (
            <>
              {/* 用户概要行 */}
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-white">{profile.username}</span>
                  {profile.is_power_user && <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-900/30 text-yellow-400 border border-yellow-700/30">💪 重度</span>}
                  {profile.is_report_focused && <span className="text-xs px-1.5 py-0.5 rounded bg-blue-900/30 text-blue-400 border border-blue-700/30">📊 报告导向</span>}
                  {profile.is_strategy_focused && <span className="text-xs px-1.5 py-0.5 rounded bg-purple-900/30 text-purple-400 border border-purple-700/30">🎯 策略导向</span>}
                </div>
                <div className="flex items-center gap-3 text-[11px] text-gray-500">
                  <span>首次: {profile.first_visit || '—'}</span>
                  <span>最近: {profile.last_visit ? new Date(profile.last_visit).toLocaleDateString('zh-CN') : '—'}</span>
                  {profile.computed_at && <span className="text-gray-600">更新: {new Date(profile.computed_at).toLocaleString('zh-CN')}</span>}
                  <button
                    onClick={handleComputeProfile}
                    disabled={computing}
                    className="px-2 py-0.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-400 disabled:opacity-50 transition-colors"
                  >{computing ? '⏳' : '🔄'}</button>
                </div>
              </div>

              {/* 概览卡片 */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <MetricCard label="活跃天数(30日)" value={`${profile.active_days_30d}天`} />
                <MetricCard label="日均访问页数" value={profile.avg_daily_pages_30d.toFixed(1)} />
                <MetricCard label="累计会话" value={profile.total_sessions} />
                <MetricCard
                  label="累计活跃时长"
                  value={profile.total_active_sec >= 3600
                    ? `${(profile.total_active_sec / 3600).toFixed(1)}h`
                    : `${Math.round(profile.total_active_sec / 60)}min`}
                />
              </div>

              {/* 雷达图 + 偏好细节 并排 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <RadarChart profile={profile} />
                <PreferenceDetail profile={profile} />
              </div>
            </>
          ) : (
            <div className="text-center text-gray-500 py-12">
              该用户暂无画像数据
              <button
                onClick={handleComputeProfile}
                className="ml-2 text-blue-400 hover:text-blue-300 underline text-sm"
              >
                点击生成
              </button>
            </div>
          )}
        </>
      )}

      {/* 未选择用户时的引导 */}
      {!selectedUserId && (
        <div className="text-center text-gray-600 py-16">
          <div className="text-4xl mb-3">👤</div>
          <div className="text-sm">请从上方下拉框搜索选择一个用户查看行为画像</div>
          <div className="text-xs text-gray-700 mt-1">画像包含雷达图、活跃度、功能偏好和流失风险评估</div>
        </div>
      )}
    </div>
  );
};

export default UserProfilePanel;
