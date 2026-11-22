import type { PortfolioDetail, PortfolioRiskItem } from '@/api/portfolio'
import { formatPercent, formatYears, panelClass } from './common'

export function MetricCards({ portfolio }: { portfolio: PortfolioDetail }) {
  const { metrics } = portfolio
  const cards = [
    { label: '已投资权重', value: formatPercent(metrics.invested_weight), meta: `最大持仓 ${formatPercent(metrics.max_holding_weight)}`, tone: 'text-[#9eb5ff]' },
    { label: '现金权重', value: formatPercent(metrics.cash_weight), meta: '由未投资权重自动形成', tone: 'text-gray-100' },
    { label: '加权久期', value: formatYears(metrics.weighted_duration), meta: `久期覆盖率 ${formatPercent(metrics.duration_coverage)}`, tone: 'text-amber-200' },
    { label: '加权到期收益率', value: formatPercent(metrics.weighted_yield), meta: `收益率覆盖率 ${formatPercent(metrics.yield_coverage)}`, tone: 'text-[#7fd4c1]' },
  ]
  return (
    <section aria-label="组合指标" className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className={`${panelClass} p-3.5`}>
          <div className="text-[11px] text-gray-400">{card.label}</div>
          <div className={`mt-2 font-mono text-xl font-semibold ${card.tone}`}>{card.value}</div>
          <div className="mt-1.5 text-[11px] text-gray-500">{card.meta}</div>
        </div>
      ))}
    </section>
  )
}

function AllocationBars({ portfolio }: { portfolio: PortfolioDetail }) {
  const allocations = portfolio.metrics.asset_allocations
  if (!allocations.length) return <p className="py-4 text-center text-xs text-gray-600">暂无资产分类数据</p>
  return (
    <table className="w-full text-left text-xs" aria-label="资产分类权重">
      <thead className="sr-only"><tr><th>资产分类</th><th>权重条形</th><th>权重</th></tr></thead>
      <tbody className="divide-y divide-[#222226]">
        {allocations.map((item) => {
          const width = item.weight === null || !Number.isFinite(item.weight) ? 0 : Math.max(0, Math.min(100, item.weight))
          const value = formatPercent(item.weight)
          return (
            <tr key={item.category} title={`${item.category}：${value}`}>
              <td className="w-24 py-2.5 pr-2 text-gray-300">{item.category}</td>
              <td className="px-2 py-2.5">
                <div className="h-1.5 overflow-hidden rounded-full bg-[#29292e]" role="img" aria-label={`${item.category}权重 ${value}`}>
                  {item.weight !== null && <div className="h-full rounded-r bg-[#6f8cff]" style={{ width: `${width}%` }} />}
                </div>
              </td>
              <td className="w-20 py-2.5 pl-2 text-right font-mono text-gray-300">{value}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function riskLabel(level: string): string {
  const normalized = level.toLowerCase()
  if (normalized === 'high' || level === '高') return '高'
  if (normalized === 'medium' || normalized === 'warning' || level === '中') return '中'
  if (normalized === 'low' || level === '低') return '低'
  if (normalized === 'info' || level === '提示') return '提示'
  return level || '提示'
}

function riskBadgeText(level: string): string {
  const label = riskLabel(level)
  return label === '提示' ? label : `${label}风险`
}

function riskTone(level: string): string {
  const label = riskLabel(level)
  if (label === '高') return 'bg-red-500/15 text-red-300'
  if (label === '中') return 'bg-amber-500/15 text-amber-200'
  return 'bg-emerald-500/15 text-emerald-200'
}

function RiskList({ items }: { items: PortfolioRiskItem[] }) {
  if (!items.length) return <p className="py-4 text-center text-xs text-gray-600">当前无规则风险项</p>
  return (
    <div className="space-y-3">
      {items.map((risk) => (
        <article key={`${risk.code}-${risk.title}`} className="rounded-lg border border-[#303034] bg-[#0d0d0d] p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded px-1.5 py-0.5 text-[10px] ${riskTone(risk.level)}`}>{riskBadgeText(risk.level)}</span>
            <strong className="text-xs font-medium text-gray-200">{risk.title}</strong>
          </div>
          <p className="mt-2 text-[11px] leading-5 text-gray-400">{risk.detail}</p>
        </article>
      ))}
    </div>
  )
}

export function PortfolioInsights({ portfolio }: { portfolio: PortfolioDetail }) {
  return (
    <>
      <section className={`${panelClass} p-4`}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-medium text-gray-200">资产分类</h2>
          <span className="text-[10px] text-gray-600">指标日期 {portfolio.as_of_date}</span>
        </div>
        <p className="mt-1 text-[11px] text-gray-600">占组合配置金额的权重</p>
        <div className="mt-3"><AllocationBars portfolio={portfolio} /></div>
      </section>
      <section className={`${panelClass} p-4`}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-medium text-gray-200">集中度</h2>
        </div>
        <dl className="mt-3 space-y-2 text-xs">
          <div className="flex justify-between gap-3"><dt className="text-gray-500">最大持仓权重</dt><dd className="font-mono text-gray-300">{formatPercent(portfolio.metrics.max_holding_weight)}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-gray-500">占已投资部分</dt><dd className="font-mono text-gray-300">{formatPercent(portfolio.metrics.max_holding_share_of_invested)}</dd></div>
        </dl>
      </section>
      <section className={`${panelClass} p-4`}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-gray-200">规则风险项</h2>
          <span className="text-[10px] text-gray-600">{portfolio.metrics.risk_items.length} 项</span>
        </div>
        <div className="mt-3"><RiskList items={portfolio.metrics.risk_items} /></div>
        <p className="mt-3 text-[10px] leading-4 text-gray-600">风险项由确定性规则生成，仅用于研究，不构成投资建议。</p>
      </section>
    </>
  )
}
