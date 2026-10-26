import { Link } from 'react-router-dom'
import { ArrowRight, Building2, Gavel, Users } from 'lucide-react'

import { useExecutives } from '@/api/agents'
import { EXECUTIVE_PORTRAITS } from '@/assets/executives'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * Phase 1 dashboard: navigation plus the empty state. The meeting, risk, and
 * action-item panels land in Phases 4 and 8 with real data behind them, so
 * they are deliberately absent rather than mocked.
 */
export function Dashboard() {
  const { data: executives } = useExecutives()

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-10 lg:py-12">
      <header className="mb-10">
        <p className="text-xs font-semibold uppercase tracking-wider text-accent-soft">
          Ghost Board
        </p>
        <h1 className="mt-2 font-display text-4xl tracking-tight text-balance">
          Every founder deserves a world-class executive team.
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-muted">
          Put a decision in front of nine executives who will analyse it independently,
          argue with each other about it, and hand you a brief you can act on.
        </p>
      </header>

      {/* Roster strip — the product identity, visible before any data exists */}
      {executives && (
        <div className="mb-10 flex gap-2 overflow-x-auto pb-2">
          {executives.map((exec) => {
            const Portrait = EXECUTIVE_PORTRAITS[exec.avatar_ref]
            return (
              // The portrait SVG carries its own role="img" and label, so
              // the wrapper stays a plain box: nesting a second image here
              // makes a screen reader read every executive twice.
              <div
                key={exec.agent_id}
                className="relative h-28 w-21 shrink-0 overflow-hidden rounded-lg border border-line"
                style={{ width: 84 }}
                title={`${exec.display_name} — ${exec.title}`}
              >
                {Portrait && (
                  <Portrait
                    accent={exec.theme_color}
                    accentSoft={exec.theme_color_soft}
                    className="size-full"
                  />
                )}
              </div>
            )
          })}
        </div>
      )}

      <section className="grid gap-4 md:grid-cols-3">
        <OnboardingCard
          icon={Building2}
          step="1"
          title="Describe the company"
          body="The board reasons over your real numbers. Nothing is assumed, and anything unverified stays labelled as an assumption."
          to="/company"
          cta="Add company context"
        />
        <OnboardingCard
          icon={Users}
          step="2"
          title="Meet the executives"
          body="Nine fixed roles, from the CFO who checks your runway to the consultant whose job is to disagree with everyone."
          to="/board"
          cta="View the board"
        />
        <OnboardingCard
          icon={Gavel}
          step="3"
          title="Convene a meeting"
          body="Bring a real decision. The Chair sets an agenda, the executives assess it independently, then they debate."
          to="/meetings/new"
          cta="Convene the board"
        />
      </section>
    </div>
  )
}

function OnboardingCard({
  icon: Icon,
  step,
  title,
  body,
  to,
  cta,
  disabled = false,
}: {
  icon: typeof Building2
  step: string
  title: string
  body: string
  to: string
  cta: string
  disabled?: boolean
}) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="mb-1 flex items-center gap-2">
          <span className="grid size-7 place-items-center rounded-md bg-accent/15 text-accent-soft">
            <Icon className="size-4" />
          </span>
          <span className="text-xs font-semibold text-ink-faint">Step {step}</span>
        </div>
        <CardTitle as="h2">{title}</CardTitle>
        <CardDescription className="leading-relaxed">{body}</CardDescription>
      </CardHeader>
      <CardContent className="mt-auto">
        {disabled ? (
          <Button variant="ghost" size="sm" disabled>
            {cta}
          </Button>
        ) : (
          <Button variant="ghost" size="sm" asChild>
            <Link to={to}>
              {cta}
              <ArrowRight />
            </Link>
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
