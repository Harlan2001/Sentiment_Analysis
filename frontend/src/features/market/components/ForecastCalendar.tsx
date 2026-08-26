import { useMemo, useState } from 'react'

const DAY_HEADERS = ['一', '二', '三', '四', '五', '六', '日']

function monthCells(year: number, month: number): (number | null)[] {
  const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7 // 周一=0
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  return [...Array.from({ length: firstWeekday }, () => null), ...Array.from({ length: daysInMonth }, (_, index) => index + 1)]
}

type Direction = 'up' | 'down'

export default function ForecastCalendar({
  history,
  selectedDate,
  onSelect,
}: {
  history?: any[]
  selectedDate: string | null
  onSelect: (date: string) => void
}) {
  const today = useMemo(() => new Date(), [])
  const [month, setMonth] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1))

  // 日期 -> 当日日度预测方向（看涨/看跌）
  const dayMap = useMemo(() => {
    const map = new Map<string, Direction>()
    for (const item of history || []) {
      const day = item.reports?.full_report?.预测结果?.日 || item.reports?.day
      if (!day) continue
      map.set(item.date, (day.上涨概率 || 0) >= (day.下跌概率 || 0) ? 'up' : 'down')
    }
    return map
  }, [history])

  function changeMonth(offset: number) {
    setMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + offset, 1))
  }

  return (
    <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] px-4 pb-4 pt-2">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-white">预测日历</h2>
        <span className="text-[11px] text-gray-500">点击日期查看当日预测报告</span>
      </div>
      <div className="returns-calendar-month-controls flex items-center justify-between">
        <button onClick={() => changeMonth(-1)} className="w-7 h-7 rounded border border-[#2a2a2e] text-gray-400 hover:bg-[#181818]" aria-label="上个月">‹</button>
        <h3>{month.getFullYear()}年 {month.getMonth() + 1}月</h3>
        <button onClick={() => changeMonth(1)} className="w-7 h-7 rounded border border-[#2a2a2e] text-gray-400 hover:bg-[#181818]" aria-label="下个月">›</button>
      </div>
      <div className="returns-month-calendar">
        {DAY_HEADERS.map((day) => <span className="returns-calendar-weekday" key={day}>{day}</span>)}
        {monthCells(month.getFullYear(), month.getMonth()).map((day, index) => {
          if (day === null) return <span key={`blank-${index}`} />
          const value = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const direction = dayMap.get(value)
          const cls = `returns-calendar-day${selectedDate === value ? ' selected' : ''}`
          if (!direction) return <span key={value} className={cls} style={{ opacity: 0.25, cursor: 'default' }}>{day}</span>
          return (
            <button key={value} className={cls} onClick={() => onSelect(value)}>
              <span>{day}</span>
              {direction === 'up' ? <i><b>●</b></i> : <i><em>●</em></i>}
            </button>
          )
        })}
      </div>
      <div className="returns-calendar-legend"><span><i className="bullish" />看涨</span><span><i className="bearish" />看跌</span></div>
    </section>
  )
}
