import { useState, type FormEvent } from 'react'
import { AlertCircle, Loader2, Send } from 'lucide-react'

import { useQueueIntervention } from '@/api/meetings'
import { EXECUTIVE_PORTRAITS } from '@/assets/executives'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import type { ExecutiveDefinition } from '@/types/agents'
import type { Intervention, InterventionKind } from '@/types/meetings'

interface KindOption {
  kind: InterventionKind
  label: string
  placeholder: (name: string) => string
  needsTarget?: boolean
}

/** Mirrors InterventionKind in backend/app/models/intervention.py. */
const KINDS: KindOption[] = [
  {
    kind: 'ask',
    label: 'Ask a question',
    placeholder: (n) => `Something you want ${n} to answer directly…`,
  },
  {
    kind: 'challenge',
    label: 'Challenge them',
    placeholder: () => 'Which part of their position do you not believe, and why?',
  },
  {
    kind: 'request_evidence',
    label: 'Ask what it rests on',
    placeholder: () => 'Which claim do you want the evidence for?',
  },
  {
    kind: 'critique_colleague',
    label: 'Critique a colleague',
    placeholder: () => 'What should they examine in their colleague’s conclusion?',
    needsTarget: true,
  },
  {
    kind: 'request_alternative',
    label: 'Ask for an alternative',
    placeholder: () => 'What kind of option is missing from the discussion?',
  },
  {
    kind: 'implementation_detail',
    label: 'Ask how it would work',
    placeholder: () => 'Which part of the plan do you want made concrete?',
  },
  {
    kind: 'explain_risk',
    label: 'Ask about a risk',
    placeholder: () => 'Which risk do you want explained properly?',
  },
]

export interface InterventionPanelProps {
  meetingId: string
  executive: ExecutiveDefinition | null
  colleagues: ExecutiveDefinition[]
  interventions: Intervention[]
  open: boolean
  onOpenChange: (open: boolean) => void
  /** False when the meeting is not running or paused. */
  canIntervene: boolean
}

export function InterventionPanel({
  meetingId,
  executive,
  colleagues,
  interventions,
  open,
  onOpenChange,
  canIntervene,
}: InterventionPanelProps) {
  const queue = useQueueIntervention(meetingId)
  const [kind, setKind] = useState<InterventionKind>('ask')
  const [text, setText] = useState('')
  const [about, setAbout] = useState('')

  if (!executive) return null

  const Portrait = EXECUTIVE_PORTRAITS[executive.avatar_ref]
  const option = KINDS.find((k) => k.kind === kind) ?? KINDS[0]
  const mine = interventions.filter((i) => i.agent_id === executive.agent_id)
  const ready = text.trim().length > 2 && (!option.needsTarget || about)

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!ready || queue.isPending) return
    queue.mutate(
      {
        agent_id: executive!.agent_id,
        kind,
        prompt: text.trim(),
        about_agent_id: option.needsTarget ? about : undefined,
      },
      { onSuccess: () => setText('') },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent side="right" className="flex max-h-dvh flex-col overflow-y-auto p-0">
        <DialogHeader className="flex-row items-center gap-3 p-4 pb-3">
          <div
            className="size-10 shrink-0 overflow-hidden rounded-md border"
            style={{ borderColor: `${executive.theme_color}66` }}
          >
            {Portrait && (
              <Portrait
                accent={executive.theme_color}
                accentSoft={executive.theme_color_soft}
                className="size-full"
              />
            )}
          </div>
          <div className="min-w-0">
            <DialogTitle className="text-base">{executive.display_name}</DialogTitle>
            <DialogDescription>{executive.title}</DialogDescription>
          </div>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 px-4 pb-4">
          {!canIntervene ? (
            <p className="rounded-md border border-dashed border-line p-3 text-xs text-ink-muted">
              This meeting is not in progress, so there is nobody to interrupt.
              Interventions only apply to a running or paused meeting.
            </p>
          ) : (
            <form onSubmit={submit} className="space-y-3">
              <div className="flex flex-wrap gap-1.5">
                {KINDS.map((k) => (
                  <button
                    key={k.kind}
                    type="button"
                    data-kind={k.kind}
                    aria-pressed={k.kind === kind}
                    onClick={() => setKind(k.kind)}
                    className={cn(
                      'rounded-full border px-2.5 py-1 text-[11px] transition-colors',
                      k.kind === kind
                        ? 'border-accent bg-accent/15 text-accent-soft'
                        : 'border-line text-ink-muted hover:text-ink',
                    )}
                  >
                    {k.label}
                  </button>
                ))}
              </div>

              {option.needsTarget && (
                <select
                  value={about}
                  onChange={(e) => setAbout(e.target.value)}
                  aria-label="Whose conclusion"
                  className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink focus:border-accent"
                >
                  <option value="">Whose conclusion?</option>
                  {colleagues
                    .filter((c) => c.agent_id !== executive.agent_id)
                    .map((c) => (
                      <option key={c.agent_id} value={c.agent_id}>
                        {c.display_name}
                      </option>
                    ))}
                </select>
              )}

              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={3}
                maxLength={4000}
                placeholder={option.placeholder(executive.display_name)}
                aria-label="Your instruction"
                className="w-full resize-y rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent"
              />

              {queue.isError && (
                <p role="alert" className="flex items-start gap-1.5 text-xs text-critical">
                  <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
                  {queue.error instanceof Error ? queue.error.message : 'Could not send'}
                </p>
              )}

              <div className="flex items-center gap-2">
                <Button type="submit" size="sm" disabled={!ready || queue.isPending}>
                  {queue.isPending ? <Loader2 className="animate-spin" /> : <Send />}
                  Send to {executive.short_title}
                </Button>
                <p className="text-[11px] text-ink-faint">
                  Answered at the next safe point, not mid-step.
                </p>
              </div>
            </form>
          )}

          <section>
            <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              Your exchanges with {executive.short_title}
            </h4>
            {mine.length === 0 ? (
              <p className="text-xs italic text-ink-faint">Nothing yet.</p>
            ) : (
              <ul className="space-y-2">
                {mine.map((item) => (
                  <li
                    key={item.id}
                    data-status={item.status}
                    className="rounded-md border border-line bg-surface p-2.5"
                  >
                    <div className="mb-1 flex items-center gap-2">
                      <span className="text-[11px] text-ink-faint">
                        {KINDS.find((k) => k.kind === item.kind)?.label ?? item.kind}
                      </span>
                      <StatusBadge status={item.status} />
                    </div>
                    <p className="text-xs italic text-ink-muted">“{item.prompt}”</p>
                    {item.response && (
                      <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                        {item.response}
                      </p>
                    )}
                    {item.error_message && (
                      <p className="mt-1.5 text-xs text-critical">{item.error_message}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function StatusBadge({ status }: { status: Intervention['status'] }) {
  const map = {
    queued: { label: 'Queued', variant: 'default' as const },
    running: { label: 'Answering', variant: 'accent' as const },
    answered: { label: 'Answered', variant: 'positive' as const },
    failed: { label: 'Failed', variant: 'critical' as const },
    abandoned: { label: 'Meeting ended', variant: 'default' as const },
  }
  const v = map[status]
  return (
    <Badge variant={v.variant} className="ml-auto">
      {v.label}
    </Badge>
  )
}

export { KINDS as INTERVENTION_KINDS }
