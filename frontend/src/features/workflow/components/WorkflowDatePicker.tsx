import { useEffect, useMemo, useRef, useState } from 'react'

type Props = {
  value: string
  onChange: (value: string) => void
  label?: string
  popupAlign?: 'left' | 'right'
  inlinePopup?: boolean
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

export function WorkflowDatePicker({ value, onChange, label = '日期', popupAlign = 'right', inlinePopup = false }: Props) {
  const selectedDate = useMemo(() => value ? new Date(`${value}T00:00:00`) : new Date(), [value])
  const [open, setOpen] = useState(false)
  const [year, setYear] = useState(selectedDate.getFullYear())
  const [month, setMonth] = useState(selectedDate.getMonth())
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  function toggleCalendar() {
    setYear(selectedDate.getFullYear())
    setMonth(selectedDate.getMonth())
    setOpen((current) => !current)
  }

  function changeMonth(delta: number) {
    const next = new Date(year, month + delta, 1)
    setYear(next.getFullYear())
    setMonth(next.getMonth())
  }

  return (
    <div className={`computer-date-range${popupAlign === 'left' ? ' calendar-align-left' : ''}${inlinePopup ? ' calendar-inline-popup' : ''}`} ref={ref}>
      <button type="button" className={`computer-chip ${value ? 'selected' : ''}`} onClick={toggleCalendar}>
        <span>▣</span>{value || label}
      </button>
      {value && <button type="button" className="computer-chip" onClick={() => onChange('')} aria-label="清除日期筛选">×</button>}
      {open && (
        <div className="calendar-popup report-calendar-popup">
          <div className="calendar-head">
            <button type="button" onClick={() => changeMonth(-1)}>‹</button>
            <strong>{year}年 {MONTH_NAMES[month]}</strong>
            <button type="button" onClick={() => changeMonth(1)}>›</button>
          </div>
          <div className="calendar-grid">
            {DAY_HEADERS.map((day) => <span key={day} className="calendar-day-header">{day}</span>)}
            {getMonthDays(year, month).map((day, index) => {
              if (day === null) return <span key={`empty-${index}`} />
              const nextValue = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
              return <button type="button" key={nextValue} className={`calendar-day ${nextValue === value ? 'selected' : ''}`} onClick={() => { onChange(nextValue); setOpen(false) }}>{day}</button>
            })}
          </div>
        </div>
      )}
    </div>
  )
}
