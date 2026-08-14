/**
 * 监控看板 — 用户管理 Tab
 * 二级导航：行为总览 / 用户画像 / Token消耗
 */
import React, { useState } from 'react'
import { BehaviorPanel } from '@/features/monitor/panels/BehaviorPanel'
import { UserProfilePanel } from '@/features/monitor/panels/UserProfilePanel'
import UserTokenPanel from '@/features/monitor/panels/UserTokenPanel'
import { useBehaviorStats } from '@/features/monitor/hooks/useSimpleBehavior'

type SubTab = 'overview' | 'profile' | 'token'

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: 'overview', label: '行为总览' },
  { key: 'profile', label: '用户画像' },
  { key: 'token', label: 'Token消耗' },
]

export const UserManagementTab: React.FC = () => {
  const [subTab, setSubTab] = useState<SubTab>('overview')

  return (
    <div className="space-y-4">
      <nav className="monitor-drawer-subtabs">
        {SUB_TABS.map((t) => (
          <button
            key={t.key}
            className={subTab === t.key ? 'active' : ''}
            onClick={() => setSubTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {subTab === 'overview' && <BehaviorOverview />}
      {subTab === 'profile' && <UserProfilePanel />}
      {subTab === 'token' && <UserTokenPanel />}
    </div>
  )
}

function BehaviorOverview() {
  const [days, setDays] = useState(7)
  const { data: behaviorStats, isLoading: behaviorLoading } = useBehaviorStats(days, true)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">范围:</span>
          <select
            className="rounded bg-gray-700 border border-gray-600 text-gray-200 text-xs px-2 py-1"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={1}>最近1天</option>
            <option value={7}>最近7天</option>
            <option value={30}>最近30天</option>
          </select>
        </div>
      </div>
      <BehaviorPanel stats={behaviorStats} statsLoading={behaviorLoading} days={days} />
    </div>
  )
}

export default UserManagementTab
