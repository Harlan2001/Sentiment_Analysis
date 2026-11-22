import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Skeleton } from '@/components/ui'
import {
  addPortfolioHolding,
  archivePortfolio,
  deletePortfolioHolding,
  exportPortfolioCsv,
  getPortfolio,
  importPortfolioHoldings,
  isPortfolioConflict,
  isPortfolioNotFound,
  portfolioKeys,
  reorderPortfolioHoldings,
  restorePortfolio,
  updatePortfolio,
  updatePortfolioHolding,
  type HoldingId,
  type HoldingInput,
  type PortfolioDetail,
  type PortfolioId,
  type PortfolioSettingsInput,
} from '@/api/portfolio'
import {
  applyPortfolioDetail,
  EmptyState,
  errorMessage,
  formatAmount,
  formatYears,
  InlineAlert,
  panelClass,
  PortfolioLayout,
  primaryButtonClass,
  secondaryButtonClass,
  StatusBadge,
} from './common'
import { PortfolioFormModal } from './PortfolioFormModal'
import { ImportHoldingsModal } from './ImportHoldingsModal'
import { HoldingsTable } from './HoldingsTable'
import { MetricCards, PortfolioInsights } from './PortfolioInsights'

export function PortfolioDetailView({ portfolioId }: { portfolioId: PortfolioId }) {
  const queryClient = useQueryClient()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [actionError, setActionError] = useState('')
  const [conflict, setConflict] = useState(false)
  const [exporting, setExporting] = useState(false)

  const detailQuery = useQuery({
    queryKey: portfolioKeys.detail(portfolioId),
    queryFn: () => getPortfolio(portfolioId),
    enabled: String(portfolioId).length > 0,
  })
  const data = detailQuery.data

  function expectedVersion(): number {
    if (!data) throw new Error('组合尚未加载，请刷新后重试。')
    return data.version
  }

  function updateCache(detail: PortfolioDetail) {
    applyPortfolioDetail(queryClient, detail)
    setActionError('')
    setConflict(false)
  }

  function handleMutationError(reason: unknown) {
    const isConflict = isPortfolioConflict(reason)
    setConflict(isConflict)
    setActionError(
      isConflict
        ? '检测到组合版本冲突，其他操作已先更新数据。请刷新组合并重新查询后再试。'
        : errorMessage(reason, '组合操作失败'),
    )
    if (isConflict) {
      void queryClient.invalidateQueries({ queryKey: portfolioKeys.detail(portfolioId) })
      void queryClient.invalidateQueries({ queryKey: portfolioKeys.lists() })
    }
  }

  const settingsMutation = useMutation({
    mutationFn: (values: PortfolioSettingsInput) => updatePortfolio(portfolioId, { ...values, expected_version: expectedVersion() }),
    onSuccess: updateCache,
    onError: handleMutationError,
  })
  const archiveMutation = useMutation({
    mutationFn: (action: 'archive' | 'restore') => action === 'archive'
      ? archivePortfolio(portfolioId, expectedVersion())
      : restorePortfolio(portfolioId, expectedVersion()),
    onSuccess: (detail) => {
      updateCache(detail)
      setNotice(detail.status === 'archived' ? '组合已归档，当前为只读状态。' : '组合已恢复，可以继续编辑。')
    },
    onError: handleMutationError,
  })
  const addMutation = useMutation({
    mutationFn: (input: HoldingInput) => addPortfolioHolding(portfolioId, input, expectedVersion()),
    onSuccess: updateCache,
    onError: handleMutationError,
  })
  const editMutation = useMutation({
    mutationFn: ({ holdingId, input }: { holdingId: HoldingId; input: HoldingInput }) =>
      updatePortfolioHolding(portfolioId, holdingId, input, expectedVersion()),
    onSuccess: updateCache,
    onError: handleMutationError,
  })
  const deleteMutation = useMutation({
    mutationFn: (holdingId: HoldingId) => deletePortfolioHolding(portfolioId, holdingId, expectedVersion()),
    onSuccess: updateCache,
    onError: handleMutationError,
  })
  const reorderMutation = useMutation({
    mutationFn: (holdingIds: HoldingId[]) => reorderPortfolioHoldings(portfolioId, holdingIds, expectedVersion()),
    onSuccess: updateCache,
    onError: handleMutationError,
  })
  const importMutation = useMutation({
    mutationFn: ({ file, mode }: { file: File; mode: 'append' | 'replace' }) =>
      importPortfolioHoldings(portfolioId, file, mode, expectedVersion()),
    onSuccess: (result) => updateCache(result.portfolio),
    onError: handleMutationError,
  })

  async function refreshDetail() {
    const result = await detailQuery.refetch()
    if (result.data) {
      setActionError('')
      setConflict(false)
      setNotice('已刷新为服务端最新组合。')
      setSettingsOpen(false)
      setImportOpen(false)
    }
  }

  async function handleExport() {
    if (!data) return
    setExporting(true)
    setActionError('')
    try {
      const blob = await exportPortfolioCsv(data.id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      const safeName = data.name.replace(/[\\/:*?"<>|]/g, '_')
      anchor.href = url
      anchor.download = `${safeName}-${data.as_of_date}.csv`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setNotice('CSV 已导出。')
    } catch (reason) {
      setConflict(false)
      setActionError(errorMessage(reason, '导出失败'))
    } finally {
      setExporting(false)
    }
  }

  if (detailQuery.isLoading) {
    return (
      <PortfolioLayout
        main={<div className="space-y-4 pt-2"><Skeleton height="76px" variant="rectangular" /><Skeleton height="130px" variant="rectangular" /><Skeleton height="360px" variant="rectangular" /></div>}
        aside={<Skeleton height="240px" variant="rectangular" />}
      />
    )
  }

  if (detailQuery.isError || !data) {
    const notFound = isPortfolioNotFound(detailQuery.error)
    return (
      <PortfolioLayout
        main={
          <>
            <Link to="/portfolio" className="inline-block pt-2 text-xs text-gray-400 hover:text-white">← 返回组合列表</Link>
            <EmptyState
              title={notFound ? '组合不存在或无权访问' : '组合加载失败'}
              detail={notFound ? '该组合可能已删除，或不属于当前账号。' : errorMessage(detailQuery.error, '请检查网络连接后重试。')}
              action={notFound
                ? <Link to="/portfolio" className={secondaryButtonClass}>返回组合列表</Link>
                : <button type="button" className={secondaryButtonClass} onClick={() => void detailQuery.refetch()}>重试</button>}
            />
          </>
        }
        aside={<section className={`${panelClass} p-4 text-xs leading-5 text-gray-500`}>组合数据按账号隔离。列表页可新建组合或打开其他研究组合。</section>}
      />
    )
  }

  const archived = data.status === 'archived'
  const holdingBusy = addMutation.isPending || editMutation.isPending || deleteMutation.isPending || reorderMutation.isPending
  const busy = holdingBusy || settingsMutation.isPending || archiveMutation.isPending || importMutation.isPending
  const fullCash = data.metrics.cash_weight === 100

  const main = (
    <>
      <header className="space-y-3 pt-2">
        <Link to="/portfolio" className="inline-block text-xs text-gray-500 hover:text-white">← 返回组合列表</Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="break-all text-lg font-bold text-white">{data.name}</h1>
              <StatusBadge status={data.status} />
              <span className="rounded border border-[#343438] bg-[#191919] px-1.5 py-0.5 text-[10px] text-gray-500">版本 {data.version}</span>
            </div>
            <p className="mt-1 text-xs leading-5 text-gray-500">
              指标日期 {data.as_of_date} · 配置金额 {formatAmount(data.size_amount)}（估算） · 目标久期 {formatYears(data.target_duration)}
            </p>
            {data.description && <p className="mt-2 max-w-2xl text-xs leading-5 text-gray-400">{data.description}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            {!archived && <button type="button" className={secondaryButtonClass} disabled={busy} onClick={() => { setNotice(''); setSettingsOpen(true) }}>编辑组合设置</button>}
            {!archived && <button type="button" className={secondaryButtonClass} disabled={busy} onClick={() => { setNotice(''); setImportOpen(true) }}>导入 CSV</button>}
            <button type="button" className={secondaryButtonClass} disabled={exporting} onClick={() => void handleExport()}>{exporting ? '导出中…' : '导出 CSV'}</button>
            <button type="button" className={archived ? primaryButtonClass : 'rounded-lg border border-amber-500/30 px-3 py-2 text-xs text-amber-200 hover:bg-amber-500/10 disabled:opacity-40'} disabled={busy} onClick={() => { setNotice(''); archiveMutation.mutate(archived ? 'restore' : 'archive') }}>
              {archiveMutation.isPending ? '处理中…' : archived ? '恢复组合' : '归档组合'}
            </button>
          </div>
        </div>
      </header>

      {archived && <InlineAlert tone="info" action={<button type="button" className={secondaryButtonClass} disabled={busy} onClick={() => archiveMutation.mutate('restore')}>恢复后可编辑</button>}>已归档组合为只读，持仓和指标仍可查看、导出。</InlineAlert>}
      {notice && <InlineAlert tone="success">{notice}</InlineAlert>}
      {actionError && (
        <InlineAlert action={conflict ? <button type="button" className={secondaryButtonClass} disabled={detailQuery.isFetching} onClick={() => void refreshDetail()}>{detailQuery.isFetching ? '刷新中…' : '刷新组合'}</button> : undefined}>
          {actionError}
        </InlineAlert>
      )}

      <MetricCards portfolio={data} />
      {fullCash && <InlineAlert tone="info">当前为全现金组合；新增持仓后，现金与已投资权重将由后端重新计算。</InlineAlert>}

      <HoldingsTable
        portfolio={data}
        readOnly={archived}
        busy={busy}
        onAdd={(input) => addMutation.mutateAsync(input)}
        onEdit={(holdingId, input) => editMutation.mutateAsync({ holdingId, input })}
        onDelete={(holdingId) => deleteMutation.mutateAsync(holdingId)}
        onReorder={(holdingIds) => reorderMutation.mutateAsync(holdingIds)}
        onSuccess={(detail, message) => { updateCache(detail); setNotice(message) }}
        onError={handleMutationError}
      />

      <p className="text-[11px] leading-5 text-gray-600">
        权重以配置金额为基数，持仓合计无需等于 100%；未投资部分自动形成现金。久期与收益率仅对有值持仓加权，覆盖率不足时不会将缺失值按 0 处理。
      </p>

      <PortfolioFormModal
        isOpen={settingsOpen}
        portfolio={data}
        onClose={() => setSettingsOpen(false)}
        onSubmit={(values) => settingsMutation.mutateAsync(values)}
        onSuccess={(detail) => { updateCache(detail); setSettingsOpen(false); setNotice('组合设置已保存。') }}
      />
      <ImportHoldingsModal
        isOpen={importOpen}
        onClose={() => setImportOpen(false)}
        onSubmit={(file, mode) => importMutation.mutateAsync({ file, mode })}
        onSuccess={(result) => {
          updateCache(result.portfolio)
          setNotice(result.errors.length ? 'CSV 校验未通过，整批未写入。' : `成功导入 ${result.imported_count} 条持仓。`)
        }}
      />
    </>
  )

  return <PortfolioLayout main={main} aside={<PortfolioInsights portfolio={data} />} />
}
