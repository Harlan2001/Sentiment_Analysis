import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import NewsContentBlocks from './NewsContentBlocks'
import type { NewsContentBlock } from '@/types'

/** 构造内容块（覆盖 block_type / block_order, 其余字段给默认值, 按组件实际使用字段填充） */
function mk(partial: Record<string, unknown>): NewsContentBlock {
  return {
    id: Math.floor(Math.random() * 1e6),
    block_type: 'text',
    block_order: 0,
    content: '',
    ...partial,
  } as unknown as NewsContentBlock
}

describe('NewsContentBlocks', () => {
  it('按 block_order 升序渲染多个块', () => {
    render(
      <NewsContentBlocks
        blocks={[
          mk({ block_order: 2, content: '第二段' }),
          mk({ block_order: 1, content: '第一段' }),
        ]}
      />,
    )
    const ps = screen.getAllByText(/段/)
    expect(ps[0]).toHaveTextContent('第一段')
    expect(ps[1]).toHaveTextContent('第二段')
  })

  it('text 块渲染段落内容', () => {
    render(<NewsContentBlocks blocks={[mk({ block_type: 'text', content: '正文段落' })]} />)
    expect(screen.getByText('正文段落')).toBeInTheDocument()
  })

  it('heading 块渲染默认 h2', () => {
    render(<NewsContentBlocks blocks={[mk({ block_type: 'heading', content: '小标题' })]} />)
    expect(screen.getByRole('heading', { name: '小标题', level: 2 })).toBeInTheDocument()
  })

  it('heading 块按 heading_level 渲染 h1', () => {
    render(
      <NewsContentBlocks
        blocks={[mk({ block_type: 'heading', heading_level: 'h1', content: '大标题' })]}
      />,
    )
    expect(screen.getByRole('heading', { name: '大标题', level: 1 })).toBeInTheDocument()
  })

  it('quote 块渲染 blockquote', () => {
    render(<NewsContentBlocks blocks={[mk({ block_type: 'quote', content: '引文' })]} />)
    expect(screen.getByText('引文').tagName).toBe('BLOCKQUOTE')
  })

  it('image 块渲染图片与 alt 说明', () => {
    render(
      <NewsContentBlocks
        blocks={[
          mk({
            block_type: 'image',
            image_url: 'http://img.local/x.png',
            image_alt: '图一',
          }),
        ]}
      />,
    )
    const img = screen.getByRole('img', { name: '图一' })
    expect(img).toHaveAttribute('src', 'http://img.local/x.png')
    expect(screen.getByText('图一')).toBeInTheDocument()
  })

  it('image 块无 alt 时用默认文案', () => {
    render(
      <NewsContentBlocks blocks={[mk({ block_type: 'image', image_url: 'http://img.local/y.png' })]} />,
    )
    expect(screen.getByRole('img', { name: '新闻图片' })).toBeInTheDocument()
  })

  it('table 块渲染标题/表头/单元格', () => {
    render(
      <NewsContentBlocks
        blocks={[
          mk({
            block_type: 'table',
            table_caption: '收益率',
            table_unit: '%',
            table_headers: ['期限', '收益率'],
            table_rows: [['1Y', '1.50']],
          }),
        ]}
      />,
    )
    expect(screen.getAllByText(/收益率/).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText(/\(%\)/)).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByText('期限')).toBeInTheDocument()
    expect(within(table).getByText('1Y')).toBeInTheDocument()
  })

  it('未知块类型不渲染', () => {
    const { container } = render(
      <NewsContentBlocks blocks={[mk({ block_type: 'video', content: '不渲染' })]} />,
    )
    expect(screen.queryByText('不渲染')).not.toBeInTheDocument()
    expect(container.textContent).toBe('')
  })
})