import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  DeletedItemsData,
  getDeletedItems,
  restoreConversation,
  restoreProject,
} from '../../api/workbench'
import { ComputerDatePicker } from './components/ComputerDatePicker'

type SourceFilter = '全部' | '项目' | '会话'

const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function DeletedItemsPanel({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const [data, setData] = useState<DeletedItemsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('全部')
  const [search, setSearch] = useState('')
  const [selectedDate, setSelectedDate] = useState('')
  const [restoringId, setRestoringId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await getDeletedItems()
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : '读取已删除项失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      load()
      setSearch('')
      setSourceFilter('全部')
      setSelectedDate('')
    }
  }, [open, load])

  async function handleRestoreProject(id: string) {
    setRestoringId(id)
    try {
      await restoreProject(id)
      await load()
      window.dispatchEvent(new CustomEvent('bondsense-sidebar-refresh'))
    } catch (e) {
      setError(e instanceof Error ? e.message : '恢复项目失败')
    } finally {
      setRestoringId(null)
    }
  }

  async function handleRestoreConversation(id: string) {
    setRestoringId(id)
    try {
      await restoreConversation(id)
      await load()
      window.dispatchEvent(new CustomEvent('bondsense-sidebar-refresh'))
    } catch (e) {
      setError(e instanceof Error ? e.message : '恢复会话失败')
    } finally {
      setRestoringId(null)
    }
  }

  const filtered = useMemo(() => {
    if (!data) return { projects: [], conversations: [] }
    const q = search.trim().toLowerCase()
    const filterList = <T extends { name?: string; title?: string }>(
      items: T[],
    ) =>
      q
        ? items.filter((item) => {
            const text = (item.name || (item as any).title || '').toLowerCase()
            return text.includes(q)
          })
        : items

    let projects = filterList(data.deleted_projects)
    let conversations = filterList(data.deleted_conversations)

    if (sourceFilter === '项目') conversations = []
    if (sourceFilter === '会话') projects = []

    if (selectedDate) {
      const matchDate = (item: { deleted_at: string }) =>
        item.deleted_at.slice(0, 10) === selectedDate
      projects = projects.filter(matchDate)
      conversations = conversations.filter(matchDate)
    }

    return { projects, conversations }
  }, [data, search, sourceFilter, selectedDate])

  const totalCount = data
    ? data.deleted_projects.length + data.deleted_conversations.length
    : 0

  const filteredCount = filtered.projects.length + filtered.conversations.length

  if (!open) return null

  return (
    <>
      <div className="deleted-overlay" onClick={onClose} aria-hidden="true" />
      <aside className="deleted-drawer" role="dialog" aria-label="最近删除">
        {/* 头部 */}
        <div className="deleted-drawer-head">
          <h2>最近删除</h2>
          <button className="deleted-drawer-close" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>

        {/* 来源筛选 */}
        <div className="deleted-drawer-filters">
          {(['全部', '项目', '会话'] as SourceFilter[]).map((tab) => (
            <button
              key={tab}
              className={sourceFilter === tab ? 'active' : ''}
              onClick={() => setSourceFilter(tab)}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* 日期筛选 + 搜索 */}
        <div className="deleted-drawer-toolbar">
          <ComputerDatePicker
            value={selectedDate}
            onChange={setSelectedDate}
            label={today()}
          />
          <div className="deleted-drawer-search">
            <span>⌕</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索名称…"
            />
            {search && (
              <button
                className="deleted-search-clear"
                onClick={() => setSearch('')}
                aria-label="清除搜索"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* 统计 */}
        <div className="deleted-drawer-count">
          {loading
            ? '正在读取…'
            : search || sourceFilter !== '全部' || selectedDate
              ? `显示 ${filteredCount} / ${totalCount} 项`
              : `共 ${totalCount} 项`}
        </div>

        {/* 错误 */}
        {error && (
          <div className="deleted-drawer-error">
            {error}
            <button onClick={load}>重试</button>
          </div>
        )}

        {/* 列表 */}
        <div className="deleted-drawer-list">
          {loading ? (
            <div className="deleted-empty">正在读取…</div>
          ) : !data ? null : (
            <>
              {sourceFilter !== '会话' && (
                <div className="deleted-group">
                  <div className="deleted-group-title">已删除的项目</div>
                  {filtered.projects.length === 0 ? (
                    <div className="deleted-empty">
                      {search || selectedDate
                        ? '没有匹配的项目'
                        : '暂无已删除的项目'}
                    </div>
                  ) : (
                    filtered.projects.map((project) => (
                      <div className="deleted-item-row" key={project.id}>
                        <span className="deleted-item-name">{project.name}</span>
                        <time>
                          {new Date(project.deleted_at).toLocaleDateString('zh-CN')}
                        </time>
                        <button
                          className="deleted-restore"
                          disabled={restoringId === project.id}
                          onClick={() => handleRestoreProject(project.id)}
                        >
                          {restoringId === project.id ? '…' : '恢复'}
                        </button>
                      </div>
                    ))
                  )}
                </div>
              )}
              {sourceFilter !== '项目' && (
                <div className="deleted-group">
                  <div className="deleted-group-title">已删除的会话</div>
                  {filtered.conversations.length === 0 ? (
                    <div className="deleted-empty">
                      {search || selectedDate
                        ? '没有匹配的会话'
                        : '暂无已删除的会话'}
                    </div>
                  ) : (
                    filtered.conversations.map((conv) => (
                      <div className="deleted-item-row" key={conv.id}>
                        <span className="deleted-item-name">
                          {conv.title || '新建对话'}
                        </span>
                        <time>
                          {new Date(conv.deleted_at).toLocaleDateString('zh-CN')}
                        </time>
                        <button
                          className="deleted-restore"
                          disabled={restoringId === conv.id}
                          onClick={() => handleRestoreConversation(conv.id)}
                        >
                          {restoringId === conv.id ? '…' : '恢复'}
                        </button>
                      </div>
                    ))
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </aside>
    </>
  )
}
