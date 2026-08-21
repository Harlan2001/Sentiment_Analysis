import { useNavigate, useParams } from 'react-router-dom'
import FactorDetailPanel from '../components/FactorDetailPanel'

/** 因子详情深链路由壳 */
export default function FactorDetailPage() {
  const { factorId } = useParams()
  const navigate = useNavigate()
  return (
    <div className="detail-route-page">
      <FactorDetailPanel
        factorId={Number(factorId)}
        onClose={() => navigate('/market')}
        onNewsClick={(id) => navigate(`/news/${id}`)}
      />
    </div>
  )
}
