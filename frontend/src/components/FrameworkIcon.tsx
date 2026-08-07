import type { Framework } from '@/types'
import { cn } from '@/lib/utils'

interface FrameworkIconProps {
  framework: Framework
  className?: string
}

// Official brand marks (path data from Simple Icons, CC0 - the standard
// source for this exact use: monochrome brand glyphs to embed in an app's
// own UI, not the multi-color logo lockups). Colored with each brand's own
// accent instead of `currentColor` so the badge stays recognizable in both
// light and dark mode without a separate per-theme variant.
const TENSORFLOW_PATH =
  'M1.292 5.856L11.54 0v24l-4.095-2.378V7.603l-6.168 3.564.015-5.31zm21.43 5.311l-.014-5.31L12.46 0v24l4.095-2.378V14.87l3.092 1.788-.018-4.618-3.074-1.756V7.603l6.168 3.564z'
const PYTORCH_PATH =
  'M12.005 0L4.952 7.053a9.865 9.865 0 000 14.022 9.866 9.866 0 0014.022 0c3.984-3.9 3.986-10.205.085-14.023l-1.744 1.743c2.904 2.905 2.904 7.634 0 10.538s-7.634 2.904-10.538 0-2.904-7.634 0-10.538l4.647-4.646.582-.665zm3.568 3.899a1.327 1.327 0 00-1.327 1.327 1.327 1.327 0 001.327 1.328A1.327 1.327 0 0016.9 5.226 1.327 1.327 0 0015.573 3.9z'

export default function FrameworkIcon({ framework, className }: FrameworkIconProps) {
  const isPth = framework === 'pth'
  return (
    <svg
      viewBox="0 0 24 24"
      className={cn('size-4', className)}
      fill={isPth ? '#EE4C2C' : '#FF6F00'}
      role="img"
      aria-label={isPth ? 'PyTorch' : 'TensorFlow'}
    >
      <title>{isPth ? 'PyTorch' : 'TensorFlow'}</title>
      <path d={isPth ? PYTORCH_PATH : TENSORFLOW_PATH} />
    </svg>
  )
}
