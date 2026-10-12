import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * 上传弹窗测试（TDD，对应 docs/PRD-研报分析功能细化.md P2-9 批量上传）
 * - 多选 / 多文件拖拽
 * - 逐份显示「解析 → 分析中 → 完成/失败」进度
 * - 去重清单：is_duplicate 的文件标记「已在库」且不再触发分析
 */

vi.mock('@/api/client', () => ({
  API_PREFIX: '/sapi',
  request: vi.fn(),
}))
vi.mock('@/components/ui', () => ({
  Modal: ({ isOpen, title, children }: { isOpen: boolean; title: string; children: React.ReactNode }) =>
    isOpen ? (
      <div role="dialog" aria-label={title}>
        {children}
      </div>
    ) : null,
}))

import { request } from '@/api/client'
import ResearchUploadModal from './ResearchUploadModal'

const requestMock = vi.mocked(request)

function pdfFile(name: string): File {
  return new File(['pdf-bytes'], name, { type: 'application/pdf' })
}

function fileInput(container: HTMLElement): HTMLInputElement {
  const input = container.querySelector('input[type="file"]')
  if (!input) throw new Error('file input not found')
  return input as HTMLInputElement
}

/** 从 FormData 中取出当前上传的文件名，供 mock 按文件区分结果 */
async function uploadFileName(options: { body?: BodyInit }): Promise<string> {
  const form = options.body as FormData
  return (form.get('file') as File).name
}

function renderModal() {
  const onSubmitted = vi.fn()
  const utils = render(<ResearchUploadModal isOpen onClose={vi.fn()} onSubmitted={onSubmitted} />)
  return { ...utils, onSubmitted }
}

beforeEach(() => {
  let seq = 0
  requestMock.mockImplementation(async (url: string, options) => {
    if (url.includes('/research/upload')) {
      const name = await uploadFileName(options as { body?: BodyInit })
      if (name.includes('损坏')) throw new Error('PDF 解析失败')
      seq += 1
      return {
        report_id: 100 + seq,
        title: `研报 ${seq}`,
        status: 'parsed',
        is_duplicate: name.includes('重复'),
      } as never
    }
    return { status: 'processing' } as never
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ResearchUploadModal · P2-9 批量上传', () => {
  it('一次选择多个 PDF，逐份列出并显示待解析数量', () => {
    const { container } = renderModal()
    fireEvent.change(fileInput(container), {
      target: { files: [pdfFile('a.pdf'), pdfFile('b.pdf')] },
    })

    expect(screen.getByText('a.pdf')).toBeInTheDocument()
    expect(screen.getByText('b.pdf')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /上传并解析（\s*2\s*份）/ })).toBeInTheDocument()
  })

  it('支持多文件拖拽', () => {
    const { container } = renderModal()
    fireEvent.drop(container.querySelector('.upload-dropzone') as HTMLElement, {
      dataTransfer: { files: [pdfFile('c.pdf'), pdfFile('d.pdf')] },
    })

    expect(screen.getByText('c.pdf')).toBeInTheDocument()
    expect(screen.getByText('d.pdf')).toBeInTheDocument()
  })

  it('非 PDF 文件被忽略并提示', () => {
    const { container } = renderModal()
    fireEvent.change(fileInput(container), {
      target: { files: [pdfFile('ok.pdf'), new File(['x'], 'notes.txt', { type: 'text/plain' })] },
    })

    expect(screen.getByText('ok.pdf')).toBeInTheDocument()
    expect(screen.queryByText('notes.txt')).not.toBeInTheDocument()
    expect(screen.getByText(/仅支持 PDF/)).toBeInTheDocument()
  })

  it('逐份解析后批量触发分析，重复文件标记已在库且不重复分析', async () => {
    const { container, onSubmitted } = renderModal()
    fireEvent.change(fileInput(container), {
      target: { files: [pdfFile('新研报.pdf'), pdfFile('重复研报.pdf')] },
    })

    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }))

    // 两份都完成解析：新文件待分析，重复文件进入去重清单
    await waitFor(() => expect(screen.getByText('已解析，待分析')).toBeInTheDocument())
    expect(screen.getByText('已在库，跳过分析')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /开始 AI 分析/ }))

    await waitFor(() => expect(screen.getByText('分析已提交')).toBeInTheDocument())

    const analyzeUrls = requestMock.mock.calls
      .map(([url]) => String(url))
      .filter((url) => url.includes('/analyze'))
    expect(analyzeUrls).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: /完成/ }))
    expect(onSubmitted).toHaveBeenCalledTimes(1)
  })

  it('单份解析失败不影响其余文件，最终汇总成功与失败', async () => {
    const { container } = renderModal()
    fireEvent.change(fileInput(container), {
      target: { files: [pdfFile('正常研报.pdf'), pdfFile('损坏研报.pdf')] },
    })

    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }))

    await waitFor(() => {
      expect(screen.getByText('已解析，待分析')).toBeInTheDocument()
      // 状态标签精确匹配（行内另有错误详情「PDF 解析失败」）
      expect(screen.getByText('解析失败')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /开始 AI 分析/ }))
    await waitFor(() => expect(screen.getByText('分析已提交')).toBeInTheDocument())

    // 汇总会同时给出成功与失败数量
    expect(screen.getByText(/成功 1 份/)).toBeInTheDocument()
    expect(screen.getByText(/失败 1 份/)).toBeInTheDocument()
  })
})
