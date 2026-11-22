import { useParams } from 'react-router-dom'
import { PortfolioDetailView } from '../components/portfolio/PortfolioDetailView'
import { PortfolioList } from '../components/portfolio/PortfolioList'

/** /portfolio 为列表；/portfolio/:portfolioId 复用本页展示账号级组合详情。 */
export default function PortfolioPage() {
  const { portfolioId } = useParams<{ portfolioId: string }>()
  return portfolioId ? <PortfolioDetailView portfolioId={portfolioId} /> : <PortfolioList />
}
