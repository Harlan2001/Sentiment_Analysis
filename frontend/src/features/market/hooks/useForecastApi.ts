import { useQuery } from '@tanstack/react-query'
import { fetchForecastReport, fetchForecastHistory, fetchForecastDiagnosis } from '@/api/market'
import type { ForecastResponse } from '@/types'

// 导出API函数供外部使用
export { fetchForecastReport, fetchForecastHistory, fetchForecastDiagnosis }

// 获取预测报告
export const useForecastReport = (date?: string) => {
  return useQuery({
    queryKey: ['forecast', 'report', date],
    queryFn: () => fetchForecastReport(date),
    staleTime: 5 * 60 * 1000, // 5分钟
    select: (data: ForecastResponse) => ({
      ...data,
      // 按类型分类预测
      predictionsByType: data.reports.reduce((acc: any, report) => {
        const type = report.forecast_type
        if (!acc[type]) acc[type] = []
        acc[type].push(report)
        return acc
      }, {}),
      // 按日期排序
      sortedReports: [...data.reports].sort(
        (a, b) => new Date(b.trade_date).getTime() - new Date(a.trade_date).getTime()
      ),
      // 最新报告（空数组时返回 undefined，避免取 reports[0] 越界）
      latestReport: data.reports.length
        ? data.reports.reduce((latest, current) =>
            new Date(current.created_at) > new Date(latest.created_at) ? current : latest
          )
        : undefined,
    }),
  })
}

// 获取预测历史
export const useForecastHistory = (limit: number = 30) => {
  return useQuery({
    queryKey: ['forecast', 'history', limit],
    queryFn: () => fetchForecastHistory(limit),
    staleTime: 10 * 60 * 1000, // 10分钟
  })
}

// 获取预测诊断（准确度诊断）：历史预测与事后实际收益率对账
export const useForecastDiagnosis = () => {
  return useQuery({
    queryKey: ['forecast', 'diagnosis'],
    queryFn: fetchForecastDiagnosis,
    staleTime: 10 * 60 * 1000, // 诊断结论不常变，缓存久一些
  })
}
