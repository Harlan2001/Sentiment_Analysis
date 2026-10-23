import React, { useCallback, useRef, useState } from 'react'
import { Modal } from '@/components/ui'
import { API_PREFIX, request } from '@/api/client'

/**
 * 政策文件上传弹窗。
 *
 * 与研报上传（ResearchUploadModal）保持同一交互风格（拖拽 + 分步状态），
 * 但**上传后直接触发 AI 解读** —— 政策文件通常只有一份，
 * 不像研报需要"先攒一批再合成"，省掉一次手动点击。
 */

type Step = 'select' | 'uploading' | 'analyzing' | 'submitted' | 'error'

interface UploadResult {
  document_id: number
  title: string
  status: string
  is_duplicate: boolean
  issuer?: string | null
  document_no?: string | null
  publish_date?: string | null
  page_count?: number
  warnings?: string[]
}

interface PolicyUploadModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmitted: () => void
  variant?: 'default' | 'computer'
}

export default function PolicyUploadModal({
  isOpen,
  onClose,
  onSubmitted,
  variant = 'default',
}: PolicyUploadModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [step, setStep] = useState<Step>('select')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [dragOver, setDragOver] = useState(false)

  const reset = useCallback(() => {
    setStep('select')
    setSelectedFile(null)
    setResult(null)
    setErrorMsg('')
    setDragOver(false)
  }, [])

  const handleFileSelect = useCallback((file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setErrorMsg('仅支持 PDF 格式（政策文件若为 Word，请先导出为 PDF）')
      setStep('error')
      return
    }
    setSelectedFile(file)
    setErrorMsg('')
    setResult(null)
    setStep('select')
  }, [])

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      setDragOver(false)
      const file = event.dataTransfer.files[0]
      if (file) handleFileSelect(file)
    },
    [handleFileSelect],
  )

  const handleUpload = async () => {
    if (!selectedFile) return
    setStep('uploading')
    setErrorMsg('')
    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      // 后端在上传成功后会立即在后台启动分析
      const data = await request<UploadResult>(`${API_PREFIX}/policy-documents/upload`, {
        method: 'POST',
        body: formData,
      })
      setResult(data)
      setStep('analyzing')
      // 给后台分析留出时间后进入完成态（分析在服务端异步进行）
      setTimeout(() => setStep('submitted'), 1200)
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : '上传失败，请重试')
      setStep('error')
    }
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const handleDone = () => {
    reset()
    onSubmitted()
  }

  const busy = step === 'uploading' || step === 'analyzing'

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="上传政策文件 PDF"
      size="md"
      panelClassName={variant === 'computer' ? 'computer-upload-dialog' : ''}
      contentClassName={variant === 'computer' ? 'computer-upload-dialog-content' : ''}
    >
      <div className={`space-y-4 ${variant === 'computer' ? 'computer-upload-modal' : ''}`}>
        {(step === 'select' || step === 'uploading' || step === 'error') && (
          <>
            <div
              onClick={() => fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={(e) => {
                e.preventDefault()
                setDragOver(true)
              }}
              onDragLeave={(e) => {
                e.preventDefault()
                setDragOver(false)
              }}
              className={`relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-10 transition-all duration-200 ${
                dragOver
                  ? 'border-blue-400 bg-blue-500/10'
                  : selectedFile
                    ? 'border-blue-500/50 bg-blue-500/5'
                    : 'border-gray-600 bg-gray-800/30 hover:border-gray-500 hover:bg-gray-800/50'
              } ${busy ? 'pointer-events-none opacity-60' : 'cursor-pointer'}`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) handleFileSelect(file)
                }}
              />
              <svg
                className="mb-3 h-12 w-12 text-blue-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              {selectedFile ? (
                <>
                  <p className="text-sm text-gray-200">{selectedFile.name}</p>
                  <p className="mt-1 text-xs text-gray-500">
                    {(selectedFile.size / 1024).toFixed(0)} KB · 点击可重新选择
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm text-gray-300">拖拽 PDF 到此处，或点击选择</p>
                  <p className="mt-1 text-xs text-gray-500">仅支持文本型 PDF，单文件 ≤ 20MB</p>
                </>
              )}
            </div>

            {errorMsg && (
              <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {errorMsg}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <button
                onClick={handleClose}
                className="rounded-lg border border-[#3d3d42] px-3 py-2 text-xs text-gray-300 hover:bg-[#1b1b1d]"
              >
                取消
              </button>
              <button
                onClick={handleUpload}
                disabled={!selectedFile || busy}
                className="rounded-lg bg-white px-3 py-2 text-xs font-medium text-black hover:bg-gray-200 disabled:opacity-40"
              >
                {step === 'uploading' ? '上传解析中…' : '上传并解读'}
              </button>
            </div>
          </>
        )}

        {busy && step === 'analyzing' && (
          <div className="flex flex-col items-center py-8">
            <div className="mb-3 h-8 w-8 animate-spin rounded-full border-2 border-gray-600 border-t-blue-400" />
            <p className="text-sm text-gray-300">AI 正在解读政策文件…</p>
            <p className="mt-1 text-xs text-gray-500">解析要点、判断对债市的影响方向</p>
          </div>
        )}

        {step === 'submitted' && result && (
          <>
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
              <p className="text-sm font-medium text-emerald-300">上传成功，解读已启动</p>
              <dl className="mt-3 space-y-1.5 text-xs">
                <div className="flex gap-2">
                  <dt className="w-16 shrink-0 text-gray-500">标题</dt>
                  <dd className="text-gray-300">{result.title}</dd>
                </div>
                {result.issuer && (
                  <div className="flex gap-2">
                    <dt className="w-16 shrink-0 text-gray-500">发文机关</dt>
                    <dd className="text-gray-300">{result.issuer}</dd>
                  </div>
                )}
                {result.document_no && (
                  <div className="flex gap-2">
                    <dt className="w-16 shrink-0 text-gray-500">文号</dt>
                    <dd className="text-gray-300">{result.document_no}</dd>
                  </div>
                )}
                {result.page_count ? (
                  <div className="flex gap-2">
                    <dt className="w-16 shrink-0 text-gray-500">页数</dt>
                    <dd className="text-gray-300">{result.page_count}</dd>
                  </div>
                ) : null}
              </dl>
              {result.is_duplicate && (
                <p className="mt-3 text-xs text-amber-300">
                  该文件此前已上传过，直接使用已有记录。
                </p>
              )}
            </div>

            {result.warnings?.length ? (
              <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                {result.warnings.join('；')}
              </p>
            ) : null}

            <div className="flex justify-end gap-2">
              <button
                onClick={handleDone}
                className="rounded-lg bg-white px-3 py-2 text-xs font-medium text-black hover:bg-gray-200"
              >
                查看解读结果
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}