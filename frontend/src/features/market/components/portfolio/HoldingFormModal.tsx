import { useEffect, useState, type FormEvent } from 'react'
import { Input, Modal } from '@/components/ui'
import { isPortfolioConflict, type Holding, type HoldingInput, type PortfolioDetail } from '@/api/portfolio'
import { errorMessage, primaryButtonClass, secondaryButtonClass } from './common'

type Props = {
  isOpen: boolean
  onClose: () => void
  holding?: Holding | null
  onSubmit: (input: HoldingInput) => Promise<PortfolioDetail>
  onSuccess: (detail: PortfolioDetail) => void
}

export function HoldingFormModal({ isOpen, onClose, holding, onSubmit, onSuccess }: Props) {
  const editing = Boolean(holding)
  const [bondCode, setBondCode] = useState('')
  const [bondName, setBondName] = useState('')
  const [category, setCategory] = useState('')
  const [weight, setWeight] = useState('')
  const [yieldPct, setYieldPct] = useState('')
  const [duration, setDuration] = useState('')
  const [note, setNote] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isOpen) return
    setBondCode(holding?.bond_code ?? '')
    setBondName(holding?.bond_name ?? '')
    setCategory(holding?.asset_category ?? '')
    setWeight(holding ? String(holding.weight_pct) : '')
    setYieldPct(holding?.yield_pct === null || holding?.yield_pct === undefined ? '' : String(holding.yield_pct))
    setDuration(holding?.duration_years === null || holding?.duration_years === undefined ? '' : String(holding.duration_years))
    setNote(holding?.note ?? '')
    setPending(false)
    setError('')
  }, [isOpen, holding?.id])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const weightValue = Number(weight)
    const yieldValue = yieldPct.trim() === '' ? null : Number(yieldPct)
    const durationValue = duration.trim() === '' ? null : Number(duration)
    if (!bondCode.trim() || !bondName.trim()) return setError('请输入债券代码和债券名称。')
    if (!category.trim()) return setError('请输入资产分类。')
    if (weight.trim() === '' || !Number.isFinite(weightValue) || weightValue < 0) {
      return setError('权重须为不小于 0 的百分数。')
    }
    if (yieldValue !== null && !Number.isFinite(yieldValue)) return setError('收益率格式不正确。')
    if (durationValue !== null && (!Number.isFinite(durationValue) || durationValue < 0)) {
      return setError('久期须为不小于 0 的数字，也可留空。')
    }

    setPending(true)
    setError('')
    try {
      const detail = await onSubmit({
        bond_code: bondCode.trim(),
        bond_name: bondName.trim(),
        asset_category: category.trim(),
        weight_pct: weightValue,
        yield_pct: yieldValue,
        duration_years: durationValue,
        note: note.trim() || null,
      })
      onSuccess(detail)
    } catch (reason) {
      setError(
        isPortfolioConflict(reason)
          ? '组合版本冲突，请关闭弹窗并刷新组合后重新操作。'
          : errorMessage(reason, editing ? '保存持仓失败' : '新增持仓失败'),
      )
    } finally {
      setPending(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={() => { if (!pending) onClose() }} title={editing ? '编辑持仓' : '新增持仓'} size="md">
      <form className="space-y-4 text-left" onSubmit={handleSubmit} noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input aria-label="债券代码" label="债券代码" value={bondCode} onChange={(event) => setBondCode(event.target.value)} placeholder="例如：240004" required />
          <Input aria-label="债券名称" label="债券名称" value={bondName} onChange={(event) => setBondName(event.target.value)} placeholder="例如：24附息国债04" required />
          <Input aria-label="资产分类" label="资产分类" value={category} onChange={(event) => setCategory(event.target.value)} placeholder="例如：国债、政策性金融债" required />
          <Input
            aria-label="持仓权重（%）"
            label="持仓权重（%）"
            type="number"
            min="0"
            step="0.01"
            value={weight}
            onChange={(event) => setWeight(event.target.value)}
            helperText="按组合配置金额的百分数填写。"
            required
          />
          <Input aria-label="到期收益率（%）" label="到期收益率（%，可选）" type="number" step="0.0001" value={yieldPct} onChange={(event) => setYieldPct(event.target.value)} placeholder="缺失时留空" />
          <Input aria-label="持仓久期（年）" label="久期（年，可选）" type="number" min="0" step="0.01" value={duration} onChange={(event) => setDuration(event.target.value)} placeholder="缺失时留空" />
          <label className="grid gap-1 text-sm font-medium text-gray-300 sm:col-span-2">
            备注（可选）
            <textarea aria-label="持仓备注" value={note} onChange={(event) => setNote(event.target.value)} rows={2} className="rounded-lg border border-gray-600 bg-gray-900 px-3.5 py-2.5 text-sm font-normal text-white outline-none focus:border-purple-500" />
          </label>
        </div>
        <p className="text-[11px] leading-5 text-gray-500">
          不要求持仓权重合计等于 100%；未投资部分自动形成现金。若合计超过 100%，将展示后端返回的错误。
        </p>
        {error && <p role="alert" className="text-xs leading-5 text-red-300">{error}</p>}
        <div className="flex justify-end gap-2 border-t border-gray-700 pt-4">
          <button type="button" className={secondaryButtonClass} onClick={onClose} disabled={pending}>取消</button>
          <button type="submit" className={primaryButtonClass} disabled={pending}>
            {pending ? '提交中…' : editing ? '保存持仓' : '添加持仓'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
