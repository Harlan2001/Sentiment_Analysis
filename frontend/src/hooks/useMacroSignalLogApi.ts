import { useQuery } from '@tanstack/react-query'
import { fetchMacroSignalRequestLogs } from '@/api'
import type { MacroSignalRequestLogQuery } from '@/types'

export const useMacroSignalRequestLogs = (query: MacroSignalRequestLogQuery) => {
  return useQuery({
    queryKey: ['macroSignalLogs', query],
    queryFn: () => fetchMacroSignalRequestLogs(query),
    staleTime: 1 * 60 * 1000, // 1分钟
    retry: 1,
  })
}
