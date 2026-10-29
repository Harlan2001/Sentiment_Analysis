import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import NewsDetailPanel from '../components/NewsDetailPanel'

/** 新闻详情深链路由壳：把 /market 里的浮层提成可 URL 直达的页面 */
export default function NewsDetailPage() {
  const { newsId } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const strategyId = Number(searchParams.get('strategyId'))
  const fromStrategy = Number.isFinite(strategyId) && strategyId > 0
  const newsSearch = fromStrategy ? `?strategyId=${strategyId}` : ''
  return (
    <div className="detail-route-page">
      <NewsDetailPanel
        newsId={Number(newsId)}
        closeLabel={fromStrategy ? '返回策略生成' : undefined}
        onClose={() => navigate(fromStrategy ? `/strategy/prompt?id=${strategyId}&view=strategy-news` : '/market')}
        onNewsClick={(id) => navigate(`/news/${id}${newsSearch}`)}
      />
    </div>
  )
}
