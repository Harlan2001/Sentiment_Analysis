/**
 * 看板通用小部件：状态灯、指标卡片、进度条
 */
import React from 'react'

// ========== 状态灯 ==========

interface StatusLightProps {
  label: string
  ok: boolean
  detail?: string
}

export const StatusLight: React.FC<StatusLightProps> = ({ label, ok, detail }) => (
  <div
    className={`flex items-center space-x-2 px-3 py-2 rounded-lg border ${
      ok ? 'bg-green-900/20 border-green-700/30' : 'bg-red-900/20 border-red-700/30'
    }`}
  >
    <span
      className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
        ok ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.5)]' : 'bg-red-400 shadow-[0_0_6px_rgba(248,113,113,0.5)]'
      }`}
    />
    <div>
      <span className="text-xs font-medium text-gray-200">{label}</span>
      {detail && <span className="text-[10px] text-gray-400 ml-2">{detail}</span>}
    </div>
  </div>
)

// ========== 指标卡片 ==========

interface MetricCardProps {
  label: string
  value: number | string
  status?: 'normal' | 'warning' | 'danger'
  className?: string
}

const statusColors = {
  normal: 'border-gray-700/50 bg-gray-800/40',
  warning: 'border-yellow-700/30 bg-yellow-900/20',
  danger: 'border-red-700/30 bg-red-900/20',
}

const statusTextColors = {
  normal: 'text-white',
  warning: 'text-yellow-400',
  danger: 'text-red-400',
}

export const MetricCard: React.FC<MetricCardProps> = ({ label, value, status = 'normal', className = '' }) => (
  <div className={`rounded-lg border ${statusColors[status]} px-4 py-3 ${className}`}>
    <div className="text-[11px] text-gray-400 font-medium truncate">{label}</div>
    <div className={`text-xl font-bold mt-0.5 ${statusTextColors[status]}`}>{value}</div>
  </div>
)

// ========== 进度条 ==========

interface ProgressBarProps {
  label: string
  value: number // 0-100
  max?: number
  status?: 'normal' | 'warning' | 'danger'
}

const barColors = {
  normal: 'bg-gradient-to-r from-blue-500 to-cyan-500',
  warning: 'bg-gradient-to-r from-yellow-500 to-orange-500',
  danger: 'bg-gradient-to-r from-red-500 to-pink-500',
}

const bgBarColors = {
  normal: 'bg-gray-800',
  warning: 'bg-yellow-900/30',
  danger: 'bg-red-900/30',
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ label, value, max = 100, status = 'normal' }) => {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  // 当值接近100但不足100时，toFixed(1) 会进位显示为 "100.0"，此处保留2位避免误导
  const display = pct < 100 && pct.toFixed(1) === '100.0' ? pct.toFixed(2) : pct.toFixed(1)
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-gray-400">{label}</span>
        <span
          className={`font-medium ${status === 'danger' ? 'text-red-400' : status === 'warning' ? 'text-yellow-400' : 'text-cyan-400'}`}
        >
          {display}%
        </span>
      </div>
      <div className={`h-2 rounded-full ${bgBarColors[status]}`}>
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColors[status]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// ========== 时效性标签 ==========

interface TimelinessLabelProps {
  label: string
  diffHours: number | null
  diffMinutes?: number | null
  threshold: number // 超过此值显示 warning
}

export const TimelinessLabel: React.FC<TimelinessLabelProps> = ({ label, diffHours, diffMinutes, threshold }) => {
  let text = 'N/A'
  let status: 'normal' | 'warning' = 'normal'

  if (diffHours !== null) {
    if (diffHours < 1) {
      text = `${Math.round((diffHours || 0) * 60)}分钟前`
    } else {
      text = `${diffHours.toFixed(1)}小时前`
    }
    status = diffHours > threshold ? 'warning' : 'normal'
  } else if (diffMinutes != null) {
    if (diffMinutes < 60) {
      text = `${Math.round(diffMinutes)}分钟前`
    } else {
      text = `${(diffMinutes / 60).toFixed(1)}小时前`
    }
    status = diffMinutes / 60 > threshold ? 'warning' : 'normal'
  }

  return (
    <div className="flex items-center space-x-2">
      <span className="text-xs text-gray-400">{label}:</span>
      <span className={`text-xs font-medium ${status === 'warning' ? 'text-yellow-400' : 'text-gray-300'}`}>
        {text}
      </span>
    </div>
  )
}

// ========== 面板标题 ==========

interface PanelTitleProps {
  title: string
  icon: string
}

export const PanelTitle: React.FC<PanelTitleProps> = ({ title, icon }) => (
  <div className="flex items-center space-x-2 mb-4">
    <span className="text-lg">{icon}</span>
    <h3 className="text-sm font-semibold text-gray-200">{title}</h3>
  </div>
)

// ========== 空状态 ==========

export const EmptyState: React.FC<{ message?: string }> = ({ message = '暂无数据' }) => (
  <div className="flex items-center justify-center h-24 text-gray-500 text-sm">{message}</div>
)
