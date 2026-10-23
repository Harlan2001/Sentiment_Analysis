import { useEffect, useMemo, useState } from 'react'
import { Modal } from '@/components/ui'
import {
  ReportGenerationTask,
  ResearchListItem,
  createReportGenerationTask,
} from '@/api/reportGeneration'

const MODEL_OPTIONS = [
  { value: 'glm', label: 'GLM（默认）' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: 'Qwen' },
  { value: 'kimi', label: 'Kimi' },
]

const fieldClass =
  'w-full rounded-lg border border-gray-600 bg-gray-800/80 px-3 py-2 text-sm text-gray-200 ' +
  'placeholder:text-gray-500 outline-none focus:border-blue-500 transition-colors'

type Props = {
  open: boolean
  items: ResearchListItem[]
  loading: boolean
  dateStart?: string
  dateEnd?: string
  onClose: () => void
  onCreated: (task: ReportGenerationTask) => void
}

/**
 * 板块三：多步「新建综合研报」弹窗 —— 选来源 → 填标题与分析重点 → 提交。
 * 替代旧版底部聊天式 composer（旧 composer 的已选状态无入口设置，链路是断的）。
 */
export function ReportCreateModal({ open, items, loading, dateStart, dateEnd, onClose, onCreated }: Props) {
  const [title, setTitle] = useState('')
  const [requirement, setRequirement] = useState('')
  const [model, setModel] = useState('glm')
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [keyword, setKeyword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) {
      setTitle(''); setRequirement(''); setModel('glm'); setSelectedIds([])
      setKeyword(''); setSubmitting(false); setError('')
    }
  }, [open])

  const selectable = useMemo(
    () => items.filter((item) => item.status === 'analyzed'),
    [items],
  )
  const visibleItems = useMemo(() => {
    const word = keyword.trim()
    if (!word) return selectable
    return selectable.filter((item) => `${item.title}${item.institution ?? ''}${item.industry ?? ''}`.includes(word))
  }, [selectable, keyword])

  if (!open) return null

  function toggle(id: number) {
    setSelectedIds((current) => (
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    ))
  }

  async function submit() {
    if (!title.trim()) return setError('请输入报告标题')
    if (!requirement.trim()) return setError('请填写分析重点')
    if (selectedIds.length === 0) return setError('请至少勾选一份已完成分析的研报')
    setSubmitting(true)
    setError('')
    try {
      const task = await createReportGenerationTask({
        title: title.trim(),
        requirement: requirement.trim(),
        report_ids: selectedIds,
        date_start: dateStart || undefined,
        date_end: dateEnd || undefined,
        model,
      })
      onCreated(task)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '创建研报生成任务失败')
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen={open} onClose={onClose} title="新建综合研报" size="lg">
      <div className="space-y-5">
        {/* 第一步：选择来源 */}
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <strong className="text-sm text-gray-200">
              1. 选择来源研报（{selectedIds.length}/{selectable.length} 可选）
            </strong>
            <span className="report-create-count text-xs text-gray-500">已选 {selectedIds.length} 份来源</span>
          </div>
          <input
            className={fieldClass}
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="输入机构或行业筛选来源"
          />
          <div className="report-create-source-list max-h-60 overflow-y-auto rounded-lg border border-gray-700/60 divide-y divide-gray-700/40">
            {loading
              ? <div className="px-3 py-6 text-center text-sm text-gray-500">正在读取研报库…</div>
              : visibleItems.length === 0
                ? <div className="px-3 py-6 text-center text-sm text-gray-500">当前条件下没有已完成分析的研报。</div>
                : visibleItems.map((item) => (
                  <label key={item.id} className="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-gray-800/60">
                    <input
                      type="checkbox"
                      className="h-4 w-4 flex-shrink-0 accent-blue-600"
                      checked={selectedIds.includes(item.id)}
                      onChange={() => toggle(item.id)}
                    />
                    <span className="min-w-0">
                      <strong className="block truncate text-sm text-gray-200">{item.title}</strong>
                      <small className="block truncate text-xs text-gray-500">
                        {item.institution || '未知机构'} · {item.publish_date || '日期未知'} · {item.industry || item.report_type || '未分类'}
                      </small>
                    </span>
                  </label>
                ))}
          </div>
        </section>

        {/* 第二步：填写要求 */}
        <section className="space-y-2">
          <strong className="block text-sm text-gray-200">2. 填写报告要求</strong>
          <input
            className={fieldClass}
            value={title}
            onChange={(event) => setTitle(event.target.value.replace(/[\r\n]+/g, ' '))}
            maxLength={255}
            placeholder="报告标题，例如：1 月利率债市场观点综述"
          />
          <textarea
            className={`${fieldClass} resize-y`}
            value={requirement}
            onChange={(event) => setRequirement(event.target.value)}
            maxLength={4000}
            rows={4}
            placeholder="分析重点：希望比较的问题、目标读者、输出侧重…"
          />
          <label className="flex items-center gap-3 text-sm text-gray-300">
            分析模型
            <select
              className={`${fieldClass} w-auto`}
              value={model}
              onChange={(event) => setModel(event.target.value)}
            >
              {MODEL_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
        </section>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="report-create-actions flex justify-end gap-3 border-t border-gray-700/60 pt-4">
          <button
            type="button"
            className="rounded-lg px-4 py-2 text-sm text-gray-300 bg-gray-700/60 hover:bg-gray-700 transition-colors"
            onClick={onClose}
          >
            取消
          </button>
          <button
            type="button"
            className="rounded-lg px-5 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-500
                       disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            disabled={submitting}
            onClick={() => void submit()}
          >
            {submitting ? '提交中…' : '开始生成'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
