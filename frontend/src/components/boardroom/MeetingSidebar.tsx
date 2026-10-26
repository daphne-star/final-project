import { BookOpen, ListChecks, Scale, Swords, Target } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { BoardroomState } from '@/lib/boardroomState'
import { cn } from '@/lib/utils'
import type { ExecutiveDefinition } from '@/types/agents'

export interface EvidenceEntry {
  agentId: string
  claim: string
  source: string
  isVerified: boolean
}

export interface MeetingSidebarProps {
  state: BoardroomState
  executivesById: Record<string, ExecutiveDefinition>
  /** Citations pulled from the persisted assessments. */
  evidence?: EvidenceEntry[]
  className?: string
}

/** Agenda, live disagreements, and where each executive currently stands. */
export function MeetingSidebar({
  state,
  executivesById,
  evidence = [],
  className,
}: MeetingSidebarProps) {
  const positions = Object.entries(state.emergingPositions)

  return (
    <div className={cn('space-y-6', className)}>
      <Panel icon={Target} title="Agenda">
        {state.reframedQuestion ? (
          <>
            <p className="mb-2 text-xs leading-relaxed text-ink">{state.reframedQuestion}</p>
            <ol className="space-y-1.5">
              {state.agendaItems.map((item, i) => (
                <li key={i} className="text-xs text-ink-muted">
                  <span className="text-ink-faint">{i + 1}.</span> {item.title}
                </li>
              ))}
            </ol>
          </>
        ) : (
          <Empty>The Chair has not set the agenda yet.</Empty>
        )}
      </Panel>

      {state.tensions.length > 0 && (
        <Panel icon={Scale} title="Tensions to test">
          <ul className="space-y-1.5">
            {state.tensions.map((tension, i) => (
              <li key={i} className="text-xs leading-relaxed text-ink-muted">
                {tension}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel icon={Swords} title="Disagreements">
        {state.disagreements.length === 0 ? (
          <Empty>None raised.</Empty>
        ) : (
          <ul className="space-y-2.5">
            {state.disagreements.map((d) => {
              const challenger = executivesById[d.challenger]
              const target = executivesById[d.target]
              return (
                <li key={d.id} className="rounded-md border border-line bg-canvas/40 p-2">
                  <div className="mb-1 flex items-center gap-1.5 text-[11px]">
                    <span style={{ color: challenger?.theme_color_soft }}>
                      {challenger?.short_title ?? d.challenger}
                    </span>
                    <span className="text-ink-faint">→</span>
                    <span style={{ color: target?.theme_color_soft }}>
                      {target?.short_title ?? d.target}
                    </span>
                    <Badge
                      variant={
                        d.severity === 'critical' || d.severity === 'major'
                          ? 'critical'
                          : 'caution'
                      }
                      className="ml-auto"
                    >
                      {d.severity}
                    </Badge>
                  </div>
                  <p className="text-xs leading-relaxed text-ink-muted">
                    <q>{d.claim}</q>
                  </p>
                </li>
              )
            })}
          </ul>
        )}
      </Panel>

      <Panel icon={BookOpen} title="Evidence cited">
        {evidence.length === 0 ? (
          <Empty>Nothing cited yet.</Empty>
        ) : (
          <ul className="space-y-2">
            {evidence.slice(0, 12).map((item, i) => {
              const executive = executivesById[item.agentId]
              return (
                <li key={i} className="text-xs">
                  <p className="leading-relaxed text-ink">{item.claim}</p>
                  <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-ink-faint">
                    <span style={{ color: executive?.theme_color_soft }}>
                      {executive?.short_title ?? item.agentId}
                    </span>
                    <span>·</span>
                    <span>{item.source}</span>
                    {!item.isVerified && (
                      <Badge variant="caution" className="ml-auto">
                        unverified
                      </Badge>
                    )}
                  </p>
                </li>
              )
            })}
          </ul>
        )}
      </Panel>

      <Panel icon={ListChecks} title="Where they stand">
        {positions.length === 0 ? (
          <Empty>No positions yet.</Empty>
        ) : (
          <ul className="space-y-2">
            {positions.map(([agentId, position]) => {
              const executive = executivesById[agentId]
              return (
                <li key={agentId}>
                  <p
                    className="text-[11px] font-medium"
                    style={{ color: executive?.theme_color_soft }}
                  >
                    {executive?.display_name ?? agentId}
                  </p>
                  <p className="text-xs leading-relaxed text-ink-muted">{position}</p>
                </li>
              )
            })}
          </ul>
        )}
      </Panel>
    </div>
  )
}

function Panel({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Target
  title: string
  children: React.ReactNode
}) {
  return (
    <section>
      <h2 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
        <Icon className="size-3.5" />
        {title}
      </h2>
      {children}
    </section>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-xs italic text-ink-faint">{children}</p>
}
