import { Check, CircleDashed, Loader2, MessagesSquare, Pencil, Swords, X } from 'lucide-react'

import { EXECUTIVE_PORTRAITS } from '@/assets/executives'
import { ACTIVITY_LABEL, ACTIVE_ACTIVITIES, type AgentActivity } from '@/lib/boardroomState'
import { cn } from '@/lib/utils'
import type { ExecutiveDefinition } from '@/types/agents'

const ICON: Record<AgentActivity, typeof Check> = {
  waiting: CircleDashed,
  analyzing: Loader2,
  speaking: MessagesSquare,
  challenging: Swords,
  revising: Pencil,
  finished: Check,
  failed: X,
  skipped: CircleDashed,
}

export interface ParticipantRailProps {
  executives: ExecutiveDefinition[]
  /** agent_id -> activity, driven entirely by backend events. */
  activity: Record<string, AgentActivity>
  chairId?: string
  onSelect?: (agentId: string) => void
  selectedAgentId?: string | null
  className?: string
}

export function ParticipantRail({
  executives,
  activity,
  chairId = 'chairperson',
  onSelect,
  selectedAgentId,
  className,
}: ParticipantRailProps) {
  const chair = executives.find((e) => e.agent_id === chairId)
  const specialists = executives.filter((e) => e.agent_id !== chairId)

  return (
    <div className={cn('space-y-5', className)}>
      {chair && (
        <section>
          <RailLabel>Chair</RailLabel>
          <ParticipantRow
            executive={chair}
            activity={activity[chair.agent_id] ?? 'waiting'}
            onSelect={onSelect}
            selected={selectedAgentId === chair.agent_id}
          />
        </section>
      )}

      <section>
        <RailLabel>Executives</RailLabel>
        <div className="space-y-1.5">
          {specialists.map((executive) => (
            <ParticipantRow
              key={executive.agent_id}
              executive={executive}
              activity={activity[executive.agent_id] ?? 'waiting'}
              onSelect={onSelect}
              selected={selectedAgentId === executive.agent_id}
            />
          ))}
        </div>
      </section>
    </div>
  )
}

function RailLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
      {children}
    </h2>
  )
}

function ParticipantRow({
  executive,
  activity,
  onSelect,
  selected,
}: {
  executive: ExecutiveDefinition
  activity: AgentActivity
  onSelect?: (agentId: string) => void
  selected?: boolean
}) {
  const Portrait = EXECUTIVE_PORTRAITS[executive.avatar_ref]
  const Icon = ICON[activity]
  const isActive = ACTIVE_ACTIVITIES.has(activity)
  const dimmed = activity === 'skipped' || activity === 'waiting'

  return (
    <button
      type="button"
      onClick={() => onSelect?.(executive.agent_id)}
      aria-pressed={selected}
      data-activity={activity}
      data-agent-id={executive.agent_id}
      className={cn(
        'flex w-full items-center gap-2.5 rounded-lg border px-2 py-2 text-left transition-colors',
        selected
          ? 'border-transparent bg-surface-raised'
          : 'border-transparent hover:bg-surface-raised/60',
      )}
      style={selected ? { boxShadow: `inset 0 0 0 1px ${executive.theme_color}` } : undefined}
    >
      <div
        className={cn(
          'relative size-9 shrink-0 overflow-hidden rounded-md border transition-opacity',
          dimmed && 'opacity-50',
        )}
        style={{
          borderColor: isActive ? executive.theme_color : 'var(--color-line)',
        }}
      >
        {Portrait && (
          <Portrait
            accent={executive.theme_color}
            accentSoft={executive.theme_color_soft}
            className="size-full"
          />
        )}
        {isActive && (
          <span
            aria-hidden
            className="absolute inset-0 animate-pulse-soft"
            style={{ backgroundColor: `${executive.theme_color}22` }}
          />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <p className={cn('truncate text-xs font-medium text-ink', dimmed && 'text-ink-muted')}>
          {executive.display_name}
        </p>
        <p className="truncate text-[11px]" style={{ color: executive.theme_color_soft }}>
          {executive.short_title}
        </p>
      </div>

      <span
        className={cn(
          'flex shrink-0 items-center gap-1 text-[10px] font-medium',
          activity === 'failed' ? 'text-critical' : 'text-ink-faint',
        )}
        title={ACTIVITY_LABEL[activity]}
      >
        <Icon className={cn('size-3', activity === 'analyzing' && 'animate-spin')} />
        <span className="hidden xl:inline">{ACTIVITY_LABEL[activity]}</span>
      </span>
    </button>
  )
}
