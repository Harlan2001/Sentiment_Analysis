import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Modal from './Modal'

describe('Modal', () => {
  it('isOpen 时渲染标题与内容', () => {
    render(
      <Modal isOpen title="弹窗标题" onClose={vi.fn()}>
        内容文字
      </Modal>,
    )
    expect(screen.getByText('弹窗标题')).toBeInTheDocument()
    expect(screen.getByText('内容文字')).toBeInTheDocument()
  })

  it('isOpen=false 不渲染内容', () => {
    render(
      <Modal isOpen={false} title="标题" onClose={vi.fn()}>
        不应出现
      </Modal>,
    )
    expect(screen.queryByText('不应出现')).not.toBeInTheDocument()
  })

  it('点击关闭按钮触发 onClose', async () => {
    const onClose = vi.fn()
    render(
      <Modal isOpen onClose={onClose}>
        内容
      </Modal>,
    )
    const closeButtons = screen.getAllByRole('button')
    await userEvent.click(closeButtons[0])
    expect(onClose).toHaveBeenCalled()
  })
})