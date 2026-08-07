import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

type ModuleKey = '全部' | '研报生成' | '策略开发' | '每日新闻总结'

const rows = [
  { id: 'news', module: '每日新闻总结', title: '8 月 6 日每日债券新闻总结', description: '汇总 86 条新闻，识别 12 个重要事件', source: '自动计划', result: '新闻总结_0806.md', status: '完成', updated: '09:02', needsAction: false },
  { id: 'report', module: '研报生成', title: '8 月 6 日债券市场日报', description: '部分行情数据待确认，确认后继续生成', source: '研报生成', result: '缺少输入', status: '待确认', updated: '10:20', needsAction: true },
  { id: 'strategy', module: '策略开发', title: '国债期货趋势策略', description: '策略提示词草稿已经生成，等待用户确认', source: '用户生成', result: '等待确认', status: '待确认', updated: '10:06', needsAction: true },
  { id: 'backtest', module: '策略开发', title: '利率债动量与期限利差策略', description: '正在运行样本外回测', source: '用户生成', result: '运行中 · 68%', status: '运行中', updated: '09:36', needsAction: false },
  { id: 'spread', module: '研报生成', title: '信用债利差跟踪周报', description: '报告及数据附件已经生成', source: '研报生成', result: '信用利差周报.pdf', status: '完成', updated: '昨天', needsAction: false },
] as const

const tabRoutes: Record<Exclude<ModuleKey, '全部'>, string> = {
  '研报生成': '/computer/reports',
  '策略开发': '/computer/strategies',
  '每日新闻总结': '/computer/news',
}

export function ComputerPage() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<ModuleKey>('全部')
  const [needsActionOnly, setNeedsActionOnly] = useState(false)
  const [view, setView] = useState('会话与文档')

  const visibleRows = useMemo(() => rows.filter((row) => {
    const matchesTab = activeTab === '全部' || row.module === activeTab
    return matchesTab && (!needsActionOnly || row.needsAction)
  }), [activeTab, needsActionOnly])

  function selectTab(tab: ModuleKey) {
    setActiveTab(tab)
    if (tab !== '全部') navigate(tabRoutes[tab])
  }

  return (
    <section className="computer-page">
      <div className="computer-tabs">
        {(['全部', '研报生成', '策略开发', '每日新闻总结'] as ModuleKey[]).map((tab) => (
          <button className={activeTab === tab ? 'active' : ''} onClick={() => selectTab(tab)} key={tab}>{tab}</button>
        ))}
        <span className="computer-spacer" />
        <button className="computer-button">计划管理</button>
        <button className="computer-button primary">＋ 立即生成</button>
      </div>

      <div className="computer-toolbar">
        <button className="computer-chip dropdown-chip">状态：全部<i className="inline-caret" aria-hidden="true" /></button>
        <button className="computer-chip dropdown-chip">来源：全部<i className="inline-caret" aria-hidden="true" /></button>
        <button className={'computer-chip ' + (needsActionOnly ? 'selected' : '')} onClick={() => setNeedsActionOnly((value) => !value)}>仅未读</button>
        <button className="computer-chip">▣ 2026-08-06</button>
        <button className="computer-chip">已归档</button>
        <span className="computer-spacer" />
        <span className="computer-count">{visibleRows.length} 段会话</span>
      </div>

      <section className="computer-attention">
        <div className="computer-attention-head"><strong>需要处理 · 1</strong><span>⌃</span></div>
        <div className="computer-attention-row">
          <span className="attention-dot" />
          <div><strong>8 月 6 日债券市场日报</strong><small>部分行情数据待确认，确认后继续生成</small></div>
          <span className="computer-badge warning">缺少输入</span>
          <button className="computer-button primary">补充数据</button>
          <time>10:20</time>
        </div>
      </section>

      <div className="computer-list-head">
        <div><strong>2026 年 8 月 6 日</strong><span>· {visibleRows.length} 段会话</span></div>
        <div className="computer-view-switch">
          {['会话与文档', '仅会话', '仅文档'].map((item) => <button className={view === item ? 'active' : ''} onClick={() => setView(item)} key={item}>{item}</button>)}
        </div>
      </div>

      <div className="computer-table-wrap">
        <table className="computer-table">
          <thead><tr><th /><th>任务会话</th><th>来源/类型</th><th>状态或结果</th><th>更新时间</th></tr></thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr key={row.id}>
                <td><span className={'computer-status ' + (row.status === '完成' ? 'done' : row.status === '运行中' ? 'running' : 'waiting')}>{row.status === '完成' ? '✓' : row.status === '运行中' ? '◐' : '●'}</span></td>
                <td><strong>{row.title}</strong><small>{row.description}</small>{row.status === '运行中' && <span className="computer-progress"><i /></span>}</td>
                <td>{row.source}</td>
                <td><span className={'computer-badge ' + (row.status === '完成' ? 'file' : row.status === '运行中' ? 'running' : 'warning')}>{row.result}</span></td>
                <td><time>{row.updated}</time></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}