import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertCircle, ArrowLeft, Loader2, Send } from 'lucide-react'

import { useExecutives } from '@/api/agents'
import { useConsultation, useSendMessage } from '@/api/consultations'
import { EXECUTIVE_PORTRAITS } from '@/assets/executives'
import { StructuredPanels } from '@/components/consultations/StructuredPanels'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ConsultationMessage } from '@/types/consultations'
import type { ExecutiveDefinition } from '@/types/agents'

export function ConsultationPage() {
  const { consultationId } = useParams<{ consultationId: string }>()
  const { data: consultation, isLoading, isError, error } = useConsultation(consultationId)
  const { data: executives } = useExecutives()
  const send = useSendMessage(consultationId ?? '')
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  const executive = executives?.find((e) => e.agent_id === consultation?.agent_id)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [consultation?.messages.length, send.isPending])

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    const content = draft.trim()
    if (!content || send.isPending) return
    setDraft('')
    send.mutate(content, { onError: () => setDraft(content) })
  }

  if (isLoading) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loader2 className="size-5 animate-spin text-ink-muted" />
      </div>
    )
  }

  if (isError || !consultation) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <div className="flex items-start gap-3 rounded-card border border-critical/40 bg-critical/10 p-4">
          <AlertCircle className="mt-0.5 size-5 shrink-0 text-critical" />
          <div>
            <p className="text-sm font-medium text-ink">Could not load this consultation</p>
            <p className="mt-1 text-sm text-ink-muted">
              {error instanceof Error ? error.message : 'Unknown error'}
            </p>
            <Button variant="ghost" size="sm" className="mt-3" asChild>
              <Link to="/board">
                <ArrowLeft />
                Back to the board
              </Link>
            </Button>
          </div>
        </div>
      </div>
    )
  }

  const accent = executive?.theme_color ?? '#7C5CD6'

  return (
    <div className="flex h-dvh flex-col">
      <ConsultationHeader executive={executive} title={consultation.title} />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6 sm:px-6">
          {consultation.messages.length === 0 && executive && (
            <EmptyPrompt executive={executive} />
          )}

          {consultation.messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              executive={executive}
              accent={accent}
            />
          ))}

          {send.isPending && executive && <ThinkingIndicator executive={executive} />}

          {send.isError && (
            <div
              role="alert"
              className="rounded-card border border-critical/40 bg-critical/10 p-3 text-sm"
            >
              <p className="font-medium text-ink">That turn failed</p>
              <p className="mt-1 text-ink-muted">
                {send.error instanceof Error ? send.error.message : 'Unknown error'}
              </p>
            </div>
          )}

          <div ref={endRef} />
        </div>
      </div>

      <form
        onSubmit={onSubmit}
        className="border-t border-line bg-surface/60 px-4 py-3 backdrop-blur sm:px-6"
      >
        <div className="mx-auto flex w-full max-w-3xl items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                onSubmit(e)
              }
            }}
            rows={1}
            placeholder={
              executive ? `Ask ${executive.display_name}…` : 'Ask a question…'
            }
            aria-label="Your question"
            className="max-h-40 min-h-10 flex-1 resize-y rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
          <Button type="submit" size="icon" disabled={!draft.trim() || send.isPending}>
            {send.isPending ? <Loader2 className="animate-spin" /> : <Send />}
          </Button>
        </div>
      </form>
    </div>
  )
}

function ConsultationHeader({
  executive,
  title,
}: {
  executive: ExecutiveDefinition | undefined
  title: string
}) {
  const Portrait = executive ? EXECUTIVE_PORTRAITS[executive.avatar_ref] : undefined

  return (
    <header className="flex items-center gap-3 border-b border-line bg-surface/60 px-4 py-3 backdrop-blur sm:px-6">
      <Button variant="ghost" size="icon" asChild aria-label="Back to the board">
        <Link to="/board">
          <ArrowLeft />
        </Link>
      </Button>

      {Portrait && executive && (
        <div
          className="size-10 shrink-0 overflow-hidden rounded-md border"
          style={{ borderColor: `${executive.theme_color}66` }}
        >
          <Portrait
            accent={executive.theme_color}
            accentSoft={executive.theme_color_soft}
            className="size-full"
          />
        </div>
      )}

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-ink">
          {executive?.display_name ?? title}
        </p>
        {executive && (
          <p className="truncate text-xs" style={{ color: executive.theme_color_soft }}>
            {executive.title}
          </p>
        )}
      </div>
    </header>
  )
}

function EmptyPrompt({ executive }: { executive: ExecutiveDefinition }) {
  return (
    <div className="rounded-card border border-dashed border-line p-5">
      <p className="text-sm leading-relaxed text-ink-muted">
        {executive.distinctive_perspective}
      </p>
      <p className="mt-3 text-xs text-ink-faint">
        {executive.display_name} answers from one perspective only. Questions outside
        that remit get referred to the right colleague rather than guessed at.
      </p>
    </div>
  )
}

function MessageBubble({
  message,
  executive,
  accent,
}: {
  message: ConsultationMessage
  executive: ExecutiveDefinition | undefined
  accent: string
}) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-card rounded-br-sm bg-accent/20 px-4 py-2.5">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">
            {message.content}
          </p>
        </div>
      </div>
    )
  }

  const structured = message.structured_output

  return (
    <article className="rounded-card border border-line bg-surface p-4">
      <header className="mb-3 flex items-center gap-2">
        <span
          aria-hidden
          className="size-2 rounded-full"
          style={{ backgroundColor: accent }}
        />
        <span className="text-xs font-semibold text-ink">
          {executive?.display_name ?? message.agent_id}
        </span>
        {executive && <span className="text-xs text-ink-faint">{executive.short_title}</span>}
        {structured?.out_of_scope && (
          <Badge variant="caution" className="ml-auto">
            Outside my remit
          </Badge>
        )}
      </header>

      <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">
        {message.content}
      </p>

      {structured && <StructuredPanels data={structured} accent={accent} />}
    </article>
  )
}

function ThinkingIndicator({ executive }: { executive: ExecutiveDefinition }) {
  return (
    <div
      className={cn(
        'flex items-center gap-2.5 rounded-card border border-line bg-surface px-4 py-3',
      )}
      aria-live="polite"
    >
      <Loader2 className="size-3.5 animate-spin" style={{ color: executive.theme_color }} />
      <span className="text-sm text-ink-muted">
        {executive.display_name} is thinking…
      </span>
    </div>
  )
}
