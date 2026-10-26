import { Construction } from 'lucide-react'

/**
 * Honest stub for routes whose backend does not exist yet. Named phases rather
 * than a vague "coming soon", so the nav never implies working features.
 */
export function PhasePending({ title, phase, body }: { title: string; phase: string; body: string }) {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-16 sm:px-6 lg:px-10">
      <div className="rounded-card border border-line bg-surface p-8">
        <span className="grid size-9 place-items-center rounded-md bg-surface-raised text-ink-muted">
          <Construction className="size-4" />
        </span>
        <h1 className="mt-4 font-display text-2xl tracking-tight">{title}</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">{body}</p>
        <p className="mt-4 text-xs font-medium uppercase tracking-wider text-ink-faint">
          Scheduled for {phase}
        </p>
      </div>
    </div>
  )
}

export const Boardroom = () => (
  <PhasePending
    title="The Boardroom"
    phase="Phase 4"
    body="The live meeting interface: transcript, speaker portraits, agenda and risk panels, and real streamed events from the orchestrator. It needs the meeting engine behind it, so there is nothing to show until that exists."
  />
)

export const DecisionCenter = () => (
  <PhasePending
    title="Decision Center"
    phase="Phase 4"
    body="Structured decision briefs with options, dissent, and a 30/60/90-day plan — generated from an actual board meeting, then accepted, rejected or deferred by you."
  />
)

export const CompanyIntelligence = () => (
  <PhasePending
    title="Company Intelligence"
    phase="Phase 7"
    body="Company profile, goals, financial metrics, and document upload with extraction and retrieval. The schema and API already exist; the editing surface is next."
  />
)

export const DecisionHistory = () => (
  <PhasePending
    title="Decision History"
    phase="Phase 7"
    body="Past meetings, their recommendations, and what came of them — including reopening an old decision for a fresh board review."
  />
)
