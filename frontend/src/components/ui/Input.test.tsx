import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Input } from './Input'

describe('Input', () => {
  it('渲染输入框与占位符', () => {
    render(<Input placeholder="请输入" />)
    expect(screen.getByPlaceholderText('请输入')).toBeInTheDocument()
  })

  it('渲染 label', () => {
    render(<Input label="用户名" />)
    expect(screen.getByText('用户名')).toBeInTheDocument()
  })

  it('error 时显示错误且不显示 helperText', () => {
    render(<Input error="格式错误" helperText="提示" />)
    expect(screen.getByText('格式错误')).toBeInTheDocument()
    expect(screen.queryByText('提示')).not.toBeInTheDocument()
  })

  it('无 error 时显示 helperText', () => {
    render(<Input helperText="辅助说明" />)
    expect(screen.getByText('辅助说明')).toBeInTheDocument()
  })

  it('渲染 icon', () => {
    render(<Input icon={<span data-testid="ic">@</span>} />)
    expect(screen.getByTestId('ic')).toBeInTheDocument()
  })
})