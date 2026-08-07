import type { Framework } from '@/types'
import { cn } from '@/lib/utils'

interface FrameworkIconProps {
  framework: Framework
  className?: string
}

// Small abstract per-framework badges, not the official trademarked logos -
// just enough visual distinction (shape + brand-adjacent color) to scan a
// grid of model cards at a glance. TensorFlow's brand orange is #FF6F00;
// PyTorch's is #EE4C2C.
export default function FrameworkIcon({ framework, className }: FrameworkIconProps) {
  if (framework === 'pth') {
    return (
      <svg
        viewBox="0 0 24 24"
        className={cn('size-4', className)}
        fill="none"
        stroke="#EE4C2C"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        role="img"
        aria-label="PyTorch"
      >
        <title>PyTorch</title>
        <path d="M12 3v7" />
        <path d="M8.5 7.5a6 6 0 1 0 7 0" />
      </svg>
    )
  }

  return (
    <svg
      viewBox="0 0 24 24"
      className={cn('size-4', className)}
      fill="none"
      stroke="#FF6F00"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      role="img"
      aria-label="TensorFlow"
    >
      <title>TensorFlow</title>
      <path d="M12 3 4 7.5v9L12 21l8-4.5v-9L12 3Z" />
      <path d="M12 3v18" />
      <path d="M4 7.5 12 12l8-4.5" />
    </svg>
  )
}
