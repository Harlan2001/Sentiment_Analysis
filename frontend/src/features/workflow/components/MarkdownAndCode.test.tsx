import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CodeHighlight } from '@/features/workflow/components/CodeHighlight'
import { StrategySummary } from '@/features/workflow/components/StrategySummary'

afterEach(cleanup)

describe('StrategySummary', () => {
  const markdown = `## 策略概要

**标的与周期**：FCT_T_MAIN，日频

**技术信号**
- 开多：5 日均线上穿 20 日均线
- 平多：死叉或止损 1.5%
`

  it('splits the summary into titled sections', () => {
    const { container } = render(<StrategySummary markdown={markdown} />)
    const headers = Array.from(container.querySelectorAll('.sf-summary-section h4')).map(
      (el) => el.textContent,
    )
    expect(headers).toContain('标的与周期')
    expect(headers).toContain('技术信号')
  })

  it('strips markdown emphasis markers in structured view', () => {
    render(<StrategySummary markdown={markdown} />)
    // 结构化视图不该出现 ** 之类的记号
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument()
    expect(screen.getByText(/5 日均线上穿 20 日均线/)).toBeInTheDocument()
  })

  it('falls back to markdown when nothing can be structured', () => {
    const { container } = render(
      <StrategySummary markdown="这是一段没有任何标题的说明文字。" />,
    )
    expect(container.querySelector('.sf-summary-markdown')).toBeTruthy()
  })

  it('does not repeat the module title 策略概要', () => {
    const { container } = render(<StrategySummary markdown={markdown} />)
    const headers = Array.from(container.querySelectorAll('.sf-summary-section h4')).map(
      (el) => el.textContent,
    )
    // 与页面模块名重复的标题应被跳过
    expect(headers).not.toContain('策略概要')
  })

  it('renders label:value items as key-value rows', () => {
    const md = `**技术信号**
- 开仓：站上 20 日均线
- 平仓：跌破 20 日均线`
    const { container } = render(<StrategySummary markdown={md} />)
    const rows = container.querySelectorAll('.sf-summary-kv>div')
    expect(rows).toHaveLength(2)
    expect(rows[0].querySelector('dt')?.textContent).toBe('开仓')
    expect(rows[0].querySelector('dd')?.textContent).toBe('站上 20 日均线')
  })

  it('says so when no summary was returned', () => {
    render(<StrategySummary markdown="" />)
    expect(screen.getByText('本次生成未返回策略概要。')).toBeInTheDocument()
  })
})

describe('CodeHighlight', () => {
  it('numbers lines starting from 1', () => {
    const { container } = render(<CodeHighlight code={'a = 1\nb = 2'} />)
    const numbers = Array.from(container.querySelectorAll('.sf-code-ln')).map((el) => el.textContent)
    expect(numbers).toEqual(['1', '2'])
  })

  it('highlights comments, strings and keywords', () => {
    const code = '# 这是注释\ndef foo():\n    return "文本"'
    const { container } = render(<CodeHighlight code={code} />)
    expect(container.querySelector('.sf-tk-comment')?.textContent).toBe('# 这是注释')
    expect(container.querySelector('.sf-tk-keyword')?.textContent).toBe('def')
    expect(container.querySelector('.sf-tk-string')?.textContent).toBe('"文本"')
  })

  it('does not treat hashes inside strings as comments', () => {
    const { container } = render(<CodeHighlight code={'x = "# 不是注释"'} />)
    // 整串都被识别为字符串，不应出现 comment token
    expect(container.querySelector('.sf-tk-comment')).toBeNull()
    expect(container.querySelector('.sf-tk-string')?.textContent).toBe('"# 不是注释"')
  })

  it('highlights numbers and decorators', () => {
    const { container } = render(<CodeHighlight code={'@property\nx = 1.5'} />)
    expect(container.querySelector('.sf-tk-decorator')?.textContent).toBe('@property')
    expect(container.querySelector('.sf-tk-number')?.textContent).toBe('1.5')
  })

  it('keeps self as a keyword so instance calls are visible', () => {
    const { container } = render(<CodeHighlight code="self.value = 1" />)
    expect(container.querySelector('.sf-tk-keyword')?.textContent).toBe('self')
  })

  it('renders empty input without crashing', () => {
    const { container } = render(<CodeHighlight code="" />)
    expect(container.querySelectorAll('.sf-code-line')).toHaveLength(1)
  })
})