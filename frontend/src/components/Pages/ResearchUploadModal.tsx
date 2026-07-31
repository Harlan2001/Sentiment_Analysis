import React, { useRef, useState, useCallback } from 'react'
import { Modal } from '../UI'
import { API_PREFIX } from '../../constants'
import { storage } from '../../utils/helpers'

function authHeaders(): Record<string, string> {
  const token = storage.get<string>('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function formatSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

type Step = 'select' | 'uploading' | 'parsed' | 'analyzing' | 'submitted' | 'error'

interface UploadResult {
  report_id: number
  title: string
  status: string
  is_duplicate: boolean
}

interface ResearchUploadModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmitted: () => void
}

export default function ResearchUploadModal({
  isOpen,
  onClose,
  onSubmitted,
}: ResearchUploadModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [step, setStep] = useState<Step>('select')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [dragOver, setDragOver] = useState(false)

  // 重置状态
  const reset = useCallback(() => {
    setStep('select')
    setSelectedFile(null)
    setUploadResult(null)
    setErrorMsg('')
    setDragOver(false)
  }, [])

  // 选择文件
  const handleFileSelect = useCallback((file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setErrorMsg('仅支持 PDF 格式的文件')
      setStep('error')
      return
    }
    setSelectedFile(file)
    setErrorMsg('')
    setUploadResult(null)
    setStep('select')
  }, [])

  // 拖拽事件
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFileSelect(file)
  }, [handleFileSelect])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
  }, [])

  // 上传并解析
  const handleUpload = async () => {
    if (!selectedFile) return
    setStep('uploading')
    setErrorMsg('')

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const resp = await fetch(`${API_PREFIX}/research/upload`, {
        method: 'POST',
        headers: authHeaders(),
        body: formData,
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: '上传失败' }))
        throw new Error(err.detail || `服务器错误 (${resp.status})`)
      }

      const data: UploadResult = await resp.json()
      setUploadResult(data)
      setStep('parsed')
    } catch (e: any) {
      setErrorMsg(e.message || '上传失败，请重试')
      setStep('error')
    }
  }

  // 触发 AI 分析
  const handleAnalyze = async () => {
    if (!uploadResult) return
    setStep('analyzing')
    setErrorMsg('')

    try {
      const resp = await fetch(`${API_PREFIX}/research/${uploadResult.report_id}/analyze`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: '分析触发失败' }))
        throw new Error(err.detail || `服务器错误 (${resp.status})`)
      }

      setStep('submitted')
    } catch (e: any) {
      setErrorMsg(e.message || '分析触发失败，请重试')
      setStep('error')
    }
  }

  // 关闭
  const handleClose = () => {
    reset()
    onClose()
  }

  // 完成并查看列表
  const handleDone = () => {
    reset()
    onSubmitted()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="上传研报 PDF"
      size="md"
    >
      <div className="space-y-4">
        {/* ===== 状态 1：选择文件 ===== */}
        {(step === 'select' || step === 'uploading' || step === 'error') && (
          <>
            {/* 拖拽区域 */}
            <div
              onClick={() => fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={`
                relative flex flex-col items-center justify-center py-10 px-4
                border-2 border-dashed rounded-xl cursor-pointer
                transition-all duration-200
                ${dragOver
                  ? 'border-blue-400 bg-blue-500/10 scale-[1.02]'
                  : selectedFile
                    ? 'border-blue-500/50 bg-blue-500/5'
                    : 'border-gray-600 bg-gray-800/30 hover:border-gray-500 hover:bg-gray-800/50'
                }
                ${step === 'uploading' ? 'pointer-events-none opacity-60' : ''}
              `}
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

              {/* 图标 */}
              {selectedFile ? (
                <>
                  <svg className="w-12 h-12 text-red-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  <p className="text-sm font-medium text-gray-200 mb-1">
                    {selectedFile.name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {formatSize(Math.round(selectedFile.size / 1024))}
                  </p>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedFile(null)
                      setUploadResult(null)
                    }}
                    className="mt-2 text-xs text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    移除，重新选择
                  </button>
                </>
              ) : (
                <>
                  <div className="w-16 h-16 rounded-full bg-gray-700/50 flex items-center justify-center mb-3">
                    <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                  </div>
                  <p className="text-sm text-gray-300 mb-1">
                    拖拽 PDF 文件到此处
                  </p>
                  <p className="text-xs text-gray-500">
                    或点击此区域浏览选择
                  </p>
                </>
              )}
            </div>

            {/* 上传按钮 */}
            {!selectedFile && (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full py-2.5 rounded-lg bg-gray-700/50 text-gray-300 text-sm
                           hover:bg-gray-700 transition-colors"
              >
                选择文件
              </button>
            )}

            {selectedFile && step !== 'uploading' && (
              <button
                onClick={handleUpload}
                className="w-full py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium
                           hover:bg-blue-500 transition-colors flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                上传并解析
              </button>
            )}

            {/* 上传中 */}
            {step === 'uploading' && (
              <div className="flex items-center justify-center gap-2 py-3 text-sm text-blue-400">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                正在上传并解析 PDF...
              </div>
            )}
          </>
        )}

        {/* ===== 状态 2：解析完成，等待触发分析 ===== */}
        {(step === 'parsed' || step === 'analyzing') && (
          <div className="space-y-4">
            {/* 成功提示 */}
            <div className="flex items-start gap-3 p-4 rounded-lg bg-green-500/10 border border-green-500/20">
              <svg className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <div>
                <p className="text-sm font-medium text-green-400 mb-0.5">
                  {uploadResult?.is_duplicate ? '该文件已存在' : 'PDF 解析完成'}
                </p>
                {uploadResult?.title && (
                  <p className="text-xs text-gray-400 line-clamp-2">{uploadResult.title}</p>
                )}
              </div>
            </div>

            {/* 触发分析 */}
            <button
              onClick={handleAnalyze}
              disabled={step === 'analyzing'}
              className="w-full py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium
                         hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed
                         transition-colors flex items-center justify-center gap-2"
            >
              {step === 'analyzing' ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  正在提交分析任务...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  开始 AI 分析
                </>
              )}
            </button>

            <p className="text-[11px] text-gray-600 text-center">
              AI 分析将在后台执行，预计需要 30-120 秒，可在列表中查看进度
            </p>
          </div>
        )}

        {/* ===== 状态 3：分析已提交 ===== */}
        {step === 'submitted' && (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <svg className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <div>
                <p className="text-sm font-medium text-blue-400 mb-0.5">分析任务已提交</p>
                <p className="text-xs text-gray-400">
                  研报正在后台进行 AI 分析，完成后将在列表中显示结果。您可以先浏览其他研报。
                </p>
              </div>
            </div>

            <button
              onClick={handleDone}
              className="w-full py-2.5 rounded-lg bg-gray-700 text-gray-300 text-sm
                         hover:bg-gray-600 transition-colors"
            >
              查看列表
            </button>
          </div>
        )}

        {/* ===== 错误状态 ===== */}
        {step === 'error' && errorMsg && (
          <div className="flex items-start gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
            <svg className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm font-medium text-red-400 mb-0.5">操作失败</p>
              <p className="text-xs text-red-300/80">{errorMsg}</p>
              <button
                onClick={() => {
                  setStep('select')
                  setErrorMsg('')
                }}
                className="mt-2 text-xs text-red-400 hover:text-red-300 underline transition-colors"
              >
                重新选择文件
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}
