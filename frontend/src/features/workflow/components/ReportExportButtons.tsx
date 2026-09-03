import { useState } from 'react'
import { ReportGenerationTask } from '@/api/reportGeneration'
import { storage } from '@/utils/helpers'

type Props = { task: ReportGenerationTask; onError: (message: string) => void }

export function ReportExportButtons({ task, onError }: Props) {
  const [format, setFormat] = useState<'pdf' | 'docx' | null>(null)
  if (task.status !== 'completed') return null

  async function download(nextFormat: 'pdf' | 'docx') {
    setFormat(nextFormat)
    onError('')
    try {
      const token = storage.get<string>('auth_token')
      const response = await fetch(`/sapi/report-generation/tasks/${task.id}/export?format=${nextFormat}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        throw new Error(payload?.detail || '导出失败')
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${task.title}.${nextFormat}`
      link.click()
      URL.revokeObjectURL(url)
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : '导出失败')
    } finally {
      setFormat(null)
    }
  }

  return <div className="report-export-actions">
    <button className="computer-button" disabled={format !== null} onClick={() => void download('docx')}>{format === 'docx' ? '正在生成 DOCX…' : '导出 DOCX'}</button>
    <button className="computer-button primary" disabled={format !== null} onClick={() => void download('pdf')}>{format === 'pdf' ? '正在生成 PDF…' : '导出 PDF'}</button>
  </div>
}
