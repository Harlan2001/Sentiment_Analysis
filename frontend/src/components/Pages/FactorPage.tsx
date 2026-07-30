import React, { useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/UI'
import { Loading, Empty, Button } from '@/components/UI'
import { useAllFactors } from '@/hooks/useFactorApi'
import { formatNumber } from '@/utils/helpers'
import type { FactorDefinition } from '@/types'
import FactorCard from './FactorCard'
import FactorDetailModal from './FactorDetailModal'
import FactorFilters from './FactorFilters'

const FactorPage: React.FC = () => {
  // 状态管理
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [selectedFactor, setSelectedFactor] = useState<FactorDefinition | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  
  // 数据获取
  const { data: allFactorsData, isLoading: factorsLoading, error: factorsError } = useAllFactors()
  
  // 过滤逻辑
  const filteredFactors = useMemo(() => {
    let factors = allFactorsData?.factors || []
    
    if (selectedCategory) {
      factors = factors.filter(f => f.category === selectedCategory)
    }
    
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      factors = factors.filter(f => 
        f.name.toLowerCase().includes(query) ||
        f.code.toLowerCase().includes(query) ||
        f.category.toLowerCase().includes(query)
      )
    }
    
    return factors
  }, [allFactorsData, selectedCategory, searchQuery])
  
  // 统计数据
  const stats = useMemo(() => {
    const factors = allFactorsData?.factors || []
    const categories = [...new Set(factors.map(f => f.category))]
    
    return {
      total: factors.length,
      categories: categories.length,
    }
  }, [allFactorsData])
  
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
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
          🎯 因子库
        </h1>
        <p className="text-gray-400 text-sm">
          浏览影响债券市场的各类因子，查看相关新闻
        </p>
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
        activeFiltersCount={[
          selectedCategory,
          searchQuery
        ].filter(Boolean).length}
      />
      
      {/* 因子列表 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>
              因子列表
              <span className="ml-2 text-sm font-normal text-gray-400">
                ({filteredFactors.length} 个因子)
              </span>
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
            <div className="text-red-400 text-center py-8">
              加载失败: {factorsError.message}
            </div>
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
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredFactors.map((factor) => (
                <FactorCard
                  key={factor.code}
                  factor={factor}
                  onClick={() => handleFactorClick(factor)}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* 因子详情弹窗 */}
      {selectedFactor && (
        <FactorDetailModal
          factor={selectedFactor}
          isOpen={!!selectedFactor}
          onClose={() => setSelectedFactor(null)}
        />
      )}
    </div>
  )
}

export default FactorPage
