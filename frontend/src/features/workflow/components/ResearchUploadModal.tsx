import React, { useCallback, useRef, useState } from 'react'
import { Modal } from '@/components/ui'
import { API_PREFIX, request } from '@/api/client'

function formatSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

type Phase = 'select' | 'parsing' | 'review' | 'analyzing' | 'finished'

// 逐份状态：解析 → 分析中 → 完成 / 失败（重复文件单独标记）
type RowStatus =
  | 'pending' // 待解析
  | 'parsing' // 解析中
  | 'parsed' // 已解析，待分析
  | 'duplicate' // 已在库，跳过分析
  | 'failed' // 解析失败
  | 'analyzing' // AI 分析中（已提交后台）
  | 'done' // 分析已提交
  | 'analyze_failed' // 分析触发失败

interface UploadRow {
  id: string
  file: File
  status: RowStatus
  reportId?: number
  title?: string
  error?: string
}

interface UploadResult {
  report_id: number
  title: string
  status: string
  is_duplicate: boolean
}

const STATUS_TEXT: Record<RowStatus, string> = {
  pending: '待解析',
  parsing: '解析中…',
  parsed: '已解析，待分析',
  duplicate: '已在库，跳过分析',
  failed: '解析失败',
  analyzing: '分析中…',
  done: '分析已提交',
  analyze_failed: '分析触发失败',
}

function statusTone(status: RowStatus): string {
  if (status === 'done' || status === 'parsed') return 'text-green-400'
  if (status === 'duplicate') return 'text-gray-400'
  if (status === 'failed' || status === 'analyze_failed') return 'text-red-400'
  if (status === 'parsing' || status === 'analyzing') return 'text-blue-400'
  return 'text-gray-500'
}

let rowSeq = 0
function nextRowId(): string {
  rowSeq += 1
  return `upload-row-${Date.now()}-${rowSeq}`
}

interface ResearchUploadModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmitted: () => void
  variant?: 'default' | 'computer'
}

export default function ResearchUploadModal({ isOpen, onClose, onSubmitted, variant = 'default' }: ResearchUploadModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [phase, setPhase] = useState<Phase>('select')
  const [rows, setRows] = useState<UploadRow[]>([])
  const [rejectedNote, setRejectedNote] = useState('')
  const [dragOver, setDragOver] = useState(false)

  const reset = useCallback(() => {
    setPhase('select')
    setRows([])
    setRejectedNote('')
    setDragOver(false)
  }, [])

  const patchRow = useCallback((id: string, patch: Partial<UploadRow>) => {
    setRows((current) => current.map((row) => (row.id === id ? { ...row, ...patch } : row)))
  }, [])

  // 选择 / 拖入一个或多个文件：仅保留 PDF，按 文件名+大小 去重
  const addFiles = useCallback(
    (incoming: ArrayLike<File> | File[]) => {
      const files = Array.from(incoming)
      const isPdf = (file: File) => file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf'
      const rejected = files.filter((file) => !isPdf(file))
      const pdfs = files.filter(isPdf)
      setRows((current) => {
        const known = new Set(current.map((row) => `${row.file.name}|${row.file.size}`))
        const added: UploadRow[] = []
        for (const file of pdfs) {
          const key = `${file.name}|${file.size}`
          if (known.has(key)) continue
          known.add(key)
          added.push({ id: nextRowId(), file, status: 'pending' })
        }
        return [...current, ...added]
      })
      if (rejected.length > 0) {
        setRejectedNote(`已忽略非 PDF 文件：${rejected.map((file) => file.name).join('、')}（仅支持 PDF）`)
      } else {
        setRejectedNote('')
      }
    },
    [],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files)
    },
    [addFiles],
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
  }, [])

  const removeRow = useCallback((id: string) => {
    setRows((current) => current.filter((row) => row.id !== id))
  }, [])

  // 逐份上传解析（串行，避免大文件并发打爆解析服务）
  const parseRow = useCallback(
    async (row: UploadRow) => {
      patchRow(row.id, { status: 'parsing', error: undefined })
      try {
        const formData = new FormData()
        formData.append('file', row.file)
        const data = await request<UploadResult>(`${API_PREFIX}/research/upload`, {
          method: 'POST',
          body: formData,
        })
        patchRow(row.id, {
          status: data.is_duplicate ? 'duplicate' : 'parsed',
          reportId: data.report_id,
          title: data.title,
        })
      } catch (e: any) {
        patchRow(row.id, { status: 'failed', error: e?.message || '上传解析失败' })
      }
    },
    [patchRow],
  )

  const handleUploadAll = useCallback(
    async (ids?: string[]) => {
      setPhase('parsing')
      setRejectedNote('')
      // 用快照遍历，状态更新不影响本轮选择
      const targets = rows.filter((row) => (ids ? ids.includes(row.id) : row.status === 'pending' || row.status === 'failed'))
      for (const row of targets) {
        await parseRow(row)
      }
      setPhase('review')
    },
    [rows, parseRow],
  )

  // 对全部「新解析成功」的研报逐份触发 AI 分析
  const handleAnalyzeAll = useCallback(async () => {
    setPhase('analyzing')
    const targets = rows.filter((row) => row.status === 'parsed')
    for (const row of targets) {
      if (!row.reportId) continue
      patchRow(row.id, { status: 'analyzing', error: undefined })
      try {
        await request<Record<string, unknown>>(`${API_PREFIX}/research/${row.reportId}/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
        patchRow(row.id, { status: 'done' })
      } catch (e: any) {
        patchRow(row.id, { status: 'analyze_failed', error: e?.message || '分析触发失败' })
      }
    }
    setPhase('finished')
  }, [rows, patchRow])

  const handleRetryAnalyze = useCallback(
    async (row: UploadRow) => {
      if (!row.reportId) return
      patchRow(row.id, { status: 'analyzing', error: undefined })
      try {
        await request<Record<string, unknown>>(`${API_PREFIX}/research/${row.reportId}/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
        patchRow(row.id, { status: 'done' })
      } catch (e: any) {
        patchRow(row.id, { status: 'analyze_failed', error: e?.message || '分析触发失败' })
      }
    },
    [patchRow],
  )

  const handleClose = () => {
    reset()
    onClose()
  }

  const handleDone = () => {
    reset()
    onSubmitted()
  }

  const pendingCount = rows.filter((row) => row.status === 'pending' || row.status === 'failed').length
  const analyzableCount = rows.filter((row) => row.status === 'parsed').length
  const doneCount = rows.filter((row) => row.status === 'done').length
  const duplicateCount = rows.filter((row) => row.status === 'duplicate').length
  const failedFinalCount = rows.filter((row) => row.status === 'failed' || row.status === 'analyze_failed').length
  const busy = phase === 'parsing' || phase === 'analyzing'

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="上传研报 PDF" size="md" panelClassName={variant === 'computer' ? 'computer-upload-dialog' : ''} contentClassName={variant === 'computer' ? 'computer-upload-dialog-content' : ''}>
      <div className={`space-y-4 ${variant === 'computer' ? 'computer-upload-modal' : ''}`}>
        {/* ===== 选择 / 拖拽区域（解析完成后仍可继续追加） ===== */}
        {(phase === 'select' || phase === 'parsing' || phase === 'review') && (
          <>
            <div
              className={`upload-dropzone relative flex flex-col items-center justify-center py-8 px-4
                border-2 border-dashed rounded-xl cursor-pointer transition-all duration-200
                ${dragOver ? 'border-blue-400 bg-blue-500/10 scale-[1.02]' : 'border-gray-600 bg-gray-800/30 hover:border-gray-500 hover:bg-gray-800/50'}
                ${busy ? 'pointer-events-none opacity-60' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.length) addFiles(e.target.files)
                  e.target.value = ''
                }}
              />
              <div className="w-14 h-14 rounded-full bg-gray-700/50 flex items-center justify-center mb-2">
                <svg className="w-7 h-7 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <p className="text-sm text-gray-300 mb-1">拖拽一个或多个 PDF 文件到此处</p>
              <p className="text-xs text-gray-500">或点击此区域浏览多选</p>
            </div>

            {rejectedNote && <p className="text-xs text-amber-400">{rejectedNote}</p>}

            {/* ===== 操作按钮 ===== */}
            {phase === 'select' && pendingCount > 0 && (
              <button
                onClick={() => void handleUploadAll()}
                className="w-full py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-500 transition-colors"
              >
                上传并解析（{pendingCount} 份）
              </button>
            )}

            {phase === 'parsing' && (
              <div className="flex items-center justify-center gap-2 py-2 text-sm text-blue-400">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                正在逐份上传解析…
              </div>
            )}

            {phase === 'review' && (
              <div className="space-y-2">
                <button
                  onClick={() => void handleAnalyzeAll()}
                  disabled={analyzableCount === 0}
                  className="w-full py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium
                             hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  开始 AI 分析（{analyzableCount} 份新增）
                </button>
                <button
                  onClick={() => setPhase('select')}
                  className="w-full py-2 rounded-lg bg-gray-700/50 text-gray-300 text-sm hover:bg-gray-700 transition-colors"
                >
                  继续添加文件
                </button>
                <p className="text-[11px] text-gray-600 text-center">
                  AI 分析在后台执行，每份约 30-120 秒，可在研报库中查看进度；重复文件不会重复分析。
                </p>
              </div>
            )}
          </>
        )}

        {/* ===== 逐份进度清单（各阶段常驻；失败可在结束后行内重试） ===== */}
        {rows.length > 0 && (
          <ul className="upload-row-list space-y-2 max-h-64 overflow-y-auto pr-1">
            {rows.map((row) => (
              <li key={row.id} className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-800/40 border border-gray-700/50">
                <svg className="w-5 h-5 text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200 truncate">{row.title || row.file.name}</p>
                  <p className="text-[11px] text-gray-500">{formatSize(Math.round(row.file.size / 1024))}</p>
                  {row.error && <p className="text-[11px] text-red-400/80 truncate">{row.error}</p>}
                </div>
                <span className={`text-xs flex-shrink-0 ${statusTone(row.status)}`}>
                  {(row.status === 'parsing' || row.status === 'analyzing') && (
                    <svg className="inline w-3.5 h-3.5 animate-spin mr-1 -mt-0.5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  )}
                  {STATUS_TEXT[row.status]}
                </span>
                {row.status === 'failed' && (phase === 'review' || phase === 'finished') && (
                  <button type="button" className="text-xs text-blue-400 hover:text-blue-300 flex-shrink-0" onClick={() => void handleUploadAll([row.id])}>
                    重试
                  </button>
                )}
                {row.status === 'analyze_failed' && (
                  <button type="button" className="text-xs text-blue-400 hover:text-blue-300 flex-shrink-0" onClick={() => void handleRetryAnalyze(row)}>
                    重试
                  </button>
                )}
                {row.status === 'pending' && phase === 'select' && (
                  <button
                    type="button"
                    className="text-xs text-gray-500 hover:text-gray-300 flex-shrink-0"
                    onClick={() => removeRow(row.id)}
                  >
                    移除
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {phase === 'analyzing' && (
          <div className="flex items-center justify-center gap-2 py-4 text-sm text-blue-400">
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            正在逐份提交 AI 分析…
          </div>
        )}

        {/* ===== 最终汇总 ===== */}
        {phase === 'finished' && (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <svg className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <div>
                <p className="text-sm font-medium text-blue-400 mb-1">批量入库完成</p>
                <p className="text-xs text-gray-400">
                  {[doneCount > 0 && `成功 ${doneCount} 份`, duplicateCount > 0 && `已在库 ${duplicateCount} 份`, failedFinalCount > 0 && `失败 ${failedFinalCount} 份`]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
                <p className="text-[11px] text-gray-500 mt-1">分析在后台继续执行，完成后结果会出现在研报库中。</p>
              </div>
            </div>
            <button
              onClick={handleDone}
              className="w-full py-2.5 rounded-lg bg-gray-700 text-gray-300 text-sm hover:bg-gray-600 transition-colors"
            >
              完成
            </button>
          </div>
        )}
      </div>
    </Modal>
  )
}
