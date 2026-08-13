import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const news = [
  ['利多', '央行连续开展逆回购操作，资金面保持宽松', '央行官方网站 · 官方来源权重 1.00 · 对应时间线 08-06', '今天 09:35'],
  ['利多', '跨月后资金价格回落，机构配置需求回升', '专业财经媒体 · 来源权重 0.75 · 对应时间线 08-05', '昨天 16:20'],
  ['利空', '地方债缴款规模上升，短期资金需求增加', '财政部 · 官方来源权重 1.00 · 对应时间线 08-01', '8 月 1 日'],
] as const

function Timeline() {
  const bars = [24, 38, 18, -17, 42, 27, -24, 15, 34, -13, 26, 45]
  return <svg className="factor-timeline" viewBox="0 0 900 250" aria-label="事件方向时间线">
    <line x1="42" y1="125" x2="870" y2="125" /><line x1="42" y1="54" x2="870" y2="54" className="grid" /><line x1="42" y1="196" x2="870" y2="196" className="grid" />
    {bars.map((bar, index) => { const x = 66 + index * 65; const y = bar > 0 ? 125 - bar * 1.45 : 125; return <rect key={x} x={x} y={y} width="32" height={Math.abs(bar) * 1.45} className={bar > 0 ? 'positive' : 'negative'} /> })}
    <text x="45" y="232">07-08</text><text x="250" y="232">07-15</text><text x="460" y="232">07-22</text><text x="665" y="232">07-29</text><text x="835" y="232">08-06</text>
  </svg>
}

export function FactorDetailPage() {
  const navigate = useNavigate()
  const [range, setRange] = useState('30日')
  const [filter, setFilter] = useState('全部')
  const [followed, setFollowed] = useState(false)
  return <section className="custom-page factor-detail-page">
    <div className="custom-tabs"><button className="active" onClick={() => navigate('/custom/factors')}>因子库</button><button onClick={() => navigate('/custom/macro')}>宏观指标</button><button onClick={() => navigate('/custom/skills')}>Skills</button><span className="computer-spacer" /><button className="computer-button">我的关注</button></div>
    <header className="factor-detail-head"><div><h1>银行间流动性 <span className="factor-badge up">当前利多</span></h1><p>LQ001 · 货币流动性 · 影响资金价格与债券配置需求</p></div><span className="computer-spacer" /><span className="computer-badge">近 7 日 18 个事件</span><span className="computer-badge">近 30 日 46 个事件</span><span className="computer-badge">10:20 更新</span><button className={'computer-button ' + (followed ? 'primary' : '')} onClick={() => setFollowed((value) => !value)}>{followed ? '已关注' : '关注'}</button></header>
    <section className="timeline-panel"><div className="timeline-panel-head"><div><h2>事件方向时间线</h2><p>柱高代表事件数量，零轴上方为利多、下方为利空。</p></div><div>{['7日', '30日', '90日', '1年'].map((item) => <button className={'computer-chip ' + (range === item ? 'selected' : '')} onClick={() => setRange(item)} key={item}>{item}</button>)}</div></div><Timeline /><div className="timeline-legend"><span><i className="positive" />利多事件</span><span><i className="negative" />利空事件</span><span><i className="neutral" />中性事件</span><span>点击日期可筛选下方新闻</span></div></section>
    <div className="factor-news-head"><h2>相关新闻 <small>· 与时间线双向联动</small></h2><div>{['全部', '利多', '利空'].map((item) => <button className={'computer-chip ' + (filter === item ? 'selected' : '')} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div></div>
    <div className="factor-news-list">{news.filter((item) => filter === '全部' || item[0] === filter).map((item) => <article key={item[1]}><span className={'factor-badge ' + (item[0] === '利多' ? 'up' : 'down')}>{item[0]}</span><div><strong>{item[1]}</strong><p>{item[2]}</p></div><time>{item[3]}</time></article>)}</div>
  </section>
}