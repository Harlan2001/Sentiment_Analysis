/**
 * 开发者可视化看板主页面
 * 权限模型：
 *   系统监控(数据看板) — admin + manager
 *   系统监控(Token监控) — admin only
 *   用户管理           — admin only
 *   部门概览           — manager only（部门行为+Token数据）
 *   我的使用           — 所有登录用户
 */
import React, { useState, useMemo, useCallback } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useCoreDashboard } from '@/hooks/useCoreDashboard'
import { useBehaviorStats } from '@/hooks/useSimpleBehavior'
import { TopSummaryCards } from '@/components/Dashboard/TopCards'
import { NewsModule } from '@/components/Dashboard/NewsModule'
import { AnalysisModule } from '@/components/Dashboard/AnalysisModule'
import { FactorModule } from '@/components/Dashboard/FactorModule'
import { VectorModule } from '@/components/Dashboard/VectorModule'
import { YieldModule } from '@/components/Dashboard/YieldModule'
import { ForecastModule } from '@/components/Dashboard/ForecastModule'
import { ResearchModule } from '@/components/Dashboard/ResearchModule'
import { BehaviorPanel } from '@/components/Dashboard/BehaviorPanel'
import { UserProfilePanel } from '@/components/Dashboard/UserProfilePanel'
import { HistorySnapshot } from '@/components/Dashboard/HistorySnapshot'
import TokenOverviewPanel from '@/components/Dashboard/TokenOverviewPanel'
import UserTokenPanel from '@/components/Dashboard/UserTokenPanel'
import DeptOverviewPanel from '@/components/Dashboard/DeptOverviewPanel'
import MyUsagePage from '@/components/Pages/MyUsagePage'
import MacroSignalLogPage from '@/components/Pages/MacroSignalLogPage'

type TabKey = 'monitor' | 'audit' | 'dept' | 'myusage'
type AuditSubTab = 'overview' | 'profile' | 'token'
type MonitorSection = 'data' | 'token' | 'signal'

const DashboardPage: React.FC = () => {
  const { isAdmin, role } = useAuth()
  const isManager = role === 'manager'
  const canViewMonitor = isAdmin || isManager

  // 默认Tab：admin→监控，manager→部门概览，user→我的使用
  const defaultTab: TabKey = isAdmin ? 'monitor' : isManager ? 'dept' : 'myusage'
  const [activeTab, setActiveTab] = useState<TabKey>(defaultTab)
  const [auditSubTab, setAuditSubTab] = useState<AuditSubTab>('overview')
  const [monitorSection, setMonitorSection] = useState<MonitorSection>('data')
  const [behaviorDays, setBehaviorDays] = useState(7)
  const [refreshKey, setRefreshKey] = useState(0)

  const { data: coreData, isLoading, isError, error, dataUpdatedAt } = useCoreDashboard(refreshKey)
  const { data: behaviorStats, isLoading: behaviorLoading } = useBehaviorStats(behaviorDays, activeTab === 'audit')

  const handleRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1)
  }, [])

  const lastUpdated = useMemo(() => {
    if (dataUpdatedAt) {
      return new Date(dataUpdatedAt).toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    }
    return '—'
  }, [dataUpdatedAt])

  // 部门概览Tab仅manager可见（非admin）
  const showDeptTab = isManager

  return (
    <div className="space-y-4">
      {/* 顶部栏：标题 + 主Tab + 刷新 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-white">🔧 可视化看板</h1>

          <div className="flex rounded-lg bg-gray-800/80 border border-gray-700/50 overflow-hidden">
            {canViewMonitor && (
              <button
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  activeTab === 'monitor'
                    ? 'bg-blue-600/40 text-blue-300'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50'
                }`}
                onClick={() => setActiveTab('monitor')}
              >
                系统监控
              </button>
            )}
            {isAdmin && (
              <button
                className={`px-3 py-1.5 text-xs font-medium transition-colors border-l border-gray-700/50 ${
                  activeTab === 'audit'
                    ? 'bg-blue-600/40 text-blue-300'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50'
                }`}
                onClick={() => setActiveTab('audit')}
              >
                用户管理
              </button>
            )}
            {showDeptTab && (
              <button
                className={`px-3 py-1.5 text-xs font-medium transition-colors border-l border-gray-700/50 ${
                  activeTab === 'dept'
                    ? 'bg-green-600/40 text-green-300'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50'
                }`}
                onClick={() => setActiveTab('dept')}
              >
                部门概览
              </button>
            )}
            <button
              className={`px-3 py-1.5 text-xs font-medium transition-colors border-l border-gray-700/50 ${
                activeTab === 'myusage'
                  ? 'bg-yellow-600/40 text-yellow-300'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50'
              }`}
              onClick={() => setActiveTab('myusage')}
            >
              我的使用
            </button>
          </div>
        </div>

        <div className="flex items-center space-x-3 text-xs text-gray-400">
          <span>30s刷新 · {lastUpdated}</span>
          <button
            onClick={handleRefresh}
            className="px-3 py-1 rounded bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 border border-blue-700/30 transition-colors"
          >
            🔄 刷新
          </button>
        </div>
      </div>

      {/* 系统监控 Tab */}
      {activeTab === 'monitor' && canViewMonitor && (
        <>
          <div className="flex rounded-lg bg-gray-800/60 border border-gray-700/50 overflow-hidden w-fit">
            <button
              className={`px-4 py-1.5 text-xs font-medium transition-colors ${
                monitorSection === 'data' ? 'bg-blue-600/40 text-blue-300' : 'text-gray-500 hover:text-gray-300'
              }`}
              onClick={() => setMonitorSection('data')}
            >
              📊 数据看板
            </button>
            {isAdmin && (
              <button
                className={`px-4 py-1.5 text-xs font-medium transition-colors border-l border-gray-700/50 ${
                  monitorSection === 'token' ? 'bg-purple-600/40 text-purple-300' : 'text-gray-500 hover:text-gray-300'
                }`}
                onClick={() => setMonitorSection('token')}
              >
                🪙 Token监控
              </button>
            )}
            {canViewMonitor && (
              <button
                className={`px-4 py-1.5 text-xs font-medium transition-colors border-l border-gray-700/50 ${
                  monitorSection === 'signal' ? 'bg-amber-600/40 text-amber-300' : 'text-gray-500 hover:text-gray-300'
                }`}
                onClick={() => setMonitorSection('signal')}
              >
                📡 信号日志
              </button>
            )}
          </div>

          {monitorSection === 'data' &&
            (isLoading ? (
              <div className="text-center py-16 text-gray-400">
                <div className="animate-spin w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full mx-auto mb-3" />
                加载看板数据...
              </div>
            ) : isError ? (
              <div className="text-center py-16 text-red-400">
                ⚠️ 数据加载失败: {(error as Error)?.message || '未知错误'}
                <br />
                <button onClick={handleRefresh} className="mt-3 text-sm text-blue-400 hover:text-blue-300">
                  点击重试
                </button>
              </div>
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
                    <ResearchModule data={coreData.research} />
                  </div>
                </div>
                <HistorySnapshot />
              </>
            ) : null)}

          {monitorSection === 'token' && isAdmin && <TokenOverviewPanel />}

          {monitorSection === 'signal' && canViewMonitor && <MacroSignalLogPage embedded />}
        </>
      )}

      {/* 用户管理 Tab — admin only */}
      {activeTab === 'audit' && isAdmin && (
        <>
          <div className="flex items-center justify-between">
            <div className="flex rounded-lg bg-gray-800/60 border border-gray-700/50 overflow-hidden">
              <button
                className={`px-4 py-1.5 text-xs font-medium transition-colors ${auditSubTab === 'overview' ? 'bg-green-600/30 text-green-300' : 'text-gray-500 hover:text-gray-300'}`}
                onClick={() => setAuditSubTab('overview')}
              >
                📊 行为总览
              </button>
              <button
                className={`px-4 py-1.5 text-xs font-medium transition-colors border-l border-gray-700/50 ${auditSubTab === 'profile' ? 'bg-green-600/30 text-green-300' : 'text-gray-500 hover:text-gray-300'}`}
                onClick={() => setAuditSubTab('profile')}
              >
                👤 用户画像
              </button>
              <button
                className={`px-4 py-1.5 text-xs font-medium transition-colors border-l border-gray-700/50 ${auditSubTab === 'token' ? 'bg-yellow-600/30 text-yellow-300' : 'text-gray-500 hover:text-gray-300'}`}
                onClick={() => setAuditSubTab('token')}
              >
                🪙 Token消耗
              </button>
            </div>
            {auditSubTab === 'overview' && (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500">范围:</span>
                <select
                  className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1"
                  value={behaviorDays}
                  onChange={(e) => setBehaviorDays(Number(e.target.value))}
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
          {auditSubTab === 'profile' && <UserProfilePanel />}
          {auditSubTab === 'token' && <UserTokenPanel />}
        </>
      )}

      {/* 部门概览 Tab — manager only */}
      {activeTab === 'dept' && showDeptTab && <DeptOverviewPanel />}

      {/* 我的使用 Tab — 所有登录用户 */}
      {activeTab === 'myusage' && <MyUsagePage embedded />}
    </div>
  )
}

export default DashboardPage
