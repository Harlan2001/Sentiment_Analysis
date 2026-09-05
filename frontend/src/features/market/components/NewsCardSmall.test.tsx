import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import NewsCardSmall from './NewsCardSmall'
import type { DiscoverNewsItem } from '@/types'

function makeItem(overrides: Partial<DiscoverNewsItem> = {}): DiscoverNewsItem {
  return {
    id: 1,
    title: '标题',
    direction: 'positive',
    pub_time: '',
    source: '来源',
    ...overrides,
  } as DiscoverNewsItem
}

const daysAgo = (n: number) => new Date(Date.now() - n * 864e5).toISOString()
const hoursAgo = (n: number) => new Date(Date.now() - n * 36e5).toISOString()

describe('NewsCardSmall', () => {
  it('渲染标题并展示利多方向标签', () => {
    render(<NewsCardSmall item={makeItem({ title: '央行降准', direction: 'positive' })} onClick={vi.fn()} />)
    expect(screen.getByText('央行降准')).toBeInTheDocument()
    expect(screen.getByText('利多')).toBeInTheDocument()
  })

  it('利空映射为利空标签', () => {
    render(<NewsCardSmall item={makeItem({ direction: 'negative' })} onClick={vi.fn()} />)
    expect(screen.getByText('利空')).toBeInTheDocument()
  })

  it('无方向时不渲染方向标签', () => {
    render(<NewsCardSmall item={makeItem({ direction: undefined })} onClick={vi.fn()} />)
    expect(screen.queryByText(/利多|利空|中性/)).not.toBeInTheDocument()
  })

  it('相对时间格式: 天/小时/刚刚', () => {
    const { rerender } = render(
      <NewsCardSmall item={makeItem({ pub_time: daysAgo(2) })} onClick={vi.fn()} />,
    )
    expect(screen.getByText('2天前')).toBeInTheDocument()

    rerender(<NewsCardSmall item={makeItem({ pub_time: hoursAgo(2) })} onClick={vi.fn()} />)
    expect(screen.getByText('2小时前')).toBeInTheDocument()

    const minutesAgo = new Date(Date.now() - 6e5).toISOString()
    rerender(<NewsCardSmall item={makeItem({ pub_time: minutesAgo })} onClick={vi.fn()} />)
    expect(screen.getByText('刚刚')).toBeInTheDocument()
  })

  it('点击卡片触发 onClick', async () => {
    const onClick = vi.fn()
    render(<NewsCardSmall item={makeItem({ title: '可点标题' })} onClick={onClick} />)
    await userEvent.click(screen.getByText('可点标题'))
    expect(onClick).toHaveBeenCalled()
  })
})