import React from 'react'

interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  indeterminate?: boolean
  error?: string
  helperText?: string
}

const Checkbox: React.FC<CheckboxProps> = ({
  label,
  indeterminate = false,
  error,
  helperText,
  className = '',
  ...props
}) => {
  const checkboxRef = React.useRef<HTMLInputElement>(null)
  
  React.useEffect(() => {
    if (checkboxRef.current) {
      checkboxRef.current.indeterminate = indeterminate
    }
  }, [indeterminate])
  
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <input
          ref={checkboxRef}
          type="checkbox"
          className={`
            w-4 h-4 text-purple-500 bg-gray-800 border-gray-600 rounded focus:ring-purple-500 focus:ring-2 
            ${error ? 'border-red-500' : ''}
            ${className}
          `}
          {...props}
        />
        {label && (
          <label className="text-sm text-gray-300 cursor-pointer" onClick={() => checkboxRef.current?.click()}>
            {label}
          </label>
        )}
      </div>
      
      {error && (
        <p className="text-sm text-red-400">{error}</p>
      )}
      
      {helperText && !error && (
        <p className="text-sm text-gray-400">{helperText}</p>
      )}
    </div>
  )
}

export default Checkbox