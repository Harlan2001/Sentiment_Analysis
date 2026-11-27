import type { NewsItem } from '@/types'
import './news-asset-impact.css'

type AssetKey = 'cgb' | 'credit' | 'futures' | 'ust'
type ImpactStatus = 'analyzed' | 'insufficient' | 'failed' | 'none'

interface AssetImpact {
  asset?: string
  asset_scope?: string
  direction?: string | null
  status?: string | null
}

type NewsWithAssetImpacts = NewsItem & {
  asset_impacts?: AssetImpact[]
}

const ASSETS: Array<{ key: AssetKey; label: string; metric: string }> = [
  { key: 'cgb', label: '中国国债', metric: '债券价格 / 收益率' },
  { key: 'credit', label: '信用债', metric: '信用利差' },
  { key: 'futures', label: '国债期货', metric: '期货价格' },
  { key: 'ust', label: '美债', metric: '美债收益率' },
]

const ALIASES: Record<AssetKey, string[]> = {
  cgb: ['cgb', 'china_government_bond', 'government_bond', '国债', '中国国债'],
  credit: ['credit', 'credit_bond', '信用债'],
  futures: ['futures', 'treasury_futures', '国债期货'],
  ust: ['ust', 'us_treasury', '美债', '美国国债'],
}

function normalizeStatus(value?: string | null): ImpactStatus {
  const status = (value ?? '').toLowerCase()
  if (['failed', 'error', '分析失败'].includes(status)) return 'failed'
  if (['insufficient', 'insufficient_evidence', '证据不足'].includes(status)) return 'insufficient'
  if (['analyzed', 'significant', 'no_significant_impact', '存在影响', '无显著影响'].includes(status)) return 'analyzed'
  return 'none'
}

function directionLabel(asset: AssetKey, direction?: string | null) {
  const value = (direction ?? '').toLowerCase()
  const positive = ['positive', 'bullish', '利多', 'up', 'narrower', 'down_yield'].includes(value)
  const negative = ['negative', 'bearish', '利空', 'down', 'wider', 'up_yield'].includes(value)
  const neutral = ['neutral', '中性', 'flat', 'no_significant_impact'].includes(value)
  if (!positive && !negative && !neutral) return null
  if (neutral) return { label: '无显著影响', tone: 'neutral' }
  if (asset === 'credit') return { label: positive ? '利差收窄' : '利差走阔', tone: positive ? 'positive' : 'negative' }
  if (asset === 'futures') return { label: positive ? '价格偏强' : '价格偏弱', tone: positive ? 'positive' : 'negative' }
  if (asset === 'ust') return { label: positive ? '收益率下行' : '收益率上行', tone: positive ? 'positive' : 'negative' }
  return { label: positive ? '利多' : '利空', tone: positive ? 'positive' : 'negative' }
}

function findImpact(news: NewsWithAssetImpacts, key: AssetKey) {
  return news.asset_impacts?.find((item) => {
    const value = (item.asset_scope ?? item.asset ?? '').toLowerCase()
    return ALIASES[key].some((alias) => alias.toLowerCase() === value)
  })
}

export default function NewsAssetImpactSummary({ news }: { news: NewsItem }) {
  const enriched = news as NewsWithAssetImpacts
  return (
    <section className="news-asset-impact" aria-labelledby="news-asset-impact-title">
      <header>
        <div><span>ASSET IMPACT</span><h2 id="news-asset-impact-title">四资产影响</h2></div>
        <p>仅展示方向结论；缺少影响记录不等于中性</p>
      </header>
      <div className="news-asset-impact-grid">
        {ASSETS.map((asset) => {
          const stored = findImpact(enriched, asset.key)
          const legacyDirection = asset.key === 'cgb' ? news.direction : null
          const direction = directionLabel(asset.key, stored?.direction ?? legacyDirection)
          const status = stored ? normalizeStatus(stored.status) : legacyDirection ? 'analyzed' : 'none'
          const label = status === 'failed'
            ? '分析失败'
            : status === 'insufficient'
              ? '证据不足'
              : direction?.label ?? (status === 'analyzed' ? '无显著影响' : '未分析')
          const tone = status === 'failed' ? 'failed' : status === 'insufficient' ? 'insufficient' : direction?.tone ?? 'pending'
          return (
            <article key={asset.key} className={`is-${tone}`}>
              <span>{asset.label}</span>
              <strong>{label}</strong>
              <small>{asset.metric}</small>
            </article>
          )
        })}
      </div>
    </section>
  )
}
