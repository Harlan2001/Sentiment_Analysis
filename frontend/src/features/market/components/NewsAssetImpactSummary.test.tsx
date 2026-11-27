import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { NewsItem } from '@/types'
import NewsAssetImpactSummary from './NewsAssetImpactSummary'

describe('NewsAssetImpactSummary', () => {
  it('只把现有新闻方向用于中国国债，其余资产明确显示未分析', () => {
    const news = { id: 1, title: '测试新闻', direction: 'positive', reason: '不应在紧凑影响条中展示的原因' } as NewsItem
    render(<NewsAssetImpactSummary news={news} />)

    expect(screen.getByText('中国国债')).toBeInTheDocument()
    expect(screen.getByText('利多')).toBeInTheDocument()
    expect(screen.getByText('信用债')).toBeInTheDocument()
    expect(screen.getByText('国债期货')).toBeInTheDocument()
    expect(screen.getByText('美债')).toBeInTheDocument()
    expect(screen.getAllByText('未分析')).toHaveLength(3)
    expect(screen.queryByText(news.reason!)).not.toBeInTheDocument()
  })

  it('读取独立资产影响记录并按资产语义展示方向', () => {
    const news = {
      id: 2,
      title: '多资产新闻',
      direction: 'negative',
      asset_impacts: [
        { asset_scope: 'credit', direction: 'positive', status: 'analyzed' },
        { asset_scope: 'futures', status: 'insufficient_evidence' },
        { asset_scope: 'ust', direction: 'negative', status: 'analyzed' },
      ],
    } as NewsItem & { asset_impacts: Array<{ asset_scope: string; direction?: string; status: string }> }

    render(<NewsAssetImpactSummary news={news} />)
    expect(screen.getByText('利差收窄')).toBeInTheDocument()
    expect(screen.getByText('证据不足')).toBeInTheDocument()
    expect(screen.getByText('收益率上行')).toBeInTheDocument()
  })
})
