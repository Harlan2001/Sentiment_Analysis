import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchReturnsCalendar } from '@/api/market'
import { Skeleton } from '@/components/UI'
import NewsDetailPanel from '../components/NewsDetailPanel'

const DAY_HEADERS = ['一', '二', '三', '四', '五', '六', '日']

function dateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function dateLabel(value: string) {
  const [, month, day] = value.split('-')
  return `${Number(month)}月${Number(day)}日`
}

function monthCells(year: number, month: number): (number | null)[] {
  const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  return [...Array.from({ length: firstWeekday }, () => null), ...Array.from({ length: daysInMonth }, (_, index) => index + 1)]
}

export default function ReturnsPage() {
  const today = useMemo(() => new Date(), [])
  const [calendarMonth, setCalendarMonth] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1))
  const [selectedDate, setSelectedDate] = useState(dateKey(today))
  const [newsId, setNewsId] = useState<number | null>(null)
  const range = useMemo(() => {
    const start = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 1)
    const end = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 0)
    return { start: dateKey(start), end: dateKey(end) }
  }, [calendarMonth])
  const { data, isLoading, isError } = useQuery({ queryKey: ['returns-calendar', range], queryFn: () => fetchReturnsCalendar(range), staleTime: 5 * 60 * 1000 })
  const news = data?.news_by_date?.[selectedDate] || []
  const bullish = news.filter((item) => item.direction === '利多')
  const bearish = news.filter((item) => item.direction === '利空')
  const factors = data?.days.find((day) => day.date === selectedDate)?.active_factors || []
  const yields = data?.yields_by_date?.[selectedDate] || {}
  const calendarDays = useMemo(() => new Map((data?.days || []).map((day) => [day.date, day])), [data])

  function changeMonth(offset: number) {
    const next = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + offset, 1)
    setCalendarMonth(next)
    setSelectedDate(dateKey(next))
  }

  return <div className="home-section-page">
    <header className="home-section-heading returns-section-heading"><div><h1 className="text-lg font-bold text-white">方向性新闻</h1><p className="text-xs text-gray-500 mt-1">{dateLabel(selectedDate)} · 由收益日历筛选</p></div><h2 className="returns-calendar-label">收益日历</h2></header>
    <div className="home-section-grid">
      <main className="home-section-main space-y-4">
        {isLoading ? <Skeleton height="420px" variant="rectangular" /> : isError || !data ? <Empty text="收益数据加载失败，请稍后重试" /> : <>
          {Object.keys(yields).length > 0 && <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4"><h2 className="text-sm font-medium text-amber-400 mb-3">国债收益率变动</h2><div className="grid grid-cols-3 sm:grid-cols-5 gap-3">{Object.entries(yields).map(([key, item]: [string, any]) => <div key={key}><p className="text-xs text-gray-500">{item.label || key}</p><p className={item.direction === 'up' ? 'text-sm text-red-400' : item.direction === 'down' ? 'text-sm text-green-400' : 'text-sm text-gray-300'}>{item.diff_bp > 0 ? '+' : ''}{item.diff_bp} BP</p></div>)}</div></section>}
          <NewsGroup title="利多新闻" tone="red" items={bullish} onOpen={setNewsId} /><NewsGroup title="利空新闻" tone="green" items={bearish} onOpen={setNewsId} />
          {!bullish.length && !bearish.length && <Empty text="该日期暂无方向性新闻" />}
        </>}
      </main>
      <aside className="home-section-sidebar returns-sidebar">
        <div className="returns-calendar-pane">
        <section className="returns-sidebar-card rounded-xl border border-[#2a2a2e] bg-[#111111] p-4">
          <div className="returns-calendar-month-controls flex items-center justify-between"><button onClick={() => changeMonth(-1)} className="w-7 h-7 rounded border border-[#2a2a2e] text-gray-400 hover:bg-[#181818]" aria-label="上个月">‹</button><h3>{calendarMonth.getFullYear()}年 {calendarMonth.getMonth() + 1}月</h3><button onClick={() => changeMonth(1)} className="w-7 h-7 rounded border border-[#2a2a2e] text-gray-400 hover:bg-[#181818]" aria-label="下个月">›</button></div>
          <div className="returns-month-calendar">{DAY_HEADERS.map((day) => <span className="returns-calendar-weekday" key={day}>{day}</span>)}{monthCells(calendarMonth.getFullYear(), calendarMonth.getMonth()).map((day, index) => {
            if (day === null) return <span key={`blank-${index}`} />
            const value = `${calendarMonth.getFullYear()}-${String(calendarMonth.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
            const summary = calendarDays.get(value)
            return <button key={value} onClick={() => setSelectedDate(value)} className={`returns-calendar-day${selectedDate === value ? ' selected' : ''}`}><span>{day}</span>{summary && (summary.bullish_count > 0 || summary.bearish_count > 0) && <i><b>{summary.bullish_count}</b><em>{summary.bearish_count}</em></i>}</button>
          })}</div>
          <div className="returns-calendar-legend"><span><i className="bullish" />利多</span><span><i className="bearish" />利空</span></div>
        </section>
        </div>
        <section className="returns-sidebar-card rounded-xl border border-[#2a2a2e] bg-[#111111] p-4"><h2 className="returns-factor-heading text-sm font-semibold text-white mb-3">活跃因子</h2>{factors.length ? <div className="space-y-2">{factors.map((factor, index) => <div key={factor.id} className="rounded-lg border border-[#1e1e1e] bg-[#0d0d0d] px-3 py-2"><div className="flex justify-between gap-3"><span className="text-sm text-gray-200 truncate">{index + 1}. {factor.name}</span><span className="text-xs text-amber-400">{factor.news_count}</span></div><p className="text-xs text-gray-600 mt-1">{factor.category} · {factor.news_count} 条新闻</p></div>)}</div> : <p className="text-sm text-gray-600 text-center py-5">暂无活跃因子</p>}</section>
      </aside>
    </div>
    {newsId !== null && <div className="fixed inset-0 z-50 bg-[#0d0d0d] overflow-y-auto"><NewsDetailPanel newsId={newsId} onClose={() => setNewsId(null)} onNewsClick={setNewsId} /></div>}
  </div>
}

function NewsGroup({ title, tone, items, onOpen }: { title: string; tone: 'red' | 'green'; items: any[]; onOpen: (id: number) => void }) {
  if (!items.length) return null
  const color = tone === 'red' ? 'text-red-400' : 'text-green-400'
  return <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-4"><h2 className={`text-sm font-medium ${color} mb-3`}>{title} · {items.length} 条</h2><div className="space-y-2">{items.map((item) => <button key={item.id} onClick={() => onOpen(item.id)} className="w-full text-left rounded-lg border border-[#1e1e1e] bg-[#0d0d0d] p-3 hover:bg-[#181818]"><p className="text-sm text-gray-200 leading-snug">{item.title}</p><p className="mt-2 text-xs text-gray-600">{item.source || ''} · {item.pub_time?.slice(5, 16) || ''}</p></button>)}</div></section>
}

function Empty({ text }: { text: string }) {
  return <div className="min-h-[180px] rounded-xl border border-[#2a2a2e] bg-[#111111] flex items-center justify-center text-sm text-gray-600">{text}</div>
}
