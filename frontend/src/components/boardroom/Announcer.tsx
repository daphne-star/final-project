import { useEffect, useRef, useState } from 'react'

import { STAGE_LABEL, type TranscriptEntry } from '@/lib/boardroomState'
import type { ExecutiveDefinition } from '@/types/agents'

/**
 * What a screen reader hears while the board is sitting.
 *
 * Reading each assessment aloud as it lands would be unusable — they run to a
 * couple of hundred words and three can arrive together. So this announces
 * *arrivals* ("Objection from Marcus Webb to Alex Chen") and leaves the
 * transcript itself as a heading-navigable list the reader works through at
 * their own pace. Stage and status changes get their own region so a long
 * queue of turns cannot bury "the meeting failed".
 */
export function Announcer({
  stage,
  status,
  transcript,
  executivesById,
}: {
  stage: string | null
  status: string | null
  transcript: TranscriptEntry[]
  executivesById: Record<string, ExecutiveDefinition>
}) {
  const [turns, setTurns] = useState<{ id: string; text: string }[]>([])
  // Entries already on screen when the page opened are not news. Seed the
  // watermark on the first render so opening a finished meeting stays silent.
  const seen = useRef<Set<string> | null>(null)

  useEffect(() => {
    if (seen.current === null) {
      seen.current = new Set(transcript.map((e) => e.id))
      return
    }
    const fresh = transcript.filter((e) => !seen.current!.has(e.id))
    if (fresh.length === 0) return
    for (const e of fresh) seen.current.add(e.id)
    const name = (id: string) => executivesById[id]?.display_name ?? id
    setTurns((prev) =>
      [
        ...prev,
        ...fresh.map((e) => ({
          id: e.id,
          text: e.targetAgentId
            ? `${e.title} from ${name(e.agentId)} to ${name(e.targetAgentId)}.`
            : `${e.title} from ${name(e.agentId)}.`,
        })),
      ].slice(-8),
    )
  }, [transcript, executivesById])

  const stageText =
    status === 'completed'
      ? 'The meeting is complete. The decision brief is ready.'
      : status === 'failed'
        ? 'The meeting failed.'
        : status === 'cancelled'
          ? 'The meeting was ended.'
          : status === 'paused'
            ? 'The meeting is paused.'
            : stage
              ? `Stage: ${STAGE_LABEL[stage as keyof typeof STAGE_LABEL] ?? stage}.`
              : ''

  return (
    <>
      <div className="sr-only" role="status" aria-live="polite">
        {stageText}
      </div>
      <div className="sr-only" role="log" aria-live="polite" aria-relevant="additions">
        {turns.map((t) => (
          <p key={t.id}>{t.text}</p>
        ))}
      </div>
    </>
  )
}
