import { Gavel, Lightbulb, Swords, User, Users } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { MeetingMode } from '@/types/meetings'

export interface ModeOption {
  mode: MeetingMode
  label: string
  blurb: string
  icon: typeof Gavel
  /** Who attends by default. Empty means the mode decides. */
  defaultParticipants: string[]
  /** Fixed roster the user cannot change. */
  fixedRoster: boolean
  requiresSubject: boolean
}

/** Mirrors backend/app/orchestration/modes.py. */
export const MEETING_MODES: ModeOption[] = [
  {
    mode: 'executive_meeting',
    label: 'Executive Meeting',
    blurb: 'Three to six executives whose function bears on the decision.',
    icon: Users,
    defaultParticipants: ['ceo', 'coo', 'cfo', 'strategy_consultant'],
    fixedRoster: false,
    requiresSubject: false,
  },
  {
    mode: 'full_board',
    label: 'Full Board',
    blurb: 'All eight executives plus the Chair. Thorough, and the most expensive.',
    icon: Gavel,
    defaultParticipants: [],
    fixedRoster: true,
    requiresSubject: false,
  },
  {
    mode: 'devils_advocate',
    label: "Devil's Advocate",
    blurb: 'Stress-test a decision the board already took. Needs one to attack.',
    icon: Swords,
    defaultParticipants: ['cfo', 'coo', 'customer_advocate', 'competitive_intel'],
    fixedRoster: false,
    requiresSubject: true,
  },
  {
    mode: 'strategy_workshop',
    label: 'Strategy Workshop',
    blurb: 'Generate and weigh alternatives, then have the COO plan the winner.',
    icon: Lightbulb,
    defaultParticipants: ['ceo', 'coo', 'cfo', 'cgo', 'strategy_consultant'],
    fixedRoster: false,
    requiresSubject: false,
  },
  {
    mode: 'quick_consultation',
    label: 'Quick Consultation',
    blurb: 'One executive, one answer. Cheapest way to get a read.',
    icon: User,
    defaultParticipants: ['cfo'],
    fixedRoster: false,
    requiresSubject: false,
  },
]

export function modeOption(mode: MeetingMode): ModeOption {
  return MEETING_MODES.find((m) => m.mode === mode) ?? MEETING_MODES[0]
}

export function ModePicker({
  value,
  onChange,
  className,
}: {
  value: MeetingMode
  onChange: (mode: MeetingMode) => void
  className?: string
}) {
  return (
    <div className={cn('grid gap-2 sm:grid-cols-2 lg:grid-cols-3', className)}>
      {MEETING_MODES.map((option) => {
        const Icon = option.icon
        const selected = option.mode === value
        return (
          <button
            key={option.mode}
            type="button"
            onClick={() => onChange(option.mode)}
            aria-pressed={selected}
            data-mode={option.mode}
            className={cn(
              'rounded-lg border p-3 text-left transition-colors',
              selected
                ? 'border-accent bg-accent/10'
                : 'border-line hover:border-line-strong',
            )}
          >
            <span className="flex items-center gap-2">
              <Icon
                className={cn('size-4', selected ? 'text-accent-soft' : 'text-ink-faint')}
              />
              <span className="text-sm font-medium text-ink">{option.label}</span>
            </span>
            <span className="mt-1 block text-xs leading-relaxed text-ink-muted">
              {option.blurb}
            </span>
          </button>
        )
      })}
    </div>
  )
}
