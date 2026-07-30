/**
 * 宏观数据 API hooks — 基于 @tanstack/react-query
 */
import { useQuery } from '@tanstack/react-query'
import { fetchMacroIndicators, fetchMacroData } from '@/api'
import type { MacroIndicatorsResponse, MacroDataResponse } from '@/types'

/** 获取指标元数据（稳定数据，缓存1小时） */
export function useMacroIndicators() {
  return useQuery<MacroIndicatorsResponse>({
    queryKey: ['macro-indicators'],
    queryFn: fetchMacroIndicators,
    staleTime: 60 * 60 * 1000, // 1小时
  })
}

/** 获取指定指标的时序数据（缓存5分钟） */
export function useMacroData(zbcodes: string[], start?: string, end?: string) {
  const codesKey = [...zbcodes].sort().join(',')
  return useQuery<MacroDataResponse>({
    queryKey: ['macro-data', codesKey, start, end],
    queryFn: () => fetchMacroData(zbcodes, start, end),
    enabled: zbcodes.length > 0,
    staleTime: 5 * 60 * 1000, // 5分钟
  })
}
