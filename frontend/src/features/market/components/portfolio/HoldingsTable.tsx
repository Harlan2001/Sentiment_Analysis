import { useState } from 'react'
import { Modal } from '@/components/ui'
import type { Holding, HoldingId, HoldingInput, PortfolioDetail } from '@/api/portfolio'
import { errorMessage, formatPercent, formatYears, panelClass, primaryButtonClass, secondaryButtonClass } from './common'
import { HoldingFormModal } from './HoldingFormModal'

type Props = {
  portfolio: PortfolioDetail
  readOnly: boolean
  busy: boolean
  onAdd: (input: HoldingInput) => Promise<PortfolioDetail>
  onEdit: (holdingId: HoldingId, input: HoldingInput) => Promise<PortfolioDetail>
  onDelete: (holdingId: HoldingId) => Promise<PortfolioDetail>
  onReorder: (holdingIds: HoldingId[]) => Promise<PortfolioDetail>
  onSuccess: (detail: PortfolioDetail, message: string) => void
  onError: (reason: unknown) => void
}

export function HoldingsTable({ portfolio, readOnly, busy, onAdd, onEdit, onDelete, onReorder, onSuccess, onError }: Props) {
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Holding | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Holding | null>(null)
  const [deletePending, setDeletePending] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  function openAdd() {
    setEditing(null)
    setFormOpen(true)
  }

  function openEdit(holding: Holding) {
    setEditing(holding)
    setFormOpen(true)
  }

  async function move(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= portfolio.holdings.length) return
    const ids = portfolio.holdings.map((holding) => holding.id)
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    try {
      const detail = await onReorder(ids)
      onSuccess(detail, '持仓顺序已更新。')
    } catch (reason) {
      onError(reason)
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeletePending(true)
    setDeleteError('')
    try {
      const detail = await onDelete(deleteTarget.id)
      setDeleteTarget(null)
      onSuccess(detail, `已删除持仓 ${deleteTarget.bond_name}。`)
    } catch (reason) {
      setDeleteError(errorMessage(reason, '删除持仓失败'))
      onError(reason)
    } finally {
      setDeletePending(false)
    }
  }

  return (
    <section className={`${panelClass} overflow-hidden`}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#2a2a2e] px-4 py-3.5">
        <div>
          <h2 className="text-sm font-medium text-gray-200">持仓明细</h2>
          <p className="mt-1 text-[11px] text-gray-500">共 {portfolio.holdings.length} 条 · 权重基于配置金额估算</p>
        </div>
        {!readOnly && <button type="button" className={primaryButtonClass} onClick={openAdd} disabled={busy}>新增持仓</button>}
      </div>

      {portfolio.holdings.length === 0 ? (
        <div className="flex min-h-40 flex-col items-center justify-center gap-3 p-6 text-center">
          <p className="text-sm text-gray-400">暂无持仓，当前组合以现金为主。</p>
          {!readOnly && <p className="text-xs text-gray-600">可点击“新增持仓”逐笔添加，或使用 CSV 导入。</p>}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[960px] text-left text-xs">
            <thead className="bg-[#0d0d0d] text-[11px] text-gray-400">
              <tr>
                {['债券', '资产分类', '权重', '到期收益率', '久期', '备注', ...(!readOnly ? ['操作'] : [])].map((label) => (
                  <th key={label} className="px-4 py-2.5 font-medium">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#252529]">
              {portfolio.holdings.map((holding, index) => (
                <tr key={holding.id} className="hover:bg-[#151517]">
                  <td className="px-4 py-3">
                    <div className="text-gray-200">{holding.bond_name}</div>
                    <div className="mt-0.5 font-mono text-[10px] text-gray-500">{holding.bond_code}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-300">{holding.asset_category}</td>
                  <td className="px-4 py-3 font-mono text-gray-200">{formatPercent(holding.weight_pct)}</td>
                  <td className="px-4 py-3 font-mono text-gray-300">{formatPercent(holding.yield_pct)}</td>
                  <td className="px-4 py-3 font-mono text-gray-300">{formatYears(holding.duration_years)}</td>
                  <td className="max-w-48 px-4 py-3 text-gray-400">{holding.note || '—'}</td>
                  {!readOnly && (
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 whitespace-nowrap">
                        <button type="button" aria-label={`上移 ${holding.bond_name}`} title="上移" className="rounded border border-[#343438] px-2 py-1 text-gray-400 hover:text-white disabled:opacity-25" disabled={busy || index === 0} onClick={() => void move(index, -1)}>↑</button>
                        <button type="button" aria-label={`下移 ${holding.bond_name}`} title="下移" className="rounded border border-[#343438] px-2 py-1 text-gray-400 hover:text-white disabled:opacity-25" disabled={busy || index === portfolio.holdings.length - 1} onClick={() => void move(index, 1)}>↓</button>
                        <button type="button" aria-label={`编辑 ${holding.bond_name}`} className="rounded px-2 py-1 text-[#9eb5ff] hover:bg-[#20202a]" disabled={busy} onClick={() => openEdit(holding)}>编辑</button>
                        <button type="button" aria-label={`删除 ${holding.bond_name}`} className="rounded px-2 py-1 text-red-300 hover:bg-red-500/10" disabled={busy} onClick={() => { setDeleteError(''); setDeleteTarget(holding) }}>删除</button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <HoldingFormModal
        isOpen={formOpen}
        holding={editing}
        onClose={() => setFormOpen(false)}
        onSubmit={(input) => editing ? onEdit(editing.id, input) : onAdd(input)}
        onSuccess={(detail) => {
          setFormOpen(false)
          onSuccess(detail, editing ? '持仓已更新。' : '持仓已添加。')
        }}
      />

      <Modal isOpen={Boolean(deleteTarget)} onClose={() => { if (!deletePending) setDeleteTarget(null) }} title="删除持仓" size="sm">
        <div className="space-y-4 text-left">
          <p className="text-sm leading-6 text-gray-300">确定删除“{deleteTarget?.bond_name}”吗？组合指标将按最新持仓重新计算。</p>
          {deleteError && <p role="alert" className="text-xs text-red-300">{deleteError}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" className={secondaryButtonClass} disabled={deletePending} onClick={() => setDeleteTarget(null)}>取消</button>
            <button type="button" className="rounded-lg bg-red-500 px-3 py-2 text-xs font-medium text-white hover:bg-red-400 disabled:opacity-40" disabled={deletePending} onClick={() => void confirmDelete()}>
              {deletePending ? '删除中…' : '确认删除'}
            </button>
          </div>
        </div>
      </Modal>
    </section>
  )
}
