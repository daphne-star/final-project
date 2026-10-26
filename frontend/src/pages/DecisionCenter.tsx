import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Check,
  CircleHelp,
  Clock,
  Download,
  FileText,
  Loader2,
  Star,
  X,
} from 'lucide-react'

import { useExecutives } from '@/api/agents'
import {
  downloadDecision,
  useActionItems,
  useDecision,
  useUpdateActionItem,
  useUpdateDecision,
} from '@/api/meetings'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Decision, PlanItem } from '@/types/meetings'

export function DecisionCenterPage() {
  const { decisionId } = useParams<{ decisionId: string }>()
  const { data: decision, isLoading, isError, error } = useDecision(decisionId)
  const { data: executives } = useExecutives()
  const update = useUpdateDecision(decisionId ?? '')
  const [notes, setNotes] = useState('')
  const [exporting, setExporting] = useState<string | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)

  const nameOf = (agentId: string) =>
    executives?.find((e) => e.agent_id === agentId)?.display_name ?? agentId
  const colorOf = (agentId: string) =>
    executives?.find((e) => e.agent_id === agentId)?.theme_color_soft

  if (isLoading) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loader2 className="size-5 animate-spin text-ink-muted" />
      </div>
    )
  }

  if (isError || !decision) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <p className="text-sm text-critical">
          {error instanceof Error ? error.message : 'Could not load this decision'}
        </p>
        <Button variant="ghost" size="sm" className="mt-3" asChild>
          <Link to="/meetings">
            <ArrowLeft />
            All meetings
          </Link>
        </Button>
      </div>
    )
  }

  const recommended = decision.strategic_options.find(
    (o) => o.option_id === decision.recommended_option_id,
  )

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 lg:px-10 lg:py-12">
      <header className="mb-8">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link to={decision.meeting_id ? `/boardroom/${decision.meeting_id}` : '/meetings'}>
              <ArrowLeft />
              Back to the meeting
            </Link>
          </Button>
          <VerdictBadge status={decision.status} />

          <div className="ml-auto flex gap-2">
            {(['markdown', 'pdf'] as const).map((format) => (
              <Button
                key={format}
                variant="outline"
                size="sm"
                disabled={exporting !== null}
                onClick={async () => {
                  setExporting(format)
                  setExportError(null)
                  try {
                    await downloadDecision(decision.id, format)
                  } catch (err) {
                    setExportError(
                      err instanceof Error ? err.message : 'Export failed',
                    )
                  } finally {
                    setExporting(null)
                  }
                }}
              >
                {exporting === format ? (
                  <Loader2 className="animate-spin" />
                ) : format === 'pdf' ? (
                  <Download />
                ) : (
                  <FileText />
                )}
                {format === 'pdf' ? 'PDF' : 'Markdown'}
              </Button>
            ))}
          </div>
        </div>
        {exportError && (
          <p role="alert" className="mt-2 text-sm text-critical">
            {exportError}
          </p>
        )}
        <h1 className="mt-3 font-display text-3xl tracking-tight text-balance">
          {decision.title}
        </h1>
      </header>

      <Section title="Executive summary">
        <p className="text-sm leading-relaxed text-ink">{decision.executive_summary}</p>
      </Section>

      <Section title="Problem">
        <p className="text-sm leading-relaxed text-ink-muted">{decision.problem_statement}</p>
      </Section>

      <Section title="Options">
        <div className="space-y-3">
          {decision.strategic_options.map((option) => {
            const isRecommended = option.option_id === decision.recommended_option_id
            return (
              <div
                key={option.option_id}
                className={cn(
                  'rounded-card border p-4',
                  isRecommended ? 'border-accent/50 bg-accent/5' : 'border-line bg-surface',
                )}
              >
                <div className="mb-1.5 flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-ink">{option.title}</h3>
                  {isRecommended && (
                    <Badge variant="accent">
                      <Star className="size-3" />
                      Recommended
                    </Badge>
                  )}
                </div>
                <p className="text-sm leading-relaxed text-ink-muted">{option.description}</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <MiniList label="Benefits" items={option.benefits} />
                  <MiniList label="Risks" items={option.risks} />
                </div>
                {option.evaluation && (
                  <p className="mt-3 border-t border-line pt-2 text-xs italic text-ink-faint">
                    {option.evaluation}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </Section>

      {decision.recommendation_rationale && (
        <Section title={`Why ${recommended?.title ?? 'this option'}`}>
          <p className="text-sm leading-relaxed text-ink">
            {decision.recommendation_rationale}
          </p>
        </Section>
      )}

      <div className="grid gap-6 sm:grid-cols-2">
        <Implication label="Financial" text={decision.financial_implications} />
        <Implication label="Operational" text={decision.operational_implications} />
        <Implication label="Customer" text={decision.customer_implications} />
        <Implication label="Competitive" text={decision.competitive_implications} />
        <Implication label="Legal" text={decision.legal_considerations} />
      </div>

      {decision.dissenting_opinions.length > 0 && (
        <Section title="Dissent">
          <p className="mb-2 text-xs text-ink-faint">
            Positions that did not survive into the recommendation, kept on the record.
          </p>
          <div className="space-y-2">
            {decision.dissenting_opinions.map((d, i) => (
              <div key={i} className="rounded-md border-l-2 border-caution bg-surface p-3">
                <p className="text-xs font-medium" style={{ color: colorOf(d.agent_id) }}>
                  {nameOf(d.agent_id)}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-ink">{d.position}</p>
                <p className="mt-1 text-xs text-ink-muted">{d.reasoning}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {decision.unresolved_questions.length > 0 && (
        <Section title="Still unresolved">
          <ul className="space-y-2">
            {decision.unresolved_questions.map((q, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <CircleHelp className="mt-0.5 size-3.5 shrink-0 text-ink-faint" />
                <span>
                  <span className="text-ink">{q.question}</span>
                  <span className="block text-xs text-ink-muted">{q.why_it_matters}</span>
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {decision.confidence_and_uncertainty && (
        <Section title="Confidence">
          <p className="text-sm leading-relaxed text-ink-muted">
            {decision.confidence_and_uncertainty}
          </p>
        </Section>
      )}

      <Section title="30 / 60 / 90-day plan">
        <div className="grid gap-4 sm:grid-cols-3">
          <PlanColumn label="First 30 days" items={decision.action_plan?.first_30_days} />
          <PlanColumn label="Days 30–60" items={decision.action_plan?.days_30_to_60} />
          <PlanColumn label="Days 60–90" items={decision.action_plan?.days_60_to_90} />
        </div>
      </Section>

      <ActionItemsSection decisionId={decision.id} />

      <Section title="Your decision">
        <p className="mb-3 text-xs text-ink-muted">
          The board advises. The call is yours.
        </p>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder={decision.decision_notes ?? 'Optional note on why…'}
          className="mb-3 w-full resize-y rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent"
        />
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() =>
              update.mutate({ status: 'accepted', decision_notes: notes || undefined })
            }
            disabled={update.isPending}
          >
            <Check />
            Accept
          </Button>
          <Button
            variant="outline"
            onClick={() =>
              update.mutate({ status: 'deferred', decision_notes: notes || undefined })
            }
            disabled={update.isPending}
          >
            <Clock />
            Defer
          </Button>
          <Button
            variant="outline"
            onClick={() =>
              update.mutate({ status: 'rejected', decision_notes: notes || undefined })
            }
            disabled={update.isPending}
          >
            <X />
            Reject
          </Button>
        </div>
        {update.isError && (
          <p role="alert" className="mt-2 text-sm text-critical">
            {update.error instanceof Error ? update.error.message : 'Could not save'}
          </p>
        )}
      </Section>
    </div>
  )
}

function VerdictBadge({ status }: { status: Decision['status'] }) {
  const map = {
    proposed: { label: 'Awaiting your decision', variant: 'default' as const },
    accepted: { label: 'Accepted', variant: 'positive' as const },
    rejected: { label: 'Rejected', variant: 'critical' as const },
    deferred: { label: 'Deferred', variant: 'caution' as const },
  }
  const v = map[status]
  return <Badge variant={v.variant}>{v.label}</Badge>
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">
        {title}
      </h2>
      {children}
    </section>
  )
}

function Implication({ label, text }: { label: string; text: string | null }) {
  if (!text) return null
  return (
    <div className="mb-6">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-faint">
        {label}
      </h3>
      <p className="text-sm leading-relaxed text-ink-muted">{text}</p>
    </div>
  )
}

function MiniList({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
        {label}
      </p>
      <ul className="space-y-0.5">
        {items.map((item, i) => (
          <li key={i} className="text-xs leading-relaxed text-ink-muted">
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

function PlanColumn({ label, items }: { label: string; items: PlanItem[] | undefined }) {
  return (
    <div className="rounded-card border border-line bg-surface p-3">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
        {label}
      </p>
      {!items || items.length === 0 ? (
        <p className="text-xs italic text-ink-faint">Nothing scheduled.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, i) => (
            <li key={i}>
              <p className="text-xs leading-relaxed text-ink">{item.description}</p>
              <p className="mt-0.5 text-[11px] text-ink-faint">
                {[item.priority, item.suggested_owner].filter(Boolean).join(' · ')}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}


function ActionItemsSection({ decisionId }: { decisionId: string }) {
  const { data: items } = useActionItems()
  const update = useUpdateActionItem()
  const mine = (items ?? []).filter((i) => i.decision_id === decisionId)

  if (mine.length === 0) return null

  return (
    <Section title="Action items">
      <p className="mb-2 text-xs text-ink-muted">
        Assign an owner or close one off as the work moves.
      </p>
      <ul className="space-y-2">
        {mine.map((item) => (
          <li
            key={item.id}
            data-status={item.status}
            className={cn(
              'rounded-card border border-line bg-surface p-3',
              item.status === 'done' && 'opacity-60',
            )}
          >
            <div className="flex flex-wrap items-start gap-2">
              <p
                className={cn(
                  'flex-1 text-sm leading-relaxed text-ink',
                  item.status === 'done' && 'line-through',
                )}
              >
                {item.description}
              </p>
              <Badge variant={item.priority === 'low' ? 'default' : 'caution'}>
                {item.priority}
              </Badge>
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <input
                defaultValue={item.suggested_owner ?? ''}
                placeholder="Owner"
                onBlur={(e) =>
                  e.target.value !== (item.suggested_owner ?? '') &&
                  update.mutate({ id: item.id, suggested_owner: e.target.value })
                }
                aria-label={`Owner for ${item.description}`}
                className="w-32 rounded-md border border-line bg-canvas px-2 py-1 text-xs text-ink placeholder:text-ink-faint focus:border-accent"
              />
              <select
                value={item.status}
                onChange={(e) => update.mutate({ id: item.id, status: e.target.value })}
                aria-label={`Status for ${item.description}`}
                className="rounded-md border border-line bg-canvas px-2 py-1 text-xs text-ink focus:border-accent"
              >
                {['open', 'in_progress', 'blocked', 'done', 'cancelled'].map((s) => (
                  <option key={s} value={s}>
                    {s.replace('_', ' ')}
                  </option>
                ))}
              </select>
              {item.dependencies
                .filter((d) => d.startsWith('window:'))
                .map((d) => (
                  <span key={d} className="text-[11px] text-ink-faint">
                    {d.replace('window:', '')}
                  </span>
                ))}
            </div>
          </li>
        ))}
      </ul>
    </Section>
  )
}
