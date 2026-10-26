import { useCallback, useEffect, useRef, useState } from 'react'

import { getAuthToken } from '@/api/client'
import { consumeSse, type SseFrame } from '@/api/sse'
import {
  initialBoardroomState,
  reduceEvent,
  type BoardroomState,
} from '@/lib/boardroomState'
import type { MeetingEvent } from '@/types/meetings'

export type ConnectionState = 'idle' | 'connecting' | 'open' | 'closed' | 'error'

const MAX_RETRIES = 6
const BASE_BACKOFF_MS = 700

interface UseMeetingStreamResult {
  state: BoardroomState
  connection: ConnectionState
  error: string | null
  /** Manually re-open after a terminal error. */
  retry: () => void
}

/**
 * Follows one meeting's event log.
 *
 * Replay is the same code path as live: the reducer is fed an ordered stream
 * and ignores anything at or before its cursor, so a reconnect that re-sends
 * an event cannot duplicate a transcript entry. That is why a refresh
 * mid-meeting rebuilds the identical view rather than a partial one.
 */
export function useMeetingStream(
  meetingId: string | undefined,
  enabled = true,
): UseMeetingStreamResult {
  const [state, setState] = useState<BoardroomState>(initialBoardroomState)
  const [connection, setConnection] = useState<ConnectionState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  // The cursor lives in a ref so a reconnect reads the latest value without
  // re-running the effect and tearing down the stream it just opened.
  const cursorRef = useRef(0)
  const retriesRef = useRef(0)

  const retry = useCallback(() => {
    retriesRef.current = 0
    setError(null)
    setAttempt((a) => a + 1)
  }, [])

  useEffect(() => {
    if (!meetingId || !enabled) return

    const controller = new AbortController()
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    function applyFrame(frame: SseFrame) {
      if (cancelled) return

      if (frame.event === 'stream_closed') {
        setConnection('closed')
        return
      }
      if (frame.event === 'stream_error' || frame.event === 'stream_timeout') {
        const data = frame.data as { reason?: string }
        setError(data?.reason ?? 'The stream ended unexpectedly.')
        setConnection('error')
        return
      }

      const event = frame.data as MeetingEvent
      if (!event || typeof event.sequence_number !== 'number') return
      cursorRef.current = Math.max(cursorRef.current, event.sequence_number)
      setState((prev) => reduceEvent(prev, event))
    }

    async function run() {
      setConnection('connecting')
      try {
        await consumeSse({
          url: `/api/meetings/${meetingId}/stream`,
          token: getAuthToken(),
          lastEventId: cursorRef.current,
          signal: controller.signal,
          onFrame: (frame) => {
            setConnection((c) => (c === 'connecting' ? 'open' : c))
            applyFrame(frame)
          },
        })
        if (cancelled) return
        // A clean end without a stream_closed frame means the server hung up
        // mid-meeting; resume from the cursor rather than losing the tail.
        setConnection((current) => {
          if (current === 'closed' || current === 'error') return current
          scheduleRetry()
          return 'connecting'
        })
      } catch (err) {
        if (cancelled || controller.signal.aborted) return
        const message = err instanceof Error ? err.message : 'Stream failed'
        if (retriesRef.current >= MAX_RETRIES) {
          setError(`${message}. Giving up after ${MAX_RETRIES} attempts.`)
          setConnection('error')
          return
        }
        setError(message)
        scheduleRetry()
      }
    }

    function scheduleRetry() {
      if (cancelled) return
      const delay = BASE_BACKOFF_MS * 2 ** retriesRef.current
      retriesRef.current += 1
      timer = setTimeout(() => {
        if (!cancelled) void run()
      }, Math.min(delay, 10_000))
    }

    void run()

    return () => {
      cancelled = true
      controller.abort()
      if (timer) clearTimeout(timer)
    }
  }, [meetingId, enabled, attempt])

  // A different meeting means a different transcript; reset rather than
  // appending the new one onto the old.
  useEffect(() => {
    cursorRef.current = 0
    retriesRef.current = 0
    setState(initialBoardroomState())
    setConnection('idle')
    setError(null)
  }, [meetingId])

  return { state, connection, error, retry }
}
