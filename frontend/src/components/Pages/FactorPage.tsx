import React, { useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle, Loading, Empty, Button } from '@/components/UI'
import { useAllFactors } from '@/hooks/useFactorApi'
import { formatNumber } from '@/utils/helpers'
import type { FactorDefinition } from '@/types'
import FactorCard from './FactorCard'
import FactorDetailModal from './FactorDetailModal'
import FactorFilters from './FactorFilters'

// 分类中文名映射（与后端 FACTOR_CATEGORY_MAP 语义一致）
const CATEGORY_LABELS: Record<string, string> = {
  POLICY: '政策',
  MACRO: '宏观',
  LIQUIDITY: '流动性',
  RISK: '风险',
  SENTIMENT: '情绪',
  INDUSTRY: '行业',
}

const FactorPage: React.FC = () => {
  // 状态管理
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [selectedFactor, setSelectedFactor] = useState<FactorDefinition | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // 数据获取
  const { data: allFactorsData, isLoading: factorsLoading, error: factorsError } = useAllFactors()

  // 过滤 + 排序逻辑（按活力度 recent_news_count 降序）
  const filteredFactors = useMemo(() => {
    let factors = allFactorsData?.factors || []

    if (selectedCategory) {
      factors = factors.filter((f) => f.category === selectedCategory)
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      factors = factors.filter(
        (f) =>
          f.name.toLowerCase().includes(query) ||
          f.code.toLowerCase().includes(query) ||
          f.category.toLowerCase().includes(query)
      )
    }

    return [...factors].sort((a, b) => (b.recent_news_count || 0) - (a.recent_news_count || 0))
  }, [allFactorsData, selectedCategory, searchQuery])

  // 统计数据
  const stats = useMemo(() => {
    const factors = allFactorsData?.factors || []
    const categories = [...new Set(factors.map((f) => f.category))]
    return {
      total: factors.length,
      categories: categories.length,
    }
  }, [allFactorsData])

  // 按分类聚合（仅当无搜索时展示分组视图）
  const groupedByCategory = useMemo(() => {
    const groups = new Map<string, FactorDefinition[]>()
    for (const f of filteredFactors) {
      if (!groups.has(f.category)) groups.set(f.category, [])
      groups.get(f.category)!.push(f)
    }
    return Array.from(groups.entries()).sort((a, b) => b[1].length - a[1].length)
  }, [filteredFactors])

  // 获取可用分类
  const categories = useMemo(() => {
    const factors = allFactorsData?.factors || []
    return [...new Set(factors.map((f) => f.category))]
  }, [allFactorsData])

  const handleCategoryChange = (value: string) => {
    setSelectedCategory(value)
  }

  const handleFactorClick = (factor: FactorDefinition) => {
    setSelectedFactor(factor)
  }

  const handleClearFilters = () => {
    setSelectedCategory('')
    setSearchQuery('')
  }

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div className="page-header">
        <h1 className="text-3xl font-bold text-white mb-2">🎯 因子库</h1>
        <p className="text-gray-400 text-sm">按分类聚合浏览影响债券市场的各类因子，默认按近30天活跃度排序</p>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">总因子数</p>
                <p className="text-2xl font-bold text-white">{formatNumber(stats.total)}</p>
              </div>
              <div className="w-12 h-12 bg-purple-500/20 rounded-lg flex items-center justify-center">
                <span className="text-purple-400 text-xl">📊</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">分类数</p>
                <p className="text-2xl font-bold text-white">{formatNumber(stats.categories)}</p>
              </div>
              <div className="w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center">
                <span className="text-blue-400 text-xl">📁</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 筛选器 */}
      <FactorFilters
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        selectedCategory={selectedCategory}
        onCategoryChange={handleCategoryChange}
        categories={categories}
        onClearFilters={handleClearFilters}
        activeFiltersCount={[selectedCategory, searchQuery].filter(Boolean).length}
      />

      {/* 因子列表 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>
              因子列表
              <span className="ml-2 text-sm font-normal text-gray-400">({filteredFactors.length} 个因子)</span>
            </CardTitle>
            {(selectedCategory || searchQuery) && (
              <Button variant="outline" size="sm" onClick={handleClearFilters}>
                清除筛选
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {factorsLoading ? (
            <Loading text="加载因子数据..." />
          ) : factorsError ? (
            <div className="text-red-400 text-center py-8">加载失败: {factorsError.message}</div>
          ) : filteredFactors.length === 0 ? (
            <Empty
              title="没有找到匹配的因子"
              message="尝试调整筛选条件或搜索关键词"
              action={
                Object.values({ selectedCategory, searchQuery }).some(Boolean)
                  ? { label: '清除筛选', onClick: handleClearFilters }
                  : undefined
              }
            />
          ) : searchQuery ? (
            /* 搜索结果：平铺展示 */
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredFactors.map((factor) => (
                <FactorCard key={factor.code} factor={factor} onClick={() => handleFactorClick(factor)} />
              ))}
            </div>
          ) : (
            /* 分类聚合 + 活力度排序 */
            <div className="space-y-6">
              {groupedByCategory.map(([category, factors]) => (
                <div key={category}>
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="text-base font-semibold text-white">{CATEGORY_LABELS[category] || category}</h3>
                    <span className="text-xs text-gray-400">({factors.length} 个)</span>
                    <span className="text-xs text-gray-500">近30天活跃度排序</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {factors.map((factor) => (
                      <FactorCard key={factor.code} factor={factor} onClick={() => handleFactorClick(factor)} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 因子详情弹窗 */}
      {selectedFactor && (
        <FactorDetailModal factor={selectedFactor} isOpen={!!selectedFactor} onClose={() => setSelectedFactor(null)} />
      )}
    </div>
  )
}

export default FactorPage
