import React from 'react'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  color?: 'primary' | 'secondary' | 'white'
  className?: string
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  color = 'primary',
  className = '',
}) => {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  }
  
  const colorClasses = {
    primary: 'text-purple-500',
    secondary: 'text-gray-400',
    white: 'text-white',
  }
  
  return (
    <svg
      className={`animate-spin ${sizeClasses[size]} ${colorClasses[color]} ${className}`}
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}

interface LoadingProps {
  text?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const Loading: React.FC<LoadingProps> = ({
  text = '加载中...',
  size = 'md',
  className = '',
}) => {
  return (
    <div className={`flex flex-col items-center justify-center py-10 text-gray-400 ${className}`}>
      <LoadingSpinner size={size} />
      {text && <p className="mt-3 text-sm">{text}</p>}
    </div>
  )
}

interface ErrorProps {
  title?: string
  message?: string
  onRetry?: () => void
  className?: string
}

const Error: React.FC<ErrorProps> = ({
  title = '出现错误',
  message = '请稍后重试',
  onRetry,
  className = '',
}) => {
  return (
    <div className={`text-center py-10 text-red-400 bg-red-400/10 rounded-xl border border-red-400/20 ${className}`}>
      <svg className="w-12 h-12 mx-auto mb-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <p className="text-sm mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
        >
          重试
        </button>
      )}
    </div>
  )
}

interface EmptyProps {
  title?: string
  message?: string
  icon?: React.ReactNode
  action?: {
    label: string
    onClick: () => void
  }
  className?: string
}

const Empty: React.FC<EmptyProps> = ({
  title = '暂无数据',
  message = '当前没有可显示的内容',
  icon,
  action,
  className = '',
}) => {
  const defaultIcon = (
    <svg className="w-12 h-12 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )
  
  return (
    <div className={`text-center py-10 text-gray-400 ${className}`}>
      <div className="mb-4">
        {icon || defaultIcon}
      </div>
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <p className="text-sm mb-4">{message}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  )
}

export {
  LoadingSpinner,
  Loading,
  Error,
  Empty,
}