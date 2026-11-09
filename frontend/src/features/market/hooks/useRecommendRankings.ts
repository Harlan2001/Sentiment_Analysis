/**
 * 推荐排行榜数据 hook（S3-3）
 * 后端已有 120s TTL，前端 staleTime 60s 避免切换标签时重复请求
 */
import { useQuery } from '@tanstack/react-query'
import { fetchRecommendRankings } from '@/api/market'

export function useRecommendRankings(days: number) {
  return useQuery({
    queryKey: ['discover', 'rankings', days],
    queryFn: () => fetchRecommendRankings(days),
    staleTime: 60 * 1000,
  })
}
