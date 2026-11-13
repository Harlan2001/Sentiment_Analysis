import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import NewsFeedCard from './NewsFeedCard'
import type { DiscoverNewsItem } from '@/types'

function makeItem(overrides: Partial<DiscoverNewsItem> = {}): DiscoverNewsItem {
  return {
    id: 1,
    title: '标题',
    summary: '',
    direction: 'positive',
    pub_time: '',
    source: 'wallstreetcn',
    source_name: '数据源1',
    thumbnail: null,
    reason: '',
    factors: [],
    importance_score: null,
    final_score: null,
    score_signals: null,
    top_category: null,
    ...overrides,
  }
}

const daysAgo = (n: number) => new Date(Date.now() - n * 864e5).toISOString()
const hoursAgo = (n: number) => new Date(Date.now() - n * 36e5).toISOString()

describe('NewsFeedCard', () => {
  it('渲染标题并按方向展示利多/利空/中性标签', () => {
    const { rerender } = render(<NewsFeedCard item={makeItem({ title: '央行降准', direction: 'positive' })} onClick={vi.fn()} />)
    expect(screen.getByText('央行降准')).toBeInTheDocument()
    expect(screen.getByText('利多')).toBeInTheDocument()

    rerender(<NewsFeedCard item={makeItem({ direction: 'negative' })} onClick={vi.fn()} />)
    expect(screen.getByText('利空')).toBeInTheDocument()

    rerender(<NewsFeedCard item={makeItem({ direction: 'neutral' })} onClick={vi.fn()} />)
    expect(screen.getByText('中性')).toBeInTheDocument()
  })

  it('无方向时不渲染方向标签', () => {
    render(<NewsFeedCard item={makeItem({ direction: null })} onClick={vi.fn()} />)
    expect(screen.queryByText(/利多|利空|中性/)).not.toBeInTheDocument()
  })

  it('相对时间格式: 天/小时/刚刚', () => {
    const { rerender } = render(<NewsFeedCard item={makeItem({ pub_time: daysAgo(2) })} onClick={vi.fn()} />)
    expect(screen.getByText('2天前')).toBeInTheDocument()

    rerender(<NewsFeedCard item={makeItem({ pub_time: hoursAgo(2) })} onClick={vi.fn()} />)
    expect(screen.getByText('2小时前')).toBeInTheDocument()

    rerender(<NewsFeedCard item={makeItem({ pub_time: new Date(Date.now() - 6e5).toISOString() })} onClick={vi.fn()} />)
    expect(screen.getByText('刚刚')).toBeInTheDocument()
  })

  it('因子 chips 最多展示两个，超出显示 +N', () => {
    const factors = [
      { id: 1, name: '央行货币政策' },
      { id: 2, name: '资金面' },
      { id: 3, name: '通胀' },
      { id: 4, name: '汇率' },
    ]
    render(<NewsFeedCard item={makeItem({ factors })} onClick={vi.fn()} />)
    expect(screen.getByText('央行货币政策')).toBeInTheDocument()
    expect(screen.getByText('资金面')).toBeInTheDocument()
    expect(screen.queryByText('通胀')).not.toBeInTheDocument()
    expect(screen.getByText('+2')).toBeInTheDocument()
  })

  it('有缩略图时渲染图片，无图时不渲染', () => {
    const { container, rerender } = render(<NewsFeedCard item={makeItem({ thumbnail: 'http://img.local/1.png' })} onClick={vi.fn()} />)
    expect(container.querySelector('img.news-card-thumb')).toHaveAttribute('src', 'http://img.local/1.png')

    rerender(<NewsFeedCard item={makeItem({ thumbnail: null })} onClick={vi.fn()} />)
    expect(container.querySelector('img.news-card-thumb')).toBeNull()
  })

  it('两种变体均展示分析摘要，仅 recommend 变体展示取整后的分值', () => {
    const item = makeItem({ reason: '降准释放长期流动性，利多利率债', final_score: 87.4 })
    const { rerender } = render(<NewsFeedCard item={item} variant="recommend" onClick={vi.fn()} />)
    expect(screen.getByText('降准释放长期流动性，利多利率债')).toBeInTheDocument()
    expect(screen.getByText('87')).toBeInTheDocument()

    rerender(<NewsFeedCard item={item} variant="latest" onClick={vi.fn()} />)
    expect(screen.getByText('降准释放长期流动性，利多利率债')).toBeInTheDocument()
    expect(screen.queryByText('87')).not.toBeInTheDocument()
  })

  it('分析理由为空时回退到新闻摘要', () => {
    render(<NewsFeedCard item={makeItem({ reason: '', summary: '新闻正文摘要' })} onClick={vi.fn()} />)
    expect(screen.getByText('新闻正文摘要')).toBeInTheDocument()
  })

  it('点击卡片或按 Enter 触发 onClick', async () => {
    const onClick = vi.fn()
    render(<NewsFeedCard item={makeItem({ id: 9, title: '可点标题' })} onClick={onClick} />)
    const card = screen.getByText('可点标题').closest('article')!
    await userEvent.click(card)
    expect(onClick).toHaveBeenCalledTimes(1)

    card.focus()
    await userEvent.keyboard('{Enter}')
    expect(onClick).toHaveBeenCalledTimes(2)
  })
})
