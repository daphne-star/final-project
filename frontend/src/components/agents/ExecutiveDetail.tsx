import { Loader2, MessageSquarePlus, Users } from 'lucide-react'

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
import type { ExecutiveDefinition } from '@/types/agents'

interface ExecutiveDetailProps {
  executive: ExecutiveDefinition | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onConsult?: (executive: ExecutiveDefinition) => void
  onSelectForMeeting?: (executive: ExecutiveDefinition) => void
  selectedForMeeting?: boolean
  consultPending?: boolean
}

export function ExecutiveDetail({
  executive,
  open,
  onOpenChange,
  onConsult,
  onSelectForMeeting,
  selectedForMeeting = false,
  consultPending = false,
}: ExecutiveDetailProps) {
  if (!executive) return null
  const Portrait = EXECUTIVE_PORTRAITS[executive.avatar_ref]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88dvh] overflow-y-auto p-0">
        <div className="flex flex-col gap-0 sm:flex-row">
          <div
            className="relative w-full shrink-0 sm:w-56"
            style={{ backgroundColor: `${executive.theme_color}14` }}
          >
            <div className="aspect-[3/4] w-full sm:sticky sm:top-0">
              {Portrait && (
                <Portrait
                  accent={executive.theme_color}
                  accentSoft={executive.theme_color_soft}
                  className="size-full"
                />
              )}
            </div>
          </div>

          <div className="min-w-0 flex-1">
            <DialogHeader>
              <Badge
                variant="outline"
                className="w-fit"
                style={{ color: executive.theme_color_soft, borderColor: `${executive.theme_color}66` }}
              >
                {executive.short_title}
              </Badge>
              <DialogTitle>{executive.display_name}</DialogTitle>
              <DialogDescription>{executive.title}</DialogDescription>
            </DialogHeader>

            <div className="space-y-5 px-6 pb-6">
              <Section title="Distinctive perspective">
                <p className="text-sm leading-relaxed text-ink">
                  {executive.distinctive_perspective}
                </p>
              </Section>

              <Section title="Responsibilities">
                <ul className="space-y-1.5">
                  {executive.responsibilities.map((item) => (
                    <li key={item} className="flex gap-2.5 text-sm text-ink-muted">
                      <span
                        aria-hidden
                        className="mt-1.5 size-1.5 shrink-0 rounded-full"
                        style={{ backgroundColor: executive.theme_color }}
                      />
                      <span className="leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </Section>

              <Section title="Working style">
                <p className="text-sm leading-relaxed text-ink-muted">{executive.personality}</p>
              </Section>

              <div className="flex flex-col gap-2 pt-1 sm:flex-row">
                {executive.can_consult_one_on_one && (
                  <Button
                    variant="default"
                    className="flex-1"
                    disabled={consultPending}
                    onClick={() => onConsult?.(executive)}
                  >
                    {consultPending ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <MessageSquarePlus />
                    )}
                    Consult one-on-one
                  </Button>
                )}
                <Button
                  variant={selectedForMeeting ? 'subtle' : 'outline'}
                  className="flex-1"
                  onClick={() => onSelectForMeeting?.(executive)}
                >
                  <Users />
                  {selectedForMeeting ? 'On the board' : 'Add to meeting'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">
        {title}
      </h4>
      {children}
    </section>
  )
}
