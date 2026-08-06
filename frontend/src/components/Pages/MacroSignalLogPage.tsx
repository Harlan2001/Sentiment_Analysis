import React, { useState, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle, Button, Input, Select, Loading, Error, Empty } from '@/components/UI'
import { useMacroSignalRequestLogs } from '@/hooks/useMacroSignalLogApi'
import { useNewsDetail } from '@/hooks/useNewsApi'
import { cn } from '@/utils/helpers'
import type { MacroSignalRequestLogItem, MacroSignalRequestLogQuery } from '@/types'
import NewsDetail from './NewsDetail'

// -------- 筛选区 --------
interface FiltersState {
  request_id: string
  factor_code: string
  success: string // '' | '0' | '1'
  signal_type: string // '' | 'presence' | 'directional'
  start_time: string
  end_time: string
}

const DEFAULT_FILTERS: FiltersState = {
  request_id: '',
  factor_code: '',
  success: '',
  signal_type: '',
  start_time: '',
  end_time: '',
}

function buildQuery(filters: FiltersState, page: number, page_size: number): MacroSignalRequestLogQuery {
  const q: MacroSignalRequestLogQuery = { page, page_size }
  if (filters.request_id) q.request_id = filters.request_id
  if (filters.factor_code) q.factor_code = filters.factor_code
  if (filters.success !== '') q.success = Number(filters.success)
  if (filters.signal_type) q.signal_type = filters.signal_type
  if (filters.start_time) q.start_time = filters.start_time
  if (filters.end_time) q.end_time = filters.end_time
  return q
}

// -------- 新闻详情侧边栏 --------
interface NewsSidebarProps {
  newsId: number
  onClose: () => void
}

const NewsSidebar: React.FC<NewsSidebarProps> = ({ newsId, onClose }) => {
  const { data: news, isLoading, error } = useNewsDetail(newsId)
  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-2xl z-50 flex flex-col bg-gray-900 border-l border-gray-700 shadow-2xl overflow-y-auto">
      <div className="flex items-center justify-between p-4 border-b border-gray-700 sticky top-0 bg-gray-900 z-10">
        <span className="text-gray-300 font-semibold">新闻详情 #{newsId}</span>
        <button onClick={onClose} className="text-gray-400 hover:text-white text-xl px-2">
          ✕
        </button>
      </div>
      <div className="p-4 flex-1">
        {isLoading && <Loading />}
        {error && <Error message="加载新闻详情失败" />}
        {news && !isLoading && <NewsDetail news={news} onClose={onClose} />}
      </div>
    </div>
  )
}

// -------- 请求详情面板（聚合同一 request_id 的行） --------
interface RequestDetailPanelProps {
  rows: MacroSignalRequestLogItem[]
  onNewsClick: (newsId: number) => void
  onClose: () => void
}

const RequestDetailPanel: React.FC<RequestDetailPanelProps> = ({ rows, onNewsClick, onClose }) => {
  const [expandedNewsRow, setExpandedNewsRow] = useState<number | null>(null)
  if (rows.length === 0) return null

  const successCount = rows.filter((r) => r.success === 1).length
  const totalNews = rows.reduce((s, r) => s + (r.queried_news?.length || 0), 0)
  const latencies = rows.map((r) => r.latency_ms).filter((v): v is number => v !== null)
  const latencyRange = latencies.length > 0 ? `${Math.min(...latencies)} ~ ${Math.max(...latencies)} ms` : '-'

  return (
    <div className="mt-4 bg-gray-800 border border-gray-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-gray-200">
          请求聚合视图 &nbsp;
          <span className="text-gray-400 font-mono text-xs">{rows[0].request_id}</span>
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-white text-xs">
          关闭
        </button>
      </div>
      <div className="flex gap-6 text-xs text-gray-400 mb-4">
        <span>
          因子数：<b className="text-gray-200">{rows.length}</b>
        </span>
        <span>
          成功率：
          <b className="text-gray-200">
            {successCount}/{rows.length}
          </b>
        </span>
        <span>
          命中新闻总数：<b className="text-gray-200">{totalNews}</b>
        </span>
        <span>
          耗时区间：<b className="text-gray-200">{latencyRange}</b>
        </span>
      </div>
      <div className="space-y-2">
        {rows.map((row) => (
          <div
            key={row.id}
            className={`p-3 rounded-lg border ${row.success === 0 ? 'border-red-700 bg-red-950/30' : 'border-gray-700 bg-gray-900/50'}`}
          >
            <div className="flex items-center gap-3 text-xs">
              <span
                className={`px-2 py-0.5 rounded font-semibold ${row.success === 1 ? 'bg-green-800/60 text-green-300' : 'bg-red-800/60 text-red-300'}`}
              >
                {row.success === 1 ? '成功' : '失败'}
              </span>
              <span className="text-gray-300 font-mono">{row.factor_code}</span>
              {row.factor_name && <span className="text-gray-500">{row.factor_name}</span>}
              <span className="text-gray-500">{row.signal_type}</span>
              {row.signal_value !== null && (
                <span className="text-blue-300">信号值: {row.signal_value.toFixed(4)}</span>
              )}
              {row.confidence !== null && <span className="text-purple-300">置信度: {row.confidence.toFixed(4)}</span>}
              {row.latency_ms !== null && <span className="text-gray-500">{row.latency_ms} ms</span>}
            </div>
            {row.error_message && <div className="mt-1 text-xs text-red-400">{row.error_message}</div>}
            {row.queried_news && row.queried_news.length > 0 && (
              <div className="mt-2">
                <button
                  className="text-xs text-blue-400 hover:text-blue-200 underline"
                  onClick={() => setExpandedNewsRow(expandedNewsRow === row.id ? null : row.id)}
                >
                  {expandedNewsRow === row.id ? '折叠' : `展开`} 命中新闻 ({row.queried_news.length})
                </button>
                {expandedNewsRow === row.id && (
                  <div className="mt-1 flex flex-wrap gap-2">
                    {row.queried_news.map((nid) => (
                      <button
                        key={nid}
                        className="text-xs px-2 py-0.5 bg-blue-900/50 text-blue-300 rounded hover:bg-blue-800/70 transition-colors"
                        onClick={() => onNewsClick(nid)}
                      >
                        #{nid}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// -------- 主页面 --------
const MacroSignalLogPage: React.FC<{ embedded?: boolean }> = ({ embedded = false }) => {
  const [filters, setFilters] = useState<FiltersState>(DEFAULT_FILTERS)
  const [pendingFilters, setPendingFilters] = useState<FiltersState>(DEFAULT_FILTERS)
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20

  const query = buildQuery(filters, page, PAGE_SIZE)
  const { data, isLoading, error } = useMacroSignalRequestLogs(query)

  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null)
  const [selectedNewsId, setSelectedNewsId] = useState<number | null>(null)

  const handleSearch = useCallback(() => {
    setFilters(pendingFilters)
    setPage(1)
    setSelectedRequestId(null)
  }, [pendingFilters])

  const handleReset = useCallback(() => {
    setPendingFilters(DEFAULT_FILTERS)
    setFilters(DEFAULT_FILTERS)
    setPage(1)
    setSelectedRequestId(null)
  }, [])

  const handleRowClick = (requestId: string) => {
    setSelectedRequestId((prev) => (prev === requestId ? null : requestId))
  }

  const selectedRows = data?.items.filter((r) => r.request_id === selectedRequestId) ?? []

  const pagination = data?.pagination

  return (
    <div className={cn(embedded ? 'space-y-4' : 'max-w-7xl mx-auto px-4 py-6 space-y-4')}>
      {/* 页面标题（独立页展示，嵌入看板时隐藏） */}
      {!embedded && (
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            宏观信号请求日志
          </h1>
          <p className="text-gray-500 text-sm mt-1">查询每次宏观信号接口调用的详细记录</p>
        </div>
      )}

      {/* 筛选区 */}
      <Card>
        <CardHeader>
          <CardTitle>筛选条件</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <Input
              placeholder="Request ID"
              value={pendingFilters.request_id}
              onChange={(e) => setPendingFilters((f) => ({ ...f, request_id: e.target.value }))}
            />
            <Input
              placeholder="因子代码（如 A001）"
              value={pendingFilters.factor_code}
              onChange={(e) => setPendingFilters((f) => ({ ...f, factor_code: e.target.value }))}
            />
            <Select
              value={pendingFilters.success}
              onChange={(e) => setPendingFilters((f) => ({ ...f, success: e.target.value }))}
            >
              <option value="">全部状态</option>
              <option value="1">成功</option>
              <option value="0">失败</option>
            </Select>
            <Select
              value={pendingFilters.signal_type}
              onChange={(e) => setPendingFilters((f) => ({ ...f, signal_type: e.target.value }))}
            >
              <option value="">全部信号类型</option>
              <option value="presence">presence</option>
              <option value="directional">directional</option>
            </Select>
            <Input
              type="datetime-local"
              placeholder="开始时间"
              value={pendingFilters.start_time}
              onChange={(e) => setPendingFilters((f) => ({ ...f, start_time: e.target.value }))}
            />
            <Input
              type="datetime-local"
              placeholder="结束时间"
              value={pendingFilters.end_time}
              onChange={(e) => setPendingFilters((f) => ({ ...f, end_time: e.target.value }))}
            />
          </div>
          <div className="flex gap-2 mt-3">
            <Button onClick={handleSearch} variant="primary" size="sm">
              查询
            </Button>
            <Button onClick={handleReset} variant="secondary" size="sm">
              重置
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 日志表格 */}
      <Card>
        <CardHeader>
          <CardTitle>
            日志列表
            {pagination && <span className="ml-2 text-sm font-normal text-gray-400">共 {pagination.total} 条</span>}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading && (
            <div className="p-6">
              <Loading />
            </div>
          )}
          {error && (
            <div className="p-6">
              <Error message={(error as Error).message || '加载失败'} />
            </div>
          )}
          {!isLoading && !error && data?.items.length === 0 && (
            <div className="p-6">
              <Empty message="暂无日志数据" />
            </div>
          )}
          {!isLoading && !error && data && data.items.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-gray-300">
                <thead>
                  <tr className="border-b border-gray-700 bg-gray-800/60 text-gray-400">
                    <th className="text-left px-4 py-2">状态</th>
                    <th className="text-left px-4 py-2">Request ID</th>
                    <th className="text-left px-4 py-2">因子代码</th>
                    <th className="text-left px-4 py-2">信号类型</th>
                    <th className="text-right px-4 py-2">信号值</th>
                    <th className="text-right px-4 py-2">置信度</th>
                    <th className="text-right px-4 py-2">命中新闻</th>
                    <th className="text-left px-4 py-2">started_at</th>
                    <th className="text-right px-4 py-2">耗时(ms)</th>
                    <th className="text-left px-4 py-2">错误信息</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((row) => (
                    <tr
                      key={row.id}
                      className={`border-b border-gray-800 cursor-pointer transition-colors ${
                        row.success === 0 ? 'bg-red-950/20 hover:bg-red-950/40' : 'hover:bg-gray-800/50'
                      } ${selectedRequestId === row.request_id ? 'ring-1 ring-inset ring-blue-500' : ''}`}
                      onClick={() => handleRowClick(row.request_id)}
                    >
                      <td className="px-4 py-2">
                        <span
                          className={`px-2 py-0.5 rounded font-semibold ${row.success === 1 ? 'bg-green-800/60 text-green-300' : 'bg-red-800/60 text-red-300'}`}
                        >
                          {row.success === 1 ? '成功' : '失败'}
                        </span>
                      </td>
                      <td className="px-4 py-2 font-mono text-gray-400 max-w-[160px] truncate" title={row.request_id}>
                        {row.request_id.slice(0, 8)}…
                      </td>
                      <td className="px-4 py-2 font-mono text-blue-300">
                        {row.factor_code}
                        {row.factor_name && <span className="ml-2 font-sans text-gray-400">{row.factor_name}</span>}
                      </td>
                      <td className="px-4 py-2 text-gray-400">{row.signal_type}</td>
                      <td className="px-4 py-2 text-right">
                        {row.signal_value !== null ? row.signal_value.toFixed(4) : '-'}
                      </td>
                      <td className="px-4 py-2 text-right">
                        {row.confidence !== null ? row.confidence.toFixed(4) : '-'}
                      </td>
                      <td className="px-4 py-2 text-right text-blue-400">{row.news_count}</td>
                      <td className="px-4 py-2 text-gray-500">
                        {row.started_at ? row.started_at.replace('T', ' ').slice(0, 19) : '-'}
                      </td>
                      <td className="px-4 py-2 text-right text-gray-500">{row.latency_ms ?? '-'}</td>
                      <td className="px-4 py-2 max-w-[200px] truncate text-red-400" title={row.error_message ?? ''}>
                        {row.error_message || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 分页 */}
          {pagination && pagination.total_pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
              <span className="text-xs text-gray-500">
                第 {pagination.page} / {pagination.total_pages} 页，共 {pagination.total} 条
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={pagination.page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  上一页
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={pagination.page >= pagination.total_pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一页
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 请求聚合详情 */}
      {selectedRequestId && selectedRows.length > 0 && (
        <RequestDetailPanel
          rows={selectedRows}
          onNewsClick={(id) => setSelectedNewsId(id)}
          onClose={() => setSelectedRequestId(null)}
        />
      )}

      {/* 新闻详情侧边栏 */}
      {selectedNewsId !== null && <NewsSidebar newsId={selectedNewsId} onClose={() => setSelectedNewsId(null)} />}
    </div>
  )
}

export default MacroSignalLogPage
