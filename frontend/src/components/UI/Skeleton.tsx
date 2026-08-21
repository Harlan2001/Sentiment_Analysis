import React from 'react'
import { motion } from 'framer-motion'

interface SkeletonProps {
  className?: string
  width?: string | number
  height?: string | number
  variant?: 'text' | 'rectangular' | 'circular'
  animation?: 'pulse' | 'wave' | 'none'
}

const Skeleton: React.FC<SkeletonProps> = ({
  className = '',
  width,
  height,
  variant = 'text',
  animation = 'pulse',
}) => {
  const variantClasses = {
    text: 'rounded',
    rectangular: 'rounded-md',
    circular: 'rounded-full',
  }

  const animationClasses = {
    pulse: 'animate-pulse',
    wave: '',
    none: '',
  }

  const baseClasses = 'bg-gray-700'
  const classes = `${baseClasses} ${variantClasses[variant]} ${animationClasses[animation]} ${className}`

  const style = {
    width: width || '100%',
    height: height || (variant === 'text' ? '1rem' : '40px'),
  }

  if (animation === 'wave') {
    return (
      <motion.div
        className={`${baseClasses} ${variantClasses[variant]} ${className} overflow-hidden relative`}
        style={style}
      >
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-gray-600 to-transparent"
          initial={{ x: '-100%' }}
          animate={{ x: '100%' }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'linear',
          }}
        />
      </motion.div>
    )
  }

  return <div className={classes} style={style} />
}

export { Skeleton }