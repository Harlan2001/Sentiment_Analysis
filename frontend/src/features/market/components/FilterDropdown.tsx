/**
 * 通用筛选下拉（S3-3 从 FactorsPage 抽出共享）
 * 样式沿用 workbench.css 的 .factor-filter-dropdown / .factor-filter-menu 全局类
 */
import React, { useState } from 'react'

interface Props {
  label: string
  value: string
  options: string[][]
  onChange: (value: string) => void
}

const FilterDropdown: React.FC<Props> = ({ label, value, options, onChange }) => {
  const [open, setOpen] = useState(false)
  const selected = options.find((option) => option[0] === value)?.[1] || value

  return (
    <div className="factor-filter-dropdown">
      <button type="button" onClick={() => setOpen((current) => !current)} aria-expanded={open}>
        <span>{label}</span>
        <b>{selected}</b>
        <i />
      </button>
      {open && (
        <div className="factor-filter-menu">
          {options.map(([key, text]) => (
            <button
              type="button"
              key={key}
              className={key === value ? 'active' : ''}
              onClick={() => {
                onChange(key)
                setOpen(false)
              }}
            >
              {text}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default FilterDropdown
