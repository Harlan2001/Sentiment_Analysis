import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  deletePolicyDocument,
  fetchPolicyDocuments,
  reanalyzePolicyDocument,
} from '@/api/policyDocuments'
import PolicyUploadModal from '@/features/workflow/components/PolicyUploadModal'
import type { PolicyDocumentItem, PolicyImpactDirection } from '@/types'

/**
 * 政策文件分析（工作流内）。
 *
 * 结构与「研报分析」页保持一致（computer-page 布局）：
 *   工具栏 → 统计条 → 政策文件库（筛选 + 列表 + 分页）→ 需要处理 → 历史记录 → 底部输入区
 *
 * 展示纪律：影响方向必须附原文依据（后端已强制：无依据则降级中性）。
 */

const PAGE_SIZE = 6

const STATUS_LABEL: Record<string, string> = {
  uploaded: '待解读',
  analyzing: '解读中',
  completed: '已解读',
  failed: '失败',
}

const STATUS_CSS: Record<string, string> = {
  uploaded: 'waiting',
  analyzing: 'running',
  completed: 'done',
  failed: 'failed',
}

const DIRECTION_LABEL: Record<PolicyImpactDirection, string> = {
  bullish: '利多债券',
  bearish: '利空债券',
  neutral: '中性',
}

function formatDateTime(value: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value))
}

export default function PolicyDocumentsPage() {
  const navigate = useNavigate()

  // ── 文件库 ──
  const [documents, setDocuments] = useState<PolicyDocumentItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [keyword, setKeyword] = useState('')
  const [directionFilter, setDirectionFilter] = useState('')

  // ── 上传 ──
  const [uploadOpen, setUploadOpen] = useState(false)
  // 底部输入区：分析主题与要求（提交时打开上传弹窗，随文件一起提交）
  const [focusTitle, setFocusTitle] = useState('')
  const [requirement, setRequirement] = useState('')
  const pendingUpload = Boolean(focusTitle.trim() || requirement.trim())

  const handleSubmitFocus = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    // 政策解读的输入是"文件"，故提交动作即打开上传弹窗
    setUploadOpen(true)
  }

  // ── 折叠 ──
  const [showAllHistory, setShowAllHistory] = useState(false)

  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true)
      try {
        const data = await fetchPolicyDocuments(page, PAGE_SIZE)
        setDocuments(data.items)
        setTotal(data.total)
        setError('')
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : '读取政策文件失败')
      } finally {
        if (!quiet) setLoading(false)
      }
    },
    [page],
  )

  useEffect(() => {
    void load()
  }, [load])

  // 有解读中的任务时轮询
  const hasActive = documents.some(
    (item) => item.status === 'analyzing' || item.status === 'uploaded',
  )
  useEffect(() => {
    if (!hasActive) return
    const timer = window.setInterval(() => void load(true), 4000)
    return () => window.clearInterval(timer)
  }, [hasActive, load])

  // ── 前端筛选（关键词 + 方向）──
  const filtered = useMemo(() => {
    return documents.filter((item) => {
      if (keyword && !item.title.toLowerCase().includes(keyword.toLowerCase())) return false
      if (directionFilter && item.impact_direction !== directionFilter) return false
      return true
    })
  }, [documents, keyword, directionFilter])

  const activeItems = filtered.filter(
    (item) => item.status === 'analyzing' || item.status === 'uploaded',
  )
  const historyItems = filtered.filter(
    (item) => item.status === 'completed' || item.status === 'failed',
  )
  const visibleHistory = showAllHistory ? historyItems : historyItems.slice(0, 5)

  // ── 统计 ──
  const stats = useMemo(() => {
    const done = documents.filter((item) => item.status === 'completed')
    return {
      total,
      analyzed: done.length,
      bullish: done.filter((item) => item.impact_direction === 'bullish').length,
      bearish: done.filter((item) => item.impact_direction === 'bearish').length,
      neutral: done.filter((item) => item.impact_direction === 'neutral').length,
    }
  }, [documents, total])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  async function handleReanalyze(id: number) {
    try {
      await reanalyzePolicyDocument(id)
      void load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '重新解读失败')
    }
  }

  async function handleDelete(item: PolicyDocumentItem) {
    if (!window.confirm(`将政策文件「${item.title}」删除？`)) return
    try {
      await deletePolicyDocument(item.id)
      void load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '删除失败')
    }
  }

  return (
    <section className="computer-page report-generation-page">
      {/* ── 工具栏 ── */}
      <div className="computer-toolbar">
        {/* 影响方向：等宽分段控件（与状态筛选同尺寸，视觉均匀） */}
        <div className="policy-segmented">
          {(
            [
              ['', '全部'],
              ['bullish', '利多债券'],
              ['bearish', '利空债券'],
              ['neutral', '中性'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value || 'all'}
              className={directionFilter === value ? 'active' : ''}
              onClick={() => setDirectionFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="computer-spacer" />
        <button className="computer-button" onClick={() => void load()}>
          刷新状态
        </button>
        <button className="computer-button primary" onClick={() => setUploadOpen(true)}>
          ＋ 上传政策文件
        </button>
        <span className="computer-count">
          {loading ? '读取中…' : `${total} 份文件`}
        </span>
      </div>

      {/* ── 统计条 ── */}
      <div className="report-stat-row policy-stat-row">
        {[
          { label: '文件总数', value: stats.total },
          { label: '已解读', value: stats.analyzed, tone: 'done' },
          { label: '利多债券', value: stats.bullish, tone: 'bullish' },
          { label: '利空债券', value: stats.bearish, tone: 'bearish' },
          { label: '中性', value: stats.neutral, tone: 'neutral' },
        ].map((item) => (
          <div key={item.label} className={`report-stat-chip ${item.tone || ''}`}>
            <small>{item.label}</small>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>

      {/* ── 政策文件库 ── */}
      <section className="computer-table-wrap" style={{ marginBottom: 14, overflow: 'visible' }}>
        <div style={{ padding: 13 }}>
          <div className="computer-list-head" style={{ margin: '0 0 10px', padding: 0 }}>
            <div>
              <strong>政策文件库</strong>
              <span>· {total} 份文件</span>
            </div>
            <span className="computer-count">AI 解读结果仅供参考，请以原文为准</span>
          </div>

          <div className="report-library-filters">
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索文件标题"
            />
            <select
              value={directionFilter}
              onChange={(event) => setDirectionFilter(event.target.value)}
            >
              <option value="">全部影响方向</option>
              <option value="bullish">利多债券</option>
              <option value="bearish">利空债券</option>
              <option value="neutral">中性</option>
            </select>
          </div>

          <div className="report-source-list policy-card-list">
            {loading ? (
              <div className="report-empty">正在读取政策文件…</div>
            ) : error ? (
              <div className="report-empty error">
                {error}
                <button type="button" onClick={() => void load()}>
                  重试
                </button>
              </div>
            ) : filtered.length === 0 ? (
              <div className="report-empty">
                {documents.length
                  ? '当前条件下没有匹配的文件，请调整筛选。'
                  : '暂无政策文件，点击右上角「上传政策文件」上传 PDF。'}
              </div>
            ) : (
              filtered.map((item) => (
                <button
                  type="button"
                  className="report-source-card"
                  key={item.id}
                  onClick={() => navigate(`/computer/policy/${item.id}`)}
                >
                  <span>
                    <strong>{item.title}</strong>
                    <small>
                      {item.issuer || '未识别发文机关'}
                      {item.document_no ? ` · ${item.document_no}` : ''}
                      {item.publish_date ? ` · ${item.publish_date}` : ''}
                      {item.page_count ? ` · ${item.page_count} 页` : ''}
                    </small>
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span
                      className={`computer-badge ${STATUS_CSS[item.status] === 'done' ? 'file' : STATUS_CSS[item.status] === 'running' ? 'running' : STATUS_CSS[item.status] === 'failed' ? 'failed' : ''}`}
                      style={{ fontSize: 10 }}
                    >
                      {STATUS_LABEL[item.status] ?? item.status}
                    </span>
                    {item.impact_direction && (
                      <em className={`policy-dir ${item.impact_direction}`}>
                        {DIRECTION_LABEL[item.impact_direction]}
                      </em>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>

          {totalPages > 1 && (
            <div className="report-library-pagination">
              <button
                className="computer-button"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
              >
                上一页
              </button>
              <span>
                {page} / {totalPages}
              </span>
              <button
                className="computer-button"
                disabled={page >= totalPages}
                onClick={() => setPage((value) => value + 1)}
              >
                下一页
              </button>
            </div>
          )}
        </div>
      </section>

      {/* ── 需要处理 ── */}
      <section className="computer-attention">
        <div className="computer-attention-head">
          <strong>需要处理 · {activeItems.length}</strong>
          <span>实时状态</span>
        </div>
        {activeItems.length === 0 ? (
          <div className="computer-attention-row">
            <span className="attention-dot" />
            <div>
              <strong>当前没有解读中的文件</strong>
              <small>上传政策文件后会在此显示解读状态</small>
            </div>
          </div>
        ) : (
          activeItems.map((item) => (
            <div className="computer-attention-row" key={item.id}>
              <span className="attention-dot running" />
              <div>
                <strong>{item.title}</strong>
                <small>
                  {item.issuer || '未识别发文机关'} ·{' '}
                  {item.status === 'uploaded' ? '等待开始解读' : 'AI 正在解读要点与影响方向'}
                </small>
              </div>
              <span className="computer-spacer" />
              <span className="computer-badge running">
                {STATUS_LABEL[item.status] ?? item.status}
              </span>
              <span className="attention-action-cell">
                <button
                  className="computer-button"
                  onClick={() => navigate(`/computer/policy/${item.id}`)}
                >
                  查看详情
                </button>
                <time>{formatDateTime(item.created_at)}</time>
              </span>
            </div>
          ))
        )}
      </section>

      {/* ── 历史记录 ── */}
      <div className="computer-list-head" style={{ marginTop: 18 }}>
        <div>
          <strong>历史记录</strong>
          <span>· {historyItems.length} 份</span>
        </div>
      </div>
      <div className="computer-table-wrap">
        <table className="computer-table">
          <thead>
            <tr>
              <th />
              <th>文件</th>
              <th>发文机关</th>
              <th>影响方向</th>
              <th>状态</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7}>
                  <div className="report-empty">正在读取历史…</div>
                </td>
              </tr>
            ) : visibleHistory.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <div className="report-empty">暂无历史记录</div>
                </td>
              </tr>
            ) : (
              visibleHistory.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => navigate(`/computer/policy/${item.id}`)}
                  className="clickable-row"
                >
                  <td>
                    <span
                      className={`computer-status ${item.status === 'completed' ? 'done' : 'failed'}`}
                    >
                      {item.status === 'completed' ? '✓' : '!'}
                    </span>
                  </td>
                  <td>
                    <strong>{item.title}</strong>
                    <small>{item.document_no || item.original_filename || '—'}</small>
                  </td>
                  <td>{item.issuer || '—'}</td>
                  <td>
                    {item.impact_direction ? (
                      <em className={`policy-dir ${item.impact_direction}`}>
                        {DIRECTION_LABEL[item.impact_direction]}
                      </em>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>
                    <span
                      className={`computer-badge ${item.status === 'completed' ? 'file' : 'failed'}`}
                    >
                      {STATUS_LABEL[item.status] ?? item.status}
                    </span>
                    {item.status === 'failed' && (
                      <button
                        className="inline-retry"
                        onClick={(event) => {
                          event.stopPropagation()
                          void handleReanalyze(item.id)
                        }}
                      >
                        重试
                      </button>
                    )}
                  </td>
                  <td>
                    <time>{formatDateTime(item.created_at)}</time>
                  </td>
                  <td>
                    <button
                      className="computer-delete-button"
                      onClick={(event) => {
                        event.stopPropagation()
                        void handleDelete(item)
                      }}
                      aria-label={`删除 ${item.title}`}
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        {historyItems.length > 5 && (
          <div className="report-history-toggle">
            <button
              className="expand-toggle"
              onClick={() => setShowAllHistory((value) => !value)}
            >
              <i className={'expand-arrow ' + (showAllHistory ? 'up' : 'down')} />
            </button>
          </div>
        )}
      </div>

      {/* ── 底部输入区（与研报页同一形态：标题 + 分析要求 + 发送）── */}
      <form className="report-composer" onSubmit={handleSubmitFocus}>
        <textarea
          className="report-title-input"
          value={focusTitle}
          onChange={(event) => setFocusTitle(event.target.value.replace(/[\r\n]+/g, ' '))}
          maxLength={255}
          rows={1}
          placeholder="分析主题，例如：近期货币政策对债市的影响"
        />
        <textarea
          value={requirement}
          onChange={(event) => setRequirement(event.target.value)}
          maxLength={4000}
          rows={2}
          placeholder="描述你关心的分析角度，例如：重点关注对长端利率与信用利差的影响…"
        />
        <div className="report-task-submit">
          <button
            type="button"
            className="computer-button"
            onClick={() => setUploadOpen(true)}
          >
            ＋ 上传 PDF
          </button>
          <span className="composer-status">
            {pendingUpload
              ? '已填写分析要求，请上传政策文件 PDF 后开始解读'
              : '上传政策文件后将按此要求解读；未填写则按默认角度分析'}
          </span>
          <button
            className="report-send"
            type="submit"
            aria-label="上传并解读政策文件"
            title="上传并解读政策文件"
          >
            ↑
          </button>
        </div>
      </form>

      <PolicyUploadModal
        variant="computer"
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSubmitted={() => {
          setUploadOpen(false)
          setPage(1)
          void load()
        }}
      />
    </section>
  )
}