import { useNavigate, useParams } from 'react-router-dom'
import YieldDetailPanel from '../components/YieldDetailPanel'

/** 收益率详情深链路由壳 */
export default function YieldDetailPage() {
  const { period } = useParams()
  const navigate = useNavigate()
  return (
    <div className="detail-route-page">
      <YieldDetailPanel
        period={period || '10年'}
        onClose={() => navigate('/market')}
        onNewsClick={(id) => navigate(`/news/${id}`)}
      />
    </div>
  )
}
