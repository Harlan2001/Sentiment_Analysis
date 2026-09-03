import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

type DemoWorkflow = { title: string; description: string; category: string }
type DemoTask = { id: number; title: string; source: string; status: 'pending' | 'succeeded'; updatedAt: string; detail: string }

export const DEMO_WORKFLOWS: Record<string, DemoWorkflow> = {
  financials: { title: '财报解读', description: '提取财务变化、经营指标与风险点', category: '研究分析' },
  macro: { title: '宏观数据解读', description: '跟踪宏观数据发布及市场影响', category: '研究分析' },
  valuation: { title: '债券估值跟踪', description: '观察收益率、利差与估值变化', category: '研究分析' },
  credit: { title: '信用风险扫描', description: '识别发行人与债券的风险信号', category: '风险管理' },
  issuer: { title: '发行人画像', description: '汇总主体基本面与信用信息', category: '风险管理' },
  industry: { title: '行业比较', description: '横向比较行业景气度与信用表现', category: '研究分析' },
  rates: { title: '利率情景推演', description: '评估利率路径下的市场情景', category: '策略与决策' },
  portfolio: { title: '组合诊断', description: '检查组合风险、久期与暴露', category: '策略与决策' },
  backtest: { title: '回测分析', description: '验证策略表现及关键归因', category: '策略与决策' },
  announcements: { title: '公告解读', description: '自动归纳公告要点与影响', category: '信息处理' },
  sentiment: { title: '舆情监控', description: '追踪主体与行业相关的舆情变化', category: '风险管理' },
  briefing: { title: '每日简报', description: '汇总每日市场变化与待关注事项', category: '信息处理' },
  automation: { title: '工作流编排', description: '组合多个能力并按计划自动执行', category: '自动化' },
}

function initialTasks(workflow: DemoWorkflow): DemoTask[] {
  return [
    { id: 1, title: `${workflow.title}任务`, source: '全部来源', status: 'pending', updatedAt: '刚刚', detail: '等待确认处理范围' },
    { id: 2, title: `${workflow.title}任务`, source: '演示数据', status: 'succeeded', updatedAt: '08/24 14:20', detail: workflow.description },
    { id: 3, title: `${workflow.title}任务`, source: '演示数据', status: 'succeeded', updatedAt: '08/22 10:16', detail: '已生成分析结果与重点摘要' },
  ]
}

export function WorkflowDemoPage() {
  const { workflowId = '' } = useParams()
  const workflow = DEMO_WORKFLOWS[workflowId] || DEMO_WORKFLOWS.financials
  const [tasks, setTasks] = useState(() => initialTasks(workflow))
  const [status, setStatus] = useState<'all' | DemoTask['status']>('all')
  const [draft, setDraft] = useState('')
  const [refreshMark, setRefreshMark] = useState('')

  useEffect(() => {
    setTasks(initialTasks(workflow))
    setStatus('all')
    setDraft('')
    setRefreshMark('')
  }, [workflowId])

  const active = tasks.filter((task) => task.status === 'pending')
  const history = useMemo(() => tasks.filter((task) => task.status !== 'pending' && (status === 'all' || task.status === status)), [status, tasks])

  function submit(event: FormEvent) {
    event.preventDefault()
    const detail = draft.trim() || `请生成${workflow.title}的重点结论`
    setTasks((current) => [{ id: Date.now(), title: `${workflow.title}任务`, source: '全部来源', status: 'pending', updatedAt: '刚刚', detail }, ...current])
    setDraft('')
  }

  return <section className="computer-page daily-news-page workflow-demo-page">
    <div className="computer-toolbar daily-news-history-toolbar">
      <button className={'computer-chip ' + (status === 'all' ? 'selected' : '')} onClick={() => setStatus('all')}>状态：全部</button>
      <button className={'computer-chip ' + (status === 'succeeded' ? 'selected' : '')} onClick={() => setStatus('succeeded')}>仅成功</button>
      <button className="computer-chip">来源：全部</button>
      <button className="computer-chip">日期</button>
      <span className="computer-spacer" />
      <button className="computer-button" onClick={() => setRefreshMark('已刷新')}>刷新</button>
      <button className="computer-button primary" onClick={() => document.getElementById('workflow-demo-input')?.focus()}>＋ 立即生成</button>
      <span className="computer-count">{refreshMark || `${history.length} 条历史记录`}</span>
    </div>

    <p className="workflow-demo-note">{workflow.category} · {workflow.description}。当前为前端演示数据，后续可直接接入真实任务服务。</p>

    <section className="computer-attention">
      <div className="computer-attention-head"><strong>需要处理 · {active.length}</strong><span aria-hidden="true">⌃</span></div>
      {!active.length ? <div className="computer-attention-row daily-news-empty-row"><span className="attention-dot" /><div><strong>当前没有需要处理的{workflow.title}</strong><small>创建新任务后会显示在这里。</small></div></div> : active.map((task) => (
        <div className="computer-attention-row" key={task.id}>
          <span className="attention-dot running daily-news-pulse" />
          <div><strong>{task.title}</strong><small>{task.detail}</small><span className="computer-progress"><i /></span></div>
          <span className="computer-badge running">待确认</span><button className="computer-button">查看状态</button><time>{task.updatedAt}</time>
        </div>
      ))}
    </section>

    <div className="computer-list-head"><div><strong>历史{workflow.title}</strong><span>· {history.length} 条处理记录</span></div></div>
    <div className="computer-table-wrap"><table className="computer-table"><thead><tr><th /><th>处理任务</th><th>数据来源</th><th>状态或结果</th><th>更新时间</th><th /></tr></thead><tbody>
      {!history.length ? <tr><td colSpan={6} className="daily-news-table-state">暂无符合条件的历史记录</td></tr> : history.map((task) => <tr key={task.id} className="daily-news-history-row"><td><span className="computer-status done">✓</span></td><td><strong>{task.title}</strong><small>{task.detail}</small></td><td>{task.source}</td><td><span className="computer-badge file">处理完成</span></td><td><time>{task.updatedAt}</time></td><td /></tr>)}
    </tbody></table></div>

    <form className="report-composer daily-news-composer" onSubmit={submit}>
      <textarea id="workflow-demo-input" value={draft} maxLength={1000} onChange={(event) => setDraft(event.target.value)} placeholder={`输入本次${workflow.title}的关注重点`} rows={2} />
      <div className="daily-news-composer-controls"><button type="button" className="computer-chip selected">全部来源</button><span className="computer-badge">前端演示任务</span><button className="report-send" aria-label={`生成${workflow.title}`}>→</button></div>
    </form>
  </section>
}
