import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'border-line bg-surface-raised text-ink-muted',
        accent: 'border-accent/40 bg-accent/15 text-accent-soft',
        positive: 'border-positive/40 bg-positive/15 text-positive',
        caution: 'border-caution/40 bg-caution/15 text-caution',
        critical: 'border-critical/40 bg-critical/15 text-critical',
        outline: 'border-line-strong bg-transparent text-ink-muted',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
