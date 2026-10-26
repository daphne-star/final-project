import { describe, expect, it } from 'vitest'

import { parseSseBuffer } from './sse'

describe('parseSseBuffer', () => {
  it('parses a complete frame', () => {
    const { frames, rest } = parseSseBuffer(
      'id: 3\nevent: agenda_created\ndata: {"a":1}\n\n',
    )
    expect(rest).toBe('')
    expect(frames).toHaveLength(1)
    expect(frames[0]).toEqual({ id: 3, event: 'agenda_created', data: { a: 1 } })
  })

  it('holds back an incomplete frame for the next chunk', () => {
    const first = parseSseBuffer('id: 1\nevent: meeting_started\ndata: {"x":')
    expect(first.frames).toHaveLength(0)

    const second = parseSseBuffer(first.rest + '1}\n\n')
    expect(second.frames).toHaveLength(1)
    expect(second.frames[0].data).toEqual({ x: 1 })
  })

  it('parses several frames from one chunk', () => {
    const { frames } = parseSseBuffer(
      'id: 1\nevent: a\ndata: {}\n\nid: 2\nevent: b\ndata: {}\n\n',
    )
    expect(frames.map((f) => f.id)).toEqual([1, 2])
    expect(frames.map((f) => f.event)).toEqual(['a', 'b'])
  })

  it('skips heartbeat comments without losing real frames', () => {
    const { frames } = parseSseBuffer(': heartbeat\n\nid: 5\nevent: tick\ndata: {}\n\n')
    expect(frames).toHaveLength(1)
    expect(frames[0].id).toBe(5)
  })

  it('handles CRLF line endings', () => {
    const { frames } = parseSseBuffer('id: 7\r\nevent: x\r\ndata: {"ok":true}\r\n\r\n')
    expect(frames[0]).toEqual({ id: 7, event: 'x', data: { ok: true } })
  })

  it('joins multi-line data fields', () => {
    const { frames } = parseSseBuffer('event: x\ndata: {"a":\ndata: 1}\n\n')
    expect(frames[0].data).toEqual({ a: 1 })
  })

  it('falls back to the raw string when data is not JSON', () => {
    const { frames } = parseSseBuffer('event: x\ndata: plain text\n\n')
    expect(frames[0].data).toBe('plain text')
  })

  it('defaults the event name when the server omits it', () => {
    const { frames } = parseSseBuffer('data: {}\n\n')
    expect(frames[0].event).toBe('message')
  })

  it('leaves id null when there is no id field', () => {
    const { frames } = parseSseBuffer('event: stream_closed\ndata: {}\n\n')
    expect(frames[0].id).toBeNull()
  })

  it('tolerates a field with no space after the colon', () => {
    const { frames } = parseSseBuffer('id:9\nevent:x\ndata:{"v":2}\n\n')
    expect(frames[0]).toEqual({ id: 9, event: 'x', data: { v: 2 } })
  })

  it('reassembles a stream split at arbitrary byte boundaries', () => {
    const full =
      'id: 1\nevent: one\ndata: {"n":1}\n\nid: 2\nevent: two\ndata: {"n":2}\n\n'
    const collected: number[] = []
    let buffer = ''
    for (const char of full) {
      buffer += char
      const { frames, rest } = parseSseBuffer(buffer)
      buffer = rest
      for (const frame of frames) collected.push((frame.data as { n: number }).n)
    }
    expect(collected).toEqual([1, 2])
  })
})
