/**
 * 新闻排序分段控件（S3-3）—— 同页切换「时间排序 / 推荐排序」
 * 状态写入 URL ?sort= 并 replace，刷新/分享可保持；非法值回退 latest。
 */
import React from 'react'
import { useSearchParams } from 'react-router-dom'

export type NewsSort = 'latest' | 'recommend'

const SEGMENTS: { key: NewsSort; label: string }[] = [
  { key: 'latest', label: '时间排序' },
  { key: 'recommend', label: '推荐排序' },
]

export function readSort(value: string | null): NewsSort {
  return value === 'recommend' ? 'recommend' : 'latest'
}

const NewsSortSegmented: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const sort = readSort(searchParams.get('sort'))

  const switchSort = (next: NewsSort) => {
    if (next === sort) return
    const params = new URLSearchParams(searchParams)
    if (next === 'latest') {
      params.delete('sort')
    } else {
      params.set('sort', next)
    }
    setSearchParams(params, { replace: true })
  }

  return (
    <div className="news-sort-segmented" role="group" aria-label="新闻排序方式">
      {SEGMENTS.map((seg) => (
        <button
          key={seg.key}
          type="button"
          className={sort === seg.key ? 'active' : ''}
          aria-pressed={sort === seg.key}
          onClick={() => switchSort(seg.key)}
        >
          {seg.label}
        </button>
      ))}
    </div>
  )
}

export default NewsSortSegmented
