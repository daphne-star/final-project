import { Link } from 'react-router-dom'
import { CheckCircle2, Gavel, Loader2, Plus, XCircle } from 'lucide-react'

import { useMeetings } from '@/api/meetings'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { Meeting, MeetingStatus } from '@/types/meetings'

const STATUS_BADGE: Record<
  MeetingStatus,
  { label: string; variant: 'default' | 'accent' | 'positive' | 'critical' }
> = {
  draft: { label: 'Draft', variant: 'default' },
  running: { label: 'In session', variant: 'accent' },
  paused: { label: 'Paused', variant: 'default' },
  completed: { label: 'Complete', variant: 'positive' },
  cancelled: { label: 'Cancelled', variant: 'default' },
  failed: { label: 'Failed', variant: 'critical' },
}

export function MeetingsPage() {
  const { data: meetings, isLoading, isError, error } = useMeetings()

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:px-10 lg:py-12">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl tracking-tight">Board meetings</h1>
          <p className="mt-2 text-sm text-ink-muted">
            Every meeting is kept in full — transcript, challenges, and the brief.
          </p>
        </div>
        <Button asChild>
          <Link to="/meetings/new">
            <Plus />
            New meeting
          </Link>
        </Button>
      </header>

      {isLoading && <Loader2 className="size-5 animate-spin text-ink-muted" />}

      {isError && (
        <p className="text-sm text-critical">
          {error instanceof Error ? error.message : 'Could not load meetings'}
        </p>
      )}

      {meetings?.length === 0 && (
        <div className="rounded-card border border-dashed border-line p-8 text-center">
          <Gavel className="mx-auto size-6 text-ink-faint" />
          <p className="mt-3 text-sm text-ink">No meetings yet</p>
          <p className="mx-auto mt-1 max-w-md text-sm text-ink-muted">
            Bring a decision you are actually weighing. The board is more useful on a real
            tradeoff than a hypothetical.
          </p>
          <Button className="mt-4" asChild>
            <Link to="/meetings/new">Convene the board</Link>
          </Button>
        </div>
      )}

      <ul className="space-y-2">
        {meetings?.map((meeting) => (
          <MeetingRow key={meeting.id} meeting={meeting} />
        ))}
      </ul>
    </div>
  )
}

function MeetingRow({ meeting }: { meeting: Meeting }) {
  const badge = STATUS_BADGE[meeting.status]
  return (
    <li>
      <Link
        to={`/boardroom/${meeting.id}`}
        className="flex items-center gap-4 rounded-card border border-line bg-surface p-4 transition-colors hover:border-line-strong"
      >
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-ink">{meeting.title}</p>
          <p className="mt-0.5 text-xs text-ink-faint">
            {new Date(meeting.created_at).toLocaleString()}
            {meeting.model_requests_used > 0 && ` · ${meeting.model_requests_used} model calls`}
          </p>
        </div>

        {meeting.status === 'running' && (
          <Loader2 className="size-3.5 shrink-0 animate-spin text-accent-soft" />
        )}
        {meeting.status === 'completed' && (
          <CheckCircle2 className="size-3.5 shrink-0 text-positive" />
        )}
        {meeting.status === 'failed' && <XCircle className="size-3.5 shrink-0 text-critical" />}

        <Badge variant={badge.variant}>{badge.label}</Badge>
      </Link>
    </li>
  )
}
