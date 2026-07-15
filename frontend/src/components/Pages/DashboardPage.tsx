/**
 * 开发者可视化看板主页面
 */
import React, { useState, useMemo, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useCoreDashboard } from '../../hooks/useCoreDashboard';
import { useBehaviorStats } from '../../hooks/useSimpleBehavior';
import { TopSummaryCards } from '../Dashboard/TopCards';
import { NewsModule } from '../Dashboard/NewsModule';
import { AnalysisModule } from '../Dashboard/AnalysisModule';
import { FactorModule } from '../Dashboard/FactorModule';
import { VectorModule } from '../Dashboard/VectorModule';
import { YieldModule } from '../Dashboard/YieldModule';
import { ForecastModule } from '../Dashboard/ForecastModule';
import { BehaviorPanel } from '../Dashboard/BehaviorPanel';
import { UserProfilePanel } from '../Dashboard/UserProfilePanel';
import { HistorySnapshot } from '../Dashboard/HistorySnapshot';

type TabKey = 'monitor' | 'audit';
type AuditSubTab = 'overview' | 'profile';

const DashboardPage: React.FC = () => {
  const { isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<TabKey>('monitor');
  const [auditSubTab, setAuditSubTab] = useState<AuditSubTab>('overview');
  const [behaviorDays, setBehaviorDays] = useState(7);
  const [refreshKey, setRefreshKey] = useState(0);

  const { data: coreData, isLoading, isError, error, dataUpdatedAt } = useCoreDashboard(refreshKey);
  const { data: behaviorStats, isLoading: behaviorLoading } = useBehaviorStats(behaviorDays, activeTab === 'audit');

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1);
  }, []);

  const lastUpdated = useMemo(() => {
    if (dataUpdatedAt) {
      return new Date(dataUpdatedAt).toLocaleTimeString('zh-CN', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    }
    return '—';
  }, [dataUpdatedAt]);

  return (
    <div className="space-y-4">
      {/* 顶部栏：标题 + 主Tab + 刷新 同行排列 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-white">🔧 开发者可视化看板</h1>

          {/* 主Tab — 与标题同行 */}
          <div className="flex rounded-lg bg-gray-800/80 border border-gray-700/50 overflow-hidden">
            <button
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === 'monitor'
                  ? 'bg-blue-600/40 text-blue-300'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50'
              }`}
              onClick={() => setActiveTab('monitor')}
              data-track="tab_switch"
              data-target="monitor"
            >系统监控</button>
            {isAdmin && (
              <button
                className={`px-3 py-1.5 text-xs font-medium transition-colors border-l border-gray-700/50 ${
                  activeTab === 'audit'
                    ? 'bg-blue-600/40 text-blue-300'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50'
                }`}
                onClick={() => setActiveTab('audit')}
                data-track="tab_switch"
                data-target="audit"
              >用户管理</button>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-3 text-xs text-gray-400">
          <span>30s刷新 · {lastUpdated}</span>
          <button
            onClick={handleRefresh}
            className="px-3 py-1 rounded bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 border border-blue-700/30 transition-colors"
          >🔄 刷新</button>
        </div>
      </div>

      {/* 系统监控 Tab */}
      {activeTab === 'monitor' && (
        isLoading ? (
          <div className="text-center py-16 text-gray-400"><div className="animate-spin w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full mx-auto mb-3" />加载看板数据...</div>
        ) : isError ? (
          <div className="text-center py-16 text-red-400">⚠️ 数据加载失败: {(error as Error)?.message || '未知错误'}<br /><button onClick={handleRefresh} className="mt-3 text-sm text-blue-400 hover:text-blue-300">点击重试</button></div>
        ) : coreData ? (
          <>
            <TopSummaryCards cards={coreData.top_cards} />
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
              <NewsModule data={coreData.news} />
              <AnalysisModule data={coreData.analysis} />
              <FactorModule data={coreData.factor} />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
              <YieldModule data={coreData.yield} />
              <div className="flex flex-col gap-4">
                <VectorModule data={coreData.vector} />
                <ForecastModule data={coreData.forecast} />
              </div>
            </div>
            <HistorySnapshot />
          </>
        ) : null
      )}

      {/* 用户行为管理 Tab */}
      {activeTab === 'audit' && isAdmin && (
        <>
          {/* 子Tab + 时间选择 — 紧凑一行 */}
          <div className="flex items-center justify-between">
            <div className="flex rounded-lg bg-gray-800/60 border border-gray-700/50 overflow-hidden">
              <button
                className={`px-4 py-1.5 text-xs font-medium transition-colors ${
                  auditSubTab === 'overview'
                    ? 'bg-green-600/30 text-green-300'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
                onClick={() => setAuditSubTab('overview')}
                data-track="tab_switch"
                data-target="behavior_overview"
              >📊 行为总览</button>
              <button
                className={`px-4 py-1.5 text-xs font-medium transition-colors border-l border-gray-700/50 ${
                  auditSubTab === 'profile'
                    ? 'bg-green-600/30 text-green-300'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
                onClick={() => setAuditSubTab('profile')}
                data-track="tab_switch"
                data-target="behavior_profile"
              >👤 用户画像</button>
            </div>

            {auditSubTab === 'overview' && (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500">范围:</span>
                <select
                  className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1"
                  value={behaviorDays}
                  onChange={e => setBehaviorDays(Number(e.target.value))}
                >
                  <option value={1}>最近1天</option>
                  <option value={7}>最近7天</option>
                  <option value={30}>最近30天</option>
                </select>
              </div>
            )}
          </div>

          {auditSubTab === 'overview' && (
            <BehaviorPanel stats={behaviorStats} statsLoading={behaviorLoading} days={behaviorDays} />
          )}

          {auditSubTab === 'profile' && (
            <UserProfilePanel />
          )}
        </>
      )}
    </div>
  );
};

export default DashboardPage;
