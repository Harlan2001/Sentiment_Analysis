import React from 'react'
import { motion } from 'framer-motion'

interface SkeletonProps {
  className?: string
  width?: string | number
  height?: string | number
  variant?: 'text' | 'rectangular' | 'circular'
  animation?: 'pulse' | 'wave' | 'none'
}

const Skeleton: React.FC<SkeletonProps> = ({
  className = '',
  width,
  height,
  variant = 'text',
  animation = 'pulse',
}) => {
  const variantClasses = {
    text: 'rounded',
    rectangular: 'rounded-md',
    circular: 'rounded-full',
  }

  const animationClasses = {
    pulse: 'animate-pulse',
    wave: '',
    none: '',
  }

  const baseClasses = 'bg-gray-700'
  const classes = `${baseClasses} ${variantClasses[variant]} ${animationClasses[animation]} ${className}`

  const style = {
    width: width || '100%',
    height: height || (variant === 'text' ? '1rem' : '40px'),
  }

  if (animation === 'wave') {
    return (
      <motion.div
        className={`${baseClasses} ${variantClasses[variant]} ${className} overflow-hidden relative`}
        style={style}
      >
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-gray-600 to-transparent"
          initial={{ x: '-100%' }}
          animate={{ x: '100%' }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'linear',
          }}
        />
      </motion.div>
    )
  }

  return <div className={classes} style={style} />
}

// 新闻项骨架屏
const NewsItemSkeleton: React.FC = () => (
  <div className="p-3 border border-gray-700 rounded-lg">
    <div className="flex items-start justify-between mb-2">
      <Skeleton width="70%" height="16px" />
      <div className="flex flex-col items-end gap-1">
        <Skeleton width="60px" height="12px" />
        <Skeleton width="40px" height="12px" />
      </div>
    </div>
    <Skeleton width="100%" height="12px" className="mb-1" />
    <Skeleton width="85%" height="12px" className="mb-2" />
    <div className="flex gap-2">
      <Skeleton width="40px" height="20px" variant="rectangular" />
      <Skeleton width="40px" height="20px" variant="rectangular" />
    </div>
  </div>
)

// 图表骨架屏
const ChartSkeleton: React.FC<{ height?: number }> = ({ height = 400 }) => (
  <div className="relative" style={{ height }}>
    <Skeleton height="100%" variant="rectangular" animation="wave" />
    <div className="absolute inset-0 flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
        <p className="text-sm text-gray-400">加载图表数据...</p>
      </div>
    </div>
  </div>
)

// 页面骨架屏
const NewsPageSkeleton: React.FC = () => (
  <div className="space-y-6">
    {/* 页面标题 */}
    <div>
      <Skeleton width="200px" height="32px" className="mb-2" />
      <Skeleton width="400px" height="16px" />
    </div>

    {/* 工具栏 */}
    <div>
      <Skeleton height="80px" variant="rectangular" />
    </div>

    {/* 主要内容 */}
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* 图表区域 */}
      <div className="lg:col-span-2">
        <div className="p-5 border border-gray-600 rounded-xl">
          <Skeleton width="120px" height="24px" className="mb-4" />
          <ChartSkeleton />
        </div>
      </div>

      {/* 新闻列表 */}
      <div className="lg:col-span-1">
        <div className="p-5 border border-gray-600 rounded-xl">
          <Skeleton width="100px" height="24px" className="mb-4" />
          <div className="space-y-3 max-h-96">
            <NewsItemSkeleton />
            <NewsItemSkeleton />
            <NewsItemSkeleton />
          </div>
        </div>
      </div>
    </div>
  </div>
)

export { Skeleton, NewsItemSkeleton, ChartSkeleton, NewsPageSkeleton }
