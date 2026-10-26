import {
  AlertTriangle,
  Gavel,
  MessageSquare,
  Pencil,
  Reply,
  ScrollText,
  Swords,
  User,
} from 'lucide-react'

import { EXECUTIVE_PORTRAITS } from '@/assets/executives'
import { Badge } from '@/components/ui/badge'
import type { TranscriptEntry, TranscriptKind } from '@/lib/boardroomState'
import { cn } from '@/lib/utils'
import type { ExecutiveDefinition } from '@/types/agents'

const KIND_ICON: Record<TranscriptKind, typeof Gavel> = {
  agenda: Gavel,
  assessment: User,
  objection: Swords,
  revision: Pencil,
  decision: ScrollText,
  failure: AlertTriangle,
  intervention: MessageSquare,
  intervention_answer: Reply,
}

export interface TranscriptProps {
  entries: TranscriptEntry[]
  executivesById: Record<string, ExecutiveDefinition>
  className?: string
}

export function Transcript({ entries, executivesById, className }: TranscriptProps) {
  return (
    <ol className={cn('space-y-4', className)} aria-label="Meeting transcript">
      {entries.map((entry) => (
        <TranscriptItem
          key={entry.id}
          entry={entry}
          executive={executivesById[entry.agentId]}
          target={entry.targetAgentId ? executivesById[entry.targetAgentId] : undefined}
        />
      ))}
    </ol>
  )
}

function TranscriptItem({
  entry,
  executive,
  target,
}: {
  entry: TranscriptEntry
  executive: ExecutiveDefinition | undefined
  target: ExecutiveDefinition | undefined
}) {
  const Portrait = executive ? EXECUTIVE_PORTRAITS[executive.avatar_ref] : undefined
  const accent = executive?.theme_color ?? '#7C5CD6'
  const Icon = KIND_ICON[entry.kind]

  // The Chair runs the process; specialists give analysis. Making that visible
  // is a product requirement, not decoration, so chair turns get a distinct
  // treatment rather than just a different name.
  const isChair = entry.kind === 'agenda' || entry.kind === 'decision'
  // A founder interruption is the user speaking, not an executive, so it
  // gets its own treatment rather than looking like another assessment.
  const isFounder = entry.kind === 'intervention'

  return (
    <li
      data-kind={entry.kind}
      data-agent-id={entry.agentId}
      className={cn(
        'flex gap-3',
        isChair && 'rounded-card border border-dashed border-line-strong bg-surface/40 p-3',
        isFounder && 'rounded-card border-l-2 border-accent bg-accent/5 p-3',
      )}
    >
      <div
        className="size-10 shrink-0 overflow-hidden rounded-md border"
        style={{ borderColor: `${accent}66` }}
      >
        {Portrait && executive && (
          <Portrait
            accent={executive.theme_color}
            accentSoft={executive.theme_color_soft}
            className="size-full"
          />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <header className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1">
          <h2 className="text-sm font-semibold text-ink">
            {executive?.display_name ?? entry.agentId}
          </h2>
          <span className="text-[11px]" style={{ color: executive?.theme_color_soft }}>
            {executive?.short_title}
          </span>

          <Badge
            variant={
              entry.kind === 'failure'
                ? 'critical'
                : entry.kind === 'objection'
                  ? 'caution'
                  : isChair || isFounder
                    ? 'accent'
                    : 'default'
            }
            className="ml-auto"
          >
            <Icon className="size-3" />
            {isChair ? `Chair · ${entry.title}` : entry.title}
          </Badge>
        </header>

        {target && (
          <p className="mb-1.5 text-xs text-ink-muted">
            Challenging{' '}
            <span style={{ color: target.theme_color_soft }}>{target.display_name}</span>
            {typeof entry.meta?.claim === 'string' && (
              <>
                {' '}
                on: <q className="italic">{entry.meta.claim}</q>
              </>
            )}
          </p>
        )}

        <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{entry.body}</p>

        {entry.kind === 'assessment' && typeof entry.meta?.position === 'string' && (
          <div
            className="mt-2 rounded-md border-l-2 bg-canvas/40 py-1.5 pl-3 pr-2"
            style={{ borderColor: accent }}
          >
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              Recommends
            </p>
            <p className="mt-0.5 text-sm leading-relaxed text-ink">{entry.meta.position}</p>
          </div>
        )}

        {entry.kind === 'revision' && (
          <div className="mt-2 space-y-1.5 text-xs">
            {typeof entry.meta?.before === 'string' && (
              <p className="text-ink-faint line-through decoration-ink-faint/50">
                {entry.meta.before}
              </p>
            )}
            {typeof entry.meta?.after === 'string' && (
              <p className="text-ink">{entry.meta.after}</p>
            )}
          </div>
        )}

        <footer className="mt-1.5 flex flex-wrap gap-2 text-[11px] text-ink-faint">
          {typeof entry.meta?.confidence === 'string' && entry.meta.confidence && (
            <span>confidence: {entry.meta.confidence}</span>
          )}
          {typeof entry.meta?.severity === 'string' && entry.meta.severity && (
            <span>severity: {entry.meta.severity}</span>
          )}
          {entry.kind === 'revision' && (
            <span>{entry.meta?.changed ? 'position changed' : 'position held'}</span>
          )}
          {typeof entry.meta?.dissent === 'number' && entry.meta.dissent > 0 && (
            <span>{entry.meta.dissent} dissenting</span>
          )}
        </footer>
      </div>
    </li>
  )
}
