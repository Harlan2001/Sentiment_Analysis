import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import NewsDetailPanel from '../components/NewsDetailPanel'
import { isValidDateKey } from '../utils/returnsCalendar'

/** 新闻详情深链路由壳：保留策略、收益日历与预测报告各自的返回上下文。 */
export default function NewsDetailPage() {
  const { newsId } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const strategyId = Number(searchParams.get('strategyId'))
  const fromStrategy = Number.isFinite(strategyId) && strategyId > 0
  const sourceDate = searchParams.get('date')
  const fromReturns = !fromStrategy && searchParams.get('from') === 'returns' && isValidDateKey(sourceDate)
  const fromForecast = !fromStrategy && searchParams.get('from') === 'forecast' && isValidDateKey(sourceDate)
  const newsSearch = fromStrategy
    ? `?strategyId=${strategyId}`
    : fromReturns
      ? `?from=returns&date=${sourceDate}`
      : fromForecast
        ? `?from=forecast&date=${sourceDate}`
        : ''
  const closeLabel = fromStrategy
    ? '返回策略生成'
    : fromReturns
      ? '返回收益日历'
      : fromForecast
        ? '返回预测'
        : undefined
  const closePath = fromStrategy
    ? `/strategy/prompt?id=${strategyId}&view=strategy-news`
    : fromReturns
      ? `/returns?date=${sourceDate}`
      : fromForecast
        ? `/forecast?date=${sourceDate}`
        : '/market'
  return (
    <div className="detail-route-page">
      <NewsDetailPanel
        newsId={Number(newsId)}
        closeLabel={closeLabel}
        onClose={() => navigate(closePath)}
        onNewsClick={(id) => navigate(`/news/${id}${newsSearch}`)}
      />
    </div>
  )
}
