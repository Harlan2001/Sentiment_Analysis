/**
 * 看板核心数据 Hook
 * 30s 自动轮询 A-F模块指标 + 服务健康状态
 */
import { useQuery } from '@tanstack/react-query'
import { fetchDashboardCore } from '@/api/monitor'

export function useCoreDashboard(refreshKey: number = 0) {
  return useQuery({
    queryKey: ['dashboard', 'core', refreshKey],
    queryFn: fetchDashboardCore,
    refetchInterval: 30_000,
    staleTime: 0,
    refetchOnWindowFocus: false,
    retry: 2,
  })
}
