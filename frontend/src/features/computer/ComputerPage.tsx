import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ComputerTask, getComputerTasks } from '@/api/workbench'

type WorkflowModule = {
  id: string
  title: string
  description: string
  category: string
  icon: string
  to?: string
}

const WORKFLOW_MODULES: WorkflowModule[] = [
  { id: 'reports', title: '研报分析', description: '上传、解析并提炼研报核心观点', category: '研究分析', icon: 'PDF', to: '/computer/reports' },
  { id: 'strategy', title: '策略生成', description: '从投资观点生成策略草案与代码', category: '策略与决策', icon: 'STR', to: '/computer/strategies' },
  { id: 'news', title: '新闻总结', description: '聚合市场新闻与重要事件', category: '信息处理', icon: 'NEWS', to: '/computer/news' },
  { id: 'financials', title: '财报解读', description: '提取财务变化、经营指标与风险点', category: '研究分析', icon: 'FIN' },
  { id: 'macro', title: '宏观数据解读', description: '跟踪宏观数据发布及市场影响', category: '研究分析', icon: 'MAC' },
  { id: 'valuation', title: '债券估值跟踪', description: '观察收益率、利差与估值变化', category: '研究分析', icon: 'VAL' },
  { id: 'credit', title: '信用风险扫描', description: '识别发行人和债券的风险信号', category: '风险管理', icon: 'RISK' },
  { id: 'issuer', title: '发行人画像', description: '汇总主体基本面与信用信息', category: '风险管理', icon: 'ISS' },
  { id: 'industry', title: '行业比较', description: '横向比较行业景气度与信用表现', category: '研究分析', icon: 'IND' },
  { id: 'rates', title: '利率情景推演', description: '评估利率路径下的市场情景', category: '策略与决策', icon: 'RATE' },
  { id: 'portfolio', title: '组合诊断', description: '检查组合风险、久期与暴露', category: '策略与决策', icon: 'PORT' },
  { id: 'backtest', title: '回测分析', description: '验证策略表现及关键归因', category: '策略与决策', icon: 'BT' },
  { id: 'announcements', title: '公告解读', description: '自动归纳公告要点与影响', category: '信息处理', icon: 'DOC' },
  { id: 'sentiment', title: '舆情监控', description: '追踪主体与行业相关的舆情变化', category: '风险管理', icon: 'MON' },
  { id: 'briefing', title: '每日简报', description: '汇总每日市场变化与待关注事项', category: '信息处理', icon: 'DAY' },
  { id: 'automation', title: '工作流编排', description: '组合多个能力并按计划自动执行', category: '自动化', icon: 'FLOW' },
]

function formatTime(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  const now = new Date()
  if (date.toDateString() === now.toDateString()) {
    return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }).format(date)
  }
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' }).format(date)
}

function taskTone(task: ComputerTask) {
  if (task.status === 'failed') return 'failed'
  if (task.status === 'completed' || task.status === 'succeeded') return 'done'
  if (task.needs_action || task.status === 'pending_confirmation') return 'attention'
  return 'running'
}

export function ComputerPage() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<ComputerTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadTasks = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getComputerTasks()
      setTasks(data.items)
      setError('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '读取工作流任务失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadTasks()
  }, [loadTasks])

  function openTask(task: ComputerTask) {
    const [, rawId] = task.task_id.split(':', 2)
    if (!rawId) return
    if (task.task_type === 'report_generation') navigate(`/computer/reports/${rawId}`)
    else if (task.task_type === 'strategy') navigate(`/computer/strategies/prompt?id=${rawId}`)
    else navigate(`/computer/news?task=${rawId}`)
  }

  const pendingTasks = tasks.filter((task) =>
    task.needs_action || ['pending', 'queued', 'running', 'pending_confirmation', 'failed'].includes(task.status),
  )
  const historyTasks = tasks.filter((task) => !pendingTasks.some((item) => item.task_id === task.task_id))

  return (
    <section className="workflow-page">
      <div className="workflow-layout">
        <main className="workflow-main">
          <header className="workflow-head">
            <div>
              <p className="workflow-eyebrow">智能工作台</p>
              <h1>选择一个能力开始工作</h1>
              <p>研报、策略与信息处理能力集中在这里；更多能力将持续开放。</p>
            </div>
            <span className="workflow-module-count">{WORKFLOW_MODULES.length} 个能力</span>
          </header>

          <div className="workflow-module-grid" aria-label="工作流能力">
            {WORKFLOW_MODULES.map((module) => (
              <article className={`workflow-module-card${module.to ? ' available' : ''}`} key={module.id}>
                <div className="workflow-module-card-head">
                  <span className="workflow-module-icon" aria-hidden="true">{module.icon}</span>
                  <span className={`workflow-module-state${module.to ? ' active' : ''}`}>{module.to ? '可使用' : '即将开放'}</span>
                </div>
                <div className="workflow-module-card-body">
                  <small>{module.category}</small>
                  <h2>{module.title}</h2>
                  <p>{module.description}</p>
                </div>
                {module.to ? (
                  <button type="button" onClick={() => navigate(module.to!)}>打开 <span aria-hidden="true">→</span></button>
                ) : (
                  <span className="workflow-module-placeholder">规划中</span>
                )}
              </article>
            ))}
          </div>
        </main>

        <aside className="workflow-task-rail" aria-label="任务中心">
          <header className="workflow-task-head">
            <div>
              <h2>任务中心</h2>
              <p>工作流内的全部任务</p>
            </div>
            <button type="button" onClick={() => void loadTasks()} disabled={loading} aria-label="刷新任务中心">↻</button>
          </header>

          <div className="workflow-task-summary">
            <span>待处理</span>
            <strong>{pendingTasks.length}</strong>
            <small>共 {tasks.length} 个任务</small>
          </div>

          {error && <div className="workflow-task-error">{error}<button type="button" onClick={() => void loadTasks()}>重试</button></div>}

          {loading ? <p className="workflow-task-empty">正在读取任务…</p> : tasks.length === 0 ? (
            <p className="workflow-task-empty">暂无任务。创建研报、策略或新闻总结任务后，会统一显示在这里。</p>
          ) : <div className="workflow-task-groups">
            <section className="workflow-task-group" aria-labelledby="pending-tasks-title">
              <div className="workflow-task-group-head"><h3 id="pending-tasks-title">需要处理</h3><span>{pendingTasks.length}</span></div>
              <div className="workflow-task-list">
                {pendingTasks.length === 0 ? <p className="workflow-task-empty compact">当前没有需要处理的任务</p> : pendingTasks.map((task) => (
                  <button className="workflow-task-row" type="button" key={task.task_id} onClick={() => openTask(task)}>
                    <span className={`workflow-task-dot ${taskTone(task)}`} aria-hidden="true" />
                    <span className="workflow-task-copy"><strong>{task.title}</strong><small>{task.module}</small></span>
                    <span className="workflow-task-meta"><em className={taskTone(task)}>{task.status_label}</em><time>{formatTime(task.updated_at)}</time></span>
                  </button>
                ))}
              </div>
            </section>
            <section className="workflow-task-group" aria-labelledby="history-tasks-title">
              <div className="workflow-task-group-head"><h3 id="history-tasks-title">历史记录</h3><span>{historyTasks.length}</span></div>
              <div className="workflow-task-list">
                {historyTasks.length === 0 ? <p className="workflow-task-empty compact">暂无历史记录</p> : historyTasks.map((task) => (
                  <button className="workflow-task-row" type="button" key={task.task_id} onClick={() => openTask(task)}>
                    <span className={`workflow-task-dot ${taskTone(task)}`} aria-hidden="true" />
                    <span className="workflow-task-copy"><strong>{task.title}</strong><small>{task.module}</small></span>
                    <span className="workflow-task-meta"><em className={taskTone(task)}>{task.status_label}</em><time>{formatTime(task.updated_at)}</time></span>
                  </button>
                ))}
              </div>
            </section>
          </div>}
        </aside>
      </div>
    </section>
  )
}
