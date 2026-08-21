import { useNavigate, useParams } from 'react-router-dom'
import NewsDetailPanel from '../components/NewsDetailPanel'

/** 新闻详情深链路由壳：把 /market 里的浮层提成可 URL 直达的页面 */
export default function NewsDetailPage() {
  const { newsId } = useParams()
  const navigate = useNavigate()
  return (
    <div className="detail-route-page">
      <NewsDetailPanel
        newsId={Number(newsId)}
        onClose={() => navigate('/market')}
        onNewsClick={(id) => navigate(`/news/${id}`)}
      />
    </div>
  )
}
