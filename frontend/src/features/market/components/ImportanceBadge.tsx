import React from 'react'

interface Props {
  score: number | null | undefined
  mode: 'static' | 'decayed'
  scoreVersion?: string | null
}

/** 两种评分口径共享外观，但 tooltip 与空分语义严格分开。 */
const ImportanceBadge: React.FC<Props> = ({ score, mode, scoreVersion }) => {
  const description = mode === 'static'
    ? '静态重要性评分，未叠加相对当前时间的衰减'
    : '重要性评分（已叠加时间衰减）'
  const title = `${description}${mode === 'static' && scoreVersion ? ` · ${scoreVersion}` : ''}`
  if (score === null || score === undefined) {
    return <span className="importance-badge importance-badge--empty" title={description}>暂未评分</span>
  }
  const rounded = Math.round(score)
  return (
    <span
      className="news-row-score importance-badge"
      title={title}
      aria-label={`${mode === 'static' ? '静态重要性' : '时间衰减后重要性'} ${rounded} 分`}
    >
      <strong>{rounded}</strong>
    </span>
  )
}

export default ImportanceBadge
