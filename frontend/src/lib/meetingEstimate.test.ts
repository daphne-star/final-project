import { describe, expect, it } from 'vitest'

import type { MeetingMode } from '@/types/meetings'

import {
  estimateMeetingTokens,
  estimateModelCalls,
  type PastMeetingUsage,
} from './meetingEstimate'

const CALLS_BY_MODE: Record<MeetingMode, number> = {
  quick_consultation: 4,
  executive_meeting: 10,
  devils_advocate: 10,
  strategy_workshop: 12,
  full_board: 18,
}

const sizing = (mode: MeetingMode) => ({
  expectedCalls: CALLS_BY_MODE[mode],
  callsForMode: (m: MeetingMode) => CALLS_BY_MODE[m],
})

/** The six meetings actually recorded on this machine. */
const REAL_HISTORY: PastMeetingUsage[] = [
  { mode: 'executive_meeting', totalTokens: 90_821 },
  { mode: 'full_board', totalTokens: 104_348 },
  { mode: 'executive_meeting', totalTokens: 47_124 },
  { mode: 'devils_advocate', totalTokens: 69_732 },
  { mode: 'executive_meeting', totalTokens: 67_895 },
  { mode: 'executive_meeting', totalTokens: 54_559 },
]

describe('estimateMeetingTokens', () => {
  it('declines to guess with no history', () => {
    expect(estimateMeetingTokens('executive_meeting', [], sizing('executive_meeting'))).toBeNull()
  })

  it('prefers meetings of the same mode', () => {
    const estimate = estimateMeetingTokens('full_board', REAL_HISTORY, sizing('full_board'))!
    expect(estimate.basis).toBe('same-mode')
    expect(estimate.sampleSize).toBe(1)
    expect(estimate.tokens).toBe(100_000)
  })

  it('does not let other modes drag a same-mode estimate', () => {
    // Four executive meetings: 47,124 / 54,559 / 67,895 / 90,821 -> median
    // 61,227, rounded. The 104,348 Full Board must not take part.
    const estimate = estimateMeetingTokens('executive_meeting', REAL_HISTORY, sizing('executive_meeting'))!
    expect(estimate.basis).toBe('same-mode')
    expect(estimate.sampleSize).toBe(4)
    expect(estimate.tokens).toBe(61_000)
  })

  it('widens to every mode when this one has no history, and says so', () => {
    const estimate = estimateMeetingTokens(
      'strategy_workshop',
      REAL_HISTORY,
      sizing('strategy_workshop'),
    )!
    expect(estimate.basis).toBe('all-modes')
    expect(estimate.sampleSize).toBe(6)
  })

  it('scales the cross-mode fallback by how big this meeting is', () => {
    // Without scaling, a one-executive consultation would be quoted the same
    // as a nine-agent board, because the sample is the same six meetings.
    const quick = estimateMeetingTokens(
      'quick_consultation',
      REAL_HISTORY,
      sizing('quick_consultation'),
    )!
    const workshop = estimateMeetingTokens(
      'strategy_workshop',
      REAL_HISTORY,
      sizing('strategy_workshop'),
    )!

    expect(quick.basis).toBe('all-modes')
    expect(workshop.basis).toBe('all-modes')
    // 4 calls against 12: the consultation must come out far cheaper.
    expect(quick.tokens).toBeLessThan(workshop.tokens / 2)
  })

  it('ignores meetings that never reached the model', () => {
    // A draft, or one that failed on its first call, records zero tokens and
    // would drag any median it joined towards nothing.
    const withDrafts: PastMeetingUsage[] = [
      { mode: 'full_board', totalTokens: 100_000 },
      { mode: 'full_board', totalTokens: 0 },
      { mode: 'full_board', totalTokens: 0 },
    ]
    const estimate = estimateMeetingTokens('full_board', withDrafts, sizing('full_board'))!
    expect(estimate.sampleSize).toBe(1)
    expect(estimate.tokens).toBe(100_000)
  })

  it('has nothing to offer when every past meeting recorded zero', () => {
    expect(
      estimateMeetingTokens('full_board', [{ mode: 'full_board', totalTokens: 0 }], sizing('full_board')),
    ).toBeNull()
  })

  it('takes the median, so one outlier cannot set the estimate', () => {
    const withOutlier: PastMeetingUsage[] = [
      { mode: 'full_board', totalTokens: 30_000 },
      { mode: 'full_board', totalTokens: 30_000 },
      { mode: 'full_board', totalTokens: 30_000 },
      { mode: 'full_board', totalTokens: 2_000_000 },
    ]
    expect(estimateMeetingTokens('full_board', withOutlier, sizing('full_board'))!.tokens).toBe(30_000)
  })

  it('rounds to two figures rather than implying precision', () => {
    const estimate = estimateMeetingTokens('full_board', [{ mode: 'full_board', totalTokens: 29_887 }], sizing('full_board'))!
    expect(estimate.tokens).toBe(30_000)
  })
})

describe('estimateModelCalls', () => {
  it('counts the Chair plus two turns each', () => {
    expect(estimateModelCalls(4)).toBe(10)
    expect(estimateModelCalls(8)).toBe(18)
  })

  it('is only a single-round floor, which is why it is not shown as tokens', () => {
    // The recorded Full Board made 35 calls, not 18. Multiplying this by a
    // tokens-per-call figure would have understated it roughly twofold.
    expect(estimateModelCalls(8)).toBeLessThan(35)
  })
})
