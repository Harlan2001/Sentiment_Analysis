import { useEffect, useState, type FormEvent } from 'react'
import { Input, Modal } from '@/components/ui'
import {
  isPortfolioConflict,
  type PortfolioDetail,
  type PortfolioSettingsInput,
} from '@/api/portfolio'
import { errorMessage, primaryButtonClass, secondaryButtonClass, todayInputValue } from './common'

type Props = {
  isOpen: boolean
  onClose: () => void
  portfolio?: PortfolioDetail | null
  onSubmit: (values: PortfolioSettingsInput) => Promise<PortfolioDetail>
  onSuccess: (detail: PortfolioDetail) => void
}

export function PortfolioFormModal({ isOpen, onClose, portfolio, onSubmit, onSuccess }: Props) {
  const editing = Boolean(portfolio)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [sizeWan, setSizeWan] = useState('10000')
  const [asOfDate, setAsOfDate] = useState(todayInputValue())
  const [targetDuration, setTargetDuration] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isOpen) return
    setName(portfolio?.name ?? '')
    setDescription(portfolio?.description ?? '')
    setSizeWan(portfolio ? String(portfolio.size_amount / 10_000) : '10000')
    setAsOfDate(portfolio?.as_of_date ?? todayInputValue())
    setTargetDuration(portfolio?.target_duration === null || portfolio?.target_duration === undefined ? '' : String(portfolio.target_duration))
    setError('')
    setPending(false)
  }, [isOpen, portfolio?.id, portfolio?.version])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const size = Number(sizeWan)
    const duration = targetDuration.trim() === '' ? null : Number(targetDuration)
    if (!name.trim()) return setError('请输入组合名称。')
    if (!asOfDate) return setError('请选择指标日期。')
    if (!Number.isFinite(size) || size <= 0) return setError('配置金额必须大于 0 万元。')
    if (duration !== null && (!Number.isFinite(duration) || duration < 0)) {
      return setError('目标久期须为不小于 0 的数字，也可留空。')
    }

    setPending(true)
    setError('')
    try {
      const detail = await onSubmit({
        name: name.trim(),
        description: description.trim(),
        size_amount: Math.round(size * 10_000),
        as_of_date: asOfDate,
        target_duration: duration,
      })
      onSuccess(detail)
    } catch (reason) {
      setError(
        isPortfolioConflict(reason)
          ? '组合版本冲突，请关闭弹窗并刷新组合后重新编辑。'
          : errorMessage(reason, editing ? '保存组合设置失败' : '创建组合失败'),
      )
    } finally {
      setPending(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={() => { if (!pending) onClose() }} title={editing ? '编辑组合设置' : '新建研究组合'} size="md">
      <form className="space-y-4 text-left" onSubmit={handleSubmit} noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Input aria-label="组合名称" label="组合名称" value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：稳健利率债研究" required />
          </div>
          <Input
            aria-label="配置金额（万元）"
            label="配置金额（万元）"
            type="number"
            min="0"
            step="0.01"
            value={sizeWan}
            onChange={(event) => setSizeWan(event.target.value)}
            helperText="仅用于规模与权重估算，不代表实时资产净值。"
            required
          />
          <Input aria-label="指标日期" label="指标日期" type="date" value={asOfDate} onChange={(event) => setAsOfDate(event.target.value)} required />
          <Input
            aria-label="目标久期（年）"
            label="目标久期（年，可选）"
            type="number"
            min="0"
            step="0.01"
            value={targetDuration}
            onChange={(event) => setTargetDuration(event.target.value)}
            placeholder="留空表示未设定"
          />
          <label className="grid gap-1 text-sm font-medium text-gray-300 sm:col-span-2">
            组合说明（可选）
            <textarea
              aria-label="组合说明"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className="rounded-lg border border-gray-600 bg-gray-900 px-3.5 py-2.5 text-sm font-normal text-white outline-none focus:border-purple-500"
              placeholder="记录研究目标、约束或适用场景"
            />
          </label>
        </div>
        <p className="rounded-lg border border-[#303034] bg-[#0d0d0d] p-3 text-[11px] leading-5 text-gray-500">
          金额按人民币万元输入，提交时转换为元。持仓权重不要求合计为 100%，剩余部分由后端计为现金。
        </p>
        {error && <p role="alert" className="text-xs leading-5 text-red-300">{error}</p>}
        <div className="flex justify-end gap-2 border-t border-gray-700 pt-4">
          <button type="button" className={secondaryButtonClass} onClick={onClose} disabled={pending}>取消</button>
          <button type="submit" className={primaryButtonClass} disabled={pending}>
            {pending ? '提交中…' : editing ? '保存设置' : '创建组合'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
