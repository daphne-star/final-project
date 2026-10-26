import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, Gavel, Loader2 } from 'lucide-react'

import { useExecutives } from '@/api/agents'
import { useCreateMeeting, useDecisions } from '@/api/meetings'
import { MEETING_MODES, ModePicker, modeOption } from '@/components/boardroom/ModePicker'
import { EXECUTIVE_PORTRAITS } from '@/assets/executives'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ExecutiveDefinition } from '@/types/agents'
import type { MeetingMode } from '@/types/meetings'

/** The four who sit on an Executive Meeting unless the user says otherwise. */
const DEFAULT_SELECTION = MEETING_MODES[0].defaultParticipants

const SUGGESTIONS = [
  'Should we prioritise improving retention, international expansion, or launching a new product?',
  'We have 12 months of runway. Should we raise now or cut burn and extend?',
  'A competitor just cut prices by 30%. How should we respond?',
  'What is our biggest operational bottleneck, and what would it take to fix it?',
]

export function NewMeetingPage() {
  const navigate = useNavigate()
  const { data: executives } = useExecutives()
  const create = useCreateMeeting()

  const { data: decisions } = useDecisions()

  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState<MeetingMode>('executive_meeting')
  const [selected, setSelected] = useState<string[]>(DEFAULT_SELECTION)
  const [subjectId, setSubjectId] = useState<string>('')

  const option = modeOption(mode)
  const needsSubject = option.requiresSubject
  const rosterLocked = option.fixedRoster

  function chooseMode(next: MeetingMode) {
    setMode(next)
    const preset = modeOption(next).defaultParticipants
    if (preset.length > 0) setSelected(preset)
    if (!modeOption(next).requiresSubject) setSubjectId('')
  }

  const specialists = (executives ?? []).filter((e) => !e.can_chair)
  const chair = (executives ?? []).find((e) => e.can_chair)
  const tooShort = question.trim().length > 0 && question.trim().length < 10

  function toggle(agentId: string) {
    setSelected((prev) =>
      prev.includes(agentId) ? prev.filter((a) => a !== agentId) : [...prev, agentId],
    )
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    const text = question.trim()
    if (!canSubmit) return
    create.mutate(
      {
        question: text,
        mode,
        // A full board seats everyone server-side; sending a roster would
        // only be ignored, so do not pretend the choice mattered.
        participant_agent_ids: rosterLocked ? undefined : selected,
        subject_decision_id: needsSubject ? subjectId : undefined,
        start_immediately: true,
      },
      { onSuccess: (meeting) => navigate(`/boardroom/${meeting.id}`) },
    )
  }

  const canSubmit =
    question.trim().length >= 10 &&
    (rosterLocked || selected.length > 0) &&
    (!needsSubject || Boolean(subjectId)) &&
    !create.isPending

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:py-12">
      <header className="mb-8">
        <h1 className="font-display text-3xl tracking-tight">Convene the board</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">
          Bring a real decision. The Chairperson frames it, each executive analyses it
          independently, then they argue about it in front of you.
        </p>
      </header>

      <form onSubmit={onSubmit} className="space-y-7">
        <section>
          <h2 className="mb-2 text-sm font-medium text-ink">What kind of meeting?</h2>
          <ModePicker value={mode} onChange={chooseMode} />
        </section>

        {needsSubject && (
          <section>
            <label htmlFor="subject" className="mb-2 block text-sm font-medium text-ink">
              Which decision should the board attack?
            </label>
            {decisions && decisions.length > 0 ? (
              <select
                id="subject"
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink focus:border-accent"
              >
                <option value="">Choose a decision…</option>
                {decisions.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.title}
                  </option>
                ))}
              </select>
            ) : (
              <p className="rounded-md border border-dashed border-line p-3 text-xs text-ink-muted">
                No decisions yet. Run a meeting through to a brief first — there is
                nothing to stress-test until the board has recommended something.
              </p>
            )}
          </section>
        )}

        <section>
          <label htmlFor="question" className="mb-2 block text-sm font-medium text-ink">
            What should the board decide?
          </label>
          <textarea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={4}
            maxLength={4000}
            placeholder="Should we prioritise retention, international expansion, or a new product?"
            className="w-full resize-y rounded-md border border-line bg-canvas px-3 py-2.5 text-sm leading-relaxed text-ink placeholder:text-ink-faint focus:border-accent"
          />
          <div className="mt-1.5 flex items-center justify-between text-xs">
            <span className={cn('text-ink-faint', tooShort && 'text-caution')}>
              {tooShort ? 'A bit more detail — at least 10 characters.' : 'Be specific.'}
            </span>
            <span className="text-ink-faint">{question.length}/4000</span>
          </div>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setQuestion(s)}
                className="rounded-full border border-line px-2.5 py-1 text-left text-[11px] text-ink-muted transition-colors hover:border-line-strong hover:text-ink"
              >
                {s.length > 58 ? `${s.slice(0, 58)}…` : s}
              </button>
            ))}
          </div>
        </section>

        <section>
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-medium text-ink">Who should attend?</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                The Chair decides who speaks to each item; you decide who is in the room.
              </p>
            </div>
            <Badge variant={!rosterLocked && selected.length === 0 ? 'critical' : 'accent'}>
              {rosterLocked ? 'all 8' : `${selected.length} selected`}
            </Badge>
          </div>

          {chair && (
            <div className="mb-3 flex items-center gap-2.5 rounded-lg border border-dashed border-line-strong p-2.5">
              <Gavel className="size-4 shrink-0 text-accent-soft" />
              <p className="text-xs text-ink-muted">
                <span className="text-ink">{chair.display_name}</span> chairs every meeting
                and cannot be removed.
              </p>
            </div>
          )}

          {rosterLocked ? (
            <p className="rounded-md border border-dashed border-line-strong p-3 text-xs text-ink-muted">
              A full board seats every executive. The Chair still decides who speaks
              to each agenda item.
            </p>
          ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {specialists.map((executive) => (
              <SelectableExecutive
                key={executive.agent_id}
                executive={executive}
                selected={selected.includes(executive.agent_id)}
                onToggle={() => toggle(executive.agent_id)}
              />
            ))}
          </div>
          )}

          {!rosterLocked && selected.length === 0 && (
            <p className="mt-2 text-xs text-critical">Pick at least one executive.</p>
          )}
          {selected.length > 5 && (
            <p className="mt-2 text-xs text-caution">
              Larger meetings cost more and take longer — each executive is a separate
              model call.
            </p>
          )}
        </section>

        {create.isError && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-card border border-critical/40 bg-critical/10 p-3"
          >
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-critical" />
            <div className="text-sm">
              <p className="font-medium text-ink">Could not start the meeting</p>
              <p className="mt-0.5 text-ink-muted">
                {create.error instanceof Error ? create.error.message : 'Unknown error'}
              </p>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button type="submit" size="lg" disabled={!canSubmit}>
            {create.isPending ? <Loader2 className="animate-spin" /> : <Gavel />}
            {create.isPending ? 'Convening…' : 'Convene the board'}
          </Button>
          <p className="text-xs text-ink-faint">
            Roughly {2 + (rosterLocked ? 8 : selected.length) * 2} model calls.
          </p>
        </div>
      </form>
    </div>
  )
}

function SelectableExecutive({
  executive,
  selected,
  onToggle,
}: {
  executive: ExecutiveDefinition
  selected: boolean
  onToggle: () => void
}) {
  const Portrait = EXECUTIVE_PORTRAITS[executive.avatar_ref]
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
      data-agent-id={executive.agent_id}
      className={cn(
        'group overflow-hidden rounded-lg border text-left transition-all',
        selected ? 'border-transparent' : 'border-line opacity-60 hover:opacity-100',
      )}
      style={selected ? { boxShadow: `0 0 0 2px ${executive.theme_color}` } : undefined}
    >
      <div className="aspect-[4/3] w-full overflow-hidden">
        {Portrait && (
          <Portrait
            accent={executive.theme_color}
            accentSoft={executive.theme_color_soft}
            className="size-full"
          />
        )}
      </div>
      <div className="p-2">
        <p className="truncate text-xs font-medium text-ink">{executive.display_name}</p>
        <p className="truncate text-[11px]" style={{ color: executive.theme_color_soft }}>
          {executive.short_title}
        </p>
      </div>
    </button>
  )
}
