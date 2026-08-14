/**
 * 监控看板 — 全屏详情页（仅保留左侧边栏）
 * 一级导航（按角色权限展示，与旧版一致）：
 *   系统监控 — admin + manager
 *   用户管理 — admin
 *   部门概览 — manager
 *   流量统计 — 所有用户
 * 二级导航由各 Tab 内部管理
 */
import React, { useEffect, useMemo, useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { SystemMonitorTab } from './tabs/SystemMonitorTab'
import { UserManagementTab } from './tabs/UserManagementTab'
import { TrafficStatsTab } from './tabs/TrafficStatsTab'
import DeptOverviewPanel from '@/features/monitor/panels/DeptOverviewPanel'
import './monitor-dashboard.css'

type TopTab = 'system' | 'user' | 'dept' | 'traffic'

export function MonitorDashboardPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { isAdmin, role } = useAuth()
  const isManager = role === 'manager'
  const canViewMonitor = isAdmin || isManager

  const tabs = useMemo(() => {
    return (
      [
        { key: 'system' as TopTab, label: '系统监控', visible: canViewMonitor },
        { key: 'user' as TopTab, label: '用户管理', visible: isAdmin },
        { key: 'dept' as TopTab, label: '部门概览', visible: isManager },
        { key: 'traffic' as TopTab, label: '流量统计', visible: true },
      ]
    ).filter((t) => t.visible)
  }, [canViewMonitor, isAdmin, isManager])

  const defaultTab = (): TopTab => (isAdmin ? 'system' : isManager ? 'dept' : 'traffic')
  const [tab, setTab] = useState<TopTab>(defaultTab())

  useEffect(() => {
    if (open) setTab(defaultTab())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isAdmin, isManager])

  useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [open, onClose])

  if (!open) return null

  return (
    <>
      <div className="monitor-overlay" onClick={onClose} aria-hidden="true" />
      <section className="monitor-drawer" role="dialog" aria-label="监控看板">
        <div className="monitor-drawer-head">
          <h2>监控看板</h2>
          <button className="monitor-drawer-close" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>

        <nav className="monitor-drawer-tabs">
          {tabs.map((t) => (
            <button
              key={t.key}
              className={tab === t.key ? 'active' : ''}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="monitor-drawer-body">
          {tab === 'system' && <SystemMonitorTab />}
          {tab === 'user' && <UserManagementTab />}
          {tab === 'dept' && <DeptOverviewPanel />}
          {tab === 'traffic' && <TrafficStatsTab />}
        </div>
      </section>
    </>
  )
}

export default MonitorDashboardPanel
