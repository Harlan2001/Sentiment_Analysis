import { useEffect, useMemo, useState } from 'react'

type Allocation = {
  id: string
  label: string
  current: number
  suggested: number
  color: string
  valueColor: string
}

type RiskItem = { level: '高' | '中' | '低'; title: string; detail: string }

const allocations: Allocation[] = [
  { id: 'government', label: '利率债', current: 48, suggested: 54, color: 'bg-[#6f8cff]', valueColor: 'text-[#82a6ff]' },
  { id: 'policy', label: '政策性金融债', current: 27, suggested: 28, color: 'bg-[#4fb8a8]', valueColor: 'text-[#66cabb]' },
  { id: 'credit', label: '高等级信用债', current: 18, suggested: 14, color: 'bg-[#d6a85f]', valueColor: 'text-amber-400' },
  { id: 'cash', label: '现金', current: 7, suggested: 4, color: 'bg-[#77708f]', valueColor: 'text-[#a79bd0]' },
]

const holdings = [
  ['230210', '23国开10', '政策性金融债', '18.6%', '1.83%', '5.72', '增配'],
  ['240004', '24附息国债04', '国债', '16.2%', '1.71%', '7.36', '持有'],
  ['250205', '25国开05', '政策性金融债', '13.5%', '1.66%', '3.84', '增配'],
  ['102481993', '24中电投MTN018', 'AAA信用债', '10.8%', '2.08%', '2.16', '减配'],
] as const

const aiDefault = Object.fromEntries(allocations.map((item) => [item.id, item.suggested])) as Record<string, number>

function buildRisks(values: Record<string, number>, duration: number): RiskItem[] {
  const risks: RiskItem[] = []
  if (duration > 5) risks.push({ level: duration > 6 ? '高' : '中', title: '组合久期偏高', detail: `目标久期 ${duration.toFixed(2)} 年，高于当前策略建议的 4.92 年。` })
  if (values.credit > 20) risks.push({ level: '中', title: '信用债配置偏高', detail: `高等级信用债占比 ${values.credit}%，需留意信用利差走阔。` })
  if (values.cash < 3) risks.push({ level: '中', title: '流动性缓冲不足', detail: `现金占比仅 ${values.cash}%，建议保留必要的流动性空间。` })
  if (values.government + values.policy > 85) risks.push({ level: '低', title: '利率敏感度集中', detail: '利率债与政策性金融债合计占比较高，关注长端利率波动。' })
  if (!risks.length) risks.push({ level: '低', title: '当前配置处于可控区间', detail: '仍需持续观察政策预期、资金面和收益率曲线变化。' })
  return risks.slice(0, 3)
}

function formatAmount(amountInTenThousands: number) {
  return amountInTenThousands >= 10000
    ? `${(amountInTenThousands / 10000).toFixed(2)} 亿`
    : `${Math.round(amountInTenThousands)} 万`
}

export default function PortfolioPage() {
  const [mode, setMode] = useState<'current' | 'edit'>('edit')
  const [manual, setManual] = useState<Record<string, number>>(aiDefault)
  const [duration, setDuration] = useState(4.92)
  const [portfolioSize, setPortfolioSize] = useState(12800)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    try {
      const saved = JSON.parse(window.localStorage.getItem('bondsense-portfolio-draft') || 'null')
      if (saved?.allocation && typeof saved.duration === 'number') {
        setManual({ ...aiDefault, ...saved.allocation })
        setDuration(saved.duration)
        if (typeof saved.portfolioSize === 'number') setPortfolioSize(saved.portfolioSize)
        setNotice('已恢复本浏览器保存的方案草稿。')
      }
    } catch {
      // Ignore an invalid local draft and continue with the AI demonstration data.
    }
  }, [])

  const values = mode === 'current'
    ? Object.fromEntries(allocations.map((item) => [item.id, item.current]))
    : manual
  const total = Object.values(values).reduce((sum, value) => sum + value, 0)
  const valid = total === 100 && duration >= 1 && duration <= 10
  const risks = useMemo(() => buildRisks(values, duration), [duration, values])
  const activeDuration = mode === 'current' ? 5.18 : duration

  function change(id: string, value: number) {
    const nextValue = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0))
    const delta = nextValue - manual[id]
    const balanceId = id === 'cash' ? 'government' : 'cash'
    const nextBalance = manual[balanceId] - delta
    if (nextBalance < 0) {
      setNotice(`无法再提高${allocations.find((item) => item.id === id)?.label || '该资产'}比例：用于自动平衡的${balanceId === 'cash' ? '现金' : '利率债'}不足。`)
      return
    }
    setManual({ ...manual, [id]: nextValue, [balanceId]: nextBalance })
    setNotice('')
  }

  function reset() {
    setManual(aiDefault)
    setDuration(4.92)
    setNotice('已恢复 AI 配置建议。')
  }

  function save() {
    if (!valid) {
      setNotice('请将资产比例调整为 100%，并将目标久期设置在 1–10 年之间。')
      return
    }
    window.localStorage.setItem('bondsense-portfolio-draft', JSON.stringify({ allocation: manual, duration, portfolioSize }))
    setNotice('配置方案已保存为本浏览器草稿，不会产生交易动作。')
  }

  return <div className="market-workspace" style={{ position: 'absolute', inset: 0 }}>
    <div className="market-workspace-body">
      <div className="market-discover-panel">
        <main className="space-y-4 pb-4 pl-4 pr-px pt-2">
          <header className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2"><h1 className="text-lg font-bold text-white">稳健型债券组合</h1><span className="rounded border border-[#343438] bg-[#191919] px-1.5 py-0.5 text-[10px] text-gray-300">研究方案</span></div>
              <p className="mt-1 text-xs text-gray-400">基于对话策略结论生成的演示配置；不连接真实持仓或交易。</p>
            </div>
            <div className="inline-flex rounded-lg border border-[#2a2a2e] bg-[#111111] p-0.5 text-xs">
              <button onClick={() => setMode('current')} className={`rounded-md px-3 py-1.5 ${mode === 'current' ? 'bg-[#29292d] text-white' : 'text-gray-500 hover:text-gray-300'}`}>当前配置</button>
              <button onClick={() => setMode('edit')} className={`rounded-md px-3 py-1.5 ${mode === 'edit' ? 'bg-[#29292d] text-white' : 'text-gray-500 hover:text-gray-300'}`}>修改配置</button>
            </div>
          </header>

          <section className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            {[
              ['组合规模', formatAmount(portfolioSize), `可用现金 ${formatAmount(portfolioSize * values.cash / 100)}`], ['近 30 日收益', '+0.42%', '超基准 +8BP'],
              ['组合久期', `${activeDuration.toFixed(2)} 年`, mode === 'current' ? '当前持仓' : '可手动调整'], ['加权到期收益率', mode === 'current' ? '1.86%' : '1.89%', 'AAA 及以上 92%'],
            ].map(([label, value, meta], index) => <div key={label} className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-3.5"><div className="text-[11px] text-white">{label}</div><div className={`mt-2 font-mono text-xl font-semibold ${index === 1 ? 'text-red-400' : index === 2 ? 'text-amber-300' : 'text-[#82a6ff]'}`}>{value}</div><div className="mt-1.5 text-[11px] text-gray-400">{meta}</div></div>)}
          </section>

          <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
            <div className="flex items-center justify-between"><div><h2 className="text-sm font-medium text-gray-200">资产配置</h2><p className="mt-1 text-[11px] text-gray-500">{mode === 'edit' ? '直接修改比例，右侧风险提示将随之更新。' : '切换至修改配置后可调整资产比例。'}</p></div><span className={total === 100 ? 'text-[11px] text-gray-300' : 'text-[11px] text-red-400'}>合计 {total}%</span></div>
            <div className="mt-5 flex h-2 overflow-hidden rounded-full bg-[#252529]">{allocations.map((item) => <div key={item.id} className={item.color} style={{ width: `${values[item.id]}%` }} />)}</div>
            <div className="mt-5 space-y-3">{allocations.map((item) => <div key={item.id} className="grid grid-cols-[minmax(120px,1fr)_64px_74px_64px] items-center gap-2 text-xs"><div className="flex items-center gap-2 text-white"><span className={`h-2 w-2 rounded-sm ${item.color}`} />{item.label}</div>{mode === 'edit' ? <div className="relative"><input aria-label={`${item.label} 配置比例`} type="number" min="0" max="100" value={values[item.id]} onChange={(event) => change(item.id, Number(event.target.value))} className={`h-8 w-full rounded border border-[#3d3d42] bg-[#0d0d0d] pl-3 pr-5 text-center font-mono outline-none ${item.valueColor}`} /><span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-[11px] text-gray-500">%</span></div> : <span className={`text-right font-mono font-semibold ${item.valueColor}`}>{values[item.id]}%</span>}<span className="text-right font-mono text-[11px] text-gray-500">{formatAmount(portfolioSize * values[item.id] / 100)}</span><span className="text-right font-mono text-gray-500">{mode === 'edit' ? `${values[item.id] - item.current >= 0 ? '+' : ''}${values[item.id] - item.current}pct` : '—'}</span></div>)}</div>
          </section>

          {mode === 'edit' && <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4"><div className="flex flex-wrap items-end justify-between gap-3"><div className="flex flex-wrap gap-3"><label className="grid gap-1.5 text-xs text-gray-400">组合规模（万元）<input aria-label="组合规模（万元）" type="number" min="1" step="100" value={portfolioSize} onChange={(event) => { setPortfolioSize(Math.max(1, Number(event.target.value) || 1)); setNotice('') }} className="h-9 w-32 rounded border border-[#3d3d42] bg-[#0d0d0d] px-2 font-mono text-sm text-white outline-none" /></label><label className="grid gap-1.5 text-xs text-gray-400">目标久期（年）<input aria-label="目标久期" type="number" min="1" max="10" step="0.01" value={duration} onChange={(event) => { setDuration(Number(event.target.value)); setNotice('') }} className="h-9 w-28 rounded border border-[#3d3d42] bg-[#0d0d0d] px-2 font-mono text-sm text-white outline-none" /></label></div><div className="flex gap-2"><button onClick={reset} className="rounded-lg border border-[#3d3d42] px-3 py-2 text-xs text-gray-300 hover:bg-[#1b1b1d]">恢复 AI 建议</button><button onClick={save} className="rounded-lg bg-white px-3 py-2 text-xs font-medium text-black hover:bg-gray-200">保存方案草稿</button></div></div><p className="mt-3 text-[11px] text-gray-500">修改比例时优先以现金自动平衡；修改现金时，以利率债平衡，资产配置始终合计 100%。</p>{notice && <p className={`mt-2 text-xs ${valid ? 'text-emerald-200' : 'text-amber-200'}`}>{notice}</p>}</section>}

          <section className="overflow-hidden rounded-xl border border-[#2a2a2e] bg-[#111111]"><div className="border-b border-[#2a2a2e] px-4 py-3.5"><h2 className="text-sm font-medium text-gray-200">核心持仓</h2></div><div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead className="bg-[#0d0d0d] text-[11px] text-gray-300"><tr>{['债券', '类型', '权重', '收益率', '久期', 'AI 信号'].map((label) => <th key={label} className="px-4 py-2.5 font-medium">{label}</th>)}</tr></thead><tbody className="divide-y divide-[#252529]">{holdings.map(([code, name, type, weight, bondYield, holdingDuration, signal]) => <tr key={code}><td className="px-4 py-3"><div className="text-gray-200">{name}</div><div className="mt-0.5 font-mono text-[10px] text-gray-600">{code}</div></td><td className="px-4 py-3 text-gray-300">{type}</td><td className="px-4 py-3 text-[#82a6ff]">{weight}</td><td className="px-4 py-3 text-[#66cabb]">{bondYield}</td><td className="px-4 py-3 text-amber-300">{holdingDuration}</td><td className="px-4 py-3 text-gray-300">{signal}</td></tr>)}</tbody></table></div></section>
        </main>
      </div>

      <aside className="market-side-panel"><div className="space-y-4 p-4">
        <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4"><div className="flex items-center gap-2"><h2 className="text-sm font-medium text-gray-200">AI 配置依据</h2><span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-gray-500">Sentiment</span></div><div className="mt-4 space-y-3 text-xs leading-5 text-gray-400"><p><b className="text-white">资金面：</b>流动性维持宽松，短端收益率下行提供支撑。</p><p><b className="text-white">因子与信号：</b>公开市场操作与利率债久期信号偏多，但长端仍受供给约束。</p><p><b className="text-white">建议方向：</b>增配利率债和政策性金融债，降低高等级信用债与现金占比。</p></div><div className="mt-4 rounded-lg border border-[#353535] bg-[#0d0d0d] p-3 text-[11px] text-gray-500">来源：对话中的“政策驱动”策略结论</div></section>
        <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4"><div className="flex items-center justify-between"><h2 className="text-sm font-medium text-gray-200">AI 风险提示</h2><span className="text-[10px] text-gray-600">{risks.length} 项</span></div><div className="mt-3 space-y-3">{risks.map((risk) => <div key={risk.title} className="rounded-lg border border-[#303034] bg-[#0d0d0d] p-3"><div className="flex items-center gap-2"><span className={`rounded px-1.5 py-0.5 text-[10px] ${risk.level === '高' ? 'bg-red-500/15 text-red-300' : risk.level === '中' ? 'bg-amber-500/15 text-amber-200' : 'bg-emerald-500/15 text-emerald-200'}`}>{risk.level}风险</span><strong className="text-xs font-medium text-gray-200">{risk.title}</strong></div><p className="mt-2 text-[11px] leading-5 text-gray-400">{risk.detail}</p></div>)}</div><p className="mt-3 text-[10px] leading-4 text-gray-600">风险提示仅用于研究展示，不构成投资建议或自动交易指令。</p></section>
      </div></aside>
    </div>
  </div>
}
