import { useEffect, useRef, useState } from 'react'

const DAY_HEADERS = ['\u4E00', '\u4E8C', '\u4E09', '\u56DB', '\u4E94', '\u516D', '\u65E5']
const MONTH_NAMES = ['1\u6708', '2\u6708', '3\u6708', '4\u6708', '5\u6708', '6\u6708', '7\u6708', '8\u6708', '9\u6708', '10\u6708', '11\u6708', '12\u6708']

function parseDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return value ? new Date(year, month - 1, day) : new Date()
}

function getMonthDays(year: number, month: number): (number | null)[] {
  const firstDay = new Date(year, month, 1).getDay() || 7
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  return [
    ...Array.from({ length: firstDay - 1 }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ]
}

type ComputerDatePickerProps = {
  label: string
  value: string
  onChange: (value: string) => void
  min?: string
  max?: string
  emptyLabel?: string
}

export function ComputerDatePicker({
  label,
  value,
  onChange,
  min,
  max,
  emptyLabel = '\u8BF7\u9009\u62E9',
}: ComputerDatePickerProps) {
  const initial = parseDate(value)
  const [open, setOpen] = useState(false)
  const [year, setYear] = useState(initial.getFullYear())
  const [month, setMonth] = useState(initial.getMonth())
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  function toggle() {
    const current = parseDate(value)
    setYear(current.getFullYear())
    setMonth(current.getMonth())
    setOpen((currentOpen) => !currentOpen)
  }

  function previousMonth() {
    if (month === 0) {
      setMonth(11)
      setYear((currentYear) => currentYear - 1)
    } else {
      setMonth((currentMonth) => currentMonth - 1)
    }
  }

  function nextMonth() {
    if (month === 11) {
      setMonth(0)
      setYear((currentYear) => currentYear + 1)
    } else {
      setMonth((currentMonth) => currentMonth + 1)
    }
  }

  return (
    <div className="summary-date-picker" ref={rootRef}>
      <button type="button" className={'computer-chip ' + (value ? 'selected' : '')} onClick={toggle}>
        <span className="summary-date-label">{label}</span>
        ▣ {value || emptyLabel}
      </button>
      {open && (
        <div className="calendar-popup">
          <div className="calendar-head">
            <button type="button" onClick={previousMonth} aria-label={'\u4E0A\u4E2A\u6708'}>‹</button>
            <strong>{year}{'\u5E74'}{MONTH_NAMES[month]}</strong>
            <button type="button" onClick={nextMonth} aria-label={'\u4E0B\u4E2A\u6708'}>›</button>
          </div>
          <div className="calendar-grid">
            {DAY_HEADERS.map((day) => <span key={day} className="calendar-day-header">{day}</span>)}
            {getMonthDays(year, month).map((day, index) => {
              if (day === null) return <span key={`empty-${index}`} />
              const dateString = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
              const disabled = Boolean((min && dateString < min) || (max && dateString > max))
              return (
                <button
                  type="button"
                  key={dateString}
                  className={'calendar-day ' + (dateString === value ? 'selected' : '')}
                  disabled={disabled}
                  onClick={() => {
                    onChange(dateString)
                    setOpen(false)
                  }}
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
