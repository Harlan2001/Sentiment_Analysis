/**
 * 监控看板 — 流量统计 Tab
 * 所有登录用户可见：展示当前用户自己的 Token 消耗情况 + 功能使用分布（仅新版页面）
 */
import React from 'react'
import MyUsagePage from '@/components/Pages/MyUsagePage'

export const TrafficStatsTab: React.FC = () => {
  return <MyUsagePage embedded />
}

export default TrafficStatsTab
