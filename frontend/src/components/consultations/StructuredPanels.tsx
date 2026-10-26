import { AlertTriangle, CircleHelp, ListChecks, Lightbulb } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ConsultationStructured, Severity } from '@/types/consultations'

const SEVERITY_VARIANT: Record<Severity, 'default' | 'caution' | 'critical'> = {
  minor: 'default',
  moderate: 'caution',
  major: 'critical',
  critical: 'critical',
}

const CONFIDENCE_VARIANT = {
  low: 'critical',
  medium: 'caution',
  high: 'positive',
} as const

/**
 * The structured half of an agent answer. Assumptions and open questions are
 * given the same visual weight as the recommendations — the spec treats
 * "what we are guessing" as part of the deliverable, not a disclaimer.
 */
export function StructuredPanels({
  data,
  accent,
}: {
  data: ConsultationStructured
  accent: string
}) {
  const hasAny =
    data.key_points.length ||
    data.assumptions.length ||
    data.risks.length ||
    data.open_questions.length ||
    data.recommended_actions.length

  if (!hasAny) return null

  return (
    <div className="mt-4 space-y-4 border-t border-line pt-4">
      {data.key_points.length > 0 && (
        <Panel icon={Lightbulb} title="Key points" accent={accent}>
          <ul className="space-y-1.5">
            {data.key_points.map((point, i) => (
              <li key={i} className="flex gap-2.5 text-sm text-ink-muted">
                <span
                  aria-hidden
                  className="mt-1.5 size-1.5 shrink-0 rounded-full"
                  style={{ backgroundColor: accent }}
                />
                <span className="leading-relaxed">{point}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {data.recommended_actions.length > 0 && (
        <Panel icon={ListChecks} title="Recommended actions" accent={accent}>
          <ul className="space-y-2">
            {data.recommended_actions.map((action, i) => (
              <li key={i} className="rounded-md border border-line bg-canvas/40 p-2.5">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm leading-relaxed text-ink">{action.description}</p>
                  <Badge variant={action.priority === 'low' ? 'default' : 'caution'}>
                    {action.priority}
                  </Badge>
                </div>
                {(action.suggested_owner || action.rough_timeline) && (
                  <p className="mt-1.5 text-xs text-ink-faint">
                    {[action.suggested_owner, action.rough_timeline]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {data.risks.length > 0 && (
        <Panel icon={AlertTriangle} title="Risks" accent={accent}>
          <ul className="space-y-2">
            {data.risks.map((risk, i) => (
              <li key={i} className="rounded-md border border-line bg-canvas/40 p-2.5">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm leading-relaxed text-ink">{risk.description}</p>
                  <Badge variant={SEVERITY_VARIANT[risk.severity]}>{risk.severity}</Badge>
                </div>
                {risk.mitigation && (
                  <p className="mt-1.5 text-xs text-ink-muted">
                    <span className="text-ink-faint">Mitigation: </span>
                    {risk.mitigation}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {data.assumptions.length > 0 && (
        <Panel icon={CircleHelp} title="Assumptions" accent={accent}>
          <ul className="space-y-2">
            {data.assumptions.map((a, i) => (
              <li key={i} className="rounded-md border border-dashed border-line p-2.5">
                <p className="text-sm leading-relaxed text-ink">{a.statement}</p>
                <p className="mt-1 text-xs text-ink-muted">{a.why_it_matters}</p>
                {a.how_to_validate && (
                  <p className="mt-1 text-xs text-ink-faint">
                    How to check: {a.how_to_validate}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {data.open_questions.length > 0 && (
        <Panel icon={CircleHelp} title="Open questions" accent={accent}>
          <ul className="space-y-2">
            {data.open_questions.map((q, i) => (
              <li key={i} className="text-sm">
                <p className="leading-relaxed text-ink">{q.question}</p>
                <p className="mt-0.5 text-xs text-ink-muted">{q.why_it_matters}</p>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="flex items-center gap-2 pt-1">
        <span className="text-xs text-ink-faint">Confidence</span>
        <Badge variant={CONFIDENCE_VARIANT[data.confidence_level]}>
          {data.confidence_level}
        </Badge>
      </div>
    </div>
  )
}

function Panel({
  icon: Icon,
  title,
  accent,
  children,
  className,
}: {
  icon: typeof Lightbulb
  title: string
  accent: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={cn('', className)}>
      <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-faint">
        <Icon className="size-3.5" style={{ color: accent }} />
        {title}
      </h4>
      {children}
    </section>
  )
}
