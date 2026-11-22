import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { Input, Modal, Skeleton } from '@/components/ui'
import {
  archivePortfolio,
  copyPortfolio,
  createPortfolio,
  isPortfolioConflict,
  listPortfolios,
  portfolioKeys,
  restorePortfolio,
  type PortfolioSummary,
} from '@/api/portfolio'
import {
  applyPortfolioDetail,
  EmptyState,
  errorMessage,
  formatAmount,
  formatPercent,
  InlineAlert,
  panelClass,
  PortfolioLayout,
  primaryButtonClass,
  secondaryButtonClass,
  StatusBadge,
} from './common'
import { PortfolioFormModal } from './PortfolioFormModal'

const PAGE_SIZE = 20

export function PortfolioList() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [includeArchived, setIncludeArchived] = useState(false)
  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const [copyTarget, setCopyTarget] = useState<PortfolioSummary | null>(null)
  const [copyName, setCopyName] = useState('')
  const [notice, setNotice] = useState('')
  const [actionError, setActionError] = useState('')
  const [conflict, setConflict] = useState(false)

  const listQuery = useQuery({
    queryKey: portfolioKeys.list({ includeArchived, page, pageSize: PAGE_SIZE }),
    queryFn: () => listPortfolios({ includeArchived, page, pageSize: PAGE_SIZE }),
  })

  const createMutation = useMutation({
    mutationFn: createPortfolio,
    onSuccess: (detail) => {
      applyPortfolioDetail(queryClient, detail)
      setCreateOpen(false)
      navigate(`/portfolio/${detail.id}`)
    },
  })

  const copyMutation = useMutation({
    mutationFn: ({ id, name }: { id: PortfolioSummary['id']; name?: string }) => copyPortfolio(id, name),
    onSuccess: (detail) => {
      applyPortfolioDetail(queryClient, detail)
      setCopyTarget(null)
      setNotice(`已创建副本“${detail.name}”。`)
      setActionError('')
      setConflict(false)
    },
    onError: (reason) => {
      setConflict(isPortfolioConflict(reason))
      setActionError(errorMessage(reason, '复制组合失败'))
    },
  })

  const archiveMutation = useMutation({
    mutationFn: (portfolio: PortfolioSummary) => portfolio.status === 'archived'
      ? restorePortfolio(portfolio.id, portfolio.version)
      : archivePortfolio(portfolio.id, portfolio.version),
    onSuccess: (detail) => {
      applyPortfolioDetail(queryClient, detail)
      setNotice(detail.status === 'archived' ? `已归档“${detail.name}”。` : `已恢复“${detail.name}”。`)
      setActionError('')
      setConflict(false)
    },
    onError: (reason) => {
      const isConflict = isPortfolioConflict(reason)
      setConflict(isConflict)
      setActionError(isConflict ? '组合已被其他操作更新，请刷新列表后重试。' : errorMessage(reason, '归档操作失败'))
      if (isConflict) void queryClient.invalidateQueries({ queryKey: portfolioKeys.lists() })
    },
  })

  function openCopy(portfolio: PortfolioSummary) {
    copyMutation.reset()
    setCopyTarget(portfolio)
    setCopyName(`${portfolio.name} - 副本`)
    setActionError('')
    setConflict(false)
  }

  async function submitCopy(event: FormEvent) {
    event.preventDefault()
    if (!copyTarget) return
    try {
      await copyMutation.mutateAsync({ id: copyTarget.id, name: copyName.trim() || undefined })
    } catch {
      // mutation.onError 与弹窗错误区统一展示，不产生未处理 Promise。
    }
  }

  const data = listQuery.data
  const items = data?.items ?? []
  const totalPages = data?.total_pages ?? 1

  const main = (
    <>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-white">研究组合</h1>
          <p className="mt-1 text-xs text-gray-500">账号级债券持仓与指标快照，跨浏览器保存。</p>
        </div>
        <button type="button" className={primaryButtonClass} onClick={() => setCreateOpen(true)}>新建组合</button>
      </header>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-xs text-gray-400">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => { setIncludeArchived(event.target.checked); setPage(1); setNotice(''); setActionError('') }}
            className="rounded border-gray-600 bg-gray-900"
          />
          显示已归档
        </label>
        {data && <span className="text-[11px] text-gray-600">共 {data.total} 个组合</span>}
      </div>

      {notice && <InlineAlert tone="success">{notice}</InlineAlert>}
      {actionError && (
        <InlineAlert action={conflict ? <button type="button" className={secondaryButtonClass} onClick={() => { setActionError(''); setConflict(false); void listQuery.refetch() }}>刷新列表</button> : undefined}>
          {actionError}
        </InlineAlert>
      )}

      {listQuery.isLoading ? (
        <div className="space-y-3"><Skeleton height="130px" variant="rectangular" /><Skeleton height="130px" variant="rectangular" /></div>
      ) : listQuery.isError ? (
        <EmptyState
          title="组合列表加载失败"
          detail={errorMessage(listQuery.error, '请检查网络连接后重试。')}
          action={<button type="button" className={secondaryButtonClass} onClick={() => void listQuery.refetch()}>重试</button>}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title={includeArchived ? '暂无研究组合' : '还没有使用中的研究组合'}
          detail="新建后可逐笔录入或导入 CSV；组合与持仓保存在账号下，不依赖浏览器草稿。"
          action={<button type="button" className={primaryButtonClass} onClick={() => setCreateOpen(true)}>新建组合</button>}
        />
      ) : (
        <div className="grid gap-3 xl:grid-cols-2">
          {items.map((portfolio) => (
            <article key={portfolio.id} className={`${panelClass} p-4 transition-colors hover:border-[#414149]`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link to={`/portfolio/${portfolio.id}`} className="truncate text-sm font-medium text-white hover:text-[#9eb5ff]">{portfolio.name}</Link>
                    <StatusBadge status={portfolio.status} />
                  </div>
                  <p className="mt-1 text-[11px] text-gray-500">指标日期 {portfolio.as_of_date} · 版本 {portfolio.version}</p>
                </div>
                <span className="shrink-0 font-mono text-sm text-gray-200">{formatAmount(portfolio.size_amount)}</span>
              </div>
              {portfolio.description && <p className="mt-3 line-clamp-2 text-xs leading-5 text-gray-500">{portfolio.description}</p>}
              <dl className="mt-4 grid grid-cols-3 gap-2 text-xs">
                <div><dt className="text-[10px] text-gray-600">持仓数</dt><dd className="mt-1 font-mono text-gray-300">{portfolio.holdings_count}</dd></div>
                <div><dt className="text-[10px] text-gray-600">已投资</dt><dd className="mt-1 font-mono text-[#9eb5ff]">{formatPercent(portfolio.invested_weight)}</dd></div>
                <div><dt className="text-[10px] text-gray-600">现金</dt><dd className="mt-1 font-mono text-gray-300">{formatPercent(portfolio.cash_weight)}</dd></div>
              </dl>
              <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-[#252529] pt-3">
                <button type="button" className="rounded px-2.5 py-1.5 text-xs text-gray-400 hover:bg-[#202024] hover:text-white" onClick={() => openCopy(portfolio)}>复制</button>
                <button
                  type="button"
                  aria-label={`${portfolio.status === 'archived' ? '恢复' : '归档'} ${portfolio.name}`}
                  className={`rounded px-2.5 py-1.5 text-xs ${portfolio.status === 'archived' ? 'text-emerald-300 hover:bg-emerald-500/10' : 'text-amber-200 hover:bg-amber-500/10'}`}
                  disabled={archiveMutation.isPending}
                  onClick={() => { setNotice(''); setActionError(''); archiveMutation.mutate(portfolio) }}
                >
                  {archiveMutation.isPending && String(archiveMutation.variables?.id) === String(portfolio.id) ? '处理中…' : portfolio.status === 'archived' ? '恢复' : '归档'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {data && totalPages > 1 && (
        <nav className="flex items-center justify-center gap-3 text-xs text-gray-400" aria-label="组合列表分页">
          <button type="button" className={secondaryButtonClass} disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>上一页</button>
          <span>第 {data.page} / {totalPages} 页</span>
          <button type="button" className={secondaryButtonClass} disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>下一页</button>
        </nav>
      )}

      <PortfolioFormModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmit={(values) => createMutation.mutateAsync(values)}
        onSuccess={() => setCreateOpen(false)}
      />

      <Modal isOpen={Boolean(copyTarget)} onClose={() => { if (!copyMutation.isPending) setCopyTarget(null) }} title="复制研究组合" size="sm">
        <form className="space-y-4 text-left" onSubmit={submitCopy}>
          <Input aria-label="副本名称" label="副本名称" value={copyName} onChange={(event) => setCopyName(event.target.value)} placeholder="留空则由后端生成名称" />
          <p className="text-xs leading-5 text-gray-500">复制组合设置和当前持仓，生成独立的新组合。</p>
          {copyMutation.isError && <p role="alert" className="text-xs text-red-300">{errorMessage(copyMutation.error, '复制组合失败')}</p>}
          <div className="flex justify-end gap-2 border-t border-gray-700 pt-4">
            <button type="button" className={secondaryButtonClass} disabled={copyMutation.isPending} onClick={() => setCopyTarget(null)}>取消</button>
            <button type="submit" className={primaryButtonClass} disabled={copyMutation.isPending}>{copyMutation.isPending ? '复制中…' : '确认复制'}</button>
          </div>
        </form>
      </Modal>
    </>
  )

  const aside = (
    <>
      <section className={`${panelClass} p-4`}>
        <h2 className="text-sm font-medium text-gray-200">组合口径</h2>
        <ul className="mt-3 space-y-3 text-[11px] leading-5 text-gray-500">
          <li>配置金额以人民币元保存，页面按万元录入，仅用于研究规模估算。</li>
          <li>持仓权重基于配置金额；未投资部分自动计为现金。</li>
          <li>久期和收益率按有数据持仓加权，并同时展示覆盖率。</li>
          <li>所有指标以组合标注的指标日期为准，缺失值显示为“—”。</li>
        </ul>
      </section>
      <section className={`${panelClass} p-4`}>
        <h2 className="text-sm font-medium text-gray-200">研究工作流</h2>
        <ol className="mt-3 space-y-2 text-xs leading-5 text-gray-500">
          <li>1. 新建组合并设置估算规模</li>
          <li>2. 手动添加或 CSV 导入持仓</li>
          <li>3. 查看资产分布与规则风险项</li>
          <li>4. 导出 CSV 留存或继续分析</li>
        </ol>
      </section>
    </>
  )

  return <PortfolioLayout main={main} aside={aside} />
}
