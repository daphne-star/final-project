import { motion } from 'motion/react'
import { Check, CircleDashed, MessagesSquare, Search, Zap } from 'lucide-react'

import { EXECUTIVE_PORTRAITS } from '@/assets/executives'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ExecutiveDefinition, ExecutiveStatus } from '@/types/agents'

const STATUS_META: Record<
  Exclude<ExecutiveStatus, 'idle'>,
  { label: string; icon: typeof Zap; variant: 'accent' | 'caution' | 'positive' | 'default' }
> = {
  waiting: { label: 'Waiting', icon: CircleDashed, variant: 'default' },
  speaking: { label: 'Speaking', icon: MessagesSquare, variant: 'accent' },
  researching: { label: 'Researching', icon: Search, variant: 'caution' },
  challenging: { label: 'Challenging', icon: Zap, variant: 'caution' },
  completed: { label: 'Done', icon: Check, variant: 'positive' },
  skipped: { label: 'Not called', icon: CircleDashed, variant: 'default' },
}

export interface ExecutiveCardProps {
  executive: ExecutiveDefinition
  status?: ExecutiveStatus
  selected?: boolean
  compact?: boolean
  onClick?: (executive: ExecutiveDefinition) => void
  className?: string
}

export function ExecutiveCard({
  executive,
  status = 'idle',
  selected = false,
  compact = false,
  onClick,
  className,
}: ExecutiveCardProps) {
  const Portrait = EXECUTIVE_PORTRAITS[executive.avatar_ref]
  const statusMeta = status === 'idle' ? null : STATUS_META[status]
  const interactive = Boolean(onClick)

  if (!Portrait) {
    // A missing portrait is a wiring bug, not something to paper over with a
    // placeholder circle — the illustrations are part of the product.
    throw new Error(`No portrait registered for avatar_ref "${executive.avatar_ref}"`)
  }

  return (
    <motion.div
      whileHover={interactive ? { y: -4 } : undefined}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      className={cn('relative', className)}
    >
      <button
        type="button"
        disabled={!interactive}
        aria-pressed={interactive ? selected : undefined}
        onClick={() => onClick?.(executive)}
        className={cn(
          'group relative block w-full overflow-hidden rounded-card border bg-surface text-left transition-colors',
          'disabled:cursor-default',
          selected ? 'border-transparent' : 'border-line hover:border-line-strong',
        )}
        style={selected ? { boxShadow: `0 0 0 2px ${executive.theme_color}` } : undefined}
      >
        {/* Portrait, 3:4 */}
        <div className="relative aspect-[3/4] w-full overflow-hidden">
          <Portrait
            accent={executive.theme_color}
            accentSoft={executive.theme_color_soft}
            className="size-full"
          />

          {statusMeta && (
            <div className="absolute left-3 top-3">
              <Badge variant={statusMeta.variant} className="backdrop-blur-sm">
                <statusMeta.icon
                  className={cn('size-3', status === 'speaking' && 'animate-pulse-soft')}
                />
                {statusMeta.label}
              </Badge>
            </div>
          )}

          {/* Name plate sits over the portrait fade */}
          <div className="absolute inset-x-0 bottom-0 p-3">
            <p className="text-sm font-semibold leading-tight text-ink">
              {executive.display_name}
            </p>
            <p
              className="text-xs font-medium leading-tight"
              style={{ color: executive.theme_color_soft }}
            >
              {executive.title}
            </p>
          </div>
        </div>

        {!compact && (
          <div className="border-t border-line p-3">
            <p className="text-xs leading-relaxed text-ink-muted">
              {executive.expertise_descriptor}
            </p>
          </div>
        )}

        {/* Accent rule keeps the nine palettes legible side by side */}
        <span
          aria-hidden
          className="absolute inset-x-0 top-0 h-0.5"
          style={{ backgroundColor: executive.theme_color }}
        />
      </button>
    </motion.div>
  )
}
