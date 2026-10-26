import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, Users } from 'lucide-react'

import { useExecutives } from '@/api/agents'
import { useCreateConsultation } from '@/api/consultations'
import { ExecutiveCard } from '@/components/agents/ExecutiveCard'
import { ExecutiveDetail } from '@/components/agents/ExecutiveDetail'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { ExecutiveDefinition } from '@/types/agents'

export function MyBoard() {
  const { data: executives, isLoading, isError, error } = useExecutives()
  const [inspecting, setInspecting] = useState<ExecutiveDefinition | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const navigate = useNavigate()
  const createConsultation = useCreateConsultation()

  const selectedCount = selected.size
  const chair = useMemo(
    () => executives?.find((e) => e.can_chair) ?? null,
    [executives],
  )

  function startConsultation(exec: ExecutiveDefinition) {
    createConsultation.mutate(
      { agent_id: exec.agent_id },
      { onSuccess: (c) => navigate(`/consult/${c.id}`) },
    )
  }

  function toggleSelection(exec: ExecutiveDefinition) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(exec.agent_id)) next.delete(exec.agent_id)
      else next.add(exec.agent_id)
      return next
    })
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-10 lg:py-12">
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl tracking-tight text-balance">My Board</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
            Nine executives, each with their own remit and their own way of being wrong.
            Inspect one to see how it thinks, or pick a few to convene.
          </p>
        </div>

        {selectedCount > 0 && (
          <div className="flex items-center gap-3">
            <Badge variant="accent">
              <Users className="size-3" />
              {selectedCount} selected
            </Badge>
            <Button variant="outline" size="sm" onClick={() => setSelected(new Set())}>
              Clear
            </Button>
            <Button size="sm" disabled title="Board meetings arrive in Phase 4">
              Convene
            </Button>
          </div>
        )}
      </header>

      {isLoading && <RosterSkeleton />}

      {isError && (
        <div className="flex items-start gap-3 rounded-card border border-critical/40 bg-critical/10 p-4">
          <AlertCircle className="mt-0.5 size-5 shrink-0 text-critical" />
          <div>
            <p className="text-sm font-medium text-ink">Could not load the roster</p>
            <p className="mt-1 text-sm text-ink-muted">
              {error instanceof Error ? error.message : 'Unknown error'}. Check that the
              FastAPI backend is running on port 8000.
            </p>
          </div>
        </div>
      )}

      {executives && (
        <>
          {chair && (
            <section className="mb-10">
              <SectionLabel>Chairs the meeting</SectionLabel>
              {/* Same track sizing as the team grid below, so the chair card
                  is not a different width from everyone else. */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                <ExecutiveCard
                  executive={chair}
                  selected={selected.has(chair.agent_id)}
                  onClick={setInspecting}
                />
              </div>
            </section>
          )}

          <section>
            <SectionLabel>The executive team</SectionLabel>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4">
              {executives
                .filter((e) => !e.can_chair)
                .map((exec) => (
                  <ExecutiveCard
                    key={exec.agent_id}
                    executive={exec}
                    selected={selected.has(exec.agent_id)}
                    onClick={setInspecting}
                  />
                ))}
            </div>
          </section>
        </>
      )}

      <ExecutiveDetail
        executive={inspecting}
        open={inspecting !== null}
        onOpenChange={(open) => !open && setInspecting(null)}
        selectedForMeeting={inspecting ? selected.has(inspecting.agent_id) : false}
        onSelectForMeeting={(exec) => toggleSelection(exec)}
        onConsult={startConsultation}
        consultPending={createConsultation.isPending}
      />

      {createConsultation.isError && (
        <div
          role="alert"
          className="fixed inset-x-4 bottom-4 z-50 mx-auto max-w-md rounded-card border border-critical/40 bg-surface p-3 text-sm shadow-lg"
        >
          <p className="font-medium text-ink">Could not start the consultation</p>
          <p className="mt-1 text-ink-muted">
            {createConsultation.error instanceof Error
              ? createConsultation.error.message
              : 'Unknown error'}
          </p>
        </div>
      )}
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-faint">
      {children}
    </h2>
  )
}

function RosterSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="aspect-[3/4] animate-pulse rounded-card border border-line bg-surface"
        />
      ))}
    </div>
  )
}
