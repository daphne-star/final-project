/**
 * A minimal SSE client built on fetch.
 *
 * `EventSource` cannot set an Authorization header, and every Ghost Board
 * endpoint is authenticated. Putting the token in the query string would work
 * but would also put it in every access log, so the stream is read with fetch
 * and parsed here instead.
 */

export interface SseFrame {
  id: number | null
  event: string
  data: unknown
}

/** Parse a buffer of SSE text into complete frames plus the unconsumed tail. */
export function parseSseBuffer(buffer: string): { frames: SseFrame[]; rest: string } {
  const frames: SseFrame[] = []
  // Frames are separated by a blank line. Normalise CRLF first.
  const normalised = buffer.replace(/\r\n/g, '\n')
  const parts = normalised.split('\n\n')
  // The final part may be incomplete; keep it for the next chunk.
  const rest = parts.pop() ?? ''

  for (const part of parts) {
    if (!part.trim()) continue

    let id: number | null = null
    let event = 'message'
    const dataLines: string[] = []

    for (const line of part.split('\n')) {
      if (line.startsWith(':')) continue // comment / heartbeat
      const colon = line.indexOf(':')
      const field = colon === -1 ? line : line.slice(0, colon)
      const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')

      if (field === 'id') {
        const parsed = Number.parseInt(value, 10)
        if (!Number.isNaN(parsed)) id = parsed
      } else if (field === 'event') {
        event = value
      } else if (field === 'data') {
        dataLines.push(value)
      }
    }

    if (dataLines.length === 0) continue
    const raw = dataLines.join('\n')
    try {
      frames.push({ id, event, data: JSON.parse(raw) })
    } catch {
      frames.push({ id, event, data: raw })
    }
  }

  return { frames, rest }
}

export interface StreamOptions {
  url: string
  token: string | null
  /** Resume cursor. Sent as both ?after= and Last-Event-ID. */
  lastEventId?: number
  signal: AbortSignal
  onFrame: (frame: SseFrame) => void
}

/**
 * Consume an SSE endpoint until it closes or the signal aborts.
 * Resolves normally on a clean close; throws on transport failure.
 */
export async function consumeSse({
  url,
  token,
  lastEventId,
  signal,
  onFrame,
}: StreamOptions): Promise<void> {
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (token) headers.Authorization = `Bearer ${token}`
  if (lastEventId !== undefined && lastEventId > 0) {
    headers['Last-Event-ID'] = String(lastEventId)
  }

  const separator = url.includes('?') ? '&' : '?'
  const fullUrl =
    lastEventId !== undefined && lastEventId > 0
      ? `${url}${separator}after=${lastEventId}`
      : url

  const response = await fetch(fullUrl, { headers, signal })

  if (!response.ok) {
    throw new Error(`Stream failed with HTTP ${response.status}`)
  }
  if (!response.body) {
    throw new Error('Stream response had no body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const { frames, rest } = parseSseBuffer(buffer)
      buffer = rest
      for (const frame of frames) onFrame(frame)
    }
    // Flush anything the server sent without a trailing blank line.
    const { frames } = parseSseBuffer(buffer + '\n\n')
    for (const frame of frames) onFrame(frame)
  } finally {
    reader.releaseLock()
  }
}
