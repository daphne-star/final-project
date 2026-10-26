import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Loader2,
  PanelLeft,
  PanelRight,
  Pause,
  Play,
  RefreshCw,
  XCircle,
} from 'lucide-react'

import { useExecutives } from '@/api/agents'
import {
  useCancelMeeting,
  useMeeting,
  usePauseMeeting,
  useResumeMeeting,
} from '@/api/meetings'
import { InterventionPanel } from '@/components/boardroom/InterventionPanel'
import { MeetingProgress } from '@/components/boardroom/MeetingProgress'
import { MeetingSidebar } from '@/components/boardroom/MeetingSidebar'
import { ParticipantRail } from '@/components/boardroom/ParticipantRail'
import { Announcer } from '@/components/boardroom/Announcer'
import { Transcript } from '@/components/boardroom/Transcript'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useMeetingStream } from '@/hooks/useMeetingStream'
import { cn, formatTokens } from '@/lib/utils'
import type { ExecutiveDefinition } from '@/types/agents'

export function BoardroomPage() {
  const { meetingId } = useParams<{ meetingId: string }>()
  const { data: executives } = useExecutives()
  const { data: meeting, isLoading, isError, error, refetch } = useMeeting(meetingId)
  const { state, connection, error: streamError, retry } = useMeetingStream(meetingId)
  const cancel = useCancelMeeting(meetingId ?? '')
  const pause = usePauseMeeting(meetingId ?? '')
  const resume = useResumeMeeting(meetingId ?? '')

  const [leftOpen, setLeftOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [interveningWith, setInterveningWith] = useState<string | null>(null)

  const executivesById = useMemo<Record<string, ExecutiveDefinition>>(() => {
    const map: Record<string, ExecutiveDefinition> = {}
    for (const e of executives ?? []) map[e.agent_id] = e
    return map
  }, [executives])

  // Show the Chair plus whoever the meeting actually involves, falling back to
  // the persisted participant rows when the stream has not reached the agenda.
  const roster = useMemo(() => {
    const ids = new Set<string>(['chairperson'])
    for (const id of state.participants) ids.add(id)
    for (const p of meeting?.participants ?? []) ids.add(p.agent_id)
    return (executives ?? []).filter((e) => ids.has(e.agent_id))
  }, [executives, state.participants, meeting?.participants])

  // Activity from live events, backfilled from persisted status for anyone the
  // stream has not mentioned yet (e.g. opening a finished meeting).
  const activity = useMemo(() => {
    const merged: Record<string, typeof state.activity[string]> = {}
    for (const p of meeting?.participants ?? []) {
      merged[p.agent_id] =
        p.status === 'completed'
          ? 'finished'
          : p.status === 'skipped'
            ? 'skipped'
            : 'waiting'
    }
    return { ...merged, ...state.activity }
  }, [meeting?.participants, state.activity])

  // Evidence comes from the persisted assessments rather than the event
  // stream: events carry summaries, the citations live on the rows.
  const evidence = useMemo(
    () =>
      (meeting?.assessments ?? []).flatMap((a) =>
        (a.evidence_references ?? []).map((e) => ({
          agentId: a.agent_id,
          claim: e.claim,
          source: e.source,
          isVerified: e.is_verified,
        })),
      ),
    [meeting?.assessments],
  )

  const status = state.status ?? meeting?.status ?? null
  const isPaused = state.paused || status === 'paused'
  const isRunning = status === 'running' || isPaused
  // Only a live meeting has anyone to interrupt.
  const canIntervene = isRunning
  const transcriptEnd = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll) transcriptEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [state.transcript.length, autoScroll])

  if (isLoading) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loader2 className="size-5 animate-spin text-ink-muted" />
      </div>
    )
  }

  if (isError || !meeting) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <div className="flex items-start gap-3 rounded-card border border-critical/40 bg-critical/10 p-4">
          <AlertCircle className="mt-0.5 size-5 shrink-0 text-critical" />
          <div className="flex-1">
            <p className="text-sm font-medium text-ink">Could not load this meeting</p>
            <p className="mt-1 text-sm text-ink-muted">
              {error instanceof Error ? error.message : 'Unknown error'}
            </p>
            <div className="mt-3 flex gap-2">
              <Button variant="outline" size="sm" onClick={() => void refetch()}>
                <RefreshCw />
                Try again
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/meetings">
                  <ArrowLeft />
                  All meetings
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface-raised focus:px-3 focus:py-2 focus:text-sm focus:text-ink"
      >
        Skip to transcript
      </a>

      <Announcer
        stage={state.stage ?? meeting.stage}
        status={status}
        transcript={state.transcript}
        executivesById={executivesById}
      />

      <BoardroomHeader
        title={meeting.title}
        status={status}
        totalTokens={state.totalTokens ?? meeting.total_tokens_used}
        stage={state.stage ?? meeting.stage}
        connection={connection}
        isRunning={isRunning}
        onCancel={() => cancel.mutate()}
        cancelPending={cancel.isPending}
        isPaused={isPaused}
        onPause={() => pause.mutate()}
        onResume={() => resume.mutate()}
        pausePending={pause.isPending || resume.isPending}
        onToggleLeft={() => setLeftOpen(true)}
        onToggleRight={() => setRightOpen(true)}
      />

      <div className="flex min-h-0 flex-1">
        {/* Left: participants */}
        <aside className="hidden w-60 shrink-0 overflow-y-auto border-r border-line bg-surface/40 p-3 lg:block">
          <ParticipantRail
            executives={roster}
            activity={activity}
            onSelect={(id) =>
              canIntervene
                ? setInterveningWith(id)
                : setSelectedAgent(id === selectedAgent ? null : id)
            }
            selectedAgentId={selectedAgent}
          />
          {canIntervene && (
            <p className="mt-3 px-2 text-[11px] leading-relaxed text-ink-faint">
              Click an executive to put something to them directly. They answer at
              the next safe point in the meeting.
            </p>
          )}
        </aside>

        {/* Center: transcript */}
        <main
          id="main"
          tabIndex={-1}
          className="min-w-0 flex-1 overflow-y-auto"
          onWheel={() => setAutoScroll(false)}
          // Scrolling by keyboard has to release auto-scroll too, or a keyboard
          // user gets yanked back to the bottom every time an event lands.
          onKeyDown={(e) => {
            if (SCROLL_KEYS.has(e.key)) setAutoScroll(false)
          }}
        >
          <div className="mx-auto w-full max-w-3xl px-4 py-5 sm:px-6">
            <QuestionCard question={meeting.question} />

            {status === 'failed' && (
              <FailureNotice
                reason={meeting.failure_reason ?? state.failureReason}
                onRetry={retry}
              />
            )}

            {isPaused && (
              <div className="mt-4 flex items-center gap-2.5 rounded-card border border-caution/40 bg-caution/10 p-3">
                <Pause className="size-4 shrink-0 text-caution" />
                <p className="text-sm text-ink-muted">
                  Paused at the end of the current step. Anything you ask now is
                  answered before the meeting continues.
                </p>
              </div>
            )}

            {state.transcript.length === 0 && status !== 'failed' && (
              <WaitingNotice isRunning={isRunning} connection={connection} />
            )}

            <Transcript
              entries={
                selectedAgent
                  ? state.transcript.filter(
                      (e) =>
                        e.agentId === selectedAgent || e.targetAgentId === selectedAgent,
                    )
                  : state.transcript
              }
              executivesById={executivesById}
              className="mt-5"
            />

            {isRunning && <ThinkingRow activity={activity} executivesById={executivesById} />}

            {status === 'completed' && meeting.decision && (
              <CompletedNotice
                decisionId={meeting.decision.id}
                summary={meeting.decision.executive_summary}
                totalTokens={state.totalTokens ?? meeting.total_tokens_used}
              />
            )}

            {streamError && connection === 'error' && (
              <div
                role="alert"
                className="mt-4 flex items-start gap-3 rounded-card border border-caution/40 bg-caution/10 p-3"
              >
                <AlertCircle className="mt-0.5 size-4 shrink-0 text-caution" />
                <div className="flex-1 text-sm">
                  <p className="font-medium text-ink">Live updates disconnected</p>
                  <p className="mt-0.5 text-ink-muted">{streamError}</p>
                  <p className="mt-0.5 text-xs text-ink-faint">
                    The meeting keeps running on the server. Nothing is lost.
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={retry}>
                  <RefreshCw />
                  Reconnect
                </Button>
              </div>
            )}

            {!autoScroll && isRunning && (
              <button
                type="button"
                onClick={() => setAutoScroll(true)}
                className="sticky bottom-3 mx-auto mt-4 block rounded-full border border-line bg-surface px-3 py-1.5 text-xs text-ink-muted shadow-lg hover:text-ink"
              >
                Resume auto-scroll
              </button>
            )}

            <div ref={transcriptEnd} />
          </div>
        </main>

        {/* Right: agenda and issues */}
        <aside className="hidden w-72 shrink-0 overflow-y-auto border-l border-line bg-surface/40 p-4 xl:block">
          <MeetingSidebar
            state={state}
            executivesById={executivesById}
            evidence={evidence}
          />
        </aside>
      </div>

      <InterventionPanel
        meetingId={meetingId ?? ''}
        executive={roster.find((e) => e.agent_id === interveningWith) ?? null}
        colleagues={roster}
        interventions={meeting.interventions ?? []}
        open={interveningWith !== null}
        onOpenChange={(v) => !v && setInterveningWith(null)}
        canIntervene={canIntervene}
      />

      {/* Mobile drawers for the two side panels */}
      <Dialog open={leftOpen} onOpenChange={setLeftOpen}>
        <DialogContent side="right" className="overflow-y-auto p-4">
          <DialogHeader className="p-0 pb-3">
            <DialogTitle className="text-base">Participants</DialogTitle>
          </DialogHeader>
          <ParticipantRail
            executives={roster}
            activity={activity}
            onSelect={(id) => {
              setLeftOpen(false)
              if (canIntervene) setInterveningWith(id)
              else setSelectedAgent(id === selectedAgent ? null : id)
            }}
            selectedAgentId={selectedAgent}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={rightOpen} onOpenChange={setRightOpen}>
        <DialogContent side="right" className="overflow-y-auto p-4">
          <DialogHeader className="p-0 pb-3">
            <DialogTitle className="text-base">Agenda and issues</DialogTitle>
          </DialogHeader>
          <MeetingSidebar
            state={state}
            executivesById={executivesById}
            evidence={evidence}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}

function BoardroomHeader({
  title,
  status,
  totalTokens,
  stage,
  connection,
  isRunning,
  onCancel,
  cancelPending,
  isPaused,
  onPause,
  onResume,
  pausePending,
  onToggleLeft,
  onToggleRight,
}: {
  title: string
  status: string | null
  totalTokens: number
  stage: string | null
  connection: string
  isRunning: boolean
  onCancel: () => void
  cancelPending: boolean
  isPaused: boolean
  onPause: () => void
  onResume: () => void
  pausePending: boolean
  onToggleLeft: () => void
  onToggleRight: () => void
}) {
  return (
    <header className="shrink-0 border-b border-line bg-surface/60 px-4 py-2.5 backdrop-blur sm:px-5">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild aria-label="All meetings">
          <Link to="/meetings">
            <ArrowLeft />
          </Link>
        </Button>

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-semibold text-ink">{title}</h1>
          <MeetingProgress
            stage={stage as never}
            status={status as never}
            className="mt-0.5 hidden sm:flex"
          />
        </div>

        {totalTokens > 0 && (
          <span className="hidden whitespace-nowrap text-xs text-ink-faint sm:inline">
            {formatTokens(totalTokens)}
          </span>
        )}

        <StatusChip status={status} connection={connection} />

        {isRunning && (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={isPaused ? onResume : onPause}
              disabled={pausePending}
              title={
                isPaused
                  ? 'Continue from the next step'
                  : 'Hold at the next safe point. The current step finishes first.'
              }
            >
              {pausePending ? (
                <Loader2 className="animate-spin" />
              ) : isPaused ? (
                <Play />
              ) : (
                <Pause />
              )}
              {isPaused ? 'Resume' : 'Pause'}
            </Button>
            <Button variant="outline" size="sm" onClick={onCancel} disabled={cancelPending}>
              {cancelPending ? <Loader2 className="animate-spin" /> : null}
              End
            </Button>
          </>
        )}

        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={onToggleLeft}
          aria-label="Show participants"
        >
          <PanelLeft />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="xl:hidden"
          onClick={onToggleRight}
          aria-label="Show agenda and issues"
        >
          <PanelRight />
        </Button>
      </div>
    </header>
  )
}

const SCROLL_KEYS = new Set([
  'PageUp',
  'PageDown',
  'ArrowUp',
  'ArrowDown',
  'Home',
  'End',
  ' ',
])

function StatusChip({ status, connection }: { status: string | null; connection: string }) {
  if (status === 'completed') {
    return (
      <Badge variant="positive">
        <CheckCircle2 className="size-3" />
        Complete
      </Badge>
    )
  }
  if (status === 'failed') {
    return (
      <Badge variant="critical">
        <XCircle className="size-3" />
        Failed
      </Badge>
    )
  }
  if (status === 'cancelled') return <Badge variant="default">Cancelled</Badge>
  if (status === 'running') {
    return (
      <Badge variant="accent">
        <Loader2 className="size-3 animate-spin" />
        {connection === 'open' || connection === 'connecting' ? 'Live' : 'Running'}
      </Badge>
    )
  }
  return <Badge variant="default">Draft</Badge>
}

function QuestionCard({ question }: { question: string }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
        Question before the board
      </p>
      <p className="mt-1.5 text-sm leading-relaxed text-ink">{question}</p>
    </div>
  )
}

function WaitingNotice({
  isRunning,
  connection,
}: {
  isRunning: boolean
  connection: string
}) {
  return (
    <div className="mt-5 flex items-center gap-2.5 rounded-card border border-dashed border-line p-4">
      {isRunning || connection === 'connecting' ? (
        <>
          <Loader2 className="size-4 animate-spin text-accent-soft" />
          <p className="text-sm text-ink-muted">
            Waiting for the Chairperson to open the meeting…
          </p>
        </>
      ) : (
        <p className="text-sm text-ink-muted">This meeting has not started yet.</p>
      )}
    </div>
  )
}

function ThinkingRow({
  activity,
  executivesById,
}: {
  activity: Record<string, string>
  executivesById: Record<string, ExecutiveDefinition>
}) {
  const working = Object.entries(activity).filter(([, a]) =>
    ['analyzing', 'speaking', 'challenging', 'revising'].includes(a),
  )
  if (working.length === 0) return null

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 rounded-card border border-line bg-surface/60 px-3 py-2">
      <Loader2 className="size-3.5 animate-spin text-accent-soft" />
      {working.map(([agentId, act]) => {
        const executive = executivesById[agentId]
        return (
          <span
            key={agentId}
            className="text-xs"
            style={{ color: executive?.theme_color_soft ?? undefined }}
          >
            {executive?.display_name ?? agentId} is {act}
          </span>
        )
      })}
    </div>
  )
}

function FailureNotice({
  reason,
  onRetry,
}: {
  reason: string | null | undefined
  onRetry: () => void
}) {
  return (
    <div
      role="alert"
      className="mt-5 flex items-start gap-3 rounded-card border border-critical/40 bg-critical/10 p-4"
    >
      <XCircle className="mt-0.5 size-5 shrink-0 text-critical" />
      <div className="flex-1">
        <p className="text-sm font-medium text-ink">This meeting failed</p>
        <p className="mt-1 text-sm leading-relaxed text-ink-muted">
          {reason ?? 'No reason was recorded.'}
        </p>
        <p className="mt-1.5 text-xs text-ink-faint">
          Whatever the board produced before the failure is kept below.
        </p>
        <div className="mt-3 flex gap-2">
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw />
            Reload events
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link to="/meetings/new">Start a new meeting</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}

function CompletedNotice({
  decisionId,
  summary,
  totalTokens,
}: {
  decisionId: string
  summary: string
  totalTokens: number
}) {
  return (
    <div
      className={cn(
        'mt-5 rounded-card border p-4',
        'border-positive/40 bg-positive/10',
      )}
    >
      <div className="flex items-center gap-2">
        <CheckCircle2 className="size-4 text-positive" />
        <p className="text-sm font-medium text-ink">Decision brief ready</p>
        <span className="ml-auto text-xs text-ink-faint">{formatTokens(totalTokens)}</span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-ink-muted">{summary}</p>
      <Button variant="outline" size="sm" className="mt-3" asChild>
        <Link to={`/decisions/${decisionId}`}>Open the full brief</Link>
      </Button>
    </div>
  )
}
