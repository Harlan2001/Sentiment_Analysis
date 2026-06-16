import React from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
  padding?: 'none' | 'sm' | 'md' | 'lg'
  hover?: boolean
  onClick?: () => void
}

const Card: React.FC<CardProps> = ({
  children,
  className = '',
  padding = 'md',
  hover = false,
  onClick,
}) => {
  const baseClasses = 'bg-gray-900/80 border border-gray-600 rounded-xl backdrop-blur-sm'
  
  const paddingClasses = {
    none: '',
    sm: 'p-4',
    md: 'p-5',
    lg: 'p-6',
  }
  
  const classes = `
    ${baseClasses}
    ${paddingClasses[padding]}
    ${hover ? 'hover:border-gray-500 hover:bg-gray-800/80 transition-all duration-200' : ''}
    ${onClick ? 'cursor-pointer' : ''}
    ${className}
  `
  
  return (
    <div className={classes} onClick={onClick}>
      {children}
    </div>
  )
}

const CardHeader: React.FC<{
  children: React.ReactNode
  className?: string
  onClick?: () => void
}> = ({ children, className = '', onClick }) => (
  <div className={`mb-4 ${className}`} onClick={onClick}>
    {children}
  </div>
)

const CardTitle: React.FC<{
  children: React.ReactNode
  className?: string
}> = ({ children, className = '' }) => (
  <h3 className={`text-lg font-semibold text-white mb-2 ${className}`}>
    {children}
  </h3>
)

const CardDescription: React.FC<{
  children: React.ReactNode
  className?: string
}> = ({ children, className = '' }) => (
  <p className={`text-gray-400 text-sm ${className}`}>
    {children}
  </p>
)

const CardContent: React.FC<{
  children: React.ReactNode
  className?: string
}> = ({ children, className = '' }) => (
  <div className={className}>
    {children}
  </div>
)

const CardFooter: React.FC<{
  children: React.ReactNode
  className?: string
}> = ({ children, className = '' }) => (
  <div className={`mt-4 pt-4 border-t border-gray-700 ${className}`}>
    {children}
  </div>
)

export {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
}