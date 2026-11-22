import type { ReactNode } from 'react'
import type { QueryClient } from '@tanstack/react-query'
import { portfolioKeys, type PortfolioDetail, type PortfolioListResponse } from '@/api/portfolio'

export const panelClass = 'rounded-xl border border-[#2a2a2e] bg-[#111111]'
export const secondaryButtonClass =
  'rounded-lg border border-[#3d3d42] px-3 py-2 text-xs text-gray-300 hover:bg-[#1b1b1d] disabled:cursor-not-allowed disabled:opacity-40'
export const primaryButtonClass =
  'rounded-lg bg-white px-3 py-2 text-xs font-medium text-black hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-40'

export function PortfolioLayout({ main, aside }: { main: ReactNode; aside: ReactNode }) {
  return (
    <div className="market-workspace" style={{ position: 'absolute', inset: 0 }}>
      <div className="market-workspace-body">
        <div className="market-discover-panel">
          <main className="space-y-4 pb-4 pl-4 pr-px pt-2">{main}</main>
        </div>
        <aside className="market-side-panel">
          <div className="space-y-4 p-4">{aside}</div>
        </aside>
      </div>
    </div>
  )
}

export function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${value.toFixed(digits)}%`
}

export function formatYears(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${value.toFixed(2)} 年`
}

/** 接口金额固定为人民币元；展示时才换算为万元/亿元。 */
export function formatAmount(yuan: number | null | undefined): string {
  if (yuan === null || yuan === undefined || !Number.isFinite(yuan)) return '—'
  if (Math.abs(yuan) >= 100_000_000) return `${(yuan / 100_000_000).toFixed(2)} 亿元`
  return `${(yuan / 10_000).toLocaleString('zh-CN', { maximumFractionDigits: 2 })} 万元`
}

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

export function todayInputValue(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

export function StatusBadge({ status }: { status: 'active' | 'archived' }) {
  return (
    <span
      className={`rounded border px-1.5 py-0.5 text-[10px] ${
        status === 'archived'
          ? 'border-amber-500/30 bg-amber-500/10 text-amber-200'
          : 'border-emerald-500/20 bg-emerald-500/10 text-emerald-200'
      }`}
    >
      {status === 'archived' ? '已归档' : '使用中'}
    </span>
  )
}

export function InlineAlert({
  tone = 'error',
  children,
  action,
}: {
  tone?: 'error' | 'info' | 'success'
  children: ReactNode
  action?: ReactNode
}) {
  const tones = {
    error: 'border-red-500/30 bg-red-500/10 text-red-200',
    info: 'border-[#3d3d42] bg-[#171719] text-gray-300',
    success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  }
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2 text-xs ${tones[tone]}`}>
      <div>{children}</div>
      {action}
    </div>
  )
}

export function EmptyState({ title, detail, action }: { title: string; detail?: string; action?: ReactNode }) {
  return (
    <div className={`${panelClass} flex min-h-48 flex-col items-center justify-center gap-3 p-6 text-center`}>
      <p className="text-sm text-gray-300">{title}</p>
      {detail && <p className="max-w-md text-xs leading-5 text-gray-500">{detail}</p>}
      {action}
    </div>
  )
}

/** 所有写接口都返回完整 detail：先直接写缓存，再让列表按自身过滤条件刷新。 */
export function applyPortfolioDetail(queryClient: QueryClient, detail: PortfolioDetail): void {
  queryClient.setQueryData(portfolioKeys.detail(detail.id), detail)
  queryClient.setQueriesData<PortfolioListResponse>({ queryKey: portfolioKeys.lists() }, (current) => {
    if (!current) return current
    const index = current.items.findIndex((item) => String(item.id) === String(detail.id))
    if (index < 0) return current
    const { holdings: _holdings, metrics: _metrics, ...summary } = detail
    const items = [...current.items]
    items[index] = { ...items[index], ...summary }
    return { ...current, items }
  })
  void queryClient.invalidateQueries({ queryKey: portfolioKeys.lists() })
}
