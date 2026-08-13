import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ComputerTask, getComputerTasks } from '../../api/workbench'
import { ComputerDatePicker } from './components/ComputerDatePicker'

type ModuleKey = '全部' | '研报生成' | '策略开发' | '每日新闻总结'

/** 业务状态分组：对外展示用中文分类，对内映射到多个原始状态值 */
const STATUS_GROUPS: { label: string; statuses: string[] }[] = [
  { label: '状态：全部', statuses: [] },
  { label: '已完成', statuses: ['completed', 'succeeded'] },
  { label: '进行中', statuses: ['running', 'pending', 'queued'] },
  { label: '待确认', statuses: ['pending_confirmation'] },
  { label: '失败', statuses: ['failed'] },
  { label: '无新闻', statuses: ['empty'] },
]

const STATUS_ICON: Record<string, string> = {
  quued: 'waiting',
  running: 'running',
  completed: 'done',
  failed: 'failed',
  pending: 'waiting',
  succeeded: 'done',
  empty: 'waiting',
  pending_confirmation: 'waiting',
}

const tabRoutes: Record<Exclude<ModuleKey, '全部'>, string> = {
  '研报生成': '/computer/reports',
  '策略开发': '/computer/strategies',
  '每日新闻总结': '/computer/news',
}

function formatTime(value: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) {
    return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }).format(d)
  }
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  if (d.toDateString() === yesterday.toDateString()) return '昨天'
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' }).format(d)
}

export function ComputerPage() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<ComputerTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<ModuleKey>('全部')
  const [statusGroupIndex, setStatusGroupIndex] = useState(0)
  const [needsActionOnly, setNeedsActionOnly] = useState(false)
  const [selectedDate, setSelectedDate] = useState('')
  const [view, setView] = useState('会话与文档')
  const [showAllActions, setShowAllActions] = useState(false)
  const [expandedDateKeys, setExpandedDateKeys] = useState<Set<string>>(() => new Set())

  const loadTasks = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getComputerTasks()
      setTasks(data.items)
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : '读取 Computer 任务失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadTasks()
  }, [loadTasks])

  const visibleRows = useMemo(() => {
    let filtered = tasks
    if (activeTab !== '全部') {
      const map: Record<Exclude<ModuleKey, '全部'>, string> = {
        '研报生成': 'report_generation',
        '策略开发': 'strategy',
        '每日新闻总结': 'daily_news',
      }
      filtered = filtered.filter((t) => t.task_type === map[activeTab])
    }
    const activeStatuses = STATUS_GROUPS[statusGroupIndex]?.statuses
    if (activeStatuses && activeStatuses.length > 0) {
      filtered = filtered.filter((t) => activeStatuses.includes(t.status))
    }
    if (view === '仅会话') {
      filtered = filtered.filter((t) => t.task_type === 'strategy')
    } else if (view === '仅文档') {
      filtered = filtered.filter((t) => t.task_type !== 'strategy')
    }
    if (selectedDate) filtered = filtered.filter((t) => t.date === selectedDate)
    if (needsActionOnly) filtered = filtered.filter((t) => t.needs_action)
    return filtered
  }, [activeTab, needsActionOnly, selectedDate, statusGroupIndex, tasks, view])

  function openTask(task: ComputerTask) {
    const [, rawId] = task.task_id.split(':', 2)
    if (!rawId) return
    if (task.task_type === 'report_generation') navigate('/computer/reports/' + rawId)
    else if (task.task_type === 'strategy') navigate('/computer/strategies/prompt?id=' + rawId)
    else navigate('/computer/news?task=' + rawId)
  }

  function selectTab(tab: ModuleKey) {
    setActiveTab(tab)
    if (tab !== '全部') navigate(tabRoutes[tab])
  }

  const actionItems = visibleRows.filter((t) => t.needs_action)
  const dateLabel = selectedDate || '全部日期'

  /* 按 selectedDate 将 visibleRows 分组 */
  const groupedByDate = useMemo(() => {
    const map = new Map<string, ComputerTask[]>()
    for (const task of visibleRows) {
      const key = task.date || '未知日期'
      const list = map.get(key) || []
      list.push(task)
      map.set(key, list)
    }
    return [...map.entries()].sort((a, b) => b[0].localeCompare(a[0]))
  }, [visibleRows])

  const displayActions = showAllActions ? actionItems : actionItems.slice(0, 2)

  /* 未筛选时仅展示最近三个自然日；每个日期默认最多四条。 */
  const displayGroups = useMemo(() => {
    if (selectedDate) return groupedByDate
    const today = new Date()
    const cutoff = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 2)
    const cutoffKey = `${cutoff.getFullYear()}-${String(cutoff.getMonth() + 1).padStart(2, '0')}-${String(cutoff.getDate()).padStart(2, '0')}`
    return groupedByDate.filter(([dateKey]) => dateKey >= cutoffKey)
  }, [groupedByDate, selectedDate])

  function toggleDateGroup(dateKey: string) {
    setExpandedDateKeys((current) => {
      const next = new Set(current)
      if (next.has(dateKey)) next.delete(dateKey)
      else next.add(dateKey)
      return next
    })
  }
  const totalHistoryCount = groupedByDate.reduce((sum, [, tasks]) => sum + tasks.length, 0)

  return (
    <section className="computer-page">
      <div className="computer-tabs">
        {(['全部', '研报生成', '策略开发', '每日新闻总结'] as ModuleKey[]).map(
          (tab) => (
            <button
              className={activeTab === tab ? 'active' : ''}
              onClick={() => selectTab(tab)}
              key={tab}
            >
              {tab}
            </button>
          ),
        )}
        <span className="computer-spacer" />
        <button className="computer-button" onClick={() => void loadTasks()}>
          刷新
        </button>
      </div>

      <div className="computer-toolbar">
        <select
          className="computer-chip computer-select"
          value={statusGroupIndex}
          onChange={(e) => setStatusGroupIndex(Number(e.target.value))}
        >
          {STATUS_GROUPS.map((group, i) => (
            <option value={i} key={group.label}>
              {group.label}
            </option>
          ))}
        </select>
        <button
          className={'computer-chip ' + (needsActionOnly ? 'selected' : '')}
          onClick={() => setNeedsActionOnly((v) => !v)}
        >
          仅未读
        </button>
        <ComputerDatePicker
          value={selectedDate}
          onChange={setSelectedDate}
          label="任务日期"
        />
        <span className="computer-spacer" />
        {loading ? (
          <span className="computer-count">读取中…</span>
        ) : (
          <span className="computer-count">
            {visibleRows.length} 段会话
          </span>
        )}
      </div>

      {error && (
        <div
          className="chat-error"
          style={{ margin: '0 0 14px', display: 'flex', alignItems: 'center', gap: 10 }}
        >
          {error}
          <button onClick={() => void loadTasks()} className="computer-button">
            重试
          </button>
        </div>
      )}

      {/* 需要处理 */}
      <section className="computer-attention">
        <div className="computer-attention-head">
          <strong>需要处理 · {actionItems.length}</strong>
          <span>⌃</span>
        </div>
        {loading ? (
          <div className="computer-attention-row">
            <span className="attention-dot" />
            <div>
              <strong>正在读取任务…</strong>
              <small>从研报、策略和新闻模块加载最新状态</small>
            </div>
          </div>
        ) : actionItems.length === 0 ? (
          <div className="computer-attention-row">
            <span className="attention-dot" />
            <div>
              <strong>当前无待处理的任务</strong>
              <small>所有任务均已完成或无异常</small>
            </div>
          </div>
        ) : (
          <>
            {displayActions.map((task) => (
              <div className="computer-attention-row computer-task-link" key={task.task_id} role="button" tabIndex={0} onClick={() => openTask(task)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openTask(task) } }}>
                <span className={'attention-dot ' + (task.status === 'failed' ? 'failed' : 'running')} />
                <div>
                  <strong>{task.title}</strong>
                  <small>{task.description}</small>
                </div>
                <span className={'computer-badge ' + (task.status === 'failed' ? 'failed' : 'warning')}>{task.status_label}</span>
                <time>{formatTime(task.updated_at)}</time>
              </div>
            ))}
            {actionItems.length > 2 && (
              <div style={{textAlign:'center',padding:'6px 0 2px'}}>
                <button className="expand-toggle" onClick={() => setShowAllActions((v) => !v)} aria-label={showAllActions ? '收起' : '展开'}>
                  <i className={'expand-arrow ' + (showAllActions ? 'up' : 'down')} />
                </button>
              </div>
            )}
          </>
        )}
      </section>

      {/* 按日期分组 */}
      {displayGroups.length === 0 && !loading ? (
        <div className="computer-list-head">
          <div>
            <strong>{dateLabel}</strong>
            <span>· 0 段会话</span>
          </div>
        </div>
      ) : (
        <>
          {displayGroups.map(([dateKey, dateTasks]) => {
          const visibleDateTasks = expandedDateKeys.has(dateKey) ? dateTasks : dateTasks.slice(0, 4)
          const isExpanded = expandedDateKeys.has(dateKey)
          return <div key={dateKey}>
            <div className="computer-list-head">
              <div>
                <strong>{dateKey}</strong>
                <span>· {dateTasks.length} 段会话</span>
              </div>
              <div className="computer-view-switch">
                {['会话与文档', '仅会话', '仅文档'].map((item) => (
                  <button
                    className={view === item ? 'active' : ''}
                    onClick={() => setView(item)}
                    key={item}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>

            <div className="computer-table-wrap">
              <table className="computer-table">
                <thead>
                  <tr>
                    <th />
                    <th>任务会话</th>
                    <th>来源/类型</th>
                    <th>状态或结果</th>
                    <th>更新时间</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleDateTasks.map((task) => (
                    <tr key={task.task_id} className="clickable-row" onClick={() => openTask(task)}>
                      <td>
                        <span
                          className={
                            'computer-status ' +
                            (STATUS_ICON[task.status] || 'waiting')
                          }
                        >
                          {task.status === 'completed' || task.status === 'succeeded'
                            ? '✓'
                            : task.status === 'running' || task.status === 'pending'
                              ? '◐'
                              : task.status === 'failed'
                                ? '!'
                                : '●'}
                        </span>
                      </td>
                      <td>
                        <strong>{task.title}</strong>
                        <small>{task.description}</small>
                        {task.task_type === 'strategy' && task.status === 'completed' && (
                          <span className="computer-progress">
                            <i style={{ width: '100%' }} />
                          </span>
                        )}
                      </td>
                      <td>{task.source}</td>
                      <td>
                        <span
                          className={
                            'computer-badge ' +
                            (task.status === 'completed' ||
                            task.status === 'succeeded'
                              ? 'file'
                              : task.status === 'failed'
                                ? 'failed'
                                : task.status === 'running'
                                  ? 'running'
                                  : 'warning')
                          }
                        >
                          {task.result}
                        </span>
                      </td>
                      <td>
                        <time>{formatTime(task.updated_at)}</time>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {dateTasks.length > 4 && (
                <div className="computer-date-group-expand">
                  <button className="expand-toggle" onClick={() => toggleDateGroup(dateKey)} aria-label={isExpanded ? '收起该日期任务' : '展开该日期任务'}>
                    <i className={'expand-arrow ' + (isExpanded ? 'up' : 'down')} />
                  </button>
                </div>
              )}
            </div>
          </div>
        })}
        {!selectedDate && totalHistoryCount > displayGroups.reduce((sum, [, dateTasks]) => sum + dateTasks.length, 0) && (
          <p className="computer-history-hint">仅显示最近 3 天的任务。查看更早记录，请使用上方“任务日期”筛选。</p>
        )}        </>
      )}

      {!loading && tasks.length === 0 && !error && (
        <div
          style={{
            textAlign: 'center',
            padding: '48px 24px',
            color: '#809188',
            fontSize: 13,
          }}
        >
          <strong style={{ display: 'block', marginBottom: 6 }}>
            暂无 Computer 任务
          </strong>
          在研报生成、策略开发或每日新闻总结中创建第一个任务后，它将会出现在这里。
        </div>
      )}
    </section>
  )
}
