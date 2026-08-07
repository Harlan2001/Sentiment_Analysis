import { FormEvent, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const skills = [
  { name: '债券日报模板', type: '系统', description: '按市场、资金面、利率和信用四段生成债券日报框架。' },
  { name: '信用风险快筛', type: '系统', description: '汇总主体风险事件、估值变化与重点负面新闻。' },
  { name: '流动性周度复盘', type: '系统', description: '快速整理资金价格、公开市场操作和期限利差变化。' },
  { name: '我的信用债跟踪', type: '我的', description: '基于关注主体和持仓范围的信用债日常跟踪模板。' },
  { name: '利率债交易备忘', type: '我的', description: '沉淀利率债交易假设、触发条件和复盘结果。' },
]

export function SkillsPage() {
 const navigate = useNavigate()
 const [tab,setTab] = useState('全部')
 const [query,setQuery] = useState('')
 const [created,setCreated] = useState(false)
 const visible = useMemo(() => skills.filter((skill) => (tab === '全部' || skill.type === tab) && (skill.name + skill.description).includes(query.trim())), [query,tab])
 function createSkill(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setCreated(true) }
 return <section className="custom-page skills-page">
  <div className="custom-tabs"><button onClick={()=>navigate('/custom/factors')}>因子库</button><button onClick={()=>navigate('/custom/macro')}>宏观指标</button><button className="active">Skills</button></div>
  <header className="skills-head"><div><h1>技能</h1><p>通过可复用的能力扩展 BondSense 的研究与工作流。</p></div><div className="skills-actions"><label><span>⌕</span><input value={query} onChange={(event)=>setQuery(event.target.value)} placeholder="搜索技能"/></label></div></header>
  <div className="skills-filter-tabs">{['全部','系统','我的','新建'].map((item)=><button className={tab===item?'active':''} onClick={()=>setTab(item)} key={item}>{item === '新建' ? '＋ 新建' : item}</button>)}</div>
  {tab === '新建' ? <form className="skills-create" onSubmit={createSkill}><h2>创建新技能</h2><p>第一期先记录 Skill 名称、用途和输出说明；后续再接入提示词、输入参数和执行能力。</p><input placeholder="技能名称，例如：信用债违约风险快筛"/><textarea placeholder="描述这个技能何时使用、需要什么输入、希望输出什么结果…" rows={4}/><div><button className="computer-button">取消</button><button className="computer-button primary" type="submit">创建 Skill</button></div>{created&&<small>已创建 Mock Skill，后续可在“我的”中管理。</small>}</form> : <><div className="skills-grid">{visible.map((skill)=><article key={skill.name}><div><h2>{skill.name}</h2><button aria-label={'更多 ' + skill.name}>⋮</button></div><p>{skill.description}</p><small>{skill.type === '系统' ? '系统技能 · 可直接使用' : '我的技能 · 仅自己可见'}</small></article>)}</div>{!visible.length && <div className="skills-no-result">没有找到匹配的技能。</div>}</>}
 </section>
}