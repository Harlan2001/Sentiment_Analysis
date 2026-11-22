import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  downloadWorkflowTaskFile,
  getWorkflowTaskDetail,
  retryWorkflowTask,
  type WorkflowTask,
  type WorkflowTaskDetailResponse,
} from '@/api/tasks'
import {
  formatTaskTime,
  isTaskConflictError,
  isTaskNotFoundError,
  taskStageLabel,
  taskTone,
} from './taskUtils'

type WorkflowTaskDetailPanelProps = {
  selectedTask: WorkflowTask
  refreshVersion: number
  onClose: () => void
  onChanged: () => void | Promise<void>
}

function taskErrorMessage(reason: unknown, fallback: string): string {
  if (isTaskNotFoundError(reason)) return '任务不存在或当前用户不可访问'
  return reason instanceof Error ? reason.message : fallback
}

export function WorkflowTaskDetailPanel({
  selectedTask,
  refreshVersion,
  onClose,
  onChanged,
}: WorkflowTaskDetailPanelProps) {
  const [detail, setDetail] = useState<WorkflowTaskDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [retrying, setRetrying] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const requestId = useRef(0)

  const loadDetail = useCallback(async (showLoading = true) => {
    const currentRequest = ++requestId.current
    if (showLoading) setLoading(true)
    setError('')
    try {
      const data = await getWorkflowTaskDetail(selectedTask.task_type, selectedTask.domain_id)
      if (currentRequest === requestId.current) setDetail(data)
    } catch (reason) {
      if (currentRequest === requestId.current) {
        setError(taskErrorMessage(reason, '读取任务详情失败'))
      }
    } finally {
      if (currentRequest === requestId.current) setLoading(false)
    }
  }, [selectedTask.domain_id, selectedTask.task_type])

  useEffect(() => {
    void loadDetail()
  }, [loadDetail, refreshVersion])

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  useEffect(() => () => {
    requestId.current += 1
  }, [])

  async function handleRetry() {
    if (!detail || detail.task.task_type === 'strategy') return
    setRetrying(true)
    setActionError('')
    try {
      const updated = await retryWorkflowTask(detail.task.task_type, detail.task.domain_id)
      setDetail((current) => current ? { ...current, task: updated } : current)
      await Promise.all([loadDetail(false), onChanged()])
    } catch (reason) {
      if (isTaskConflictError(reason)) setActionError('状态已变化，请刷新')
      else setActionError(taskErrorMessage(reason, '任务重试失败'))
    } finally {
      setRetrying(false)
    }
  }

  async function handleDownload(task: WorkflowTask) {
    setDownloading(true)
    setActionError('')
    try {
      const file = await downloadWorkflowTaskFile(task)
      const objectUrl = URL.createObjectURL(file.blob)
      const anchor = document.createElement('a')
      anchor.href = objectUrl
      anchor.download = file.filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
    } catch (reason) {
      setActionError(taskErrorMessage(reason, '文件下载失败'))
    } finally {
      setDownloading(false)
    }
  }

  const task = detail?.task ?? selectedTask
  const canRetry = task.status === 'failed' && task.task_type !== 'strategy'
  const canOpenResult = Boolean(task.result_url) && (
    task.status === 'succeeded' || task.status === 'empty' || task.task_type === 'strategy'
  )

  return (
    <div className="workflow-task-detail-layer">
      <button type="button" className="workflow-task-detail-backdrop" onClick={onClose} aria-label="关闭任务详情背景" />
      <aside className="workflow-task-detail" role="dialog" aria-modal="true" aria-label="任务详情">
        <header className="workflow-task-detail-head">
          <div>
            <small>{task.source || task.module}</small>
            <h2>{task.title}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭任务详情">×</button>
        </header>

        <div className="workflow-task-detail-body">
          {loading && !detail ? (
            <p className="workflow-task-empty">正在读取任务详情…</p>
          ) : error && !detail ? (
            <div className="workflow-task-error" role="alert">
              <span>{error}</span>
              <button type="button" onClick={() => void loadDetail()}>重试</button>
            </div>
          ) : (
            <>
              {error && <div className="workflow-task-error" role="alert">{error}<button type="button" onClick={() => void loadDetail(false)}>刷新</button></div>}
              <section className="workflow-task-detail-section" aria-label="任务状态">
                <div className="workflow-task-detail-status">
                  <span className={`workflow-task-dot ${taskTone(task)}`} aria-hidden="true" />
                  <strong>{task.status_label}</strong>
                  <span>{taskStageLabel(task)}</span>
                </div>
                <dl className="workflow-task-detail-grid">
                  <div><dt>任务类型</dt><dd>{task.module}</dd></div>
                  <div><dt>领域状态</dt><dd>{task.domain_status}</dd></div>
                  <div><dt>更新时间</dt><dd>{formatTaskTime(task.updated_at)}</dd></div>
                  <div><dt>已重试</dt><dd>{task.retry_count} 次</dd></div>
                </dl>
                {task.description && <p className="workflow-task-detail-description">{task.description}</p>}
              </section>

              {task.error_message && (
                <section className="workflow-task-detail-section workflow-task-detail-error" aria-label="任务错误">
                  <h3>错误详情</h3>
                  <pre>{task.error_message}</pre>
                </section>
              )}

              <section className="workflow-task-detail-section" aria-label="执行记录">
                <h3>执行记录</h3>
                {detail?.execution ? (
                  <dl className="workflow-task-detail-grid">
                    <div><dt>执行 ID</dt><dd>{detail.execution.id}</dd></div>
                    <div><dt>执行状态</dt><dd>{detail.execution.status}</dd></div>
                    <div><dt>开始时间</dt><dd>{formatTaskTime(detail.execution.started_at)}</dd></div>
                    <div><dt>结束时间</dt><dd>{formatTaskTime(detail.execution.finished_at)}</dd></div>
                  </dl>
                ) : <p className="workflow-task-detail-muted">{task.task_type === 'strategy' ? '策略历史仅保留只读结果，无执行记录。' : '暂无执行记录'}</p>}
                {detail?.execution?.error_message && <pre className="workflow-task-execution-error">{detail.execution.error_message}</pre>}
              </section>

              <section className="workflow-task-detail-section" aria-label="事件时间线">
                <h3>事件时间线</h3>
                {detail?.items.length ? (
                  <ol className="workflow-task-timeline">
                    {detail.items.map((event) => (
                      <li key={event.id}>
                        <span className={`workflow-task-dot ${event.status === 'failed' ? 'failed' : event.status === 'succeeded' ? 'done' : 'running'}`} aria-hidden="true" />
                        <div>
                          <strong>{event.event_type}<small>{event.status}</small></strong>
                          <p>{event.message}</p>
                          <time dateTime={event.created_at}>{formatTaskTime(event.created_at)}</time>
                        </div>
                      </li>
                    ))}
                  </ol>
                ) : <p className="workflow-task-detail-muted">暂无阶段事件</p>}
              </section>
            </>
          )}
        </div>

        {detail && (
          <footer className="workflow-task-detail-actions">
            {actionError && <p role="alert">{actionError}</p>}
            <div>
              {canOpenResult && task.result_url && <Link className="primary" to={task.result_url}>查看结果</Link>}
              {task.download_url && (
                <button type="button" disabled={downloading} onClick={() => void handleDownload(task)}>
                  {downloading ? '下载中…' : '下载文件'}
                </button>
              )}
              {canRetry && (
                <button type="button" className="danger" disabled={retrying} onClick={() => void handleRetry()}>
                  {retrying ? '重试中…' : '重试任务'}
                </button>
              )}
              {task.task_type === 'strategy' && <small>策略历史只读</small>}
            </div>
          </footer>
        )}
      </aside>
    </div>
  )
}
