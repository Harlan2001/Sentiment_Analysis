import { useQuery } from '@tanstack/react-query'
import { 
  fetchAllFactors, 
  fetchFactorsByCategory, 
  fetchNewsByFactor 
} from '@/api'
import type { 
  AllFactorsResponse
} from '@/types'

// 获取所有因子
export const useAllFactors = () => {
  return useQuery({
    queryKey: ['factors', 'all'],
    queryFn: fetchAllFactors,
    staleTime: 10 * 60 * 1000, // 10分钟
    select: (data: AllFactorsResponse) => ({
      ...data,
      // 按分类组织因子
      factorsByCategory: data.factors.reduce((acc: Record<string, typeof data.factors>, factor) => {
        if (!acc[factor.category]) {
          acc[factor.category] = []
        }
        acc[factor.category].push(factor)
        return acc
      }, {}),
    })
  })
}

// 按分类获取因子
export const useFactorsByCategory = (category: string) => {
  return useQuery({
    queryKey: ['factors', 'category', category],
    queryFn: () => fetchFactorsByCategory(category),
    enabled: !!category,
    staleTime: 5 * 60 * 1000, // 5分钟
  })
}

// 获取因子相关新闻
export const useFactorNews = (factorCode: string, enabled: boolean = false, model?: string) => {
  return useQuery({
    queryKey: ['factor', 'news', factorCode, model],
    queryFn: () => fetchNewsByFactor(factorCode, model),
    enabled: enabled && !!factorCode,
    staleTime: 5 * 60 * 1000, // 5分钟
  })
}

// 因子统计信息
export const useFactorStats = () => {
  const { data } = useAllFactors()
  
  if (!data) return null
  
  const stats = {
    total: data.factors.length,
    categories: data.factorsByCategory ? Object.keys(data.factorsByCategory).length : 0,
    byCategory: data.factorsByCategory ? Object.entries(data.factorsByCategory).map(([category, factors]) => ({
      category,
      factorCount: factors.length,
    })) : [],
    latestFactors: data.factors
      .sort((a: any, b: any) => b.code.localeCompare(a.code))
      .slice(0, 10),
  }
  
  return stats
}

// 因子搜索Hook
export const useFactorSearch = (query: string, factors?: any[]) => {
  return useQuery({
    queryKey: ['factors', 'search', query],
    queryFn: async () => {
      if (!query.trim()) return []
      
      const searchQuery = query.toLowerCase()
      return (factors || []).filter((factor: any) => 
        factor.name.toLowerCase().includes(searchQuery) ||
        factor.code.toLowerCase().includes(searchQuery) ||
        factor.category.toLowerCase().includes(searchQuery)
      )
    },
    enabled: query.trim().length > 0,
    staleTime: 2 * 60 * 1000, // 2分钟
  })
}

// 因子详细分析Hook
export const useFactorAnalysis = (factorCode: string, model?: string) => {
  const factorNewsQuery = useFactorNews(factorCode, true, model)
  
  const analysis = {
    news: factorNewsQuery.data,
    isLoading: factorNewsQuery.isLoading,
    error: factorNewsQuery.error,
    
    // 新闻统计
    newsStats: factorNewsQuery.data ? {
      total: factorNewsQuery.data.count,
      byDirection: factorNewsQuery.data.news.reduce((acc: any, item: any) => {
        const direction = item.factor_direction || 'unknown'
        acc[direction] = (acc[direction] || 0) + 1
        return acc
      }, {}),
      byHorizon: factorNewsQuery.data.news.reduce((acc: any, item: any) => {
        const horizon = item.horizon || 'unknown'
        acc[horizon] = (acc[horizon] || 0) + 1
        return acc
      }, {}),
      recentNews: factorNewsQuery.data.news
        .sort((a: any, b: any) => new Date(b.publish_time).getTime() - new Date(a.publish_time).getTime())
        .slice(0, 10),
    } : null,
    
    // 时间范围
    dateRange: factorNewsQuery.data?.news && factorNewsQuery.data.news.length > 0 ? {
      start: factorNewsQuery.data.news.reduce((earliest: any, item: any) => 
        new Date(item.publish_time) < new Date(earliest.publish_time) ? item : earliest
      ).publish_date,
      end: factorNewsQuery.data.news.reduce((latest: any, item: any) => 
        new Date(item.publish_time) > new Date(latest.publish_time) ? item : latest
      ).publish_date,
    } : null,
  }
  
  return analysis
}
