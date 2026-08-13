import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const categories = [
  { name: '政策监管', count: 72, up: 12, neutral: 18, down: 9 },
  { name: '经济增长', count: 88, up: 8, neutral: 15, down: 14 },
  { name: '货币流动性', count: 96, up: 19, neutral: 10, down: 6 },
  { name: '债券供需', count: 71, up: 7, neutral: 12, down: 13 },
  { name: '情绪风险', count: 73, up: 14, neutral: 11, down: 8 },
]

const factors = [
  { name: '银行间流动性', code: 'LQ001', category: '货币流动性', direction: '利多', heat: '高', follows: '较高', trend: [5, 8, 6, 12, 15, 18, 16], events: 18, updated: '今天 10:20' },
  { name: '央行公开市场操作', code: 'PL027', category: '政策监管', direction: '中性', heat: '高', follows: '高', trend: [4, 5, 9, 7, 13, 12, 10], events: 12, updated: '今天 09:40' },
  { name: '制造业景气度', code: 'GR015', category: '经济增长', direction: '利空', heat: '中', follows: '中', trend: [8, 7, 6, 11, 8, 6, 5], events: 9, updated: '昨天' },
  { name: '地方债发行节奏', code: 'SD008', category: '债券供需', direction: '利空', heat: '中', follows: '较高', trend: [3, 5, 4, 8, 10, 7, 6], events: 7, updated: '昨天' },
  { name: '机构风险偏好', code: 'ST041', category: '情绪风险', direction: '利多', heat: '中', follows: '高', trend: [2, 4, 7, 5, 8, 11, 9], events: 6, updated: '2 天前' },
  { name: '资金面宽松预期', code: 'LQ033', category: '货币流动性', direction: '利多', heat: '低', follows: '中', trend: [3, 4, 3, 6, 5, 7, 8], events: 5, updated: '3 天前' },
]

function Trend({ values, direction }: { values: number[]; direction: string }) {
  const max = Math.max(...values)
  const min = Math.min(...values)
  const points = values.map((value, index) => {
    const x = index * 17 + 2
    const y = 25 - ((value - min) / Math.max(1, max - min)) * 20
    return x + ',' + y
  }).join(' ')
  return <svg className={'factor-trend ' + (direction === '利空' ? 'down' : '')} viewBox="0 0 110 30" aria-hidden="true"><polyline points={points} /></svg>
}

export function FactorLibraryPage() {
  const navigate = useNavigate()
  const [view, setView] = useState('今日活跃')
  const [query, setQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState('货币流动性')

  const visibleFactors = useMemo(() => factors.filter((factor) => {
    const matchesQuery = (factor.name + factor.code + factor.category).includes(query.trim())
    const matchesCategory = view === '全部因子' || !activeCategory || factor.category === activeCategory
    return matchesQuery && matchesCategory
  }), [activeCategory, query, view])

  return (
    <section className="custom-page">
      <div className="custom-tabs">
        <button className="active">因子库</button><button onClick={() => navigate('/custom/macro')}>宏观指标</button><button onClick={() => navigate('/custom/skills')}>Skills</button>
        <span className="computer-spacer" /><button className="computer-button">我的关注</button>
      </div>

      <div className="factor-title-row">
        <div><h1>因子库 <span>400 个因子</span></h1><p>默认展示今日活跃；热度由事件、时效、来源和用户关注共同计算。</p></div>
        <div className="factor-view-switch">{['今日活跃', '我的关注', '全部因子'].map((item) => <button className={view === item ? 'active' : ''} onClick={() => setView(item)} key={item}>{item}</button>)}</div>
      </div>

      <div className="factor-category-grid">
        {categories.map((category) => {
          const total = category.up + category.neutral + category.down
          return <button className={activeCategory === category.name ? 'active' : ''} onClick={() => setActiveCategory(category.name)} key={category.name}>
            <strong>{category.name}</strong><span>{category.count}</span><small>近 7 日方向分布</small>
            <i><b className="up" style={{ width: category.up / total * 100 + '%' }} /><b className="neutral" style={{ width: category.neutral / total * 100 + '%' }} /><b className="down" style={{ width: category.down / total * 100 + '%' }} /></i>
          </button>
        })}
      </div>

      <div className="factor-filter-row">
        <label><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索因子名称、代码或主题" /></label>
        <button className="computer-chip dropdown-chip">方向：全部<i className="inline-caret" aria-hidden="true" /></button><button className="computer-chip dropdown-chip">热度：全部<i className="inline-caret" aria-hidden="true" /></button><button className="computer-chip dropdown-chip">时间：近 7 日<i className="inline-caret" aria-hidden="true" /></button><button className="computer-chip dropdown-chip">来源：全部<i className="inline-caret" aria-hidden="true" /></button>
        <span className="computer-spacer" /><button className="computer-chip dropdown-chip">排序：综合热度<i className="inline-caret" aria-hidden="true" /></button>
      </div>

      <div className="factor-table-wrap">
        <table className="factor-table">
          <thead><tr><th>因子</th><th>分类</th><th>当前方向</th><th>研究热度</th><th>用户关注</th><th>7 日趋势</th><th>事件</th><th>最后更新</th></tr></thead>
          <tbody>{visibleFactors.map((factor) => <tr key={factor.code} onClick={() => navigate('/custom/factors/' + factor.code)} className="factor-clickable">
            <td><strong>{factor.name}</strong><small>{factor.code}</small></td><td>{factor.category}</td>
            <td><span className={'factor-badge ' + (factor.direction === '利多' ? 'up' : factor.direction === '利空' ? 'down' : '')}>{factor.direction}</span></td>
            <td><span className={'factor-badge ' + (factor.heat === '高' ? 'heat' : '')}>{factor.heat}</span></td><td>{factor.follows}</td><td><Trend values={factor.trend} direction={factor.direction} /></td><td>{factor.events}</td><td>{factor.updated}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <p className="factor-footnote">综合排序默认权重：研究热度 80% · 用户关注 20%；原始点击量不直接作为重要度。</p>
    </section>
  )
}