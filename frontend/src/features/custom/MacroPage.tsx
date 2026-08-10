import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const categories = [['通胀与价格',28],['经济增长',35],['货币与信贷',31],['流动性与利率',24],['就业与收入',21],['房地产',26],['财政与融资',19],['外贸与国际',22]]
const indicators = [
  ['居民消费价格指数同比','月度 · % · 国家统计局','CPI_YOY'],
  ['工业生产者出厂价格同比','月度 · % · 国家统计局','PPI_YOY'],
  ['10 年期国债收益率','日度 · % · 中债','CGB10Y'],
  ['核心 CPI 同比','月度 · % · 国家统计局','CORE_CPI'],
  ['GDP 平减指数','季度 · % · 国家统计局','GDP_DEF'],
] as const

function CompareChart() {
 return <svg className="macro-chart" viewBox="0 0 800 320"><line x1="55" y1="48" x2="770" y2="48"/><line x1="55" y1="130" x2="770" y2="130"/><line x1="55" y1="210" x2="770" y2="210"/><line x1="55" y1="288" x2="770" y2="288"/><path className="macro-green" d="M60 210 C150 190 180 142 270 135 S400 98 475 126 S595 145 660 98 S725 88 765 102"/><path className="macro-red" d="M60 210 C150 165 205 72 290 90 S420 220 500 245 S650 268 720 205 S750 185 765 192"/><path className="macro-purple" d="M60 210 C150 225 210 236 285 205 S430 180 510 135 S640 150 710 166 S745 150 765 145"/><text x="57" y="312">2022</text><text x="235" y="312">2023</text><text x="415" y="312">2024</text><text x="595" y="312">2025</text><text x="735" y="312">2026</text></svg>
}

function SingleChart() {
 return <svg className="macro-chart single-chart" viewBox="0 0 800 320"><line x1="55" y1="48" x2="770" y2="48"/><line x1="55" y1="130" x2="770" y2="130"/><line x1="55" y1="210" x2="770" y2="210"/><line x1="55" y1="288" x2="770" y2="288"/><path className="macro-green" d="M60 238 C120 220 160 246 220 201 S330 170 388 188 S495 144 550 158 S650 94 710 116 S748 84 765 91"/><circle cx="765" cy="91" r="5"/><text x="57" y="312">2022</text><text x="235" y="312">2023</text><text x="415" y="312">2024</text><text x="595" y="312">2025</text><text x="735" y="312">2026</text></svg>
}

export function MacroPage() {
 const navigate = useNavigate()
 const [selected, setSelected] = useState([0,1,2])
 const [singleIndex, setSingleIndex] = useState(0)
 const [mode, setMode] = useState('对比模式')
 const toggle = (index: number) => setSelected((items) => items.includes(index) ? items.filter((item) => item !== index) : items.length < 4 ? [...items,index] : items)
 const single = indicators[singleIndex]
 return <section className="custom-page macro-page">
  <div className="custom-tabs"><button onClick={() => navigate('/custom/factors')}>因子库</button><button className="active">宏观指标</button><button onClick={() => navigate('/custom/skills')}>Skills</button><span className="computer-spacer"/><button className="computer-button">我的关注</button></div>
  <div className="factor-title-row"><div><h1>宏观指标 <span>200+ 指标</span></h1><p>按经济含义分类，相关性只作为辅助标签。</p></div><div className="factor-view-switch">{['单指标','对比模式'].map((item)=><button className={mode===item?'active':''} onClick={()=>setMode(item)} key={item}>{item}</button>)}</div></div>
  <div className="macro-category-grid">{categories.map(([name,count],index)=><button className={index===0?'active':''} key={name}><strong>{name}</strong><span>{count}</span><small>本周更新 {Math.max(2,Math.round(Number(count)/6))} 个</small><i><b/><b/><b/></i></button>)}</div>
  <div className="factor-filter-row"><label><span>⌕</span><input placeholder="搜索指标名称、代码或主题"/></label><button className="computer-chip dropdown-chip">频率：全部<i className="inline-caret" aria-hidden="true" /></button><button className="computer-chip dropdown-chip">来源：全部<i className="inline-caret" aria-hidden="true" /></button><span className="computer-spacer"/><button className="computer-chip selected">近 5 年</button>{mode === '对比模式' && <button className="computer-chip dropdown-chip">起始值=100<i className="inline-caret" aria-hidden="true" /></button>}</div>
  <div className="macro-main"><div className="macro-indicator-list">{indicators.map((item,index)=>{ const checked = mode === '单指标' ? singleIndex === index : selected.includes(index); return <label className={checked?'active':''} key={item[2]}><input type={mode === '单指标' ? 'radio' : 'checkbox'} name="macro-indicator" checked={checked} onChange={()=>mode === '单指标' ? setSingleIndex(index) : toggle(index)}/><div><strong>{item[0]}</strong><small>{item[1]}</small></div><code>{item[2]}</code></label>})}</div>
  {mode === '对比模式' ? <section className="macro-compare"><header><div><h2>指标比较</h2><p>已选 {selected.length}/4 · 不同单位已标准化为起始值 100</p></div><div><span className="factor-badge up">CPI 同比</span><span className="factor-badge down">PPI 同比</span><span className="factor-badge">10 年国债</span></div></header><CompareChart/><footer><span>● CPI 同比</span><span>● PPI 同比</span><span>● 10 年国债收益率</span></footer></section> : <section className="macro-single"><header><div><h2>{single[0]}</h2><p>{single[2]} · {single[1]}</p></div><span className="factor-badge up">温和回升</span></header><div className="macro-metrics"><div><small>最新值</small><strong>0.6%</strong><span>较上期 +0.2</span></div><div><small>同比变化</small><strong>+0.3</strong><span>近 12 月高位</span></div><div><small>历史分位</small><strong>72%</strong><span>过去 5 年</span></div><div><small>下次发布</small><strong>08-09</strong><span>国家统计局</span></div></div><SingleChart/><div className="macro-impact"><strong>对债市影响</strong><p>当前读数温和回升，若后续持续高于预期，可能抬升利率债估值压力；需结合资金面和政策信号共同判断。</p></div></section>}</div>
 </section>
}