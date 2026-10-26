import { describe, expect, it } from 'vitest'

import {
  initialBoardroomState,
  reduceEvent,
  reduceEvents,
  stageProgress,
} from './boardroomState'
import {
  ev,
  failedMeetingEvents,
  interventionEvents,
  fullMeetingEvents,
  partialFailureEvents,
  resetSeq,
} from '@/test/fixtures'

describe('boardroom reducer', () => {
  it('builds the whole meeting from its event log', () => {
    const state = reduceEvents(fullMeetingEvents())

    expect(state.status).toBe('completed')
    expect(state.reframedQuestion).toContain('protects revenue')
    expect(state.agendaItems).toHaveLength(2)
    expect(state.participants).toEqual(['ceo', 'coo', 'cfo', 'strategy_consultant'])
    expect(state.modelRequests).toBe(10)
  })

  it('orders the transcript by sequence, not arrival', () => {
    const state = reduceEvents(fullMeetingEvents())
    const sequences = state.transcript.map((t) => t.sequence)
    expect(sequences).toEqual([...sequences].sort((a, b) => a - b))
  })

  it('produces one transcript entry per contribution', () => {
    const state = reduceEvents(fullMeetingEvents())
    const kinds = state.transcript.map((t) => t.kind)
    expect(kinds.filter((k) => k === 'assessment')).toHaveLength(4)
    expect(kinds.filter((k) => k === 'objection')).toHaveLength(2)
    expect(kinds.filter((k) => k === 'revision')).toHaveLength(1)
    expect(kinds.filter((k) => k === 'decision')).toHaveLength(1)
  })

  it('attributes each assessment to its own executive', () => {
    const state = reduceEvents(fullMeetingEvents())
    const assessments = state.transcript.filter((t) => t.kind === 'assessment')
    expect(assessments.map((a) => a.agentId)).toEqual([
      'ceo',
      'cfo',
      'coo',
      'strategy_consultant',
    ])
  })

  it('records who challenged whom', () => {
    const state = reduceEvents(fullMeetingEvents())
    expect(state.disagreements).toHaveLength(2)
    expect(state.disagreements[0]).toMatchObject({
      challenger: 'cfo',
      target: 'ceo',
      severity: 'major',
    })
    const objection = state.transcript.find((t) => t.kind === 'objection')
    expect(objection?.targetAgentId).toBe('ceo')
  })

  it('tracks the latest position per executive, including after revision', () => {
    const state = reduceEvents(fullMeetingEvents())
    expect(state.emergingPositions.cfo).toBe('Improve retention.')
    // The CEO revised, so the revised text wins over the original assessment.
    expect(state.emergingPositions.ceo).toBe('Stage the launch behind a retention push.')
  })

  it('keeps the before and after of a revision', () => {
    const state = reduceEvents(fullMeetingEvents())
    const revision = state.transcript.find((t) => t.kind === 'revision')
    expect(revision?.meta?.before).toBe('Launch the new product.')
    expect(revision?.meta?.after).toBe('Stage the launch behind a retention push.')
    expect(revision?.meta?.changed).toBe(true)
  })

  it('surfaces the decision and its recommendation', () => {
    const state = reduceEvents(fullMeetingEvents())
    expect(state.decisionGenerated).toBe(true)
    expect(state.recommendedOptionId).toBe('retention')
  })
})

describe('agent activity', () => {
  it('moves agents through real backend-reported states', () => {
    resetSeq()
    let state = initialBoardroomState()
    state = reduceEvent(state, ev('agent_status_changed', 'cfo', { status: 'speaking' }))
    expect(state.activity.cfo).toBe('speaking')

    state = reduceEvent(state, ev('agent_started', 'cfo', { stage: 'objection' }))
    expect(state.activity.cfo).toBe('challenging')

    state = reduceEvent(state, ev('agent_started', 'cfo', { stage: 'revision' }))
    expect(state.activity.cfo).toBe('revising')

    state = reduceEvent(state, ev('agent_status_changed', 'cfo', { status: 'completed' }))
    expect(state.activity.cfo).toBe('finished')
  })

  it('maps researching to analyzing for display', () => {
    resetSeq()
    const state = reduceEvent(
      initialBoardroomState(),
      ev('agent_status_changed', 'cfo', { status: 'researching' }),
    )
    expect(state.activity.cfo).toBe('analyzing')
  })

  it('marks every selected participant waiting once the agenda lands', () => {
    const events = fullMeetingEvents().slice(0, 4)
    const state = reduceEvents(events)
    expect(state.activity.ceo).toBe('waiting')
    expect(state.activity.cfo).toBe('waiting')
    expect(state.activity.chairperson).toBe('finished')
  })

  it('finishes everyone who did not fail when the meeting completes', () => {
    const state = reduceEvents(partialFailureEvents())
    expect(state.activity.coo).toBe('skipped')
    expect(state.activity.ceo).toBe('finished')
  })
})

describe('replay and reconnection', () => {
  it('ignores events at or before the cursor, so replay cannot duplicate', () => {
    const events = fullMeetingEvents()
    const once = reduceEvents(events)
    // Feed the whole log again, as a reconnect without a cursor would.
    const twice = events.reduce(reduceEvent, once)

    expect(twice.transcript).toHaveLength(once.transcript.length)
    expect(twice.disagreements).toHaveLength(once.disagreements.length)
    expect(twice.lastSequence).toBe(once.lastSequence)
  })

  it('produces identical state whether events arrive at once or in chunks', () => {
    const events = fullMeetingEvents()
    const atOnce = reduceEvents(events)

    const half = Math.floor(events.length / 2)
    let chunked = reduceEvents(events.slice(0, half))
    chunked = events.slice(half).reduce(reduceEvent, chunked)

    expect(chunked).toEqual(atOnce)
  })

  it('resuming from a cursor yields the same end state', () => {
    const events = fullMeetingEvents()
    const full = reduceEvents(events)

    const cut = 8
    let resumed = reduceEvents(events.filter((e) => e.sequence_number <= cut))
    resumed = events
      .filter((e) => e.sequence_number > cut)
      .reduce(reduceEvent, resumed)

    expect(resumed.transcript.map((t) => t.id)).toEqual(full.transcript.map((t) => t.id))
  })
})

describe('failure handling', () => {
  it('records an agent failure without ending the meeting', () => {
    const state = reduceEvents(partialFailureEvents())
    expect(state.status).toBe('completed')
    expect(state.activity.coo).toBe('skipped')
    const failure = state.transcript.find((t) => t.kind === 'failure')
    expect(failure?.agentId).toBe('coo')
    expect(failure?.body).toContain('503')
  })

  it('captures a meeting-level failure and its reason', () => {
    const state = reduceEvents(failedMeetingEvents())
    expect(state.status).toBe('failed')
    expect(state.failureReason).toContain('could not produce an agenda')
  })
})

describe('stageProgress', () => {
  it('advances monotonically through the stages', () => {
    expect(stageProgress(null)).toBe(0)
    expect(stageProgress('agenda')).toBeLessThan(stageProgress('assessments'))
    expect(stageProgress('assessments')).toBeLessThan(stageProgress('synthesis'))
    expect(stageProgress('persisted')).toBe(100)
  })
})


describe('founder interventions', () => {
  it('records the question and the reply as separate turns', () => {
    const state = reduceEvents(interventionEvents())
    const kinds = state.transcript.map((t) => t.kind)
    expect(kinds).toContain('intervention')
    expect(kinds).toContain('intervention_answer')

    const asked = state.transcript.find((t) => t.kind === 'intervention')
    const replied = state.transcript.find((t) => t.kind === 'intervention_answer')
    expect(asked?.body).toBe('Can we really do this in six months?')
    expect(replied?.body).toContain('two new hires')
    // The reply comes after the question.
    expect(replied!.sequence).toBeGreaterThan(asked!.sequence)
  })

  it('attributes the exchange to the executive addressed', () => {
    const state = reduceEvents(interventionEvents())
    const turns = state.transcript.filter(
      (t) => t.kind === 'intervention' || t.kind === 'intervention_answer',
    )
    expect(turns.every((t) => t.agentId === 'coo')).toBe(true)
  })

  it('tracks pause and resume', () => {
    const events = interventionEvents()
    const pausedAt = events.findIndex((e) => e.event_type === 'meeting_paused')
    const whilePaused = reduceEvents(events.slice(0, pausedAt + 1))
    expect(whilePaused.paused).toBe(true)

    const afterResume = reduceEvents(events)
    expect(afterResume.paused).toBe(false)
    expect(afterResume.status).toBe('completed')
  })

  it('replaying the log does not duplicate the exchange', () => {
    const events = interventionEvents()
    const once = reduceEvents(events)
    const twice = events.reduce(reduceEvent, once)
    expect(twice.transcript).toHaveLength(once.transcript.length)
  })
})
