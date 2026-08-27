import { useLocation, useNavigate, useParams } from 'react-router-dom'
import FactorDetailPanel from '../components/FactorDetailPanel'

/** 因子详情深链路由壳 */
export default function FactorDetailPage() {
  const { factorId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = (location.state as { from?: string } | null)?.from || '/factors'
  return (
    <div className="detail-route-page">
      <FactorDetailPanel
        factorId={Number(factorId)}
        onClose={() => navigate(returnTo)}
        onNewsClick={(id) => navigate(`/news/${id}`)}
        onFactorClick={(id) => navigate(`/factor/${id}`, { state: { from: returnTo } })}
      />
    </div>
  )
}
