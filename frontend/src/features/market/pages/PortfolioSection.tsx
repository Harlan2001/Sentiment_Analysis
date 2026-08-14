import React, { useState } from 'react'

type Mode = 'current' | 'suggested'

const allocations = [
  { label: '利率债', current: 48, suggested: 54, color: 'bg-[#6f8cff]', valueColor: 'text-[#82a6ff]' },
  { label: '政策性金融债', current: 27, suggested: 28, color: 'bg-[#4fb8a8]', valueColor: 'text-[#66cabb]' },
  { label: '高等级信用债', current: 18, suggested: 14, color: 'bg-[#d6a85f]', valueColor: 'text-amber-400' },
  { label: '现金', current: 7, suggested: 4, color: 'bg-[#77708f]', valueColor: 'text-[#a79bd0]' },
]

const maturities = [
  ['0–1年', 18, 'bg-[#5f7fe8]', 'text-[#7895f2]'], ['1–3年', 31, 'bg-[#6f8cff]', 'text-[#82a6ff]'],
  ['3–5年', 27, 'bg-[#4fb8a8]', 'text-[#66cabb]'], ['5–10年', 19, 'bg-[#d6a85f]', 'text-amber-400'],
  ['10年以上', 5, 'bg-[#8c79c6]', 'text-[#ad9be0]'],
] as const

const holdings = [
  ['230210', '23国开10', '政策金融债', '18.6%', '1.83%', '5.72', '增配'],
  ['240004', '24附息国债04', '国债', '16.2%', '1.71%', '7.36', '持有'],
  ['250205', '25国开05', '政策金融债', '13.5%', '1.66%', '3.84', '增配'],
  ['102481993', '24中电投MTN018', 'AAA信用债', '10.8%', '2.08%', '2.16', '减配'],
  ['240013', '24附息国债13', '国债', '9.4%', '1.54%', '4.91', '持有'],
] as const

const PortfolioSection: React.FC = () => {
  const [mode, setMode] = useState<Mode>('current')
  const [showPlan, setShowPlan] = useState(false)
  const [analysisTime, setAnalysisTime] = useState('09:42')

  const metrics = [
    ['组合规模', '1.28亿', '可用现金 896万'],
    ['近30日收益', '+0.42%', '超基准 +8BP'],
    ['组合久期', mode === 'current' ? '5.18年' : '4.92年', mode === 'current' ? '目标 4.5–5.0年' : '回到目标区间'],
    ['加权到期收益率', mode === 'current' ? '1.86%' : '1.89%', 'AAA及以上 92%'],
  ]

  return (
    <div className="market-workspace" style={{ position: 'absolute', inset: 0 }}>
      <div className="market-workspace-body">
        <div className="market-discover-panel">
          <main className="space-y-4 pb-4 pl-4 pr-px pt-2">
            <header className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-bold text-white">稳健型债券组合</h1>
                  <span className="rounded border border-[#343438] bg-[#191919] px-1.5 py-0.5 text-[10px] text-gray-300">演示数据</span>
                </div>
                <p className="mt-1 text-xs text-gray-300">组合净值与风险敞口 · 数据截至 2026-07-15</p>
              </div>
              <div className="inline-flex shrink-0 rounded-lg border border-[#2a2a2e] bg-[#111111] p-0.5 text-xs">
                <button onClick={() => setMode('current')} className={'rounded-md px-3 py-1.5 transition-colors ' + (mode === 'current' ? 'bg-[#29292d] text-white' : 'text-gray-500 hover:text-gray-300')}>当前持仓</button>
                <button onClick={() => setMode('suggested')} className={'rounded-md px-3 py-1.5 transition-colors ' + (mode === 'suggested' ? 'bg-[#29292d] text-white' : 'text-gray-500 hover:text-gray-300')}>AI 建议</button>
              </div>
            </header>

            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              {metrics.map(([label, value, meta], index) => (
                <div key={label} className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-3.5">
                  <div className="text-[11px] font-medium text-white">{label}</div>
                  <div className={'mt-2 font-mono text-xl font-semibold tracking-tight ' + (index === 1 ? 'text-red-400' : index === 2 ? 'text-[#e2b86b]' : index === 3 ? 'text-[#82a6ff]' : 'text-[#7dd3fc]')}>{value}</div>
                  <div className="mt-1.5 text-[11px] text-gray-400">{meta}</div>
                </div>
              ))}
            </div>

            <div className="grid gap-4 xl:grid-cols-[1.08fr_.92fr]">
              <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-medium text-gray-200">资产配置</h2>
                  <span className="text-[11px] text-gray-300">合计 100%</span>
                </div>
                <div className="mt-5 flex h-2 overflow-hidden rounded-full bg-[#252529]">
                  {allocations.map(item => <div key={item.label} className={item.color} style={{ width: item[mode] + '%' }} />)}
                </div>
                <div className="mt-5 space-y-3">
                  {allocations.map(item => {
                    const delta = item.suggested - item.current
                    return (
                      <div key={item.label} className="grid grid-cols-[1fr_48px_52px] items-center gap-2 text-xs">
                        <div className="flex items-center gap-2 text-white"><span className={'h-2 w-2 rounded-sm ' + item.color} />{item.label}</div>
                        <span className={"text-right font-mono font-semibold " + item.valueColor}>{item[mode]}%</span>
                        <span className={'text-right font-mono ' + (mode === 'suggested' ? (delta > 0 ? 'text-red-400' : 'text-green-400') : 'text-gray-600')}>
                          {mode === 'suggested' ? (delta > 0 ? '+' : '') + delta + 'pct' : '—'}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </section>

              <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
                <div className="flex items-center justify-between"><h2 className="text-sm font-medium text-gray-200">期限分布</h2><span className="text-[11px] text-gray-600">按市值</span></div>
                <div className="mt-5 flex h-[136px] items-end justify-between gap-3 border-b border-[#2a2a2e] px-1">
                  {maturities.map(([label, value, color, textColor]) => (
                    <div key={label} className="flex h-full flex-1 flex-col items-center justify-end">
                      <span className={"mb-2 font-mono text-[11px] font-semibold " + textColor}>{value}%</span>
                      <div className={'w-full max-w-9 rounded-t opacity-90 ' + color} style={{ height: value * 2.5 + 'px' }} />
                    </div>
                  ))}
                </div>
                <div className="mt-2 grid grid-cols-5 gap-2 text-center text-[10px] text-gray-300">{maturities.map(([label]) => <span key={label}>{label}</span>)}</div>
              </section>
            </div>

            <section className="overflow-hidden rounded-xl border border-[#2a2a2e] bg-[#111111]">
              <div className="flex items-center justify-between border-b border-[#2a2a2e] px-4 py-3.5">
                <div><h2 className="text-sm font-medium text-gray-200">核心持仓</h2><p className="mt-0.5 text-[11px] text-gray-400">按市值权重排序 · 前五大持仓占比 68.5%</p></div>
                <button className="text-xs text-gray-300 hover:text-white">查看全部 12 只 →</button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[650px] text-left text-xs">
                  <thead className="bg-[#0d0d0d] text-[11px] text-gray-300"><tr>
                    <th className="py-2.5 pl-4 pr-3 font-medium">债券</th>
                    <th className="px-3 py-2.5 font-medium">类型</th>
                    {['权重', '收益率', '久期', 'AI 信号'].map(label => <th key={label} className="px-3 py-2.5 text-right font-medium">{label}</th>)}
                  </tr></thead>
                  <tbody className="divide-y divide-[#252529]">
                    {holdings.map(([code, name, type, weight, bondYield, duration, signal]) => (
                      <tr key={code} className="transition-colors hover:bg-[#151515]">
                        <td className="py-3 pl-4 pr-3"><div className="font-medium text-gray-200">{name}</div><div className="mt-0.5 font-mono text-[10px] text-gray-600">{code}</div></td>
                        <td className="px-3 py-3 text-gray-300">{type}</td>
                        <td className="px-3 py-3 text-right font-mono font-semibold text-[#82a6ff]">{weight}</td>
                        <td className="px-3 py-3 text-right font-mono text-[#66cabb]">{bondYield}</td>
                        <td className="px-3 py-3 text-right font-mono text-amber-400">{duration}</td>
                        <td className="px-4 py-3 text-right"><span className={'rounded px-1.5 py-1 text-[10px] ' + (signal === '增配' ? 'bg-red-500/10 text-red-400' : signal === '减配' ? 'bg-green-500/10 text-green-400' : 'bg-white/5 text-gray-300')}>{signal}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </main>
        </div>

        <aside className="market-side-panel">
          <div className="space-y-4 p-4">
            <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
              <div className="flex items-start justify-between gap-2">
                <div><div className="flex items-center gap-2"><h2 className="text-sm font-medium text-gray-200">AI 组合解读</h2><span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-gray-500">Sentiment</span></div><p className="mt-1 text-[11px] text-gray-400">市场、因子、预测与策略信号</p></div>
                <button onClick={() => setAnalysisTime(new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }))} className="shrink-0 rounded-lg border border-[#2a2a2e] px-2 py-1.5 text-[10px] text-gray-500 hover:bg-[#191919] hover:text-white">重新分析</button>
              </div>
              <div className="mt-4 rounded-lg border border-[#2a2a2e] bg-[#0d0d0d] p-3.5">
                <div className="flex items-center gap-2 text-xs text-gray-300"><span className="h-1.5 w-1.5 rounded-full bg-amber-400" />当前判断：中性偏多</div>
                <p className="mt-2 text-xs leading-6 text-gray-300">长端收益率小幅下行，宽松预期仍有支撑，但组合久期已高于目标中枢。建议增配 3–5 年政策性金融债，同时降低高等级信用债和现金占比。</p>
              </div>
              <div className="mt-3 flex justify-between text-[10px] text-gray-400"><span>分析时间 {analysisTime}</span><span>置信度 78%</span></div>
            </section>

            <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
              <div className="flex items-center justify-between"><h2 className="text-sm font-medium text-gray-200">市场上下文</h2><span className="text-[10px] text-gray-600">近5日</span></div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                {[
                  ['10Y 国债', '1.710%', '↓ -1BP'], ['10Y–2Y', '0.45%', '曲线偏陡'], ['新闻情绪', '中性', '多空对冲'], ['月度预测', '35%', '收益率上行'],
                ].map(([label, value, change], index) => (
                  <div key={label} className="rounded-lg border border-[#252529] bg-[#0d0d0d] p-3"><div className="text-[10px] font-medium text-gray-200">{label}</div><div className={"mt-1.5 font-mono text-sm font-semibold " + (index === 0 ? "text-green-400" : index === 1 ? "text-amber-400" : index === 3 ? "text-[#82a6ff]" : "text-white")}>{value}</div><div className={'mt-1 text-[10px] ' + (index === 0 ? 'text-green-400' : 'text-gray-600')}>{change}</div></div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">{['流动性宽松', '基本面分化', '避险需求', '长端震荡'].map(tag => <span key={tag} className="rounded-md border border-[#2a2a2e] px-2 py-1 text-[10px] text-gray-300">{tag}</span>)}</div>
            </section>

            <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
              <div className="flex items-center justify-between"><h2 className="text-sm font-medium text-gray-200">风险提示</h2><span className="text-[10px] text-gray-600">2 项</span></div>
              <div className="mt-3 space-y-2">
                {[
                  ['中', '组合久期高于目标中枢', '当前 5.18 年，建议回落至 4.8–5.0 年'],
                  ['低', '单券集中度接近上限', '23国开10 距 20% 上限 1.4pct'],
                ].map(([level, title, detail], index) => (
                  <div key={title} className="flex gap-3 rounded-lg border border-[#252529] bg-[#0d0d0d] p-3">
                    <span className={'flex h-5 w-5 shrink-0 items-center justify-center rounded border text-[10px] ' + (index === 0 ? 'border-amber-500/30 bg-amber-500/10 text-amber-400' : 'border-white/10 bg-white/5 text-gray-300')}>{level}</span>
                    <div><div className="text-xs text-gray-300">{title}</div><p className="mt-1 text-[10px] leading-5 text-gray-400">{detail}</p></div>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
              <div className="flex items-center justify-between"><div><h2 className="text-sm font-medium text-gray-200">再平衡建议</h2><p className="mt-1 text-[11px] text-gray-400">预计提升到期收益率 3BP</p></div><span className="font-mono text-sm text-red-400">4 笔</span></div>
              <button onClick={() => setShowPlan(value => !value)} className="mt-4 w-full rounded-lg border border-[#3a3a3e] bg-[#1a1a1d] py-2 text-xs text-gray-200 transition-colors hover:bg-[#242428]">{showPlan ? '收起调整方案' : '查看调整方案'}</button>
              {showPlan && <div className="mt-3 space-y-2 border-t border-[#2a2a2e] pt-3 text-[11px]">
                <div className="flex justify-between"><span className="text-gray-200">增持 25国开05</span><span className="font-mono text-red-400">+600万</span></div>
                <div className="flex justify-between"><span className="text-gray-200">减持 24中电投MTN018</span><span className="font-mono text-green-400">-400万</span></div>
                <div className="flex justify-between"><span className="text-gray-200">压降现金头寸</span><span className="font-mono text-green-400">-200万</span></div>
              </div>}
            </section>
          </div>
        </aside>
      </div>
    </div>
  )
}

export default PortfolioSection
