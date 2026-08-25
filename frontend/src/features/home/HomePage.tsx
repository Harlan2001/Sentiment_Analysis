import { FormEvent, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const marketCards = [
  { name: '10年国债收益率', value: '1.842%', delta: '-1.7 bp', tone: 'good', path: 'M4 30 C36 24 70 43 104 33 S160 20 194 43 S250 52 284 57 S314 63 326 59' },
  { name: '30年国债收益率', value: '2.091%', delta: '-1.2 bp', tone: 'good', path: 'M4 24 C36 16 70 24 104 30 S160 38 194 33 S250 48 284 52 S314 58 326 59' },
  { name: '国债期货 T 主力', value: '108.42', delta: '+0.18%', tone: 'rise', path: 'M4 61 C36 66 70 57 104 62 S158 34 190 38 S244 28 278 32 S312 35 326 40' },
  { name: 'DR007', value: '1.563%', delta: '+2.1 bp', tone: 'warn', path: 'M4 28 C36 34 66 27 96 33 S142 45 176 42 S228 54 264 57 S306 65 326 59' },
]

const watchlist = [
  ['10Y', '10年国债', 'CGB10Y', '1.842%', '-1.7 bp', 'good'],
  ['30Y', '30年国债', 'CGB30Y', '2.091%', '-1.2 bp', 'good'],
  ['T', '国债期货 T', 'T2609', '108.42', '+0.18%', 'rise'],
  ['TF', '5年国债期货', 'TF2609', '106.83', '+0.09%', 'rise'],
  ['CS', 'AAA信用利差', '3Y · 中债', '32 bp', '-0.8 bp', 'good'],
] as const

const navigation = ['市场', '收益', '预测', '筛选器', '关注列表', '投资组合', '工作流']

function Sparkline({ path, tone }: { path: string; tone: string }) {
  return <svg className="market-sparkline" viewBox="0 0 330 82" aria-hidden="true"><line x1="4" y1="41" x2="326" y2="41" /><path className={tone === 'rise' ? 'spark-rise' : tone === 'warn' ? 'spark-warn' : 'spark-good'} d={path} /><circle className={tone === 'rise' ? 'dot-rise' : tone === 'warn' ? 'dot-warn' : 'dot-good'} cx="326" cy={tone === 'rise' ? 40 : 59} r="3" /></svg>
}

export function HomePage() {
  const navigate = useNavigate()
  const formRef = useRef<HTMLFormElement>(null)
  const [activeTab, setActiveTab] = useState('市场')
  const [question, setQuestion] = useState('')
  const [updatedAt, setUpdatedAt] = useState('10:20')
  const signalLabel = useMemo(() => activeTab === '市场' ? '市场情绪：谨慎偏多' : `${activeTab}视图 · Mock 数据`, [activeTab])

  function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const draft = question.trim()
    navigate(draft ? `/chat?draft=${encodeURIComponent(draft)}` : '/chat')
  }

  return <section className="home-page">
    <nav className="finance-nav" aria-label="金融首页导航">
      {navigation.map((item) => <button key={item} className={activeTab === item ? 'active' : ''} onClick={() => setActiveTab(item)}>{item}</button>)}
      <span className="finance-nav-spacer" />
      <span className="sentiment-badge">{signalLabel}</span>
    </nav>

    <div className="home-dashboard">
      <div className="market-column">
        <div className="market-card-grid">
          {marketCards.map((card) => <article className="market-card" key={card.name}>
            <div className="market-card-head"><div><h2>{card.name}</h2><strong>{card.value}</strong></div><span className={`market-delta ${card.tone}`}>{card.delta}</span></div>
            <Sparkline path={card.path} tone={card.tone} />
          </article>)}
        </div>

        <section className="market-summary-card">
          <div className="section-title-row"><div><h2>市场摘要</h2><p>资金面维持平稳，长端配置需求延续。</p></div><button className="quiet-button" onClick={() => setUpdatedAt('刚刚')}>刷新</button></div>
          <div className="summary-points"><span>• 公开市场净投放呵护跨月流动性</span><span>• 国债期货延续偏强震荡</span><span>• 信用利差小幅收窄</span></div>
        </section>

          <form className="home-composer" onSubmit={submitQuestion} ref={formRef}>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); formRef.current?.requestSubmit() } }} placeholder="询问关于今日债券市场的任何问题…" rows={2} />
            <div className="composer-actions"><span className="composer-chip">＋ 附加</span><span className="composer-chip">⌕ 搜索</span><span className="composer-chip">▣ 工作流</span><button type="submit" aria-label="进入新会话">↑</button></div>
          </form>
      </div>

      <aside className="watchlist-card">
        <div className="section-title-row"><div><h2>我的关注</h2><p>{updatedAt} 更新</p></div><button className="quiet-button">编辑</button></div>
        <div className="watchlist-items">
          {watchlist.map(([code, name, sub, value, delta, tone]) => <div className="watch-row" key={code}>
            <span className="watch-code">{code}</span><div><strong>{name}</strong><small>{sub}</small></div><div><strong>{value}</strong><small className={tone}>{delta}</small></div>
          </div>)}
        </div>
        <div className="daily-signal"><div><span>今日信号</span><strong>偏多</strong></div><p>资金面宽松预期增强，长端配置需求回升。</p></div>
      </aside>
    </div>
  </section>
}
