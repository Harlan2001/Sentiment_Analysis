import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getWorkflowTasks,
  type WorkflowTask,
  type WorkflowTaskListResponse,
  type WorkflowTaskStatus,
  type WorkflowTaskType,
} from '@/api/tasks'
import { WorkflowDatePicker } from '../WorkflowDatePicker'
import { WorkflowTaskDetailPanel } from './WorkflowTaskDetailPanel'
import { WorkflowTaskList } from './WorkflowTaskList'
import { WorkflowTaskPagination } from './WorkflowTaskPagination'
import { isPollingTask, TASK_STATUS_OPTIONS, TASK_TYPE_OPTIONS } from './taskUtils'
import './tasks.css'

const TASK_PAGE_SIZE = 20
const POLL_INTERVAL = 3000

export function WorkflowTaskCenter() {
  const [data, setData] = useState<WorkflowTaskListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [taskType, setTaskType] = useState<WorkflowTaskType | ''>('')
  const [status, setStatus] = useState<WorkflowTaskStatus | ''>('')
  const [selectedDate, setSelectedDate] = useState('')
  const [page, setPage] = useState(1)
  const [selectedTask, setSelectedTask] = useState<WorkflowTask | null>(null)
  const [refreshVersion, setRefreshVersion] = useState(0)
  const requestId = useRef(0)

  const loadTasks = useCallback(async (quiet = false) => {
    const currentRequest = ++requestId.current
    if (!quiet) setLoading(true)
    try {
      const result = await getWorkflowTasks({
        task_type: taskType || undefined,
        status: status || undefined,
        date: selectedDate || undefined,
        page,
        page_size: TASK_PAGE_SIZE,
      })
      if (currentRequest !== requestId.current) return
      setData(result)
      setError('')
      setRefreshVersion((version) => version + 1)
    } catch (reason) {
      if (currentRequest !== requestId.current) return
      setError(reason instanceof Error ? reason.message : '读取工作流任务失败')
    } finally {
      if (currentRequest === requestId.current && !quiet) setLoading(false)
    }
  }, [page, selectedDate, status, taskType])

  useEffect(() => {
    void loadTasks()
  }, [loadTasks])

  const hasActiveTasks = data?.items.some(isPollingTask) === true
  useEffect(() => {
    if (!hasActiveTasks) return
    const refreshWhenVisible = () => {
      if (!document.hidden) void loadTasks(true)
    }
    const timer = window.setInterval(refreshWhenVisible, POLL_INTERVAL)
    document.addEventListener('visibilitychange', refreshWhenVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', refreshWhenVisible)
    }
  }, [hasActiveTasks, loadTasks])

  useEffect(() => () => {
    requestId.current += 1
  }, [])

  function changeTaskType(value: WorkflowTaskType | '') {
    setTaskType(value)
    setPage(1)
  }

  function changeStatus(value: WorkflowTaskStatus | '') {
    setStatus(value)
    setPage(1)
  }

  function changeDate(value: string) {
    setSelectedDate(value)
    setPage(1)
  }

  function clearFilters() {
    setTaskType('')
    setStatus('')
    setSelectedDate('')
    setPage(1)
  }

  const tasks = data?.items ?? []
  const runningCount = (data?.status_counts.queued ?? 0) + (data?.status_counts.running ?? 0)
  const hasFilters = Boolean(taskType || status || selectedDate)

  return (
    <aside className="workflow-task-rail" aria-label="任务中心" aria-busy={loading}>
      <header className="workflow-task-head">
        <div>
          <h2>任务中心</h2>
          <p>统一查看各模块真实执行进度</p>
        </div>
        <button type="button" onClick={() => void loadTasks()} disabled={loading} aria-label="刷新任务中心">↻</button>
      </header>

      <div className="workflow-task-summary">
        <span>进行中</span>
        <strong>{runningCount}</strong>
        <small>共 {data?.total ?? 0} 个任务</small>
      </div>

      <div className="workflow-task-filters" aria-label="任务筛选">
        <select
          className="computer-chip workflow-task-select"
          aria-label="任务类型"
          value={taskType}
          onChange={(event) => changeTaskType(event.target.value as WorkflowTaskType | '')}
        >
          <option value="">全部类型</option>
          {TASK_TYPE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <select
          className="computer-chip workflow-task-select"
          aria-label="任务状态"
          value={status}
          onChange={(event) => changeStatus(event.target.value as WorkflowTaskStatus | '')}
        >
          <option value="">全部状态</option>
          {TASK_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <WorkflowDatePicker value={selectedDate} onChange={changeDate} label="日期" popupAlign="left" inlinePopup />
        {hasFilters && <button type="button" className="workflow-filter-clear" onClick={clearFilters}>清除筛选</button>}
      </div>

      {error && (
        <div className="workflow-task-error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void loadTasks()}>重试</button>
        </div>
      )}

      {loading ? (
        <p className="workflow-task-empty">正在读取任务…</p>
      ) : tasks.length === 0 ? (
        <p className="workflow-task-empty">
          {hasFilters ? '当前筛选条件下暂无任务，请调整筛选。' : '暂无任务。创建研报、政策、策略或新闻总结任务后，会统一显示在这里。'}
        </p>
      ) : (
        <WorkflowTaskList tasks={tasks} onSelect={setSelectedTask} />
      )}

      {data && (
        <WorkflowTaskPagination
          page={data.page}
          totalPages={data.total_pages}
          total={data.total}
          disabled={loading}
          onPageChange={(nextPage) => {
            setSelectedTask(null)
            setPage(nextPage)
          }}
        />
      )}

      {selectedTask && (
        <WorkflowTaskDetailPanel
          key={selectedTask.task_id}
          selectedTask={selectedTask}
          refreshVersion={refreshVersion}
          onClose={() => setSelectedTask(null)}
          onChanged={() => loadTasks()}
        />
      )}
    </aside>
  )
}
