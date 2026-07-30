import React from 'react'
import { Card, CardContent } from '@/components/UI'
import { formatDate } from '@/utils/helpers'
import type { FactorDefinition } from '@/types'

interface FactorCardProps {
  factor: FactorDefinition
  onClick: () => void
  className?: string
}

const FactorCard: React.FC<FactorCardProps> = ({
  factor,
  onClick,
  className = '',
}) => {
  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      '宏观经济': 'bg-green-400/20 text-green-300',
      '货币政策': 'bg-blue-400/20 text-blue-300', 
      '市场情绪': 'bg-orange-400/20 text-orange-300',
      '国际因素': 'bg-purple-400/20 text-purple-300',
      '政策法规': 'bg-red-400/20 text-red-300',
      '行业发展': 'bg-cyan-400/20 text-cyan-300',
      '技术分析': 'bg-yellow-400/20 text-yellow-300',
    }
    return colors[category] || 'bg-gray-400/20 text-gray-300'
  }
  
  return (
    <Card
      hover
      onClick={onClick}
      className={`cursor-pointer transition-all duration-200 hover:scale-[1.02] hover:shadow-lg ${className}`}
    >
      <CardContent className="p-4">
        {/* 头部信息 */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-white text-sm mb-1 truncate">
              {factor.name}
            </h3>
            <p className="text-xs text-gray-400 font-mono">
              {factor.code}
            </p>
          </div>
          
            <div />
        </div>
        
        {/* 分类信息 */}
        <div className="space-y-2 mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs font-medium px-2 py-1 rounded-full ${getCategoryColor(factor.category)}`}>
              {factor.category}
            </span>
          </div>
        </div>
        
        {/* 描述（如果有） */}
        {factor.description && (
          <div className="mb-3">
            <p className="text-xs text-gray-400 line-clamp-2 leading-relaxed">
              {factor.description}
            </p>
          </div>
        )}
        
        {/* 底部信息 */}
        <div className="flex items-center justify-between pt-3 border-t border-gray-700">
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
              </svg>
              分类
            </span>
            
            {factor.last_updated && (
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {formatDate(factor.last_updated, 'MM-DD')}
              </span>
            )}
          </div>
          
          {/* 悬停指示器 */}
          <div className="text-gray-600">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default FactorCard
