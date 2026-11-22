import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { WorkflowTaskType } from '@/api/tasks'
import { WorkflowTaskCenter } from '../components/tasks/WorkflowTaskCenter'

type WorkflowModule = {
  id: string
  title: string
  description: string
  category: string
  to?: string
  taskTypes: WorkflowTaskType[]
}

const WORKFLOW_MODULES: WorkflowModule[] = [
  {
    id: 'reports',
    title: '研报分析',
    description: '上传、解析并提炼研报核心观点',
    category: '研究分析',
    to: '/computer/reports',
    taskTypes: ['research_report', 'report_generation'],
  },
  {
    id: 'news',
    title: '新闻总结',
    description: '聚合市场新闻与重要事件',
    category: '信息处理',
    to: '/computer/news',
    taskTypes: ['daily_news'],
  },
  {
    id: 'policy',
    title: '政策文件分析',
    description: '上传政策文件，AI 解读要点与债市影响',
    category: '研究分析',
    to: '/computer/policy',
    taskTypes: ['policy_document'],
  },
]

const MODULES_PER_PAGE = 8

export function WorkflowHomePage() {
  const navigate = useNavigate()
  const [modulePage, setModulePage] = useState(0)
  const modulePageCount = Math.ceil(WORKFLOW_MODULES.length / MODULES_PER_PAGE)
  const visibleModules = WORKFLOW_MODULES.slice(
    modulePage * MODULES_PER_PAGE,
    (modulePage + 1) * MODULES_PER_PAGE,
  )

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
              <article
                className={`workflow-module-card${module.to ? ' available' : ''}`}
                key={module.id}
                role={module.to ? 'button' : undefined}
                tabIndex={module.to ? 0 : undefined}
                onClick={() => module.to && navigate(module.to)}
                onKeyDown={(event) => {
                  if (module.to && (event.key === 'Enter' || event.key === ' ')) {
                    event.preventDefault()
                    navigate(module.to)
                  }
                }}
              >
                <div className="workflow-module-card-body">
                  <small>{module.category}</small>
                  <h2>{module.title}</h2>
                  <p>{module.description}</p>
                </div>
              </article>
            ))}
          </div>
          {modulePageCount > 1 && (
            <nav className="workflow-module-pagination" aria-label="工作流模块分页">
              <button type="button" onClick={() => setModulePage((current) => Math.max(0, current - 1))} disabled={modulePage === 0}>← 上一页</button>
              <span>{modulePage + 1} / {modulePageCount}</span>
              <button type="button" onClick={() => setModulePage((current) => Math.min(modulePageCount - 1, current + 1))} disabled={modulePage === modulePageCount - 1}>下一页 →</button>
            </nav>
          )}
        </main>

        <WorkflowTaskCenter />
      </div>
    </section>
  )
}
