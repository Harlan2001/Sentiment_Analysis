import { useEffect, useMemo, useRef, useState } from 'react'

type Props = {
  start: string
  end: string
  onChange: (start: string, end: string) => void
  label?: string
}

const DAY_HEADERS = ['一', '二', '三', '四', '五', '六', '日']
const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

function getMonthDays(year: number, month: number): (number | null)[] {
  const firstDay = new Date(year, month, 1).getDay() || 7
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  return [
    ...Array.from({ length: firstDay - 1 }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ]
}

function today() {
  const value = new Date()
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
}

export function WorkflowDateRangePicker({ start, end, onChange, label = '日期范围' }: Props) {
  const anchor = start || end || today()
  const anchorDate = useMemo(() => new Date(`${anchor}T00:00:00`), [anchor])
  const [open, setOpen] = useState(false)
  const [selectingEnd, setSelectingEnd] = useState(false)
  const [year, setYear] = useState(anchorDate.getFullYear())
  const [month, setMonth] = useState(anchorDate.getMonth())
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  function selectDate(value: string) {
    if (!selectingEnd || !start) {
      onChange(value, '')
      setSelectingEnd(true)
      return
    }
    if (value < start) onChange(value, start)
    else onChange(start, value)
    setSelectingEnd(false)
    setOpen(false)
  }

  function changeMonth(delta: number) {
    const next = new Date(year, month + delta, 1)
    setYear(next.getFullYear())
    setMonth(next.getMonth())
  }

  const valueLabel = start ? `${start}${end ? ` 至 ${end}` : ' 至 …'}` : label
  return (
    <div className="computer-date-range" ref={ref}>
      <button
        type="button"
        className={`computer-chip ${start ? 'selected' : ''}`}
        onClick={() => setOpen((value) => !value)}
      >
        <span>▣</span>{valueLabel}
      </button>
      {start && (
        <button type="button" className="computer-chip" onClick={() => { onChange('', ''); setSelectingEnd(false) }}>
          ✕
        </button>
      )}
      {open && (
        <div className="calendar-popup report-calendar-popup">
          <div className="calendar-head">
            <button type="button" onClick={() => changeMonth(-1)}>‹</button>
            <strong>{year}年 {MONTH_NAMES[month]} · {selectingEnd && start ? '选择结束日期' : '选择开始日期'}</strong>
            <button type="button" onClick={() => changeMonth(1)}>›</button>
          </div>
          <div className="calendar-grid">
            {DAY_HEADERS.map((day) => <span key={day} className="calendar-day-header">{day}</span>)}
            {getMonthDays(year, month).map((day, index) => {
              if (day === null) return <span key={`empty-${index}`} />
              const value = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
              const inRange = Boolean(start && end && value >= start && value <= end)
              return (
                <button
                  type="button"
                  key={value}
                  className={`calendar-day ${value === start || value === end ? 'selected' : ''} ${inRange ? 'in-range' : ''}`}
                  onClick={() => selectDate(value)}
                >
                  {day}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
