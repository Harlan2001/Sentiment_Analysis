import { API_PREFIX, authHeaders, request } from './client'

export type PortfolioId = string | number
export type HoldingId = string | number
export type PortfolioStatus = 'active' | 'archived'

export type PortfolioSummary = {
  id: PortfolioId
  name: string
  description: string | null
  size_amount: number
  as_of_date: string
  target_duration: number | null
  status: PortfolioStatus
  version: number
  created_at: string
  updated_at: string
  holdings_count: number
  invested_weight: number
  cash_weight: number
}

export type Holding = {
  id: HoldingId
  bond_code: string
  bond_name: string
  asset_category: string
  weight_pct: number
  yield_pct: number | null
  duration_years: number | null
  sort_order: number
  note: string | null
}

export type AssetAllocation = {
  category: string
  weight: number | null
}

export type PortfolioRiskItem = {
  code: string
  level: string
  title: string
  detail: string
}

export type PortfolioMetrics = {
  invested_weight: number | null
  cash_weight: number | null
  weighted_duration: number | null
  duration_coverage: number | null
  weighted_yield: number | null
  yield_coverage: number | null
  asset_allocations: AssetAllocation[]
  max_holding_weight: number | null
  max_holding_share_of_invested: number | null
  risk_items: PortfolioRiskItem[]
}

export type PortfolioDetail = PortfolioSummary & {
  holdings: Holding[]
  metrics: PortfolioMetrics
}

export type PortfolioListResponse = {
  items: PortfolioSummary[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type PortfolioSettingsInput = {
  name: string
  description?: string
  size_amount: number
  as_of_date: string
  target_duration?: number | null
}

export type HoldingInput = {
  bond_code: string
  bond_name: string
  asset_category: string
  weight_pct: number
  yield_pct?: number | null
  duration_years?: number | null
  note?: string | null
}

export type PortfolioImportError = {
  row: number
  field: string
  message: string
}

export type PortfolioImportResult = {
  imported_count: number
  errors: PortfolioImportError[]
  portfolio: PortfolioDetail
}

const BASE = `${API_PREFIX}/portfolios`

export const portfolioKeys = {
  all: ['portfolios'] as const,
  lists: () => [...portfolioKeys.all, 'list'] as const,
  list: (params: { includeArchived: boolean; page: number; pageSize: number }) =>
    [...portfolioKeys.lists(), params] as const,
  detail: (id: PortfolioId) => [...portfolioKeys.all, 'detail', String(id)] as const,
}

function queryString(values: Record<string, string | number | boolean | undefined>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined) params.set(key, String(value))
  }
  return params.toString()
}

function json(body: unknown): Pick<RequestInit, 'headers' | 'body'> {
  return { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

export function listPortfolios(params: { includeArchived?: boolean; page?: number; pageSize?: number } = {}) {
  const { includeArchived = false, page = 1, pageSize = 20 } = params
  return request<PortfolioListResponse>(`${BASE}?${queryString({
    include_archived: includeArchived,
    page,
    page_size: pageSize,
  })}`)
}

export function getPortfolio(id: PortfolioId) {
  return request<PortfolioDetail>(`${BASE}/${encodeURIComponent(String(id))}`)
}

export function createPortfolio(input: PortfolioSettingsInput) {
  return request<PortfolioDetail>(BASE, { method: 'POST', ...json(input) })
}

export function updatePortfolio(
  id: PortfolioId,
  input: Partial<PortfolioSettingsInput> & { expected_version: number },
) {
  return request<PortfolioDetail>(`${BASE}/${encodeURIComponent(String(id))}`, {
    method: 'PATCH',
    ...json(input),
  })
}

export function copyPortfolio(id: PortfolioId, name?: string) {
  return request<PortfolioDetail>(`${BASE}/${encodeURIComponent(String(id))}/copy`, {
    method: 'POST',
    ...json(name ? { name } : {}),
  })
}

export function archivePortfolio(id: PortfolioId, expectedVersion: number) {
  return request<PortfolioDetail>(`${BASE}/${encodeURIComponent(String(id))}/archive`, {
    method: 'POST',
    ...json({ expected_version: expectedVersion }),
  })
}

export function restorePortfolio(id: PortfolioId, expectedVersion: number) {
  return request<PortfolioDetail>(`${BASE}/${encodeURIComponent(String(id))}/restore`, {
    method: 'POST',
    ...json({ expected_version: expectedVersion }),
  })
}

export function addPortfolioHolding(id: PortfolioId, input: HoldingInput, expectedVersion: number) {
  return request<PortfolioDetail>(`${BASE}/${encodeURIComponent(String(id))}/holdings`, {
    method: 'POST',
    ...json({ ...input, expected_version: expectedVersion }),
  })
}

export function updatePortfolioHolding(
  id: PortfolioId,
  holdingId: HoldingId,
  input: Partial<HoldingInput>,
  expectedVersion: number,
) {
  return request<PortfolioDetail>(
    `${BASE}/${encodeURIComponent(String(id))}/holdings/${encodeURIComponent(String(holdingId))}`,
    { method: 'PATCH', ...json({ ...input, expected_version: expectedVersion }) },
  )
}

export function deletePortfolioHolding(id: PortfolioId, holdingId: HoldingId, expectedVersion: number) {
  const path = `${BASE}/${encodeURIComponent(String(id))}/holdings/${encodeURIComponent(String(holdingId))}`
  return request<PortfolioDetail>(`${path}?${queryString({ expected_version: expectedVersion })}`, {
    method: 'DELETE',
  })
}

export function reorderPortfolioHoldings(id: PortfolioId, holdingIds: HoldingId[], expectedVersion: number) {
  return request<PortfolioDetail>(`${BASE}/${encodeURIComponent(String(id))}/holdings/order`, {
    method: 'PUT',
    ...json({ expected_version: expectedVersion, holding_ids: holdingIds }),
  })
}

export function importPortfolioHoldings(
  id: PortfolioId,
  file: File,
  mode: 'append' | 'replace',
  expectedVersion: number,
) {
  const body = new FormData()
  body.append('file', file)
  const path = `${BASE}/${encodeURIComponent(String(id))}/holdings/import`
  return request<PortfolioImportResult>(`${path}?${queryString({ mode, expected_version: expectedVersion })}`, {
    method: 'POST',
    body,
  })
}

/** CSV 是二进制响应，不能走会解析标准 data 壳的 request()。 */
export async function exportPortfolioCsv(id: PortfolioId): Promise<Blob> {
  const response = await fetch(`${BASE}/${encodeURIComponent(String(id))}/export`, {
    headers: authHeaders(),
  })
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string; message?: string } | null
    throw new Error(payload?.detail || payload?.message || '导出失败')
  }
  return response.blob()
}

/** 公共 client 目前只保留服务端错误文案；按后端 409 约定识别可恢复的版本冲突。 */
export function isPortfolioConflict(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return /409|版本.*(?:冲突|变化)|刷新后重试|已归档|并发|已被.*(?:修改|更新|归档)|conflict|expected_version|version mismatch/i.test(message)
}

export function isPortfolioNotFound(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return /404|不存在|无权访问|not found/i.test(message)
}
