import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Button from './Button'

describe('Button', () => {
  it('渲染 children', () => {
    render(<Button>保存</Button>)
    expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument()
  })

  it('loading 时禁用并显示 spinner', () => {
    render(<Button loading>保存中</Button>)
    const btn = screen.getByRole('button', { name: /保存中/ })
    expect(btn).toBeDisabled()
    expect(btn.querySelector('svg')).not.toBeNull()
  })

  it('disabled 透传到原生按钮', () => {
    render(<Button disabled>禁用</Button>)
    expect(screen.getByRole('button', { name: '禁用' })).toBeDisabled()
  })

  it('渲染 icon 并触发点击', async () => {
    const onClick = vi.fn()
    render(
      <Button icon={<span data-testid="ico">i</span>} onClick={onClick}>
        带图标
      </Button>,
    )
    expect(screen.getByTestId('ico')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /带图标/ }))
    expect(onClick).toHaveBeenCalled()
  })
})