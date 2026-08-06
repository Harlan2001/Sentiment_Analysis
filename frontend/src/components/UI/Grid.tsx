import React from 'react'

interface ResponsiveGridProps {
  children: React.ReactNode
  cols?: {
    sm?: number
    md?: number
    lg?: number
    xl?: number
  }
  gap?: string | number
  className?: string
}

const ResponsiveGrid: React.FC<ResponsiveGridProps> = ({
  children,
  cols = { sm: 1, md: 2, lg: 3 },
  gap = 4,
  className = '',
}) => {
  const getGridClasses = () => {
    const classes = ['grid']

    if (cols.sm) classes.push(`grid-cols-${cols.sm}`)
    if (cols.md) classes.push(`md:grid-cols-${cols.md}`)
    if (cols.lg) classes.push(`lg:grid-cols-${cols.lg}`)
    if (cols.xl) classes.push(`xl:grid-cols-${cols.xl}`)

    return classes.join(' ')
  }

  const gapClass = typeof gap === 'number' ? `gap-${gap}` : gap

  return <div className={`${getGridClasses()} ${gapClass} ${className}`}>{children}</div>
}

// 预定义的网格布局
export const NewsGridLayout: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <ResponsiveGrid cols={{ sm: 1, md: 1, lg: 3 }} gap={6} className={className}>
    {children}
  </ResponsiveGrid>
)

export const FactorGridLayout: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <ResponsiveGrid cols={{ sm: 1, md: 2, lg: 3, xl: 4 }} gap={4} className={className}>
    {children}
  </ResponsiveGrid>
)

export const DashboardGridLayout: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <ResponsiveGrid cols={{ sm: 1, md: 2, lg: 2 }} gap={6} className={className}>
    {children}
  </ResponsiveGrid>
)

export default ResponsiveGrid
