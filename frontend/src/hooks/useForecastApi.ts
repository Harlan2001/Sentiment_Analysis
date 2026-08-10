import { useQuery } from '@tanstack/react-query'
import { fetchForecastReport, fetchForecastHistory } from '@/api'
import type { ForecastResponse, ForecastHistoryResponse } from '@/types'

// 导出API函数供外部使用
export { fetchForecastReport, fetchForecastHistory }

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
      // 最新报告
      latestReport: data.reports.reduce(
        (latest, current) => (new Date(current.created_at) > new Date(latest.created_at) ? current : latest),
        data.reports[0]
      ),
    }),
  })
}

// 获取预测历史
export const useForecastHistory = (limit: number = 30) => {
  return useQuery({
    queryKey: ['forecast', 'history', limit],
    queryFn: () => fetchForecastHistory(limit),
    staleTime: 10 * 60 * 1000, // 10分钟
    select: (data: ForecastHistoryResponse) => ({
      ...data,
      // 按日期排序
      sortedHistory: [...data.history].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()),
      // 统计信息
      stats: {
        totalDays: data.history.length,
        averageDayProb:
          data.history.reduce((sum, day) => sum + (day.reports.day?.上涨概率 || 0), 0) / data.history.length,
        averageWeekProb:
          data.history.reduce((sum, day) => sum + (day.reports.week?.上涨概率 || 0), 0) / data.history.length,
        averageMonthProb:
          data.history.reduce((sum, day) => sum + (day.reports.month?.上涨概率 || 0), 0) / data.history.length,
      },
    }),
  })
}

// 预测准确性分析
export const useForecastAccuracy = () => {
  const { data: historyData } = useForecastHistory(100)

  return useQuery({
    queryKey: ['forecast', 'accuracy'],
    queryFn: async () => {
      if (!historyData?.history) return null

      // 这里可以实现准确性计算逻辑
      // 需要对比预测结果与实际市场走势
      const accuracy = {
        dayAccuracy: 0,
        weekAccuracy: 0,
        monthAccuracy: 0,
        overallAccuracy: 0,
        samples: historyData.history.length,
      }

      return accuracy
    },
    enabled: !!historyData?.history,
    staleTime: 60 * 60 * 1000, // 1小时
  })
}

// 预测趋势分析
export const useForecastTrends = () => {
  const { data: historyData } = useForecastHistory(60) // 最近60天

  return useQuery({
    queryKey: ['forecast', 'trends'],
    queryFn: async () => {
      if (!historyData?.history) return null

      const trends = {
        dayTrend: [] as Array<{ date: string; probability: number }>,
        weekTrend: [] as Array<{ date: string; probability: number }>,
        monthTrend: [] as Array<{ date: string; probability: number }>,
      }

      historyData.history.forEach((day) => {
        if (day.reports.day) {
          trends.dayTrend.push({
            date: day.date,
            probability: day.reports.day.上涨概率,
          })
        }

        if (day.reports.week) {
          trends.weekTrend.push({
            date: day.date,
            probability: day.reports.week.上涨概率,
          })
        }

        if (day.reports.month) {
          trends.monthTrend.push({
            date: day.date,
            probability: day.reports.month.上涨概率,
          })
        }
      })

      return trends
    },
    enabled: !!historyData?.history,
    staleTime: 10 * 60 * 1000, // 10分钟
  })
}
