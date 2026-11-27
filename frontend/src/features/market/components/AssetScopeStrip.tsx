import { useQuery } from '@tanstack/react-query'
import { fetchMarketPanel } from '@/api/market'
import { fetchCreditSpreadOverview } from '@/api/creditSpread'
import { fetchFuturesOverview } from '@/api/futures'
import { fetchTreasurySpread } from '@/api/treasury'
import './asset-scope.css'

export type AssetScope = 'all' | 'cgb' | 'credit' | 'futures' | 'ust'

interface Props {
  value: AssetScope
  onChange: (value: AssetScope) => void
  includeAll?: boolean
  compact?: boolean
  selectionOnly?: boolean
}

function signed(value: number | null, digits = 1, suffix = '') {
  if (value === null || !Number.isFinite(value)) return '暂无前值'
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}${suffix}`
}

export function AssetScopeStrip({ value, onChange, includeAll = true, compact = false, selectionOnly = false }: Props) {
  const cgb = useQuery({ queryKey: ['asset-scope', 'cgb'], queryFn: fetchMarketPanel, staleTime: 5 * 60 * 1000, enabled: !selectionOnly })
  const credit = useQuery({ queryKey: ['asset-scope', 'credit'], queryFn: () => fetchCreditSpreadOverview('10Y'), staleTime: 5 * 60 * 1000, enabled: !selectionOnly })
  const futures = useQuery({ queryKey: ['asset-scope', 'futures'], queryFn: fetchFuturesOverview, staleTime: 5 * 60 * 1000, enabled: !selectionOnly })
  const ust = useQuery({ queryKey: ['asset-scope', 'ust'], queryFn: () => fetchTreasurySpread('10Y'), staleTime: 5 * 60 * 1000, enabled: !selectionOnly })

  const cgb10y = cgb.data?.yields.items.find((item) => item.period === '10Y')
  const creditSeries = credit.data?.series ?? []
  const creditPrevious = creditSeries.length > 1 ? creditSeries[creditSeries.length - 2] : null
  const creditDelta = credit.data?.latest && creditPrevious ? credit.data.latest.spread_bp - creditPrevious.spread_bp : null
  const tRatio = futures.data?.comparison.find((item) => item.variety === 'T')?.ratio ?? null
  const ustSeries = ust.data?.series ?? []
  const ustPrevious = ustSeries.length > 1 ? ustSeries[ustSeries.length - 2] : null
  const ustDelta = ust.data?.latest && ustPrevious ? (ust.data.latest.us - ustPrevious.us) * 100 : null

  const assets: { key: Exclude<AssetScope, 'all'>; name: string; metric: string; change: string; meta: string }[] = [
    { key: 'cgb', name: '中国国债', metric: cgb10y ? `${cgb10y.value.toFixed(3)}%` : '—', change: signed(cgb10y?.diff_bp ?? null, 1, 'bp'), meta: '10Y收益率' },
    { key: 'credit', name: '信用债', metric: credit.data?.latest ? `${credit.data.latest.spread_bp.toFixed(1)}bp` : '—', change: signed(creditDelta, 1, 'bp'), meta: '10Y整体利差' },
    { key: 'futures', name: '国债期货', metric: tRatio?.toFixed(3) ?? '—', change: '会员口径', meta: '10年期多空比' },
    { key: 'ust', name: '美债', metric: ust.data?.latest ? `${ust.data.latest.us.toFixed(3)}%` : '—', change: signed(ustDelta, 1, 'bp'), meta: '10Y收益率' },
  ]

  if (selectionOnly) {
    return (
      <section className="asset-scope-selection" aria-label="选择市场表现资产">
        {includeAll && <button type="button" className={value === 'all' ? 'active' : ''} onClick={() => onChange('all')}>全部资产</button>}
        {assets.map((asset) => <button type="button" key={asset.key} className={value === asset.key ? 'active' : ''} onClick={() => onChange(asset.key)}>{asset.name}</button>)}
      </section>
    )
  }

  return (
    <section className={`asset-scope-strip${compact ? ' is-compact' : ''}`} aria-label="四资产范围">
      {includeAll && (
        <button type="button" className={`asset-scope-all${value === 'all' ? ' active' : ''}`} onClick={() => onChange('all')}>
          <span>全部资产</span><strong>四资产总览</strong><small>公共事件与市场状态</small>
        </button>
      )}
      <div className="asset-scope-grid">
        {assets.map((asset) => (
          <button type="button" key={asset.key} className={value === asset.key ? 'active' : ''} onClick={() => onChange(asset.key)}>
            <span>{asset.name}<small>{asset.meta}</small></span>
            <strong>{asset.metric}</strong>
            <em>{asset.change}</em>
          </button>
        ))}
      </div>
    </section>
  )
}
