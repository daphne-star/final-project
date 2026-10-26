import { STAGE_LABEL, STAGE_ORDER } from '@/lib/boardroomState'
import { cn } from '@/lib/utils'
import type { MeetingStage, MeetingStatus } from '@/types/meetings'

export interface MeetingProgressProps {
  stage: MeetingStage | null
  status: MeetingStatus | null
  className?: string
}

/** Stage rail. Position comes from backend stage_changed events only. */
export function MeetingProgress({ stage, status, className }: MeetingProgressProps) {
  const visible: MeetingStage[] = STAGE_ORDER.filter((s) => s !== 'intake')
  const currentIndex = stage ? visible.indexOf(stage) : -1
  const failed = status === 'failed' || status === 'cancelled'

  return (
    <ol
      className={cn('flex items-center gap-1 text-[11px]', className)}
      aria-label="Meeting progress"
    >
      {visible.map((s, i) => {
        const done = currentIndex > i
        const active = currentIndex === i
        return (
          <li key={s} className="flex min-w-0 items-center gap-1">
            <span
              data-stage={s}
              data-state={active ? 'active' : done ? 'done' : 'pending'}
              className={cn(
                'whitespace-nowrap rounded px-1.5 py-0.5 transition-colors',
                active && !failed && 'bg-accent/20 text-accent-soft',
                active && failed && 'bg-critical/20 text-critical',
                done && 'text-ink-muted',
                !done && !active && 'text-ink-faint',
              )}
            >
              {STAGE_LABEL[s]}
            </span>
            {i < visible.length - 1 && (
              <span aria-hidden className="text-ink-faint">
                ·
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}
