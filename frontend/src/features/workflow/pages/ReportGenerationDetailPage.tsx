import { useCallback, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useNavigate, useParams } from 'react-router-dom'
import { ReportGenerationTask, getReportGenerationTask, retryReportGenerationTask } from '@/api/reportGeneration'
import { ReportExportButtons } from '../components/ReportExportButtons'
import { ReportSourceDetailPanel } from '../components/ReportSourceDetailPanel'

const LABEL = { queued: '排队中', running: '正在生成', completed: '已完成', failed: '生成失败' }

export function ReportGenerationDetailPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const [task, setTask] = useState<ReportGenerationTask | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(false)
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null)
  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    try { setTask(await getReportGenerationTask(taskId)); setError('') }
    catch (reason) { setError(reason instanceof Error ? reason.message : '读取研报详情失败') }
    finally { if (!quiet) setLoading(false) }
  }, [taskId])
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (!task || (task.status !== 'queued' && task.status !== 'running')) return
    const timer = window.setInterval(() => void load(true), 4000)
    return () => window.clearInterval(timer)
  }, [load, task])
  async function retry() {
    setRetrying(true)
    try { setTask(await retryReportGenerationTask(taskId)); setError('') }
    catch (reason) { setError(reason instanceof Error ? reason.message : '重试失败') }
    finally { setRetrying(false) }
  }
  return <section className="computer-page report-detail-page">
    <div className="computer-tabs"><button onClick={() => navigate('/computer/reports')}>← 返回研报分析</button><span className="computer-spacer" /><button className="computer-button" onClick={() => void load()}>刷新状态</button></div>
    {loading ? <div className="report-detail-state">正在读取任务详情…</div>
      : error && !task ? <div className="report-detail-state error">{error}<button className="computer-button" onClick={() => void load()}>重试</button></div>
      : task && <>
        <header className="report-detail-header">
          <div>
            <span className={`computer-badge ${task.status === 'completed' ? 'file' : task.status === 'failed' ? 'warning' : 'running'}`}>{LABEL[task.status]}</span>
            <h1>{task.title}</h1>
            <p>{task.requirement}</p>
          </div>
          <div className="report-detail-actions">
            {task.status === 'failed' && <button className="computer-button primary" disabled={retrying} onClick={() => void retry()}>{retrying ? '正在重试…' : '重试生成'}</button>}
          </div>
        </header>
        {error && <p className="chat-error">{error}</p>}
        <ReportExportButtons task={task} onError={setError} />
        <div className="report-detail-meta"><span>来源 {task.source_snapshot_json.length} 份</span><span>范围 {task.date_start || '未限定'} 至 {task.date_end || '未限定'}</span><span>模型 {task.model_name || '等待分配'}</span><span>重试 {task.retry_count} 次</span></div>
        {(task.status === 'queued' || task.status === 'running') && <div className="report-detail-state running"><span className="report-spinner" /><strong>{task.status === 'queued' ? '任务正在排队' : '模型正在综合研报'}</strong><p>页面会自动刷新；关闭或刷新页面不会丢失任务。</p></div>}
        {task.status === 'failed' && <div className="report-detail-state error"><strong>本次生成未完成</strong><p>{task.error_message || '生成服务返回未知错误，请重试。'}</p></div>}
        {task.status === 'completed' && task.result_markdown && <article className="report-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{task.result_markdown}</ReactMarkdown></article>}
        <section className="report-detail-sources">
          <h2>来源研报</h2>
          {task.source_snapshot_json.map((source, index) => (
            <div className="report-source-group" key={source.id}>
              <button
                className={selectedSourceId === source.id ? 'active' : ''}
                onClick={() => setSelectedSourceId(selectedSourceId === source.id ? null : source.id)}
              >
                <span>{index + 1}</span>
                <div>
                  <strong>{source.title}</strong>
                  <small>{source.institution || '未知机构'} · {source.publish_date || '日期未知'} · {source.industry || source.report_type || '未分类'}</small>
                </div>
              </button>
              {selectedSourceId === source.id && (
                <div className="report-source-detail-inline">
                  <ReportSourceDetailPanel reportId={source.id} onClose={() => setSelectedSourceId(null)} />
                  <div className="report-source-detail-close-row">
                    <button className="computer-button" onClick={() => setSelectedSourceId(null)}>收起 ↑</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </section>
      </>}
  </section>
}
