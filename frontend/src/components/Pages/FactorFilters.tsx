import React from 'react'
import { Input, Select, Button } from '../UI'

interface FactorFiltersProps {
  searchQuery: string
  onSearchChange: (value: string) => void
  selectedCategory: string
  onCategoryChange: (value: string) => void
  categories: string[]
  onClearFilters: () => void
  activeFiltersCount: number
}

const FactorFilters: React.FC<FactorFiltersProps> = ({
  searchQuery,
  onSearchChange,
  selectedCategory,
  onCategoryChange,
  categories,
  onClearFilters,
  activeFiltersCount,
}) => {
  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      POLICY: '政策驱动',
      MACRO: '基本面驱动',
      LIQUIDITY: '流动性驱动',
      RISK: '风险/避险驱动',
      SENTIMENT: '市场情绪驱动',
      INDUSTRY: '行业/结构性驱动',
    }
    return labels[category] || category
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">筛选条件</h3>
        {activeFiltersCount > 0 && (
          <Button variant="outline" size="sm" onClick={onClearFilters}>
            清除所有 ({activeFiltersCount})
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* 搜索框 */}
        <div className="lg:col-span-2">
          <Input
            placeholder="搜索因子名称或代码..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            icon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            }
          />
        </div>

        {/* 分类筛选 */}
        <Select
          value={selectedCategory}
          onChange={(e) => onCategoryChange(e.target.value)}
          options={[
            { value: '', label: '所有分类' },
            ...categories.map(cat => ({ value: cat, label: getCategoryLabel(cat) }))
          ]}
        />
      </div>

      {/* 活跃筛选标签 */}
      {activeFiltersCount > 0 && (
        <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-700">
          {searchQuery && (
            <span className="inline-flex items-center gap-1 px-3 py-1 bg-purple-500/20 text-purple-300 rounded-full text-sm">
              搜索: {searchQuery}
              <button
                onClick={() => onSearchChange('')}
                className="ml-1 hover:text-purple-200"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </span>
          )}

          {selectedCategory && (
            <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-sm">
              分类: {getCategoryLabel(selectedCategory)}
              <button
                onClick={() => onCategoryChange('')}
                className="ml-1 hover:text-blue-200"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export default FactorFilters
