import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchYields,
  fetchNewsByDate,
  fetchNewsById,
  fetchNewsSources,
  fetchNewsByDateRange,
  fetchLatestTradingDay,
} from '@/api'
import { storage } from '@/utils/helpers'
import { API_PREFIX } from '@/constants'
import type { YieldPoint, NewsItem, NewsSource } from '@/types'

function authHeaders(): Record<string, string> {
  const token = storage.get<string>('auth_token')
  if (token) {
    return { Authorization: `Bearer ${token}` }
  }
  return {}
}

// 收益率数据Hook
export const useYields = (start: string, end: string, type: string) => {
  return useQuery({
    queryKey: ['yields', start, end, type],
    queryFn: () => fetchYields(start, end, type),
    enabled: !!(start && end && type),
    staleTime: 5 * 60 * 1000, // 5分钟
  })
}

// 多期限收益率数据Hook：并行拉取多个期限，供新闻页固定展示 1年/5年/10年/30年
export const useMultiYields = (periods: string[], start: string, end: string) => {
  return useQuery({
    queryKey: ['yields', 'multi', periods, start, end],
    queryFn: async () => {
      const results = await Promise.all(
        periods.map(async (label) => ({
          label,
          data: await fetchYields(start, end, label),
        }))
      )
      return results
    },
    enabled: !!(start && end && periods.length > 0),
    staleTime: 5 * 60 * 1000, // 5分钟
  })
}

// 按日期获取新闻Hook
export const useNewsByDate = (
  date: string,
  sources?: string[],
  model?: string,
  view: 'best' | 'single' | 'all' = 'best'
) => {
  return useQuery({
    queryKey: ['news', 'date', date, sources, model, view],
    queryFn: () => fetchNewsByDate(date, sources, model, view),
    enabled: !!date,
    staleTime: 2 * 60 * 1000, // 2分钟
  })
}

// 按日期范围获取新闻Hook
export const useNewsByDateRange = (
  startDate: string,
  endDate: string,
  sources?: string[],
  model?: string,
  view: 'best' | 'single' | 'all' = 'best'
) => {
  return useQuery({
    queryKey: ['news', 'dateRange', startDate, endDate, sources, model, view],
    queryFn: () => fetchNewsByDateRange(startDate, endDate, sources, model, view),
    enabled: !!(startDate && endDate),
    staleTime: 2 * 60 * 1000, // 2分钟
  })
}

// 新闻详情Hook
export const useNewsDetail = (newsId: number, model?: string, includeAllModels: boolean = false) => {
  return useQuery({
    queryKey: ['news', 'detail', newsId, model, includeAllModels],
    queryFn: () => fetchNewsById(newsId, model, includeAllModels),
    enabled: !!newsId,
    staleTime: 10 * 60 * 1000, // 10分钟
  })
}

// 新闻源Hook
export const useNewsSources = () => {
  return useQuery({
    queryKey: ['news', 'sources'],
    queryFn: fetchNewsSources,
    staleTime: 30 * 60 * 1000, // 30分钟
  })
}

// 新闻分析Mutation Hook
export const useNewsAnalysis = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ newsId, period, modelName }: { newsId: number; period?: string; modelName?: string }) => {
      const params = new URLSearchParams({
        period: period || '10年',
      })
      if (modelName) {
        params.append('model_name', modelName)
      }
      const response = await fetch(`${API_PREFIX}/news/${newsId}/analyze?${params.toString()}`, {
        method: 'POST',
        headers: authHeaders(),
      })
      return response.json()
    },
    onSuccess: (data, variables) => {
      // 分析成功后，可能需要更新相关查询
      queryClient.invalidateQueries({ queryKey: ['news', 'detail', variables.newsId] })
    },
  })
}

// 相似新闻Hook
export const useSimilarNews = (newsId: number) => {
  return useQuery({
    queryKey: ['news', 'similar', newsId],
    queryFn: async () => {
      const response = await fetch(`${API_PREFIX}/news/similar?news_id=${newsId}`, { headers: authHeaders() })
      return response.json()
    },
    enabled: !!newsId,
    staleTime: 15 * 60 * 1000, // 15分钟
  })
}

// 新闻搜索Hook
export const useSearchNews = (keyword: string, limit: number = 20) => {
  return useQuery({
    queryKey: ['news', 'search', keyword, limit],
    queryFn: async () => {
      const params = new URLSearchParams({
        keyword: keyword.trim(),
        limit: limit.toString(),
      })
      const response = await fetch(`${API_PREFIX}/search/news?${params}`, { headers: authHeaders() })
      if (!response.ok) throw new Error('搜索失败')
      return response.json()
    },
    enabled: !!keyword && keyword.trim().length > 0,
    staleTime: 5 * 60 * 1000, // 5分钟
  })
}

// 获取最新交易日Hook
export const useLatestTradingDay = () => {
  return useQuery({
    queryKey: ['news', 'latestTradingDay'],
    queryFn: fetchLatestTradingDay,
    staleTime: 60 * 60 * 1000, // 1小时缓存
  })
}
