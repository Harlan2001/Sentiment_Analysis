import { useNavigate } from 'react-router-dom'
import StrategyDetailPanel from '../components/StrategyDetailPanel'

/** 策略推荐详情深链路由壳 */
export default function StrategyDetailPage() {
  const navigate = useNavigate()
  return (
    <div className="detail-route-page">
      <StrategyDetailPanel onClose={() => navigate('/market')} />
    </div>
  )
}
