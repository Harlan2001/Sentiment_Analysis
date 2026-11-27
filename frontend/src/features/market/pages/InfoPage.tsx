import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { MarketDataOverview, type MarketDataAsset } from '@/features/market/components/MarketDataOverview'
import ChinaGovernmentDataPage from '@/features/market/pages/ChinaGovernmentDataPage'
import FuturesPage from '@/features/market/pages/FuturesPage'
import CreditSpreadPage from '@/features/market/pages/CreditSpreadPage'
import TreasurySpreadPage from '@/features/market/pages/TreasurySpreadPage'
import './market-data.css'

const ASSETS: { key: MarketDataAsset; label: string; hint: string }[] = [
  { key: 'cgb', label: '中国国债', hint: '收益率与期限曲线' },
  { key: 'credit', label: '信用债', hint: '整体信用利差' },
  { key: 'futures', label: '国债期货', hint: '会员持仓结构' },
  { key: 'ust', label: '美债', hint: '美债收益率与中美比较' },
]

const LEGACY_TAB_ASSET: Record<string, MarketDataAsset> = {
  credit: 'credit',
  futures: 'futures',
  treasury: 'ust',
}

function normalizeAsset(value: string | null): MarketDataAsset | null {
  return ASSETS.some((item) => item.key === value) ? value as MarketDataAsset : null
}

/**
 * 市场数据统一入口。
 * /info 默认展示四资产真实数据总览；选择资产后在同一路由中进入完整详情。
 * 旧的 ?tab=futures/credit/treasury 查询参数继续兼容，独立旧路由也仍保留。
 */
export default function InfoPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const asset = useMemo(() => {
    const current = normalizeAsset(searchParams.get('asset'))
    if (current) return current
    return LEGACY_TAB_ASSET[searchParams.get('tab') ?? ''] ?? null
  }, [searchParams])

  const openAsset = (next: MarketDataAsset) => {
    const params = new URLSearchParams(searchParams)
    params.delete('tab')
    params.set('asset', next)
    setSearchParams(params)
  }

  const showOverview = () => {
    const params = new URLSearchParams(searchParams)
    params.delete('asset')
    params.delete('tab')
    setSearchParams(params)
  }

  if (!asset) return <MarketDataOverview onOpen={openAsset} />

  const current = ASSETS.find((item) => item.key === asset)!
  return (
    <section className="market-data-detail-shell">
      <header className="market-data-detail-nav">
        <button type="button" className="market-data-back" onClick={showOverview}>← 返回四资产总览</button>
        <div className="market-data-breadcrumb"><span>市场数据</span><i>/</i><strong>{current.label}</strong><small>{current.hint}</small></div>
        <label className="market-data-asset-switch">
          <span>切换资产</span>
          <select value={asset} onChange={(event) => openAsset(event.target.value as MarketDataAsset)}>
            {ASSETS.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select>
        </label>
      </header>
      <div className="market-data-detail-body" key={asset}>
        {asset === 'cgb' && <ChinaGovernmentDataPage />}
        {asset === 'credit' && <CreditSpreadPage />}
        {asset === 'futures' && <FuturesPage />}
        {asset === 'ust' && <TreasurySpreadPage />}
      </div>
    </section>
  )
}
