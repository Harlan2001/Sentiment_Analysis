/**
 * 用户行为审计 Hook
 * 仅在激活 Tab2 时按需请求，不自动轮询
 */
import { useQuery } from '@tanstack/react-query';
import { fetchBehaviorStats, fetchBehaviorLogs, fetchUserProfiles, fetchUserProfile, fetchUserCompare } from '@/api';

export function useBehaviorStats(days: number = 7, enabled: boolean = false) {
  return useQuery({
    queryKey: ['dashboard', 'behavior-stats', { days }],
    queryFn: () => fetchBehaviorStats(days),
    enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useBehaviorLogs(
  params: {
    user_id?: string;
    page_route?: string;
    action_type?: string;
    start?: string;
    end?: string;
    limit?: number;
    offset?: number;
  } = {},
  enabled: boolean = false,
) {
  return useQuery({
    queryKey: ['dashboard', 'behavior-logs', params],
    queryFn: () => fetchBehaviorLogs(params),
    enabled,
    staleTime: 30_000,
  });
}

export function useUserProfiles(sortBy: string = 'last_visit', order: string = 'desc', enabled: boolean = false) {
  return useQuery({
    queryKey: ['dashboard', 'behavior-profiles', { sortBy, order }],
    queryFn: () => fetchUserProfiles(sortBy, order),
    enabled,
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
}

export function useUserProfile(userId: number | null, enabled: boolean = false) {
  return useQuery({
    queryKey: ['dashboard', 'behavior-profile', userId],
    queryFn: () => fetchUserProfile(userId!),
    enabled: enabled && userId !== null,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useUserCompare(userIds: number[], enabled: boolean = false) {
  return useQuery({
    queryKey: ['dashboard', 'behavior-compare', userIds],
    queryFn: () => fetchUserCompare(userIds),
    enabled: enabled && userIds.length >= 2,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}
