import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '@/components/ui'
import { isPortfolioConflict, type PortfolioImportResult } from '@/api/portfolio'
import { errorMessage, primaryButtonClass, secondaryButtonClass } from './common'

type Props = {
  isOpen: boolean
  onClose: () => void
  onSubmit: (file: File, mode: 'append' | 'replace') => Promise<PortfolioImportResult>
  onSuccess: (result: PortfolioImportResult) => void
}

export function ImportHoldingsModal({ isOpen, onClose, onSubmit, onSuccess }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [mode, setMode] = useState<'append' | 'replace'>('append')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<PortfolioImportResult | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setFile(null)
    setMode('append')
    setPending(false)
    setError('')
    setResult(null)
  }, [isOpen])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!file) return setError('请选择 CSV 文件。')
    setPending(true)
    setError('')
    setResult(null)
    try {
      const response = await onSubmit(file, mode)
      setResult(response)
      onSuccess(response)
    } catch (reason) {
      setError(
        isPortfolioConflict(reason)
          ? '组合版本冲突，请关闭弹窗并刷新组合后重新导入。'
          : errorMessage(reason, 'CSV 导入失败'),
      )
    } finally {
      setPending(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={() => { if (!pending) onClose() }} title="导入 CSV 持仓" size="lg">
      <form className="space-y-4 text-left" onSubmit={handleSubmit}>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="grid gap-2 text-sm text-gray-300">
            CSV 文件
            <input
              aria-label="CSV 文件"
              type="file"
              accept=".csv,text/csv"
              className="block w-full rounded-lg border border-gray-600 bg-gray-900 p-2 text-xs text-gray-300 file:mr-3 file:rounded file:border-0 file:bg-gray-700 file:px-3 file:py-2 file:text-gray-100"
              onChange={(event) => { setFile(event.target.files?.[0] ?? null); setResult(null); setError('') }}
            />
          </label>
          <fieldset>
            <legend className="text-sm text-gray-300">导入方式</legend>
            <div className="mt-2 flex gap-4 text-xs text-gray-300">
              <label className="flex items-center gap-2"><input type="radio" name="import-mode" value="append" checked={mode === 'append'} onChange={() => setMode('append')} />追加到现有持仓</label>
              <label className="flex items-center gap-2"><input type="radio" name="import-mode" value="replace" checked={mode === 'replace'} onChange={() => setMode('replace')} />替换全部持仓</label>
            </div>
          </fieldset>
        </div>
        <div className="rounded-lg border border-[#303034] bg-[#0d0d0d] p-3 text-[11px] leading-5 text-gray-500">
          <p>字段：bond_code、bond_name、asset_category、weight_pct、yield_pct、duration_years、note。</p>
          <p>权重使用百分数。任一数据行有误时整批不写入；替换模式也遵循这一规则。</p>
        </div>
        {error && <p role="alert" className="text-xs leading-5 text-red-300">{error}</p>}

        {result && result.errors.length > 0 && (
          <div className="space-y-3">
            <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-200">
              导入未执行：发现 {result.errors.length} 个错误，整批持仓均未写入。请修正后重新上传。
            </div>
            <div className="max-h-64 overflow-auto rounded-lg border border-[#303034]">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#0d0d0d] text-gray-400"><tr><th className="px-3 py-2">行号</th><th className="px-3 py-2">字段</th><th className="px-3 py-2">错误说明</th></tr></thead>
                <tbody className="divide-y divide-[#252529]">
                  {result.errors.map((item, index) => <tr key={`${item.row}-${item.field}-${index}`}><td className="px-3 py-2 font-mono text-gray-300">{item.row}</td><td className="px-3 py-2 font-mono text-gray-400">{item.field || '—'}</td><td className="px-3 py-2 text-red-200">{item.message}</td></tr>)}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {result && result.errors.length === 0 && (
          <div role="status" className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-200">
            成功导入 {result.imported_count} 条持仓，组合指标已更新。
          </div>
        )}

        <div className="flex justify-end gap-2 border-t border-gray-700 pt-4">
          <button type="button" className={secondaryButtonClass} onClick={onClose} disabled={pending}>{result?.errors.length === 0 ? '完成' : '取消'}</button>
          <button type="submit" className={primaryButtonClass} disabled={pending || !file}>{pending ? '导入中…' : result ? '重新导入' : '开始导入'}</button>
        </div>
      </form>
    </Modal>
  )
}
