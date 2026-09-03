import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { WorkflowTask, getWorkflowTasks } from '@/api/workbench'
import { WorkflowDatePicker } from '../components/WorkflowDatePicker'

type WorkflowModule = {
  id: string
  title: string
  description: string
  category: string
  to?: string
  taskTypes?: WorkflowTask['task_type'][]
}

const WORKFLOW_MODULES: WorkflowModule[] = [
  { id: 'reports', title: '研报分析', description: '上传、解析并提炼研报核心观点', category: '研究分析', to: '/computer/reports', taskTypes: ['report_generation'] },
  { id: 'strategy', title: '策略生成', description: '从投资观点生成策略草案与代码', category: '策略与决策', to: '/computer/strategies', taskTypes: ['strategy'] },
  { id: 'news', title: '新闻总结', description: '聚合市场新闻与重要事件', category: '信息处理', to: '/computer/news', taskTypes: ['daily_news'] },
  { id: 'financials', title: '财报解读', description: '提取财务变化、经营指标与风险点', category: '研究分析', to: '/computer/demo/financials' },
  { id: 'macro', title: '宏观数据解读', description: '跟踪宏观数据发布及市场影响', category: '研究分析', to: '/computer/demo/macro' },
  { id: 'valuation', title: '债券估值跟踪', description: '观察收益率、利差与估值变化', category: '研究分析', to: '/computer/demo/valuation' },
  { id: 'credit', title: '信用风险扫描', description: '识别发行人和债券的风险信号', category: '风险管理', to: '/computer/demo/credit' },
  { id: 'issuer', title: '发行人画像', description: '汇总主体基本面与信用信息', category: '风险管理', to: '/computer/demo/issuer' },
  { id: 'industry', title: '行业比较', description: '横向比较行业景气度与信用表现', category: '研究分析', to: '/computer/demo/industry' },
  { id: 'rates', title: '利率情景推演', description: '评估利率路径下的市场情景', category: '策略与决策', to: '/computer/demo/rates' },
  { id: 'portfolio', title: '组合诊断', description: '检查组合风险、久期与暴露', category: '策略与决策', to: '/computer/demo/portfolio' },
  { id: 'backtest', title: '回测分析', description: '验证策略表现及关键归因', category: '策略与决策', to: '/computer/demo/backtest' },
  { id: 'announcements', title: '公告解读', description: '自动归纳公告要点与影响', category: '信息处理', to: '/computer/demo/announcements' },
  { id: 'sentiment', title: '舆情监控', description: '追踪主体与行业相关的舆情变化', category: '风险管理', to: '/computer/demo/sentiment' },
  { id: 'briefing', title: '每日简报', description: '汇总每日市场变化与待关注事项', category: '信息处理', to: '/computer/demo/briefing' },
  { id: 'automation', title: '工作流编排', description: '组合多个能力并按计划自动执行', category: '自动化', to: '/computer/demo/automation' },
]

const MODULES_PER_PAGE = 8

function formatTime(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  const now = new Date()
  if (date.toDateString() === now.toDateString()) {
    return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }).format(date)
  }
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' }).format(date)
}

function taskTone(task: WorkflowTask) {
  if (task.status === 'failed') return 'failed'
  if (task.status === 'completed' || task.status === 'succeeded') return 'done'
  if (task.needs_action || task.status === 'pending_confirmation') return 'attention'
  return 'running'
}

function taskDate(task: WorkflowTask) {
  if (task.date) return task.date
  const date = new Date(task.updated_at)
  return Number.isNaN(date.getTime()) ? '未知日期' : date.toISOString().slice(0, 10)
}

export function WorkflowHomePage() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<WorkflowTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modulePage, setModulePage] = useState(0)
  const [sourceFilter, setSourceFilter] = useState('all')
  const [sourceFilterOpen, setSourceFilterOpen] = useState(false)
  const [selectedDate, setSelectedDate] = useState('')
  const sourceFilterRef = useRef<HTMLDivElement>(null)

  const loadTasks = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getWorkflowTasks()
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

  useEffect(() => {
    const closeSourceFilter = (event: MouseEvent) => {
      if (sourceFilterRef.current && !sourceFilterRef.current.contains(event.target as Node)) setSourceFilterOpen(false)
    }
    if (sourceFilterOpen) document.addEventListener('mousedown', closeSourceFilter)
    return () => document.removeEventListener('mousedown', closeSourceFilter)
  }, [sourceFilterOpen])

  function openTask(task: WorkflowTask) {
    const [, rawId] = task.task_id.split(':', 2)
    if (!rawId) return
    if (task.task_type === 'report_generation') navigate(`/computer/reports/${rawId}`)
    else if (task.task_type === 'strategy') navigate(`/computer/strategies/prompt?id=${rawId}`)
    else navigate(`/computer/news?task=${rawId}`)
  }

  const selectedSource = WORKFLOW_MODULES.find((module) => module.id === sourceFilter)
  const filteredTasks = tasks.filter((task) =>
    (sourceFilter === 'all' || selectedSource?.taskTypes?.includes(task.task_type) === true) && (!selectedDate || taskDate(task) === selectedDate),
  )
  const pendingTasks = filteredTasks.filter((task) =>
    task.needs_action || ['pending', 'queued', 'running', 'pending_confirmation', 'failed'].includes(task.status),
  ).sort((a, b) => b.updated_at.localeCompare(a.updated_at))
  const historyTasks = filteredTasks.filter((task) => !pendingTasks.some((item) => item.task_id === task.task_id))
  const historyByDate = new Map<string, WorkflowTask[]>()
  for (const task of historyTasks) {
    const date = taskDate(task)
    const group = historyByDate.get(date) || []
    group.push(task)
    historyByDate.set(date, group)
  }
  const historyDateGroups = [...historyByDate.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .slice(0, 3)
    .map(([date, dateTasks]) => [date, dateTasks.sort((a, b) => b.updated_at.localeCompare(a.updated_at))] as const)
  const modulePageCount = Math.ceil(WORKFLOW_MODULES.length / MODULES_PER_PAGE)
  const visibleModules = WORKFLOW_MODULES.slice(modulePage * MODULES_PER_PAGE, (modulePage + 1) * MODULES_PER_PAGE)

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
            {visibleModules.map((module) => (
              <article className={`workflow-module-card${module.to ? ' available' : ''}`} key={module.id} role={module.to ? 'button' : undefined} tabIndex={module.to ? 0 : undefined} onClick={() => module.to && navigate(module.to)} onKeyDown={(event) => {
                if (module.to && (event.key === 'Enter' || event.key === ' ')) {
                  event.preventDefault()
                  navigate(module.to)
                }
              }}>
                <div className="workflow-module-card-body">
                  <small>{module.category}</small>
                  <h2>{module.title}</h2>
                  <p>{module.description}</p>
                </div>
              </article>
            ))}
          </div>
          {modulePageCount > 1 && <nav className="workflow-module-pagination" aria-label="工作流模块分页">
            <button type="button" onClick={() => setModulePage((current) => Math.max(0, current - 1))} disabled={modulePage === 0}>← 上一页</button>
            <span>{modulePage + 1} / {modulePageCount}</span>
            <button type="button" onClick={() => setModulePage((current) => Math.min(modulePageCount - 1, current + 1))} disabled={modulePage === modulePageCount - 1}>下一页 →</button>
          </nav>}
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
            <small>共 {filteredTasks.length} 个任务</small>
          </div>

          <div className="workflow-task-filters" aria-label="任务筛选">
            <div className="workflow-source-dropdown" ref={sourceFilterRef}>
              <button type="button" className={`computer-chip workflow-source-trigger${sourceFilter !== 'all' ? ' selected' : ''}`} onClick={() => setSourceFilterOpen((current) => !current)} aria-expanded={sourceFilterOpen} aria-haspopup="listbox">
                来源：{selectedSource?.title || '全部'} <span className="workflow-source-caret" aria-hidden="true" />
              </button>
              {sourceFilterOpen && <div className="workflow-source-menu" role="listbox" aria-label="来源筛选">
                <button type="button" role="option" aria-selected={sourceFilter === 'all'} className={sourceFilter === 'all' ? 'selected' : ''} onClick={() => { setSourceFilter('all'); setSourceFilterOpen(false) }}>全部</button>
                {WORKFLOW_MODULES.map((module) => <button type="button" role="option" aria-selected={sourceFilter === module.id} className={sourceFilter === module.id ? 'selected' : ''} onClick={() => { setSourceFilter(module.id); setSourceFilterOpen(false) }} key={module.id}>{module.title}</button>)}
              </div>}
            </div>
            <WorkflowDatePicker value={selectedDate} onChange={setSelectedDate} label="日期" popupAlign="left" inlinePopup />
            {selectedDate && <button type="button" className="workflow-filter-clear" onClick={() => setSelectedDate('')}>清除</button>}
          </div>

          {error && <div className="workflow-task-error">{error}<button type="button" onClick={() => void loadTasks()}>重试</button></div>}

          {loading ? <p className="workflow-task-empty">正在读取任务…</p> : tasks.length === 0 ? (
            <p className="workflow-task-empty">暂无任务。创建研报、策略或新闻总结任务后，会统一显示在这里。</p>
          ) : <div className="workflow-task-groups">
            <section className="workflow-task-group workflow-pending-group" aria-labelledby="pending-tasks-title">
              <div className="workflow-task-group-head"><h3 id="pending-tasks-title">需要处理</h3><span>{pendingTasks.length}</span></div>
              <div className="workflow-task-group-scroll"><div className="workflow-task-list">
                {pendingTasks.length === 0 ? <p className="workflow-task-empty compact">当前没有需要处理的任务</p> : pendingTasks.map((task) => (
                  <button className="workflow-task-row" type="button" key={task.task_id} onClick={() => openTask(task)}>
                    <span className={`workflow-task-dot ${taskTone(task)}`} aria-hidden="true" />
                    <span className="workflow-task-copy"><strong>{task.title}</strong><small>{task.module}</small></span>
                    <span className="workflow-task-meta"><em className={taskTone(task)}>{task.status_label}</em><time>{formatTime(task.updated_at)}</time></span>
                  </button>
                ))}
              </div></div>
            </section>
            <section className="workflow-task-group workflow-history-group" aria-labelledby="history-tasks-title">
              <div className="workflow-task-group-head"><h3 id="history-tasks-title">历史记录</h3><span>{historyTasks.length}</span></div>
              <div className="workflow-task-group-scroll workflow-history-groups">
                {historyTasks.length === 0 ? <p className="workflow-task-empty compact">暂无历史记录</p> : historyDateGroups.map(([date, dateTasks]) => <div className="workflow-history-date-group" key={date}>
                  <h4>{date}</h4>
                  <div className="workflow-task-list workflow-history-date-list">{dateTasks.map((task) => (
                    <button className="workflow-task-row" type="button" key={task.task_id} onClick={() => openTask(task)}>
                      <span className={`workflow-task-dot ${taskTone(task)}`} aria-hidden="true" />
                      <span className="workflow-task-copy"><strong>{task.title}</strong><small>{task.module}</small></span>
                      <span className="workflow-task-meta"><em className={taskTone(task)}>{task.status_label}</em><time>{formatTime(task.updated_at)}</time></span>
                    </button>
                  ))}</div>
                </div>)}
              </div>
              <p className="workflow-history-hint">仅展示最近三个日期；可使用上方日期筛选定位指定日期。</p>
            </section>
          </div>}
        </aside>
      </div>
    </section>
  )
}
