/**
 * 监控看板 — 全屏详情页（仅保留左侧边栏）
 * 一级导航：系统监控 / 用户管理 / 流量统计（按角色权限展示，与旧版一致）
 * 二级导航由各 Tab 内部管理
 */
import React, { useEffect, useMemo, useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { SystemMonitorTab } from './tabs/SystemMonitorTab'
import { UserManagementTab } from './tabs/UserManagementTab'
import { TrafficStatsTab } from './tabs/TrafficStatsTab'
import './monitor-dashboard.css'

type TopTab = 'system' | 'user' | 'traffic'

export function MonitorDashboardPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { isAdmin, role } = useAuth()
  const isManager = role === 'manager'
  const canViewMonitor = isAdmin || isManager

  const tabs = useMemo(() => {
    return (
      [
        { key: 'system' as TopTab, label: '系统监控', visible: canViewMonitor },
        { key: 'user' as TopTab, label: '用户管理', visible: isAdmin },
        { key: 'traffic' as TopTab, label: '流量统计', visible: true },
      ]
    ).filter((t) => t.visible)
  }, [canViewMonitor, isAdmin])

  const [tab, setTab] = useState<TopTab>(canViewMonitor ? 'system' : 'traffic')

  useEffect(() => {
    if (open) setTab(canViewMonitor ? 'system' : 'traffic')
  }, [open, canViewMonitor])

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
          {tab === 'traffic' && <TrafficStatsTab />}
        </div>
      </section>
    </>
  )
}

export default MonitorDashboardPanel
