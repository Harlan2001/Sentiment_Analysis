import React from 'react'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helperText?: string
  icon?: React.ReactNode
}

const Input: React.FC<InputProps> = ({ label, error, helperText, icon, className = '', ...props }) => {
  const inputClasses = `
    w-full px-3.5 py-2.5 border rounded-lg text-sm bg-gray-900 text-white outline-none transition-all duration-200
    ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/10' : 'border-gray-600 focus:border-purple-500 focus:ring-purple-500/10'}
    ${icon ? 'pl-10' : ''}
    ${className}
  `

  return (
    <div className="space-y-1">
      {label && <label className="block text-sm font-medium text-gray-300">{label}</label>}

      <div className="relative">
        {icon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <span className="text-gray-400">{icon}</span>
          </div>
        )}

        <input className={inputClasses} {...props} />
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {helperText && !error && <p className="text-sm text-gray-400">{helperText}</p>}
    </div>
  )
}

export { Input }