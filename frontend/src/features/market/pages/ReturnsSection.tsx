/**
 * 收益页面 — 收益日历 + 方向性新闻 + 活跃因子 + 宏观数据
 */
import React, { useCallback, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchReturnsCalendar, fetchFactorDetail } from '@/api/market'
import NewsDetailPanel from '../components/NewsDetailPanel'
import { Skeleton } from '@/components/UI'
import type { ReturnsCalendarResponse, CalendarNewsItem, FactorDetailData } from '@/types'

function getWeekRange(date: Date): { start: string; end: string } {
  const d = new Date(date)
  const day = d.getDay()
  const mondayOffset = day === 0 ? -6 : 1 - day
  const monday = new Date(d)
  monday.setDate(d.getDate() + mondayOffset)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  const fmt = (dt: Date) => {
    const y = dt.getFullYear()
    const m = String(dt.getMonth() + 1).padStart(2, '0')
    const dd = String(dt.getDate()).padStart(2, '0')
    return `${y}-${m}-${dd}`
  }
  return { start: fmt(monday), end: fmt(sunday) }
}

function formatDateLabel(dateStr: string): string {
  const parts = dateStr.split('-')
  return `${parseInt(parts[1])}月${parseInt(parts[2])}日`
}

function formatMonthLabel(dateStr: string): string {
  const parts = dateStr.split('-')
  return `${parseInt(parts[1])}月`
}

const ReturnsSection: React.FC = () => {
  const [weekOffset, setWeekOffset] = useState(0)
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [detailNewsId, setDetailNewsId] = useState<number | null>(null)
  const [expandedFactorId, setExpandedFactorId] = useState<number | null>(null)

  const today = new Date()
  const todayStr = today.toISOString().slice(0, 10)
  const baseDate = new Date(today)
  baseDate.setDate(baseDate.getDate() + weekOffset * 7)
  const { start, end } = useMemo(() => getWeekRange(baseDate), [weekOffset])

  const { data, isLoading, isError } = useQuery({
    queryKey: ['returns-calendar', start, end],
    queryFn: () => fetchReturnsCalendar({ start, end }),
    staleTime: 5 * 60 * 1000,
  })

  const handleDayClick = useCallback((dateStr: string) => {
    setSelectedDate(dateStr)
    setExpandedFactorId(null)
  }, [])

  const handleNewsClick = useCallback((newsId: number) => {
    setDetailNewsId(newsId)
  }, [])

  const handleCloseDetail = useCallback(() => {
    setDetailNewsId(null)
  }, [])

  const weekLabel = useMemo(() => {
    if (!data) return ''
    return `${formatDateLabel(start)}-${formatDateLabel(end)}`
  }, [data, start, end])

  const selectedYields = useMemo(() => {
    return data?.yields_by_date?.[selectedDate] || {}
  }, [data, selectedDate])

  const selectedMonth = selectedDate.slice(0, 7).replace('-', '')
  const selectedMacro = useMemo(() => {
    return data?.macro_by_month?.[selectedMonth] || []
  }, [data, selectedMonth])

  const { liduoNews, likongNews } = useMemo(() => {
    const news = data?.news_by_date?.[selectedDate] || []
    return {
      liduoNews: news.filter(n => n.direction === '利多'),
      likongNews: news.filter(n => n.direction === '利空'),
    }
  }, [data, selectedDate])

  const activeFactors = useMemo(() => {
    return data?.days.find(d => d.date === selectedDate)?.active_factors || []
  }, [data, selectedDate])

  return (
    <div className="flex flex-col h-full overflow-y-auto relative">
      <div className="p-5 space-y-5">

        {/* 标题行 */}
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold text-white">收益日历</h1>
          <div className="flex items-center gap-3">
            <button
              className="w-7 h-7 rounded-full border border-[#2a2a2e] flex items-center justify-center text-gray-400 hover:text-white hover:bg-[#1a1b1e] transition-colors"
              onClick={() => setWeekOffset(w => w - 1)}
            >◀</button>
            <span className="text-sm text-gray-300 font-medium min-w-[140px] text-center">{weekLabel}</span>
            <button
              className="w-7 h-7 rounded-full border border-[#2a2a2e] flex items-center justify-center text-gray-400 hover:text-white hover:bg-[#1a1b1e] transition-colors"
              onClick={() => setWeekOffset(w => w + 1)}
            >▶</button>
            <button
              className="text-xs text-amber-400 hover:text-amber-300 transition-colors"
              onClick={() => { setWeekOffset(0); setSelectedDate(todayStr); setExpandedFactorId(null) }}
            >今天</button>
          </div>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            <Skeleton height="108px" variant="rectangular" />
            <Skeleton height="60px" variant="rectangular" />
            <Skeleton height="280px" variant="rectangular" />
          </div>
        ) : isError || !data ? (
          <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
            收益日历加载失败，请稍后重试
          </div>
        ) : (
          <>
            {/* ── 周历条 ── */}
            <div className="flex gap-2 overflow-x-auto pb-1">
              {data.days.map((day) => {
                const isSelected = day.date === selectedDate
                const isToday = day.date === todayStr
                const hasData = day.bullish_count + day.bearish_count > 0
                return (
                  <button
                    key={day.date}
                    className={[
                      'min-w-[100px] flex-1 rounded-xl border p-3 flex flex-col items-center transition-all duration-150',
                      isSelected
                        ? 'ring-1 ring-amber-500/60 border-amber-500/40 bg-[#1a1b1e]'
                        : 'border-[#2a2a2e] bg-[#111111] hover:border-[#3a3a3e] hover:bg-[#161616]',
                    ].join(' ')}
                    onClick={() => handleDayClick(day.date)}
                  >
                    <span className={['text-xs font-medium mb-1', isSelected ? 'text-gray-200' : 'text-gray-500'].join(' ')}>
                      {day.weekday}{isToday && <span className="ml-1 text-amber-400">·今</span>}
                    </span>
                    <span className={['text-sm font-medium leading-none mb-1.5', isSelected ? 'text-white' : 'text-gray-300'].join(' ')}>
                      {formatDateLabel(day.date)}
                    </span>
                    {hasData ? (
                      <div className="flex gap-1.5 text-xs">
                        <span className="text-red-400/80">利多{day.bullish_count}</span>
                        <span className="text-green-400/80">利空{day.bearish_count}</span>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-600">无数据</span>
                    )}
                  </button>
                )
              })}
            </div>

            {/* ── 选中日标题 ── */}
            <div className="flex items-center gap-2">
              <div className="h-px flex-1 bg-[#2a2a2e]" />
              <span className="text-sm text-gray-400 px-2">
                {formatDateLabel(selectedDate)} · {['周日','周一','周二','周三','周四','周五','周六'][new Date(selectedDate).getDay()]}
              </span>
              <div className="h-px flex-1 bg-[#2a2a2e]" />
            </div>

            {/* ── 国债收益率变动 ── */}
            {Object.keys(selectedYields).length > 0 && (
              <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
                <h3 className="text-xs font-medium text-gray-500 mb-3">国债收益率变动</h3>
                <div className="grid grid-cols-5 sm:grid-cols-9 gap-2">
                  {['3M','6M','1Y','2Y','3Y','5Y','7Y','10Y','30Y'].map(p => {
                    const item = selectedYields[p]
                    if (!item) return null
                    return (
                      <div key={p} className="text-center">
                        <div className="text-xs text-gray-500 mb-1">{item.label}</div>
                        <div className={['text-sm font-semibold',
                          item.direction === 'up' ? 'text-red-400' : item.direction === 'down' ? 'text-green-400' : 'text-gray-400'].join(' ')}>
                          {item.diff_bp > 0 ? '+' : ''}{item.diff_bp}BP
                        </div>
                      </div>
                    )
                  })}
                </div>
                <div className="mt-2 text-xs text-gray-600 text-right">红色=收益率上行，绿色=收益率下行</div>
              </div>
            )}

            {/* ── 方向性新闻 + 活跃因子 ── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 space-y-4">
                {/* 利多新闻 */}
                {liduoNews.length > 0 && (
                  <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
                    <h3 className="text-xs font-medium text-red-400 mb-3">
                      利多新闻 · {liduoNews.length}条
                    </h3>
                    <div className="space-y-2 max-h-[360px] overflow-y-auto">
                      {liduoNews.map(news => (
                        <NewsRow key={news.id} news={news} onClick={() => handleNewsClick(news.id)} />
                      ))}
                    </div>
                  </div>
                )}
                {/* 利空新闻 */}
                {likongNews.length > 0 && (
                  <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
                    <h3 className="text-xs font-medium text-green-400 mb-3">
                      利空新闻 · {likongNews.length}条
                    </h3>
                    <div className="space-y-2 max-h-[360px] overflow-y-auto">
                      {likongNews.map(news => (
                        <NewsRow key={news.id} news={news} onClick={() => handleNewsClick(news.id)} />
                      ))}
                    </div>
                  </div>
                )}
                {liduoNews.length === 0 && likongNews.length === 0 && (
                  <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
                    <h3 className="text-xs font-medium text-gray-500 mb-3">方向性新闻</h3>
                    <div className="text-center py-8 text-gray-600 text-sm">当日无方向性新闻</div>
                  </div>
                )}
              </div>

              {/* 活跃因子（可展开） */}
              <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
                <h3 className="text-xs font-medium text-gray-500 mb-3">当日活跃因子</h3>
                {activeFactors.length === 0 ? (
                  <div className="text-center py-8 text-gray-600 text-sm">暂无活跃因子</div>
                ) : (
                  <div className="space-y-1">
                    {activeFactors.map((f, i) => (
                      <FactorRow
                        key={f.id}
                        factor={f}
                        rank={i + 1}
                        expanded={expandedFactorId === f.id}
                        selectedDate={selectedDate}
                        onToggle={() => setExpandedFactorId(expandedFactorId === f.id ? null : f.id)}
                        onNewsClick={handleNewsClick}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* ── 本月宏观数据 ── */}
            {selectedMacro.length > 0 && (
              <div className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
                <h3 className="text-xs font-medium text-gray-500 mb-3">
                  本月宏观数据（{formatMonthLabel(selectedDate)}）
                </h3>
                <div className="flex flex-wrap gap-2">
                  {selectedMacro.map(m => (
                    <span key={m.code} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a1b1e] border border-[#2a2a2e] text-sm">
                      <span className="text-gray-400">{m.name}</span>
                      <span className="text-white font-medium">{m.value != null ? m.value : '-'}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* 新闻详情覆盖层 — 全屏覆盖 */}
      {detailNewsId != null && (
        <div className="fixed inset-0 z-50 bg-[#0d0d0d] overflow-y-auto">
          <NewsDetailPanel
            newsId={detailNewsId}
            onClose={handleCloseDetail}
            onNewsClick={handleNewsClick}
          />
        </div>
      )}
    </div>
  )
}

/** 方向性新闻行 */
function NewsRow({ news, onClick }: { news: CalendarNewsItem; onClick: () => void }) {
  const isLiduo = news.direction === '利多'
  return (
    <button
      className="w-full text-left rounded-lg border border-[#1e1e1e] bg-[#0d0d0d] hover:border-[#3a3a3e] hover:bg-[#141414] p-3 transition-all duration-150 group"
      onClick={onClick}
    >
      <div className="flex items-start gap-2">
        <span className={['mt-0.5 shrink-0 text-xs px-1.5 py-0.5 rounded font-medium',
          isLiduo ? 'bg-red-500/15 text-red-400' : 'bg-green-500/15 text-green-400'].join(' ')}>
          {news.direction}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm text-gray-200 leading-snug line-clamp-2 group-hover:text-white transition-colors">
            {news.title}
          </div>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {news.factors.map(f => (
              <span key={f.id} className="text-xs text-gray-600">{f.name}</span>
            ))}
            {news.horizon && <span className="text-xs text-gray-700">· {news.horizon}</span>}
            <span className="text-xs text-gray-700">· {news.pub_time ? news.pub_time.slice(11, 16) : ''}</span>
            {news.source && <span className="text-xs text-gray-700">· {news.source}</span>}
          </div>
        </div>
        <span className="text-gray-700 text-lg shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">→</span>
      </div>
    </button>
  )
}

/** 可展开的因子行 */
function FactorRow({
  factor, rank, expanded, selectedDate, onToggle, onNewsClick,
}: {
  factor: { id: number; name: string; category: string; news_count: number }
  rank: number
  expanded: boolean
  selectedDate: string
  onToggle: () => void
  onNewsClick: (newsId: number) => void
}) {
  const { data: factorDetail, isFetching } = useQuery({
    queryKey: ['factor-detail', factor.id],
    queryFn: () => fetchFactorDetail(factor.id),
    enabled: expanded,
    staleTime: 60 * 1000,
  })

  // 从 factor detail 中筛选选中日期的新闻
  const dayNews = useMemo(() => {
    if (!factorDetail?.related_news) return []
    return factorDetail.related_news.filter(n => n.pub_time?.startsWith(selectedDate))
  }, [factorDetail, selectedDate])

  return (
    <div>
      <button
        className="w-full flex items-center gap-3 py-2 px-2 rounded-lg hover:bg-[#1a1b1e] transition-colors group"
        onClick={onToggle}
      >
        <span className="text-xs text-gray-600 w-4">{rank}</span>
        <div className="flex-1 min-w-0 text-left">
          <div className="text-sm text-gray-200 truncate">{factor.name}</div>
          <div className="text-xs text-gray-600">{factor.category} · {factor.news_count}条新闻</div>
        </div>
        <div className="h-1.5 flex-1 max-w-[80px] rounded-full bg-[#1e1e1e] overflow-hidden">
          <div className="h-full rounded-full bg-amber-500/60" style={{ width: `${Math.min(factor.news_count * 15, 100)}%` }} />
        </div>
        <span className={['text-gray-600 text-xs transition-transform', expanded ? 'rotate-90' : ''].join(' ')}>▶</span>
      </button>

      {/* 展开后的新闻列表 */}
      {expanded && (
        <div className="ml-9 mt-1 mb-2 space-y-1">
          {isFetching ? (
            <div className="text-xs text-gray-600 py-2">加载中...</div>
          ) : dayNews.length === 0 ? (
            <div className="text-xs text-gray-600 py-2">当日暂无相关新闻</div>
          ) : (
            dayNews.slice(0, 10).map(n => (
              <button
                key={n.id}
                className="w-full text-left text-xs text-gray-400 hover:text-gray-200 hover:bg-[#1a1b1e] rounded px-1.5 py-1 transition-colors truncate block"
                onClick={(e) => { e.stopPropagation(); onNewsClick(n.id) }}
              >
                {n.direction === 'positive' && <span className="text-red-400 mr-1">利多</span>}
                {n.direction === 'negative' && <span className="text-green-400 mr-1">利空</span>}
                {n.title}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default ReturnsSection
