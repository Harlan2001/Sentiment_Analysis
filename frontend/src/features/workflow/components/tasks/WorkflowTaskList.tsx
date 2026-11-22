import type { WorkflowTask } from '@/api/tasks'
import { formatTaskTime, isHistoryTask, taskDate, taskStageLabel, taskTone } from './taskUtils'

type WorkflowTaskListProps = {
  tasks: WorkflowTask[]
  onSelect: (task: WorkflowTask) => void
}

function TaskRow({ task, onSelect }: { task: WorkflowTask; onSelect: (task: WorkflowTask) => void }) {
  const tone = taskTone(task)
  return (
    <button className="workflow-task-row" type="button" onClick={() => onSelect(task)}>
      <span className={`workflow-task-dot ${tone}`} aria-hidden="true" />
      <span className="workflow-task-copy">
        <strong>{task.title}</strong>
        <small>{task.module} · {taskStageLabel(task)}</small>
        {task.error_message && <small className="workflow-task-error-summary" title={task.error_message}>{task.error_message}</small>}
      </span>
      <span className="workflow-task-meta">
        <em className={tone}>{task.status_label}</em>
        <time dateTime={task.updated_at}>{formatTaskTime(task.updated_at)}</time>
      </span>
    </button>
  )
}

/** 仅对服务端当前页分组，计数不会冒充全量统计。 */
export function WorkflowTaskList({ tasks, onSelect }: WorkflowTaskListProps) {
  const pendingTasks = tasks.filter((task) => !isHistoryTask(task))
  const historyTasks = tasks.filter(isHistoryTask)
  const historyByDate = new Map<string, WorkflowTask[]>()
  for (const task of historyTasks) {
    const date = taskDate(task)
    historyByDate.set(date, [...(historyByDate.get(date) ?? []), task])
  }

  return (
    <div className="workflow-task-groups">
      <section className="workflow-task-group workflow-pending-group" aria-labelledby="pending-tasks-title">
        <div className="workflow-task-group-head">
          <h3 id="pending-tasks-title">需要处理</h3>
          <span title="当前页数量">{pendingTasks.length}</span>
        </div>
        <div className="workflow-task-group-scroll">
          <div className="workflow-task-list">
            {pendingTasks.length === 0 ? (
              <p className="workflow-task-empty compact">当前页没有需要处理的任务</p>
            ) : pendingTasks.map((task) => <TaskRow key={task.task_id} task={task} onSelect={onSelect} />)}
          </div>
        </div>
      </section>

      <section className="workflow-task-group workflow-history-group" aria-labelledby="history-tasks-title">
        <div className="workflow-task-group-head">
          <h3 id="history-tasks-title">历史记录</h3>
          <span title="当前页数量">{historyTasks.length}</span>
        </div>
        <div className="workflow-task-group-scroll workflow-history-groups">
          {historyTasks.length === 0 ? (
            <p className="workflow-task-empty compact">当前页暂无历史记录</p>
          ) : [...historyByDate.entries()].map(([date, dateTasks]) => (
            <div className="workflow-history-date-group" key={date}>
              <h4>{date}</h4>
              <div className="workflow-task-list workflow-history-date-list">
                {dateTasks.map((task) => <TaskRow key={task.task_id} task={task} onSelect={onSelect} />)}
              </div>
            </div>
          ))}
        </div>
        <p className="workflow-history-hint">历史按服务端当前页分组，可筛选日期或翻页查看更多。</p>
      </section>
    </div>
  )
}
