import React from 'react'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helperText?: string
  icon?: React.ReactNode
}

const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  icon,
  className = '',
  ...props
}) => {
  const inputClasses = `
    w-full px-3.5 py-2.5 border rounded-lg text-sm bg-gray-900 text-white outline-none transition-all duration-200
    ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/10' : 'border-gray-600 focus:border-purple-500 focus:ring-purple-500/10'}
    ${icon ? 'pl-10' : ''}
    ${className}
  `
  
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-gray-300">
          {label}
        </label>
      )}
      
      <div className="relative">
        {icon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <span className="text-gray-400">{icon}</span>
          </div>
        )}
        
        <input
          className={inputClasses}
          {...props}
        />
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

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  helperText?: string
  options?: Array<{ value: string; label: string }>
  placeholder?: string
}

const Select: React.FC<SelectProps> = ({
  label,
  error,
  helperText,
  options = [],
  placeholder = '请选择...',
  className = '',
  children,
  ...props
}) => {
  const selectClasses = `
    w-full px-3.5 py-2.5 border rounded-lg text-sm bg-gray-900 text-white outline-none transition-all duration-200 appearance-none cursor-pointer
    ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/10' : 'border-gray-600 focus:border-purple-500 focus:ring-purple-500/10'}
    ${className}
  `
  
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-gray-300">
          {label}
        </label>
      )}
      
      <div className="relative">
        <select className={selectClasses} {...props}>
          {children ? (
            children
          ) : (
            <>
              <option value="" disabled>
                {placeholder}
              </option>
              {options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </>
          )}
        </select>
        
        {/* Dropdown arrow */}
        <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
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

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
  helperText?: string
  containerClassName?: string
}

const Textarea: React.FC<TextareaProps> = ({
  label,
  error,
  helperText,
  containerClassName = '',
  className = '',
  ...props
}) => {
  const textareaClasses = `
    w-full px-3.5 py-2.5 border rounded-lg text-sm bg-gray-900 text-white outline-none transition-all duration-200 resize-vertical
    ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/10' : 'border-gray-600 focus:border-purple-500 focus:ring-purple-500/10'}
    ${className}
  `
  
  return (
    <div className={`space-y-1 ${containerClassName}`}>
      {label && (
        <label className="block text-sm font-medium text-gray-300">
          {label}
        </label>
      )}
      
      <textarea className={textareaClasses} {...props} />
      
      {error && (
        <p className="text-sm text-red-400">{error}</p>
      )}
      
      {helperText && !error && (
        <p className="text-sm text-gray-400">{helperText}</p>
      )}
    </div>
  )
}

export { Input, Select, Textarea }