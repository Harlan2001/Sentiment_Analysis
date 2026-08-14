/**
 * 监控看板 — 系统监控 Tab
 * 二级导航：数据看板 / Token监控（按角色权限展示，与旧版一致）
 */
import React, { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useCoreDashboard } from '@/features/monitor/hooks/useCoreDashboard'
import { TopSummaryCards } from '@/features/monitor/panels/TopCards'
import { NewsModule } from '@/features/monitor/panels/NewsModule'
import { AnalysisModule } from '@/features/monitor/panels/AnalysisModule'
import { FactorModule } from '@/features/monitor/panels/FactorModule'
import { VectorModule } from '@/features/monitor/panels/VectorModule'
import { YieldModule } from '@/features/monitor/panels/YieldModule'
import { ForecastModule } from '@/features/monitor/panels/ForecastModule'
import { ResearchModule } from '@/features/monitor/panels/ResearchModule'
import { HistorySnapshot } from '@/features/monitor/panels/HistorySnapshot'
import TokenOverviewPanel from '@/features/monitor/panels/TokenOverviewPanel'

type SubTab = 'data' | 'token'

export const SystemMonitorTab: React.FC = () => {
  const { isAdmin, role } = useAuth()
  const canViewMonitor = isAdmin || role === 'manager'
  const [subTab, setSubTab] = useState<SubTab>('data')

  const subTabs = [
    { key: 'data' as SubTab, label: '数据看板', visible: canViewMonitor },
    { key: 'token' as SubTab, label: 'Token监控', visible: isAdmin },
  ].filter((t) => t.visible)

  return (
    <div className="space-y-4">
      <nav className="monitor-drawer-subtabs">
        {subTabs.map((t) => (
          <button
            key={t.key}
            className={subTab === t.key ? 'active' : ''}
            onClick={() => setSubTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {subTab === 'data' && <DataBoard />}
      {subTab === 'token' && <TokenOverviewPanel />}
    </div>
  )
}

function DataBoard() {
  const [refreshKey, setRefreshKey] = useState(0)
  const { data: coreData, isLoading, isError, error, dataUpdatedAt } = useCoreDashboard(refreshKey)

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—'

  if (isLoading) {
    return <div className="text-center text-gray-500 text-sm py-16">加载看板数据...</div>
  }
  if (isError) {
    return (
      <div className="text-center text-red-400 text-sm py-16">
        ⚠️ 数据加载失败: {(error as Error)?.message || '未知错误'}
        <br />
        <button onClick={() => setRefreshKey((k) => k + 1)} className="mt-3 text-sm text-blue-400 hover:text-blue-300">
          点击重试
        </button>
      </div>
    )
  }
  if (!coreData) return null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">30s刷新 · {lastUpdated}</span>
        <button
          onClick={() => setRefreshKey((k) => k + 1)}
          className="px-3 py-1 rounded bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 border border-blue-700/30 transition-colors text-xs"
        >
          🔄 刷新
        </button>
      </div>

      <TopSummaryCards cards={coreData.top_cards} />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <NewsModule data={coreData.news} />
        <AnalysisModule data={coreData.analysis} />
        <FactorModule data={coreData.factor} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <YieldModule data={coreData.yield} />
        <div className="flex flex-col gap-4">
          <VectorModule data={coreData.vector} />
          <ForecastModule data={coreData.forecast} />
          <ResearchModule data={coreData.research} />
        </div>
      </div>
      <HistorySnapshot />
    </div>
  )
}

export default SystemMonitorTab
